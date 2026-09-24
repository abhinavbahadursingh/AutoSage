"""Unit tests: Celery execution layer (no broker required).

Covers: exponential-backoff math, Celery app/worker configuration,
Celery->experiment state mapping, and revoke/Redis helper contracts.
"""
from app.models.experiment import ExperimentStatus
from app.services.execution_service import celery_state_to_experiment_status
from app.workers.celery_app import celery_app
from app.workers.tasks import TASK_NAME, compute_retry_countdown, run_experiment


def test_backoff_doubles_with_cap() -> None:
    assert compute_retry_countdown(0, base=60, cap=3600) == 60
    assert compute_retry_countdown(1, base=60, cap=3600) == 120
    assert compute_retry_countdown(2, base=60, cap=3600) == 240
    assert compute_retry_countdown(10, base=60, cap=3600) == 3600
    assert compute_retry_countdown(-3, base=60, cap=3600) == 60


def test_backoff_defaults_come_from_settings() -> None:
    assert compute_retry_countdown(0) == 60
    assert compute_retry_countdown(100) == 3600


def test_task_registration_and_routing() -> None:
    assert TASK_NAME == "experiments.run_experiment"
    assert TASK_NAME in celery_app.tasks
    task = run_experiment
    assert task.name == TASK_NAME
    assert task.max_retries == 10
    routes = celery_app.conf.task_routes or {}
    assert routes[TASK_NAME]["queue"] == "experiments"


def test_worker_reliability_config() -> None:
    conf = celery_app.conf
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert conf.task_acks_late is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.task_track_started is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.task_time_limit == 1800
    assert conf.task_soft_time_limit == 1500


def test_celery_state_mapping() -> None:
    assert celery_state_to_experiment_status("PENDING") == ExperimentStatus.QUEUED.value
    assert celery_state_to_experiment_status("STARTED") == ExperimentStatus.RUNNING.value
    assert celery_state_to_experiment_status("RETRY") == ExperimentStatus.RETRYING.value
    assert celery_state_to_experiment_status("SUCCESS") == ExperimentStatus.COMPLETED.value
    assert celery_state_to_experiment_status("FAILURE") == ExperimentStatus.FAILED.value
    assert celery_state_to_experiment_status("REVOKED") == ExperimentStatus.CANCELLED.value
    assert celery_state_to_experiment_status("weird") == ExperimentStatus.QUEUED.value


def test_revoke_without_task_id_is_noop() -> None:
    from app.services.execution_service import revoke_experiment_task

    assert revoke_experiment_task(None) is False
    assert revoke_experiment_task("") is False
