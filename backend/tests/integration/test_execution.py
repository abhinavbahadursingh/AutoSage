"""Phase 5/6: async execution integration tests (no live infra required).

Broker-less strategy: Celery ``task_always_eager`` executes tasks inline,
``app.workers.tasks.task_session`` is monkeypatched onto the shared
``FakeAsyncSession``, and Redis is emulated with fakeredis. The real
LangGraph workflow, task body, retry/backoff, status sync, and API wiring
all run unmodified.

Covers: background execution, status updates, retry behavior, failure
handling, cancellation, Redis probing, and API -> Celery -> LangGraph.
"""
import asyncio
import socket
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.experiment import Experiment
from app.models.user import User
from app.models.workspace import Workspace
from app.services.execution_service import check_redis
from app.workers.celery_app import celery_app
from app.workers.tasks import _sync_failure_best_effort, run_experiment
from tests.fakes import FakeAsyncSession


@pytest.fixture()
def fake_session() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture()
def client(fake_session: FakeAsyncSession) -> TestClient:
    async def override_get_db():  # type: ignore[no-untyped-def]
        yield fake_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def patched_task_session(fake_session: FakeAsyncSession, monkeypatch: pytest.MonkeyPatch) -> FakeAsyncSession:
    @asynccontextmanager
    async def _cm():  # type: ignore[no-untyped-def]
        yield fake_session

    monkeypatch.setattr("app.workers.tasks.task_session", _cm)
    return fake_session


@pytest.fixture()
def eager_celery():  # type: ignore[no-untyped-def]
    old = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        yield
    finally:
        celery_app.conf.task_always_eager = old


def seed_experiment(
    fake_session: FakeAsyncSession,
    *,
    status: str = "QUEUED",
    max_retries: int = 3,
    config: Optional[Dict[str, Any]] = None,
    email: str = "w@autosage.local",
) -> Experiment:
    user = User(id=uuid.uuid4(), email=email, name="W")
    fake_session.add(user)
    workspace = Workspace(id=uuid.uuid4(), owner_id=user.id, name="WS", meta={})
    fake_session.add(workspace)
    experiment = Experiment(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        name="E",
        status=status,
        config=config or {},
        max_retries=max_retries,
        retry_count=0,
    )
    fake_session.add(experiment)
    return experiment


def token_for(email: str, user_id: UUID) -> str:
    return create_access_token(str(user_id), {"email": email, "name": "W"})


# -- background execution + status sync ---------------------------------------
def test_background_task_runs_workflow_to_completed(
    patched_task_session: FakeAsyncSession, eager_celery: None
) -> None:
    experiment = seed_experiment(patched_task_session)
    result = run_experiment.apply(args=[str(experiment.id)]).get()

    assert result["status"] == "COMPLETED"
    assert result["stages_completed"] == [
        "orchestrator",
        "discovery",
        "profiler",
        "preprocessor",
        "model_selector",
        "ml_experiment",
        "verification",
    ]
    final = patched_task_session._store[Experiment][experiment.id]
    assert final.status == "COMPLETED"
    assert final.result_summary["ml_result"]["value"] == 0.87
    assert final.result_summary["verification"]["passed"] is True
    assert final.celery_task_id  # task id tracked on the row


def test_task_retry_then_terminal_failure(
    patched_task_session: FakeAsyncSession, eager_celery: None
) -> None:
    experiment = seed_experiment(
        patched_task_session,
        max_retries=1,
        config={"mock_fail_stage": "ml_experiment"},
    )
    result = run_experiment.apply(args=[str(experiment.id)]).get()

    assert result["status"] == "FAILED"
    final = patched_task_session._store[Experiment][experiment.id]
    assert final.status == "FAILED"
    assert final.retry_count == 1  # FAILED -> RETRYING once, then exhausted
    assert "ml_experiment" in (final.error_detail or "")


def test_task_skips_missing_cancelled_and_finished(
    patched_task_session: FakeAsyncSession, eager_celery: None
) -> None:
    missing = run_experiment.apply(args=[str(uuid.uuid4())]).get()
    assert missing["status"] == "UNKNOWN"

    cancelled = seed_experiment(patched_task_session, status="CANCELLED")
    assert run_experiment.apply(args=[str(cancelled.id)]).get()["status"] == "CANCELLED"

    done = seed_experiment(patched_task_session, status="COMPLETED")
    assert run_experiment.apply(args=[str(done.id)]).get()["status"] == "COMPLETED"


def test_failure_sync_safety_net(patched_task_session: FakeAsyncSession) -> None:
    experiment = seed_experiment(patched_task_session, status="RUNNING")
    asyncio.run(_sync_failure_best_effort(str(experiment.id), RuntimeError("boom")))
    final = patched_task_session._store[Experiment][experiment.id]
    assert final.status == "FAILED"
    assert "boom" in (final.error_detail or "")

    # Finished rows are never clobbered.
    done = seed_experiment(patched_task_session, status="COMPLETED")
    asyncio.run(_sync_failure_best_effort(str(done.id), RuntimeError("boom")))
    assert patched_task_session._store[Experiment][done.id].status == "COMPLETED"


# -- API -> Celery wiring -------------------------------------------------------
def test_api_start_publishes_without_blocking(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = []

    class _FakeResult:
        id = "task-pub-1"

    def _apply_async(*args, **kwargs):  # type: ignore[no-untyped-def]
        sent.append({"args": args, "kwargs": kwargs})
        return _FakeResult()

    monkeypatch.setattr(run_experiment, "apply_async", _apply_async)

    headers = _headers_for_fresh_user()
    ws = client.post("/api/v1/workspaces", json={"name": "WS"}, headers=headers).json()
    created = client.post(
        "/api/v1/experiments",
        json={"name": "E", "workspace_id": ws["id"]},
        headers=headers,
    )
    assert created.status_code == 201
    started = client.post(
        f"/api/v1/experiments/{created.json()['id']}/start",
        headers=headers,
    )
    assert started.status_code == 200
    assert started.json()["status"] == "QUEUED"
    assert started.json()["celery_task_id"] == "task-pub-1"
    assert len(sent) == 1  # exactly one non-blocking publish
    assert sent[0]["kwargs"]["args"] == [created.json()["id"]]
    assert sent[0]["kwargs"]["queue"] == "experiments"


def test_api_start_full_run_eager(
    client: TestClient,
    patched_task_session: FakeAsyncSession,
    eager_celery: None,
) -> None:
    headers = _headers_for_fresh_user()
    ws = client.post("/api/v1/workspaces", json={"name": "WS"}, headers=headers).json()
    created = client.post(
        "/api/v1/experiments",
        json={"name": "E", "workspace_id": ws["id"]},
        headers=headers,
    ).json()
    started = client.post(f"/api/v1/experiments/{created['id']}/start", headers=headers)
    assert started.status_code == 200
    # Eager inline run finished before the response was sent.
    assert started.json()["status"] == "COMPLETED"
    assert started.json()["celery_task_id"]
    detail = client.get(f"/api/v1/experiments/{created['id']}", headers=headers)
    assert detail.json()["result_summary"]["ml_result"]["value"] == 0.87


def _headers_for_fresh_user() -> Dict[str, str]:
    token = create_access_token(
        str(uuid.uuid4()), {"email": f"{uuid.uuid4()}@autosage.local", "name": "API"}
    )
    return {"Authorization": f"Bearer {token}"}


def test_api_start_broker_down_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kombu.exceptions import OperationalError

    def _broken_apply(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OperationalError("broker down")

    monkeypatch.setattr(run_experiment, "apply_async", _broken_apply)
    headers = _headers_for_fresh_user()
    ws = client.post("/api/v1/workspaces", json={"name": "WS"}, headers=headers).json()
    created = client.post(
        "/api/v1/experiments",
        json={"name": "E", "workspace_id": ws["id"]},
        headers=headers,
    ).json()
    response = client.post(f"/api/v1/experiments/{created['id']}/start", headers=headers)
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    # Row stays QUEUED (recoverable) — the transition itself succeeded.
    assert client.get(f"/api/v1/experiments/{created['id']}", headers=headers).json()["status"] == "QUEUED"


# -- cancellation ---------------------------------------------------------------
def test_cancel_revokes_worker_task(
    client: TestClient, patched_task_session: FakeAsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = seed_experiment(patched_task_session, status="RUNNING")
    experiment.celery_task_id = "task-abc"
    owner = next(iter(patched_task_session._store[User].values()))
    headers = {"Authorization": f"Bearer {token_for(owner.email, owner.id)}"}

    calls = []

    class _StubControl:
        def revoke(self, task_id, terminate=None, signal=None):  # type: ignore[no-untyped-def]
            calls.append((task_id, terminate, signal))

    monkeypatch.setattr(celery_app, "control", _StubControl())
    response = client.post(f"/api/v1/experiments/{experiment.id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert calls == [("task-abc", True, "SIGTERM")]


def test_cancel_without_broker_still_cancels(
    client: TestClient, patched_task_session: FakeAsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = seed_experiment(patched_task_session, status="QUEUED")
    experiment.celery_task_id = "task-xyz"
    owner = next(iter(patched_task_session._store[User].values()))
    headers = {"Authorization": f"Bearer {token_for(owner.email, owner.id)}"}

    class _BrokenControl:
        def revoke(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise ConnectionError("broker down")

    monkeypatch.setattr(celery_app, "control", _BrokenControl())
    response = client.post(f"/api/v1/experiments/{experiment.id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


# -- redis ------------------------------------------------------------------------
def test_check_redis_with_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    from fakeredis.aioredis import FakeRedis

    fake = FakeRedis()
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **k: fake)
    assert asyncio.run(check_redis()) is True


def test_check_redis_unreachable_is_false() -> None:
    assert asyncio.run(check_redis("redis://localhost:6379/9")) is False


def test_redis_live_matches_tcp_probe() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        reachable = sock.connect_ex(("localhost", 6379)) == 0
    finally:
        sock.close()
    assert asyncio.run(check_redis("redis://localhost:6379/0")) is reachable
