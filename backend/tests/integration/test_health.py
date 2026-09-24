"""Phase 1: health endpoint contract (requires a reachable database)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_v1_health_reports_database() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "autosage-backend"
    assert body["status"] == "healthy"
    assert body["checks"]["database"] == "up"


def test_root_health_liveness() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
