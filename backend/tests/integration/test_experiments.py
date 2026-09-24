"""Phase 4: experiment management API tests (no live database).

Uses the shared :class:`tests.fakes.FakeAsyncSession` via a ``get_db``
override — the real stack (routing, JWT, deps, services, repositories,
lifecycle guards, envelopes) runs; only SQL execution is emulated.

Covers the required guarantees:
- Experiment CRUD works (POST/GET/PATCH/DELETE).
- Start/cancel endpoints work, including 409 on illegal transitions.
- Unknown experiment ids return 404 on every endpoint.
- Users cannot access another workspace's experiments (404 everywhere).
- Pagination, status/workspace filters, and validation behave.
- OpenAPI documents all experiment endpoints.
"""
import uuid
from typing import Any, Dict, Optional
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from tests.fakes import FakeAsyncSession

USER_A = {"email": "alice@autosage.local", "name": "Alice"}
USER_B = {"email": "bob@autosage.local", "name": "Bob"}


@pytest.fixture()
def fake_session() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture(autouse=True)
def _fake_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start/cancel must not touch a broker: stub publish-only dispatch."""
    monkeypatch.setattr(
        "app.services.execution_service.enqueue_experiment",
        lambda experiment_id: "task-test-123",
    )
    monkeypatch.setattr(
        "app.services.execution_service.revoke_experiment_task",
        lambda task_id: True,
    )


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
def token_a() -> str:
    """Token for user A."""
    return create_access_token(str(uuid.uuid4()), {"email": USER_A["email"], "name": USER_A["name"]})


@pytest.fixture()
def token_b() -> str:
    """Token for user B."""
    return create_access_token(str(uuid.uuid4()), {"email": USER_B["email"], "name": USER_B["name"]})


@pytest.fixture()
def missing_id() -> str:
    """A missing experiment ID."""
    return str(uuid.uuid4())


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_workspace(client: TestClient, token: str, name: str = "WS") -> Dict[str, Any]:
    response = client.post(
        "/api/v1/workspaces", json={"name": name}, headers=auth_headers(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_experiment(
    client: TestClient, token: str, workspace_id: str, name: str = "Exp"
) -> Dict[str, Any]:
    response = client.post(
        "/api/v1/experiments",
        json={
            "name": name,
            "workspace_id": workspace_id,
            "config": {"model_params": {"lr": 0.01}},
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


# -- auth enforcement ----------------------------------------------------
def test_experiment_endpoints_reject_anonymous(client: TestClient) -> None:
    assert client.get("/api/v1/experiments").status_code == 401
    assert client.post("/api/v1/experiments", json={"name": "x"}).status_code == 401
    assert client.get(f"/api/v1/experiments/{missing_id}").status_code == 401
    assert client.patch(f"/api/v1/experiments/{missing_id}", json={"name": "y"}).status_code == 401
    assert client.delete(f"/api/v1/experiments/{missing_id}").status_code == 401
    assert client.post(f"/api/v1/experiments/{missing_id}/start").status_code == 401
    assert client.post(f"/api/v1/experiments/{missing_id}/cancel").status_code == 401


# -- workspaces (experiment prerequisite) ----------------------------------
def test_workspace_crud_and_isolation(client: TestClient, token_a: str, token_b: str) -> None:
    ws = make_workspace(client, token_a, "Alice WS")
    assert ws["name"] == "Alice WS"
    assert UUID(ws["owner_id"])

    mine = client.get("/api/v1/workspaces", headers=auth_headers(token_a))
    assert mine.status_code == 200
    assert mine.json()["total"] == 1

    # Bob sees nothing and gets 404 on Alice's workspace.
    assert client.get("/api/v1/workspaces", headers=auth_headers(token_b)).json()["total"] == 0
    assert client.get(f"/api/v1/workspaces/{ws['id']}", headers=auth_headers(token_b)).status_code == 404
    assert client.get(f"/api/v1/workspaces/{ws['id']}", headers=auth_headers(token_a)).status_code == 200


# -- experiment CRUD -------------------------------------------------------
def test_experiment_crud(client: TestClient, token_a: str) -> None:
    ws = make_workspace(client, token_a)
    created = make_experiment(client, token_a, ws["id"], "First run")
    assert created["status"] == "CREATED"
    assert created["workspace_id"] == ws["id"]
    assert created["config"] == {"model_params": {"lr": 0.01}}
    assert created["retry_count"] == 0
    experiment_id = created["id"]

    detail = client.get(f"/api/v1/experiments/{experiment_id}", headers=auth_headers(token_a))
    assert detail.status_code == 200
    assert detail.json()["name"] == "First run"

    updated = client.patch(
        f"/api/v1/experiments/{experiment_id}",
        json={"name": "Renamed", "config": {"model_params": {"lr": 0.02}}},
        headers=auth_headers(token_a),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["config"] == {"model_params": {"lr": 0.02}}

    deleted = client.delete(f"/api/v1/experiments/{experiment_id}", headers=auth_headers(token_a))
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/experiments/{experiment_id}", headers=auth_headers(token_a)).status_code == 404


def test_unknown_experiment_ids_return_404(client: TestClient, token_a: str, missing_id: str) -> None:
    headers = auth_headers(token_a)
    assert client.get(f"/api/v1/experiments/{missing_id}", headers=headers).status_code == 404
    assert client.patch(f"/api/v1/experiments/{missing_id}", json={"name": "x"}, headers=headers).status_code == 404
    assert client.delete(f"/api/v1/experiments/{missing_id}", headers=headers).status_code == 404
    assert client.post(f"/api/v1/experiments/{missing_id}/start", headers=headers).status_code == 404
    assert client.post(f"/api/v1/experiments/{missing_id}/cancel", headers=headers).status_code == 404


def test_experiment_list_pagination_and_filters(client: TestClient, token_a: str) -> None:
    ws_a = make_workspace(client, token_a, "WA")
    ws_b = make_workspace(client, token_a, "WB")
    ids = {make_experiment(client, token_a, ws_a["id"], f"A-{i}")["id"] for i in range(3)}
    ids |= {make_experiment(client, token_a, ws_b["id"], "B-0")["id"]}
    assert len(ids) == 4

    page1 = client.get(
        "/api/v1/experiments", params={"page": 1, "page_size": 2}, headers=auth_headers(token_a)
    )
    assert page1.status_code == 200
    body = page1.json()
    assert body["total"] == 4 and len(body["items"]) == 2
    assert body["page"] == 1 and body["page_size"] == 2

    page2 = client.get(
        "/api/v1/experiments", params={"page": 2, "page_size": 2}, headers=auth_headers(token_a)
    )
    assert {item["id"] for item in page2.json()["items"]} == ids - {
        item["id"] for item in body["items"]
    }

    scoped = client.get(
        "/api/v1/experiments", params={"workspace_id": ws_a["id"]}, headers=auth_headers(token_a)
    )
    assert scoped.json()["total"] == 3

    # Start one experiment, then filter by status.
    queued_id = next(iter(ids))
    assert client.post(f"/api/v1/experiments/{queued_id}/start", headers=auth_headers(token_a)).status_code == 200
    filtered = client.get(
        "/api/v1/experiments", params={"status": "QUEUED"}, headers=auth_headers(token_a)
    )
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == queued_id


# -- start / cancel lifecycle ----------------------------------------------
def test_start_and_cancel_flow(client: TestClient, token_a: str) -> None:
    ws = make_workspace(client, token_a)
    exp = make_experiment(client, token_a, ws["id"])
    experiment_id = exp["id"]
    headers = auth_headers(token_a)

    started = client.post(f"/api/v1/experiments/{experiment_id}/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["status"] == "QUEUED"
    assert started.json()["started_at"] is not None
    assert started.json()["celery_task_id"] == "task-test-123"

    # Starting twice is a conflict.
    assert client.post(f"/api/v1/experiments/{experiment_id}/start", headers=headers).status_code == 409

    cancelled = client.post(f"/api/v1/experiments/{experiment_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["completed_at"] is not None

    # Terminal states reject further transitions.
    assert client.post(f"/api/v1/experiments/{experiment_id}/cancel", headers=headers).status_code == 409
    assert client.post(f"/api/v1/experiments/{experiment_id}/start", headers=headers).status_code == 409


def test_cancel_from_created(client: TestClient, token_a: str) -> None:
    ws = make_workspace(client, token_a)
    exp = make_experiment(client, token_a, ws["id"])
    response = client.post(
        f"/api/v1/experiments/{exp['id']}/cancel", headers=auth_headers(token_a)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


# -- workspace isolation -----------------------------------------------------
def test_users_cannot_access_another_workspace_experiments(client: TestClient, token_a: str, token_b: str) -> None:
    ws = make_workspace(client, token_a, "Private")
    exp = make_experiment(client, token_a, ws["id"], "Secret")
    experiment_id = exp["id"]
    headers_b = auth_headers(token_b)

    # Bob's list is empty; everything else is 404 (not 403).
    assert client.get("/api/v1/experiments", headers=headers_b).json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
    }
    assert client.get(f"/api/v1/experiments/{experiment_id}", headers=headers_b).status_code == 404
    assert client.patch(f"/api/v1/experiments/{experiment_id}", json={"name": "hijack"}, headers=headers_b).status_code == 404
    assert client.delete(f"/api/v1/experiments/{experiment_id}", headers=headers_b).status_code == 404
    assert client.post(f"/api/v1/experiments/{experiment_id}/start", headers=headers_b).status_code == 404
    assert client.post(f"/api/v1/experiments/{experiment_id}/cancel", headers=headers_b).status_code == 404

    # Bob cannot create into Alice's workspace, nor filter by it.
    assert client.post(
        "/api/v1/experiments",
        json={"name": "squat", "workspace_id": ws["id"]},
        headers=headers_b,
    ).status_code == 404
    assert client.get(
        "/api/v1/experiments", params={"workspace_id": ws["id"]}, headers=headers_b
    ).status_code == 404


# -- validation ---------------------------------------------------------------
def test_experiment_payload_validation(client: TestClient, token_a: str) -> None:
    ws = make_workspace(client, token_a)
    headers = auth_headers(token_a)

    assert client.post(
        "/api/v1/experiments", json={"name": "", "workspace_id": ws["id"]}, headers=headers
    ).status_code == 422
    assert client.post(
        "/api/v1/experiments", json={"workspace_id": ws["id"]}, headers=headers
    ).status_code == 422
    assert client.post(
        "/api/v1/experiments",
        json={"name": "x", "workspace_id": "not-a-uuid"},
        headers=headers,
    ).status_code == 422

    exp = make_experiment(client, token_a, ws["id"])
    # Status cannot be smuggled through PATCH (extra="forbid").
    assert client.patch(
        f"/api/v1/experiments/{exp['id']}", json={"status": "COMPLETED"}, headers=headers
    ).status_code == 422
    # Pagination bounds enforced.
    assert client.get("/api/v1/experiments", params={"page": 0}, headers=headers).status_code == 422
    assert client.get("/api/v1/experiments", params={"page_size": 101}, headers=headers).status_code == 422
    assert client.get(f"/api/v1/experiments/not-a-uuid", headers=headers).status_code == 422


# -- API documentation ----------------------------------------------------------
def test_openapi_documents_experiment_api() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert set(paths["/api/v1/experiments"].keys()) == {"get", "post"}
    assert set(paths["/api/v1/experiments/{experiment_id}"].keys()) == {"get", "patch", "delete"}
    assert set(paths["/api/v1/experiments/{experiment_id}/start"].keys()) == {"post"}
    assert set(paths["/api/v1/experiments/{experiment_id}/cancel"].keys()) == {"post"}
    assert set(paths["/api/v1/workspaces"].keys()) == {"get", "post"}
