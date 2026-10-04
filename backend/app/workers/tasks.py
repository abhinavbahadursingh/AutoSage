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
    log_with_context,
    log_exception_with_context,
    set_experiment_id,
    clear_experiment_id,
)
from app.models.experiment import Experiment, ExperimentStatus
from app.services import experiment_service
from app.workers.celery_app import celery_app

# Phase 15: Event publishing (sync helpers for Celery tasks)
from app.services.event_publisher import (
    publish_experiment_started,
    publish_experiment_completed,
    publish_experiment_failed,
)

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
        return asyncio.run(_await_and_dispose_engine(coro))
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _await_and_dispose_engine(coro)).result()


async def _await_and_dispose_engine(coro):  # type: ignore[no-untyped-def]
    """Await ``coro``, then dispose any DB engine bound to the current loop."""
    try:
        return await coro
    finally:
        try:
            from app.db.session import dispose_engine_for_current_loop

            await dispose_engine_for_current_loop()
        except Exception:
            pass


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
    from app.db import session as _db_session

    _db_session.init_engine()  # idempotent per event loop; recreates if the loop changed
    assert _db_session.AsyncSessionLocal is not None
    async with _db_session.AsyncSessionLocal() as session:
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
        experiment_config=config,
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

            # Execute the LangGraph experiment workflow (7-stage agent pipeline).
            # Per-stage agent/ml/verification events are published from the
            # graph node wrapper; this block syncs DB state to the final state.
            try:
                final_state = await _run_workflow(experiment)
            except Exception as exc:
                return await _handle_workflow_error(task, session, experiment, exc)

            _prev_history = (experiment.result_summary or {}).get("history")
            ml_result = dict(final_state.get("ml_result") or {})
            # Canonical result keys are always present, whatever the run did:
            # primary_metric, primary_score, metrics, model_comparison,
            # selected_model. Callers never have to guess the objective.
            primary_metric = str(
                final_state.get("primary_metric")
                or ml_result.get("primary_metric")
                or experiment.config.get("primary_metric")
                or "accuracy"
            )
            primary_score = ml_result.get("primary_score")
            selected_model = ml_result.get("selected_model")
            if primary_score is None and selected_model:
                # Legacy alias fallback, but only for a measured run: an
                # unmeasured run must stay None rather than report 0.0.
                primary_score = ml_result.get("value")
            experiment.result_summary = {
                "primary_metric": primary_metric,
                "primary_score": primary_score,
                "metrics": dict(ml_result.get("metrics") or {}),
                "model_comparison": list(ml_result.get("model_comparison") or []),
                "selected_model": selected_model,
                "compare_models": bool(ml_result.get("compare_models")),
                "baseline": dict(ml_result.get("baseline") or {}),
                "stages_completed": list(final_state.get("stages_completed") or []),
                "current_stage": final_state.get("current_stage"),
                "status": final_state.get("status"),
                "verification_passed": bool(final_state.get("verification_passed")),
                "verification": final_state.get("verification") or {},
                "ml_result": ml_result,
                "model_spec": final_state.get("model_spec") or {},
                "preprocessing_spec": final_state.get("preprocessing_spec") or {},
                "dataset_info": final_state.get("dataset_info") or {},
                "profile": final_state.get("profile") or {},
                "attempt": final_state.get("attempt"),
                "events": list(final_state.get("events") or [])[-20:],
                "history": list(_prev_history or []),
            }

            # Persist the reasoning lineage (PipelineRun -> AgentExecution ->
            # Decision -> EvidenceTrailNode) so the verification gate has
            # decisions and evidence to verify. Best effort: never fails a run.
            from app.services.evidence_persist import persist_workflow_evidence

            evidence_result = await persist_workflow_evidence(experiment_id, final_state)
            if evidence_result:
                log_with_context(
                    logger, logging.INFO, "experiment_evidence_persisted",
                    experiment=experiment_id, evidence=str(evidence_result),
                )

            from app.core.runtime import record_execution

            llm_sources = [
                (final_state.get(slot) or {}).get("source")
                for slot in ("ml_result", "verification", "model_spec", "preprocessing_spec", "dataset_info", "profile")
            ]
            used_llm = any(s == "llm" for s in llm_sources)
            record_execution(
                {
                    "experiment_id": experiment_id,
                    "status": experiment.status,
                    "training_mode": "langgraph_workflow_llm" if used_llm else "langgraph_workflow_heuristic",
                    "sandbox_used": False,
                    "mlflow_used": False,
                    "stages_completed": experiment.result_summary["stages_completed"],
                    "attempt": experiment.result_summary.get("attempt"),
                }
            )

            if final_state.get("status") == "FAILED":
                experiment.error_detail = (
                    f"{final_state.get('current_stage') or 'workflow'} stage failed — "
                    f"verification retries exhausted"
                )[:2000]
                experiment = await experiment_service.transition_experiment(
                    session, experiment, ExperimentStatus.FAILED.value
                )
                publish_experiment_failed(
                    experiment_id=UUID(experiment_id),
                    error_detail=experiment.error_detail,
                    retry_count=experiment.retry_count or 0,
                    max_retries=experiment.max_retries or 0,
                    will_retry=False,
                )
                log_with_context(
                    logger, logging.ERROR, "experiment_failed_workflow",
                    experiment=experiment_id,
                )
            else:
                experiment = await experiment_service.transition_experiment(
                    session, experiment, ExperimentStatus.COMPLETED.value
                )
                publish_experiment_completed(
                    experiment_id=UUID(experiment_id),
                    result_summary=experiment.result_summary,
                    mlflow_run_id=None,
                    ml_run_id=None,
                )
                log_with_context(
                    logger, logging.INFO, "experiment_completed",
                    experiment=experiment_id,
                )

            return {
                "experiment_id": experiment_id,
                "status": experiment.status,
                "stages_completed": experiment.result_summary["stages_completed"],
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