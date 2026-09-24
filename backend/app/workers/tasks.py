"""Background experiment execution tasks (Phase 5/11/15).

``experiments.run_experiment`` drives one experiment through the LangGraph
workflow and keeps ``experiments.status`` in sync::

    QUEUED -> RUNNING -> COMPLETED            (happy path)
    RUNNING -> FAILED -> RETRYING -> RUNNING  (retry with exponential backoff)
    * -> CANCELLED                            (API cancel + revoke; task is a no-op)

Phase 11 adds MLflow integration: each experiment creates an MLRun record
linked to an MLflow run that tracks parameters, metrics, model, and artifacts.

Phase 15 adds real-time WebSocket event publishing for experiment lifecycle.

Retry: ``countdown = min(base * 2**attempt, cap)`` from settings
(``CELERY_RETRY_BACKOFF_BASE/MAX``), bounded by the experiment's own
``max_retries``. Task-level ``max_retries`` is a backstop only.

Failure handling: terminal failures persist ``error_detail``; unexpected
worker-side failures go through ``on_failure`` (best-effort FAILED sync —
never raises, never retries).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional
from uuid import UUID

from celery import Task

from app.core.config import settings
from app.core.observability import (
    TimingContext,
    experiment_context,
    log_with_context,
    log_exception_with_context,
    set_experiment_id,
    clear_experiment_id,
    get_experiment_id,
)
from app.models.experiment import Experiment, ExperimentStatus
from app.models.ml_run import MLRun
from app.services import experiment_service
from app.workers.celery_app import celery_app

# Phase 15: Event publishing (sync helpers for Celery tasks)
from app.services.event_publisher import (
    publish_experiment_started,
    publish_experiment_completed,
    publish_experiment_failed,
    publish_ml_started,
    publish_ml_completed,
)
# Phase 17: Reproducibility
from app.services.reproducibility_service import ReproducibilityService

import json
from datetime import datetime

logger = logging.getLogger("autosage.worker")

TASK_NAME = "experiments.run_experiment"
# Hard backstop on task-level redeliveries (domain retries stop earlier).
TASK_MAX_RETRIES = 10


def _run_coro_sync(coro):  # type: ignore[no-untyped-def]
    """Drive a coroutine from sync task code, even inside a running loop.

    Workers have no running loop (plain ``asyncio.run``). Eager execution
    inside an API request does — then the coroutine is isolated on a helper
    thread with its own loop so inline runs still complete.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def compute_retry_countdown(
    task_retries: int, base: Optional[int] = None, cap: Optional[int] = None
) -> int:
    """Exponential backoff countdown in seconds: ``min(base * 2**n, cap)``."""
    base = settings.CELERY_RETRY_BACKOFF_BASE if base is None else base
    cap = settings.CELERY_RETRY_BACKOFF_MAX if cap is None else cap
    return min(base * (2 ** max(task_retries, 0)), cap)


@asynccontextmanager
async def task_session() -> AsyncIterator[Any]:
    """Fresh DB session for worker execution (monkeypatched in tests)."""
    from app.db.session import AsyncSessionLocal, init_engine

    if AsyncSessionLocal is None:
        init_engine()
    assert AsyncSessionLocal is not None
    async with AsyncSessionLocal() as session:
        yield session


async def _load_experiment(session: Any, experiment_id: str) -> Optional[Experiment]:
    from app.repositories.experiment_repository import ExperimentRepository

    try:
        repo = ExperimentRepository(session)
        return await repo.get_by_id(UUID(experiment_id))
    except (ValueError, AttributeError):
        return None


async def _run_workflow(experiment: Experiment) -> Dict[str, Any]:
    """Execute LangGraph off the event loop; return the final state."""
    from app.agents.runner import run_experiment_workflow

    config = experiment.config or {}
    return await asyncio.to_thread(
        run_experiment_workflow,
        experiment_id=str(experiment.id),
        workspace_id=str(experiment.workspace_id),
        fail_stage=config.get("mock_fail_stage"),
    )


async def _execute_async(task: Task, experiment_id: str) -> Dict[str, Any]:
    """Task body: sync statuses around one workflow run (may raise Retry)."""
    task_id = task.request.id
    exp_token = set_experiment_id(experiment_id)
    try:
        async with task_session() as session:
            experiment = await _load_experiment(session, experiment_id)
            if experiment is None:
                log_with_context(logger, logging.ERROR, "experiment_missing", experiment=experiment_id)
                return {"experiment_id": experiment_id, "status": "UNKNOWN"}

            if task_id and experiment.celery_task_id != task_id:
                experiment.celery_task_id = task_id
                await session.commit()

            if experiment.status == ExperimentStatus.CANCELLED.value:
                # Cancel won the race (revoke-then-deliver): stay cancelled.
                log_with_context(logger, logging.INFO, "experiment_cancelled_skip", experiment=experiment_id)
                return {"experiment_id": experiment_id, "status": experiment.status}

            if experiment.status in (
                ExperimentStatus.COMPLETED.value,
            ):
                # Idempotent redelivery of a finished run.
                log_with_context(
                    logger, logging.INFO, "experiment_terminal_skip",
                    experiment=experiment_id, status=experiment.status
                )
                return {"experiment_id": experiment_id, "status": experiment.status}

            if experiment.status == ExperimentStatus.FAILED.value:
                if (experiment.retry_count or 0) >= (experiment.max_retries or 0):
                    # Retries exhausted earlier — FAILED is terminal.
                    return {"experiment_id": experiment_id, "status": experiment.status}
                # Crash between FAILED and RETRYING: resume the retry cycle.
                experiment = await experiment_service.transition_experiment(
                    session, experiment, ExperimentStatus.RETRYING.value
                )

            if experiment.status == ExperimentStatus.CREATED.value:
                experiment = await experiment_service.transition_experiment(
                    session, experiment, ExperimentStatus.QUEUED.value
                )
            if experiment.status in (
                ExperimentStatus.QUEUED.value,
                ExperimentStatus.RETRYING.value,
            ):
                experiment = await experiment_service.transition_experiment(
                    session, experiment, ExperimentStatus.RUNNING.value
                )
            if experiment.status != ExperimentStatus.RUNNING.value:  # pragma: no cover
                # Defensive: every reachable state is normalized above.
                return {"experiment_id": experiment_id, "status": experiment.status}

            # Phase 15: Publish experiment.started event
            publish_experiment_started(
                experiment_id=UUID(experiment_id),
                experiment_name=experiment.name,
                workspace_id=experiment.workspace_id,
                config=experiment.config,
            )

            # Phase 11: Create MLRun record and start MLflow run
            mlflow_run_id = None
            ml_run = None
            try:
                from app.engine.mlflow.client import get_mlflow_tracker, mlflow_run_context

                # Create MLRun record
                ml_run = MLRun(
                    experiment_id=UUID(experiment_id),
                    name=experiment.name,
                    status="RUNNING",
                    params=experiment.config.get("model_params", {}),
                    started_at=datetime.utcnow(),
                )
                session.add(ml_run)
                await session.flush()  # Get the ID

                # Start MLflow run
                tracker = get_mlflow_tracker()
                mlflow_run = None
                with mlflow_run_context(
                    tracker,
                    run_name=f"autosage-{experiment.name[:50]}",
                    tags={"autosage_experiment_id": str(experiment.id), "autosage_ml_run_id": str(ml_run.id)},
                    autosage_experiment_id=UUID(str(experiment.id)),
                ) as run:
                    mlflow_run_id = run.info.run_id
                    ml_run.mlflow_run_id = mlflow_run_id
                    ml_run.status = "RUNNING"
                    await session.commit()

                    # Phase 15: Publish ml.started event
                    publish_ml_started(
                        experiment_id=UUID(experiment_id),
                        model_family=experiment.config.get("model_family", "gradient_boosting"),
                        model_params=experiment.config.get("model_params", {}),
                        mlflow_run_id=mlflow_run_id,
                        ml_run_id=str(ml_run.id),
                    )

                    # Execute sandbox with MLflow run ID
                    from app.engine.sandbox.manager import get_sandbox_manager

                    # Build training script from experiment config
                    script = _build_training_script(experiment, mlflow_run_id)

                    sandbox = get_sandbox_manager()
                    with TimingContext("sandbox_execution", extra_fields={"experiment": experiment_id, "mlflow_run_id": mlflow_run_id}):
                        result = await sandbox.execute_job(
                            job_id=f"exp-{experiment_id}",
                            script=script,
                            dataset_path=experiment.config.get("dataset_path"),
                            env_vars={
                                "MODEL_FAMILY": experiment.config.get("model_family", "gradient_boosting"),
                                "METRIC": experiment.config.get("metric", "accuracy"),
                                "DATASET_NAME": experiment.config.get("dataset_name", "dataset.csv"),
                                "MODEL_PARAMS": json.dumps(experiment.config.get("model_params", {})),
                                "TARGET_COLUMN": experiment.config.get("target_column", "target"),
                                "TASK_TYPE": experiment.config.get("task_type", "classification"),
                            },
                            mlflow_run_id=mlflow_run_id,
                        )

                    if result.success:
                        ml_run.status = "COMPLETED"
                        ml_run.metrics = result.metrics
                        ml_run.params = experiment.config.get("model_params", {})
                        ml_run.completed_at = datetime.utcnow()
                        experiment.result_summary = {
                            "ml_result": result.metrics,
                            "mlflow_run_id": mlflow_run_id,
                            "ml_run_id": str(ml_run.id),
                            "stages_completed": ["ml_training"],
                            "attempt": 1,
                        }
                        experiment = await experiment_service.transition_experiment(
                            session, experiment, ExperimentStatus.COMPLETED.value
                        )
                        # Phase 17: Create reproducibility record
                        try:
                            reproducibility_service = ReproducibilityService(session)
                            dataset = None
                            if experiment.config.get("dataset_path"):
                                from app.models.dataset import Dataset
                                from sqlalchemy import select
                                dataset_result = await session.execute(
                                    select(Dataset).where(Dataset.storage_path == experiment.config["dataset_path"])
                                )
                                dataset = dataset_result.scalar_one_or_none()

                            sandbox_result_data = {
                                "artifact_uris": result.artifacts if hasattr(result, "artifacts") else None,
                                "model_artifact_uri": result.model_artifact_uri if hasattr(result, "model_artifact_uri") else None,
                                "log_artifact_uri": result.log_artifact_uri if hasattr(result, "log_artifact_uri") else None,
                            }

                            await reproducibility_service.create_record(
                                experiment=experiment,
                                ml_run=ml_run,
                                dataset=dataset,
                                sandbox_result=sandbox_result_data,
                            )
                            log_with_context(
                                logger, logging.INFO, "reproducibility_record_created",
                                experiment=experiment_id
                            )
                        except Exception as repro_exc:
                            # Don't fail the experiment if reproducibility record creation fails
                            log_with_context(
                                logger, logging.WARNING, "reproducibility_record_failed",
                                experiment=experiment_id, error=str(repro_exc)
                            )

                        # Phase 15: Publish ml.completed and experiment.completed events
                        publish_ml_completed(
                            experiment_id=UUID(experiment_id),
                            success=True,
                            metrics=result.metrics,
                            mlflow_run_id=mlflow_run_id,
                            ml_run_id=str(ml_run.id),
                        )
                        publish_experiment_completed(
                            experiment_id=UUID(experiment_id),
                            result_summary=experiment.result_summary,
                            mlflow_run_id=mlflow_run_id,
                            ml_run_id=str(ml_run.id),
                        )
                        log_with_context(
                            logger, logging.INFO, "experiment_completed",
                            experiment=experiment_id, mlflow_run_id=mlflow_run_id
                        )
                    else:
                        ml_run.status = "FAILED"
                        ml_run.notes = result.error_message
                        ml_run.completed_at = datetime.utcnow()
                        experiment.error_detail = result.error_message
                        experiment = await experiment_service.transition_experiment(
                            session, experiment, ExperimentStatus.FAILED.value
                        )
                        # Phase 15: Publish ml.completed (failed) and experiment.failed events
                        publish_ml_completed(
                            experiment_id=UUID(experiment_id),
                            success=False,
                            error=result.error_message,
                            mlflow_run_id=mlflow_run_id,
                            ml_run_id=str(ml_run.id),
                        )
                        publish_experiment_failed(
                            experiment_id=UUID(experiment_id),
                            error_detail=result.error_message,
                            retry_count=experiment.retry_count or 0,
                            max_retries=experiment.max_retries or 0,
                            will_retry=(experiment.retry_count or 0) < (experiment.max_retries or 0),
                        )
                        log_with_context(
                            logger, logging.ERROR, "experiment_failed_sandbox",
                            experiment=experiment_id, error=result.error_message
                        )

            except Exception as exc:
                if ml_run:
                    ml_run.status = "FAILED"
                    ml_run.notes = f"{type(exc).__name__}: {exc}"[:2000]
                    ml_run.completed_at = datetime.utcnow()
                    await session.commit()
                return await _handle_workflow_error(task, session, experiment, exc)

            return {
                "experiment_id": experiment_id,
                "status": experiment.status,
                "mlflow_run_id": mlflow_run_id,
                "ml_run_id": str(ml_run.id) if ml_run else None,
            }
    finally:
        clear_experiment_id(exp_token)


def _build_training_script(experiment: Experiment, mlflow_run_id: str) -> str:
    """Build the training script from experiment config for sandbox execution."""
    config = experiment.config or {}

    # Read the base train script template
    from pathlib import Path
    script_path = Path(__file__).parent.parent / "engine" / "sandbox" / "train_script.py"
    try:
        base_script = script_path.read_text()
    except FileNotFoundError:
        # Fallback inline script
        base_script = '''
import os
os.environ["MLFLOW_RUN_ID"] = "{{MLFLOW_RUN_ID}}"
exec(open("/workspace/train_script.py").read())
'''

    # Replace placeholder with actual MLflow run ID
    script = base_script.replace("{{MLFLOW_RUN_ID}}", mlflow_run_id)
    return script


async def _handle_workflow_error(
    task: Task, session: Any, experiment: Experiment, exc: Exception
) -> Dict[str, Any]:
    """Persist FAILED, retry with backoff while attempts remain (else terminal)."""
    experiment_id = str(experiment.id)
    log_exception_with_context(logger, "experiment_failed", experiment=experiment_id)
    experiment.error_detail = f"{type(exc).__name__}: {exc}"[:2000]
    experiment = await experiment_service.transition_experiment(
        session, experiment, ExperimentStatus.FAILED.value
    )
    # Phase 15: Publish experiment.failed event
    publish_experiment_failed(
        experiment_id=UUID(experiment_id),
        error_detail=experiment.error_detail,
        retry_count=experiment.retry_count or 0,
        max_retries=experiment.max_retries or 0,
        will_retry=(experiment.retry_count or 0) < (experiment.max_retries or 0),
    )
    if (experiment.retry_count or 0) < (experiment.max_retries or 0):
        experiment = await experiment_service.transition_experiment(
            session, experiment, ExperimentStatus.RETRYING.value
        )
        countdown = compute_retry_countdown(task.request.retries)
        log_with_context(
            logger, logging.INFO, "experiment_retrying",
            experiment=experiment_id, retry=experiment.retry_count, countdown=countdown
        )
        raise task.retry(exc=exc, countdown=countdown, max_retries=TASK_MAX_RETRIES)
    log_with_context(logger, logging.WARNING, "experiment_retries_exhausted", experiment=experiment_id)
    return {"experiment_id": experiment_id, "status": experiment.status}


class ExperimentTask(Task):
    """Task base: lifecycle logging + best-effort failure sync."""

    def on_retry(self, exc, task_id, args, kwargs, einfo):  # type: ignore[no-untyped-def]
        log_with_context(logger, logging.INFO, "task_retry", task=task_id, exc=str(exc))
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # type: ignore[no-untyped-def]
        log_exception_with_context(logger, "task_failure", task=task_id)
        # Safety net: leave the experiment FAILED with the error recorded.
        # Never raises — status sync must not mask the original failure.
        try:
            _run_coro_sync(_sync_failure_best_effort(args[0] if args else None, exc))
        except Exception:
            log_exception_with_context(logger, "failure_sync_failed", task=task_id)
        super().on_failure(exc, task_id, args, kwargs, einfo)


async def _sync_failure_best_effort(experiment_id: Any, exc: BaseException) -> None:
    if not experiment_id:
        return
    async with task_session() as session:
        experiment = await _load_experiment(session, str(experiment_id))
        if experiment is None or experiment.status in (
            ExperimentStatus.COMPLETED.value,
            ExperimentStatus.CANCELLED.value,
            ExperimentStatus.FAILED.value,
        ):
            return
        experiment.status = ExperimentStatus.FAILED.value
        experiment.error_detail = f"{type(exc).__name__}: {exc}"[:2000]
        await session.commit()


@celery_app.task(
    base=ExperimentTask,
    bind=True,
    name=TASK_NAME,
    max_retries=TASK_MAX_RETRIES,
    time_limit=settings.CELERY_TASK_TIME_LIMIT,
    soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
)
def run_experiment(self, experiment_id: str) -> Dict[str, Any]:
    """Run one experiment end-to-end (sync entry for the worker pool)."""
    return _run_coro_sync(_execute_async(self, experiment_id))


@celery_app.task(bind=True, name="tasks.execute_pipeline_run")
def execute_pipeline_run(self, run_id: str, prompt: str, dataset_path: str):  # type: ignore[no-untyped-def]
    # Legacy Phase 1 placeholder (pipeline-run world); kept for compatibility.
    return {"run_id": run_id, "status": "COMPLETED"}