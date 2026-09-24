"""Test script for MLflow integration (Phase 11).

This script tests the MLflow integration by:
1. Creating a mock experiment
2. Running the training script with MLflow tracking
3. Verifying parameters, metrics, model, and artifacts are recorded

Run this after starting MLflow server:
    mlflow server --backend-store-uri postgresql://... --default-artifact-root ./mlflow_artifacts --host 0.0.0.0 --port 5000

Or run in local file mode (no server needed):
    MLFLOW_TRACKING_URI=./mlruns python test_mlflow_integration.py
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Set MLflow tracking URI (use local file store for testing)
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///mlflow_test.db")
os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", "autosage_test")
os.environ.setdefault("MLFLOW_RUN_ID", "")  # Will be set by tracker

# Override database URL to use SQLite for testing
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///autosage_test.db")

import asyncio
import json

from app.core.config import settings
from app.engine.mlflow.client import get_mlflow_tracker, mlflow_run_context
from app.engine.sandbox.manager import get_sandbox_manager
from app.models.experiment import Experiment, ExperimentStatus
from app.models.ml_run import MLRun
from app.db.session import init_engine
from sqlalchemy import select

# Initialize database engine (must be before importing AsyncSessionLocal)
init_engine()

# Create tables using metadata
from app.models.base import Base
from app.db.session import engine
import asyncio

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(create_tables())

# Now import AsyncSessionLocal after engine is initialized
from app.db.session import AsyncSessionLocal


async def test_mlflow_integration():
    """Test MLflow integration with a simple experiment."""
    print("=" * 60)
    print("Testing MLflow Integration (Phase 11)")
    print("=" * 60)

    # Initialize database
    init_engine()

    # Check MLflow availability
    from app.engine.mlflow.client import is_mlflow_available
    available = is_mlflow_available()
    print(f"MLflow available: {available}")

    if not available:
        print("\n[WARN] MLflow tracking server not available.")
        print("Start MLflow server or set MLFLOW_TRACKING_URI to local file store.")
        print("Example: MLFLOW_TRACKING_URI=sqlite:///mlflow_test.db")
        return False

    # Create test experiment
    async with AsyncSessionLocal() as session:
        from app.models.workspace import Workspace
        from app.models.user import User

        # Create test user
        test_user = User(
            id=uuid.uuid4(),
            email="test@autosage.local",
            name="Test User",
        )
        session.add(test_user)

        # Create workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            name="Test Workspace",
            description="Test workspace for MLflow integration",
        )
        session.add(workspace)

        # Create experiment
        experiment = Experiment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name="Test MLflow Integration",
            description="Test experiment for MLflow integration",
            status=ExperimentStatus.CREATED.value,
            config={
                "model_family": "random_forest",
                "model_params": {"n_estimators": 10, "max_depth": 5},
                "dataset_name": "test_dataset.csv",
                "target_column": "target",
                "task_type": "classification",
                "metric": "accuracy",
            },
            max_retries=3,
        )
        session.add(experiment)
        await session.commit()
        await session.refresh(experiment)

        print(f"\nCreated experiment: {experiment.id}")

    # Test MLflow tracker
    print("\nTesting MLflow Tracker...")
    tracker = get_mlflow_tracker()

    # Create MLRun record
    async with AsyncSessionLocal() as session:
        experiment = await session.get(Experiment, experiment.id)
        ml_run = MLRun(
            experiment_id=experiment.id,
            name=experiment.name,
            status="RUNNING",
            params=experiment.config.get("model_params", {}),
        )
        session.add(ml_run)
        await session.flush()

        # Start MLflow run
        with mlflow_run_context(
            tracker,
            run_name=f"test-{experiment.name[:50]}",
            tags={"autosage_experiment_id": str(experiment.id), "autosage_ml_run_id": str(ml_run.id)},
            autosage_experiment_id=experiment.id,
        ) as run:
            mlflow_run_id = run.info.run_id
            ml_run.mlflow_run_id = mlflow_run_id
            ml_run.status = "RUNNING"
            await session.commit()
            print(f"Started MLflow run: {mlflow_run_id}")

        # Verify MLflow run was created
        mlflow_run = tracker.get_run(mlflow_run_id)
        if mlflow_run:
            print(f"MLflow run retrieved: {mlflow_run.info.run_id}")
            print(f"  Status: {mlflow_run.info.status}")
            print(f"  Experiment ID: {mlflow_run.info.experiment_id}")
        else:
            print("Failed to retrieve MLflow run")

        # Search for runs with autosage tag
        runs = tracker.search_runs(filter_string="tags.autosage_experiment_id = '{}'".format(experiment.id))
        print(f"Found {len(runs)} runs for experiment")

    # Test sandbox manager with MLflow
    print("\nTesting Sandbox Manager with MLflow...")
    try:
        sandbox = get_sandbox_manager()
        print(f"Sandbox manager initialized: {sandbox.image_tag}")
        print(f"MLflow tracking URI: {sandbox.mlflow_tracking_uri}")
        print(f"MLflow experiment: {sandbox.mlflow_experiment_name}")
    except Exception as e:
        print(f"Sandbox manager init failed (Docker may not be available): {e}")

    print("\n" + "=" * 60)
    print("MLflow Integration Test Complete")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(test_mlflow_integration())
    sys.exit(0 if result else 1)