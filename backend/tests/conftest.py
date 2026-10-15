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


class _FakeCodegenLLM:
    """Deterministic stand-in for the real provider during tests.

    The Objective Verification flow really calls the LLM in production. Tests
    must not depend on the network, a rate limit or a model's mood, so the
    generator is fed a canned reply that exercises the same parsing path the
    real reply goes through (FILE markers, structured decision JSON).
    """

    #: One pipeline + config + README, in exactly the format the parser wants.
    FILES_TEXT = (
        "--- FILE: pipeline.py ---\n"
        '"""Design-time pipeline; generated, never executed in this session."""\n'
        "from sklearn.pipeline import Pipeline\n"
        "MODEL = {'type': 'hist_gradient_boosting', 'max_depth': 8}\n"
        "--- FILE: config.yaml ---\n"
        "test_size: 0.2\n"
        "n_splits: 5\n"
        "primary_metric: roc_auc\n"
        "--- FILE: README.md ---\n"
        "Reviewer note: this session generates but never executes this code.\n"
    )
    #: The decision record: algorithm, hp, metrics, validation, assumptions...
    DESIGN_JSON = (
        '{"algorithm": "HistGradientBoostingClassifier",'
        ' "hyperparameters": {"max_depth": 8, "learning_rate": 0.08},'
        ' "metrics": {"primary": "roc_auc", "secondary": ["f1"]},'
        ' "validation_strategy": "stratified 5-fold cross-validation",'
        ' "assumptions": ["target is binary"],'
        ' "alternatives": ["logistic regression"],'
        ' "decisions": [{"category": "algorithm",'
        ' "decision": "HistGradientBoostingClassifier",'
        ' "rationale": "Handles mixed types without heavy preprocessing.",'
        ' "confidence": 0.8, "source": "sklearn docs",'
        ' "alternatives": ["logistic regression"],'
        ' "assumptions": ["binary target"]}]}'
    )

    provider = "fake"
    model = "fake/codegen"

    def has_providers(self) -> bool:
        return True

    async def complete(self, *, system: str, user: str, **kwargs):  # noqa: ANN001
        from types import SimpleNamespace

        return SimpleNamespace(text=self.FILES_TEXT, model=self.model, provider=self.provider)

    async def complete_structured(self, *, system: str, user: str, response_model, **kwargs):  # noqa: ANN001
        import json

        return response_model.model_validate(json.loads(self.DESIGN_JSON))


@pytest.fixture()
def fake_codegen_llm() -> _FakeCodegenLLM:
    """The canned codegen provider; override in a test to vary its output."""
    return _FakeCodegenLLM()


@pytest.fixture(autouse=True)
def _stub_codegen_llm(monkeypatch, fake_codegen_llm):
    """Keep tests hermetic: no test may reach a real LLM provider.

    Production still calls the real provider — only the generator's client
    lookup is redirected here. A test that wants the *real* failure path can
    monkeypatch ``app.engine.codegen.generator.get_llm_client`` itself.
    """
    monkeypatch.setattr(
        "app.engine.codegen.generator.get_llm_client",
        lambda: fake_codegen_llm,
    )


def _write_binary_dataset(path: str, rows: int = 400) -> str:
    """Write a small imbalanced binary-classification CSV; return its path."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(7)
    n = rows
    tenure = rng.integers(1, 60, n)
    score = (
        0.045 * tenure
        + 0.8 * (rng.random(n) < 0.4)          # month-to-month contract
        - 1.1 * (rng.random(n) < 0.3)          # tech support
    )
    churn = rng.binomial(1, 1.0 / (1.0 + np.exp(-(score - 2.6))))
    frame = pd.DataFrame(
        {
            "customerID": [f"C{i:05d}" for i in range(n)],
            "tenure": tenure,
            "contract": np.where(rng.random(n) < 0.4, "Month-to-month", "Two year"),
            "tech_support": np.where(rng.random(n) < 0.3, "Yes", "No"),
            "monthly_charges": np.round(rng.normal(70, 15, n), 2),
            "Churn": churn,
        }
    )
    frame.to_csv(path, index=False)
    return path


@pytest.fixture()
def binary_dataset(tmp_path) -> str:
    """Real CSV on disk so training stages measure instead of abstaining."""
    return _write_binary_dataset(str(tmp_path / "churn_small.csv"))


@pytest.fixture()
def recall_experiment_config(binary_dataset) -> dict:
    """Experiment config for a measured recall-optimized model comparison."""
    return {
        "dataset_name": "churn_small.csv",
        "dataset_path": binary_dataset,
        "target_column": "Churn",
        "task_type": "classification",
        "primary_metric": "recall",
        "compare_models": True,
    }