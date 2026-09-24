"""Execution service — API/Celery bridge for experiments (Phase 5).

Responsibilities:
- ``enqueue_experiment``: publish-only dispatch (never blocks the request).
- ``attach_task_id``: persist the Celery task id on the experiment row.
- ``revoke_experiment_task``: best-effort revoke for cancel (never raises —
  the DB status is the source of truth, the broker is auxiliary).
- ``check_redis``: async broker reachability probe (health/diag + tests).
- ``celery_state_to_experiment_status``: pure Celery->domain state mapping.
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.experiment import Experiment
from app.models.experiment import ExperimentStatus

logger = logging.getLogger("autosage.execution")


def enqueue_experiment(experiment_id: UUID) -> str:
    """Publish the background run; return the Celery task id (non-blocking).

    Uses ``apply_async`` (not ``send_task`` — Celery ignores eager mode for
    ``send_task``, which would break broker-less runs). Returns after the
    broker accepts the message; the worker executes asynchronously.

    Raises broker errors to the caller (mapped to 503 at the endpoint) —
    the experiment row is already QUEUED, so the run can be re-triggered.
    """
    from app.workers.tasks import run_experiment  # local import: workers bind at import

    result = run_experiment.apply_async(
        args=[str(experiment_id)],
        queue=settings.CELERY_EXPERIMENT_QUEUE,
    )
    logger.info(
        "experiment_enqueued",
        extra={"experiment": str(experiment_id), "task": result.id},
    )
    return str(result.id)


async def attach_task_id(
    session: AsyncSession, experiment_id: UUID, task_id: str
) -> Experiment:
    """Persist the Celery task id on an already-QUEUED experiment."""
    from app.repositories.experiment_repository import ExperimentRepository

    repo = ExperimentRepository(session)
    experiment = await repo.get_by_id(experiment_id)
    if experiment is None:  # pragma: no cover - endpoint resolved it first
        from app.core.exceptions import NotFoundError

        raise NotFoundError(f"Experiment {experiment_id} not found")
    experiment.celery_task_id = task_id
    return await repo.save(experiment)


def revoke_experiment_task(task_id: Optional[str]) -> bool:
    """Best-effort revoke (terminate a running worker task). Never raises.

    Returns True when the revoke was accepted by the broker, False when
    there was no task id or the broker was unreachable — callers still
    mark the experiment CANCELLED either way.
    """
    if not task_id:
        return False
    try:
        from app.workers.celery_app import celery_app

        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        logger.info("experiment_task_revoked", extra={"task": task_id})
        return True
    except Exception:
        logger.warning("experiment_revoke_failed", extra={"task": task_id})
        return False


async def check_redis(url: Optional[str] = None) -> bool:
    """Ping the Redis broker; False on any connection failure."""
    import redis.asyncio as redis_async

    target = url or settings.celery_broker_url
    try:
        client = redis_async.from_url(target, socket_connect_timeout=3)
        try:
            pong = await client.ping()
            return bool(pong)
        finally:
            await client.aclose()
    except Exception:
        logger.warning("redis_unreachable", extra={"url": target})
        return False


# Celery task states -> closest experiment status (polling/inspection only;
# the task itself is authoritative for DB transitions).
CELERY_STATE_MAP: Dict[str, str] = {
    "PENDING": ExperimentStatus.QUEUED.value,
    "RECEIVED": ExperimentStatus.QUEUED.value,
    "STARTED": ExperimentStatus.RUNNING.value,
    "RETRY": ExperimentStatus.RETRYING.value,
    "SUCCESS": ExperimentStatus.COMPLETED.value,
    "FAILURE": ExperimentStatus.FAILED.value,
    "REVOKED": ExperimentStatus.CANCELLED.value,
}


def celery_state_to_experiment_status(celery_state: str) -> str:
    """Map a Celery task state name to the nearest experiment status."""
    return CELERY_STATE_MAP.get(celery_state.upper(), ExperimentStatus.QUEUED.value)


def get_task_state(task_id: str) -> Dict[str, Any]:
    """Inspect a Celery task (state + result) without touching the DB."""
    from app.workers.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    return {"task_id": task_id, "state": result.state, "result": result.result}
