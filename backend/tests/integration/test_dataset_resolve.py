"""Dataset resolve/upload endpoints — the "dataset not found" preflight.

Covers the contract the new-experiment form depends on:

- ``GET  /datasets/resolve`` answers 200 with ``available: false`` when the
  dataset is missing (a normal answer, not a 404), and ``available: true``
  once the file has been uploaded.
- ``POST /datasets/upload`` writes the file where the worker's
  ``resolve_dataset_path`` looks, so the run that was blocked can proceed.
- Both endpoints require auth and never leak other tenants' filenames.
"""
import io
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from tests.fakes import FakeAsyncSession

USER_A = {"email": "alice@autosage.local", "name": "Alice"}
CSV_BYTES = b"feature,target\n1,0\n2,1\n"


@pytest.fixture()
def fake_session() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture()
def client(fake_session: FakeAsyncSession):
    async def override_get_db():  # type: ignore[no-untyped-def]
        yield fake_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def token() -> str:
    return create_access_token(str(uuid.uuid4()), {"email": USER_A["email"], "name": USER_A["name"]})


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def stored_name(request: pytest.FixtureRequest) -> str:
    """A filename that is unique per test so runs cannot interfere."""
    name = f"autosage_test_{uuid.uuid4().hex[:8]}.csv"
    yield name
    (Path(settings.UPLOAD_DIR) / name).unlink(missing_ok=True)


# -- auth enforcement ----------------------------------------------------
def test_dataset_endpoints_reject_anonymous(client: TestClient, stored_name: str) -> None:
    assert client.get("/api/v1/datasets/resolve", params={"name": stored_name}).status_code == 401
    assert (
        client.post(
            "/api/v1/datasets/upload",
            files={"file": ("x.csv", io.BytesIO(CSV_BYTES), "text/csv")},
        ).status_code
        == 401
    )


# -- resolve --------------------------------------------------------------
def test_resolve_reports_missing_dataset_as_unavailable(
    client: TestClient, token: str, stored_name: str
) -> None:
    """The whole point of the probe: 200 + available:false, never a 404."""
    response = client.get(
        "/api/v1/datasets/resolve", params={"name": stored_name}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is False
    assert body["source"] is None


def test_resolve_finds_an_uploaded_dataset(
    client: TestClient, token: str, stored_name: str
) -> None:
    uploaded = client.post(
        "/api/v1/datasets/upload",
        files={"file": (stored_name, io.BytesIO(CSV_BYTES), "text/csv")},
        headers=auth_headers(token),
    )
    assert uploaded.status_code == 200, uploaded.text

    response = client.get(
        "/api/v1/datasets/resolve", params={"name": stored_name}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    assert body["source"] == "upload_dir"
    assert body["size_bytes"] == len(CSV_BYTES)


def test_resolve_requires_a_name(client: TestClient, token: str) -> None:
    assert (
        client.get("/api/v1/datasets/resolve", params={}, headers=auth_headers(token)).status_code
        == 422
    )


def test_resolve_normalizes_traversal_names(
    client: TestClient, token: str, stored_name: str
) -> None:
    """A traversal attempt resolves to the bare basename, never the raw input."""
    client.post(
        "/api/v1/datasets/upload",
        files={"file": (stored_name, io.BytesIO(CSV_BYTES), "text/csv")},
        headers=auth_headers(token),
    )
    response = client.get(
        "/api/v1/datasets/resolve",
        params={"name": f"../../{stored_name}"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    assert body["name"] == stored_name


# -- upload ---------------------------------------------------------------
def test_upload_persists_the_file_for_the_worker(
    client: TestClient, token: str, stored_name: str
) -> None:
    """The worker resolves from UPLOAD_DIR, so the bytes must land there."""
    from app.engine.tools.ml import resolve_dataset_path

    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": (stored_name, io.BytesIO(CSV_BYTES), "text/csv")},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body: Dict[str, Any] = response.json()
    assert body["name"] == stored_name
    assert body["status"] == "uploaded"

    # The exact call the ML tool makes must now succeed (no DatasetNotFoundError).
    resolved = Path(resolve_dataset_path(stored_name))
    assert resolved.is_file()
    assert resolved.read_bytes() == CSV_BYTES


def test_upload_rejects_a_traversal_filename(
    client: TestClient, token: str, tmp_path: Path
) -> None:
    """Traversal filenames are refused outright, never written anywhere.

    ``validate_upload_file`` rejects the name before it reaches storage, so
    this is a 400 and nothing lands in UPLOAD_DIR.
    """
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("../../evil.csv", io.BytesIO(CSV_BYTES), "text/csv")},
        headers=auth_headers(token),
    )
    assert response.status_code == 400, response.text
    assert not (Path(settings.UPLOAD_DIR) / "evil.csv").exists()
    assert not (Path(settings.UPLOAD_DIR).parent.parent / "evil.csv").exists()


def test_upload_sanitizes_a_nested_but_legal_filename(
    client: TestClient, token: str, tmp_path: Path
) -> None:
    """A plain basename is stored as-is, inside UPLOAD_DIR."""
    name = f"nested_{uuid.uuid4().hex[:8]}.csv"
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": (name, io.BytesIO(CSV_BYTES), "text/csv")},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == name

    stored = Path(settings.UPLOAD_DIR) / name
    assert stored.resolve().is_relative_to(Path(settings.UPLOAD_DIR).resolve())
    stored.unlink(missing_ok=True)


def test_upload_rejects_an_unsupported_content_type(
    client: TestClient, token: str, stored_name: str
) -> None:
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": (stored_name, io.BytesIO(b"\x00\x01"), "application/x-msdownload")},
        headers=auth_headers(token),
    )
    assert response.status_code == 415, response.text