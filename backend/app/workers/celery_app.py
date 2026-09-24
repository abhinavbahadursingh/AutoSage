"""Celery application instance (Phase 5).

Run a worker with (from ``backend/``)::

    celery -A app.workers.celery_app:celery_app worker --loglevel=info \\
        -Q experiments --concurrency=2

Broker/result backend default to ``REDIS_URL`` (``CELERY_BROKER_URL`` /
``CELERY_RESULT_BACKEND`` override). For broker-less runs (tests, local
smoke), set ``CELERY_TASK_ALWAYS_EAGER=True`` — tasks execute inline in the
publishing process.
"""
import logging

from app.core.config import settings
from app.core.observability import init_opentelemetry

from celery import Celery
from celery.signals import task_prerun, task_postrun, task_retry, task_failure, worker_init

celery_app = Celery(
    "autosage_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_extended=True,  # store task name/args/worker with results
    result_expires=86400,  # forget results after 24h
    # Routing — experiment runs are isolated on their own queue.
    task_default_queue=settings.CELERY_EXPERIMENT_QUEUE,
    task_routes={
        "experiments.run_experiment": {"queue": settings.CELERY_EXPERIMENT_QUEUE},
    },
    # Reliability — at-least-once delivery, one task at a time per worker.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    # Observability
    task_track_started=True,
    worker_send_task_events=True,
    # Safety nets (per-task overrides live in app.workers.tasks).
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    # Broker-less mode (tests/dev): execute inline instead of publishing.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=False,
)

# Initialize OpenTelemetry in worker processes
@worker_init.connect
def init_worker_telemetry(**kwargs):  # type: ignore[no-untyped-def]
    init_opentelemetry("autosage-worker")


# Task lifecycle logging via signals
_task_logger = logging.getLogger("autosage.worker.lifecycle")

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):  # type: ignore[no-untyped-def]
    _task_logger.info(
        "task_started",
        extra={
            "task_id": task_id,
            "task_name": task.name,
            "task_args": str(args)[:200],
            "task_kwargs": str(kwargs)[:200],
        },
    )


@task_postrun.connect
def task_postrun_handler(task_id, task, *args, retval=None, state=None, **kwargs):  # type: ignore[no-untyped-def]
    _task_logger.info(
        "task_completed",
        extra={
            "task_id": task_id,
            "task_name": task.name,
            "task_state": state,
            "task_retval": str(retval)[:200] if retval else None,
        },
    )


@task_retry.connect
def task_retry_handler(request, reason, einfo, *args, **kwargs):  # type: ignore[no-untyped-def]
    _task_logger.warning(
        "task_retrying",
        extra={
            "task_id": request.id,
            "task_name": request.task,
            "task_retries": request.retries,
            "retry_reason": str(reason),
            "retry_traceback": str(einfo)[:500] if einfo else None,
        },
    )


@task_failure.connect
def task_failure_handler(task_id, exception, traceback, *args, **kwargs):  # type: ignore[no-untyped-def]
    _task_logger.error(
        "task_failed",
        extra={
            "task_id": task_id,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "failure_traceback": str(traceback)[:1000] if traceback else None,
        },
    )
