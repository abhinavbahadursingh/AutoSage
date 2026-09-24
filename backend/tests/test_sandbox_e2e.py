"""End-to-end sandbox execution test (Phase 10).

Tests the Docker sandbox with a simple ML training job.
Run with: python -m pytest tests/test_sandbox_e2e.py -v
"""
import json
import tempfile
from pathlib import Path

import pytest

from app.engine.sandbox.manager import SandboxManager, get_sandbox_manager, set_sandbox_manager
from app.engine.tools.ml import ExecuteMLJobTool, ExecuteMLJobInput, ExecuteMLJobStubTool
from app.engine.tools.base import ToolResult


def create_sample_dataset(path: Path, n_samples: int = 1000) -> None:
    """Create a simple synthetic classification dataset."""
    import numpy as np
    import pandas as pd
    from sklearn.datasets import make_classification

    X, y = make_classification(
        n_samples=n_samples,
        n_features=10,
        n_informative=5,
        n_redundant=2,
        n_classes=2,
        random_state=42,
    )
    df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(10)])
    df["target"] = y
    df.to_csv(path, index=False)
    print(f"Created dataset at {path} with {len(df)} rows")


@pytest.mark.asyncio
async def test_sandbox_direct():
    """Test sandbox manager directly."""
    # Skip if Docker not available
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "test_dataset.csv"
        create_sample_dataset(dataset_path)

        sandbox = SandboxManager(
            image_tag="autosage-runner:test",
            cpu_limit=1.0,
            memory_limit="1g",
            timeout_sec=120,
        )

        try:
            sandbox.build_image(force_rebuild=True)

            result = await sandbox.execute_job(
                job_id="test-job-1",
                script="",
                dataset_path=str(dataset_path),
                env_vars={
                    "MODEL_FAMILY": "random_forest",
                    "METRIC": "accuracy",
                    "DATASET_NAME": "test_dataset.csv",
                    "MODEL_PARAMS": json.dumps({"n_estimators": 10, "max_depth": 3}),
                    "TARGET_COLUMN": "target",
                    "TASK_TYPE": "classification",
                },
            )

            assert result.success
            assert "accuracy" in result.metrics
            assert 0 <= result.metrics["accuracy"] <= 1
            assert "model.joblib" in result.artifacts
        finally:
            sandbox.cleanup()


def test_ml_tool_with_sandbox():
    """Test the execute_ml_job tool with sandbox."""
    # Skip if Docker not available
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "test_dataset.csv"
        create_sample_dataset(dataset_path)

        tool = ExecuteMLJobTool()
        params = ExecuteMLJobInput(
            model_family="random_forest",
            dataset_name="test_dataset.csv",
            metric="accuracy",
            attempt=1,
            params={"n_estimators": 10, "max_depth": 3},
            experiment_id="exp-test",
            target_column="target",
            task_type="classification",
            dataset_path=str(dataset_path),
        )

        result = tool.run(params)

        assert result.get("success") is True
        assert "metrics" in result
        assert "accuracy" in result["metrics"]
        assert "artifacts" in result
        assert "model.joblib" in result["artifacts"]


def test_ml_tool_stub():
    """Test the stub tool (no Docker required)."""
    from app.engine.tools.ml import ExecuteMLJobStubTool

    tool = ExecuteMLJobStubTool()
    params = ExecuteMLJobInput(
        model_family="gradient_boosting",
        dataset_name="mock_dataset.csv",
        metric="accuracy",
        attempt=1,
        params={"n_estimators": 100},
        experiment_id="exp-stub",
    )

    result = tool.run(params)

    assert result["success"] is True
    assert result["job_id"].startswith("job-")
    assert result["note"] == "Stub mode: Docker sandbox not available"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])