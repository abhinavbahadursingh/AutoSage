"""pytest configuration for unit tests."""
import os
from unittest.mock import patch

import pytest

# Set test-specific environment variables BEFORE any app imports
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("BETTER_AUTH_SECRET", "test-secret-key-for-testing-32chars")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_DEV_TOKEN_ENABLED", "true")
# MLflow offline: sqlite store instead of a live tracking server (tests must
# run without infra; a dead http://localhost:5000 causes long urllib3 retries,
# and this mlflow version rejects the legacy file store without an opt-out).
os.environ.setdefault(
    "MLFLOW_TRACKING_URI",
    "sqlite:///" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".pytest_mlflow.db")).replace("\\", "/"),
)
# Eager Celery retries must not sleep the production backoff (60s+) in tests.
os.environ.setdefault("CELERY_RETRY_BACKOFF_BASE", "1")
os.environ.setdefault("CELERY_RETRY_BACKOFF_MAX", "2")


@pytest.fixture(autouse=True)
def _override_jwt_for_tests():
    """Force HS256 for all unit tests (they test shared-secret path)."""
    with patch("app.core.security.settings.JWT_ALGORITHM", "HS256"):
        with patch("app.core.security.settings.BETTER_AUTH_SECRET", "test-secret-key-for-testing-32chars"):
            with patch("app.core.security.settings.APP_SECRET_KEY", "test-secret-key-for-testing-only-32chars"):
                yield