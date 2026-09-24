"""Phase 2: authentication + workspace isolation API tests.

These tests run **without a live database**: the ``get_db`` dependency is
overridden with an in-memory ``FakeAsyncSession`` that executes the real
service-layer SQLAlchemy statements (``select`` + ``==`` filters,
``session.get/add/delete``) against Python dicts. Everything else — routing,
JWT verification, auth dependencies, ownership checks, response envelopes —
is the real application stack.

Guarantees covered:
- Unauthenticated requests to protected routes return **401**.
- Invalid / expired / tampered tokens return **401**.
- Authenticated users reach protected endpoints (**200**).
- Users are isolated: user B gets **404** on user A's projects/runs/datasets.
"""
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.project import Project
from app.models.run import PipelineRun
from app.models.user import User
from tests.fakes import FakeAsyncSession

USER_A = {"email": "alice@autosage.local", "name": "Alice"}
USER_B = {"email": "bob@autosage.local", "name": "Bob"}


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


def make_token(email: str, name: str, user_id: Optional[UUID] = None, **kwargs: Any) -> str:
    return create_access_token(str(user_id or uuid.uuid4()), {"email": email, "name": name}, **kwargs)


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


TOKEN_A = make_token(**USER_A)
TOKEN_B = make_token(**USER_B)
PROJECT_ID = str(uuid.uuid4())
RUN_ID = str(uuid.uuid4())

PROTECTED_ROUTES = [
    ("GET", "/api/v1/auth/me", None),
    ("GET", "/api/v1/auth/session", None),
    ("GET", "/api/v1/projects", None),
    ("POST", "/api/v1/projects", {"name": "x"}),
    ("GET", f"/api/v1/projects/{PROJECT_ID}", None),
    ("PATCH", f"/api/v1/projects/{PROJECT_ID}", {"name": "y"}),
    ("DELETE", f"/api/v1/projects/{PROJECT_ID}", None),
    ("POST", f"/api/v1/projects/{PROJECT_ID}/datasets/upload", None),
    ("GET", f"/api/v1/projects/{PROJECT_ID}/datasets", None),
    ("POST", f"/api/v1/projects/{PROJECT_ID}/runs/", None),
    ("GET", f"/api/v1/runs/{RUN_ID}/evidence", None),
    ("GET", "/api/v1/memory/search", {"query": "q"}),
]


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_routes_reject_anonymous(client: TestClient, method: str, path: str, body: Any) -> None:
    response = client.request(method, path, json=body) if body else client.request(method, path)
    assert response.status_code == 401, f"{method} {path} should require auth"


def test_invalid_token_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers("not-a-jwt"))
    assert response.status_code == 401


def test_tampered_token_rejected(client: TestClient) -> None:
    token = make_token(**USER_A)
    header, payload, signature = token.split(".")
    response = client.get("/api/v1/auth/me", headers=auth_headers(f"{header}.{payload}X.{signature}"))
    assert response.status_code == 401


def test_expired_token_rejected(client: TestClient) -> None:
    token = make_token(**USER_A, expires_delta=timedelta(seconds=-1))
    response = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert response.status_code == 401


def test_auth_me_returns_identified_user(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers(TOKEN_A))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == USER_A["email"]
    assert body["name"] == USER_A["name"]
    assert UUID(body["id"])  # valid user id


def test_auth_session_returns_user(client: TestClient) -> None:
    response = client.get("/api/v1/auth/session", headers=auth_headers(TOKEN_A))
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["user"]["email"] == USER_A["email"]


def test_dev_token_mints_usable_credential(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/dev-token", json={"email": "dev@autosage.local", "name": "Dev"}
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "dev@autosage.local"


def test_projects_are_isolated_per_user(client: TestClient) -> None:
    created = client.post(
        "/api/v1/projects",
        json={"name": "Alice project", "description": "secret"},
        headers=auth_headers(TOKEN_A),
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    # Owner sees it.
    mine = client.get("/api/v1/projects", headers=auth_headers(TOKEN_A))
    assert mine.status_code == 200
    assert [p["id"] for p in mine.json()] == [project_id]

    detail = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers(TOKEN_A))
    assert detail.status_code == 200
    assert detail.json()["name"] == "Alice project"

    # Another user sees nothing and cannot touch it (404, not 403/200).
    theirs = client.get("/api/v1/projects", headers=auth_headers(TOKEN_B))
    assert theirs.status_code == 200
    assert theirs.json() == []

    for method, path, body in [
        ("GET", f"/api/v1/projects/{project_id}", None),
        ("PATCH", f"/api/v1/projects/{project_id}", {"name": "hijack"}),
        ("DELETE", f"/api/v1/projects/{project_id}", None),
    ]:
        kwargs = {"json": body} if body else {}
        response = client.request(method, path, headers=auth_headers(TOKEN_B), **kwargs)
        assert response.status_code == 404, f"{method} {path} leaked across users"

    # Owner can update and delete.
    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "renamed"},
        headers=auth_headers(TOKEN_A),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "renamed"

    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers(TOKEN_A))
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}", headers=auth_headers(TOKEN_A)).status_code == 404


def test_datasets_runs_evidence_enforce_ownership(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    created = client.post(
        "/api/v1/projects", json={"name": "P"}, headers=auth_headers(TOKEN_A)
    )
    project_id = created.json()["id"]

    upload = client.post(
        f"/api/v1/projects/{project_id}/datasets/upload",
        files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        headers=auth_headers(TOKEN_A),
    )
    assert upload.status_code == 200
    assert client.post(
        f"/api/v1/projects/{project_id}/datasets/upload",
        files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        headers=auth_headers(TOKEN_B),
    ).status_code == 404

    listing = client.get(
        f"/api/v1/projects/{project_id}/datasets", headers=auth_headers(TOKEN_A)
    )
    assert listing.status_code == 200
    assert client.get(
        f"/api/v1/projects/{project_id}/datasets", headers=auth_headers(TOKEN_B)
    ).status_code == 404

    launch = client.post(
        f"/api/v1/projects/{project_id}/runs/", headers=auth_headers(TOKEN_A)
    )
    assert launch.status_code == 200
    assert client.post(
        f"/api/v1/projects/{project_id}/runs/", headers=auth_headers(TOKEN_B)
    ).status_code == 404

    # Seed a real run row owned by A and check evidence isolation.
    run = PipelineRun(
        id=uuid.uuid4(), project_id=UUID(project_id), status="PENDING", user_prompt="hi"
    )
    fake_session.add(run)

    evidence = client.get(f"/api/v1/runs/{run.id}/evidence", headers=auth_headers(TOKEN_A))
    assert evidence.status_code == 200
    assert client.get(
        f"/api/v1/runs/{run.id}/evidence", headers=auth_headers(TOKEN_B)
    ).status_code == 404


def test_memory_search_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/memory/search", params={"query": "q"}).status_code == 401
    response = client.get(
        "/api/v1/memory/search", params={"query": "q"}, headers=auth_headers(TOKEN_A)
    )
    assert response.status_code == 200
    assert response.json()["results"] == []
