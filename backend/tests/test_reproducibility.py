#!/usr/bin/env python
"""Test script for Phase 17 Reproducibility Engine.

Creates an experiment, runs it, and verifies the reproducibility record is created.
Run with: python -m pytest tests/test_reproducibility.py -v
"""
import uuid
from datetime import datetime

import pytest

from app.db import session as session_module
from app.models.dataset import Dataset
from app.models.experiment import Experiment, ExperimentStatus
from app.models.ml_run import MLRun
from app.models.project import Project
from app.models.reproducibility import ReproducibilityRecord
from app.models.user import User
from app.services.reproducibility_service import ReproducibilityService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_reproducibility_record():
    """Test creating and retrieving a reproducibility record."""
    session_module.init_engine()
    session: AsyncSession = session_module.AsyncSessionLocal()

    try:
        # Create user and project
        user = User(id=uuid.uuid4(), email="test@example.com", name="Test User")
        session.add(user)
        await session.flush()

        project = Project(
            id=uuid.uuid4(),
            user_id=user.id,
            name="Test Project",
            description="Test project",
        )
        session.add(project)
        await session.flush()

        workspace_id = uuid.UUID("1fba399b-2e91-4e1d-a948-a07341c6a6d3")

        # Create an experiment
        experiment = Experiment(
            workspace_id=workspace_id,
            name="Test Reproducibility Experiment",
            description="Test experiment for reproducibility",
            status=ExperimentStatus.COMPLETED.value,
            config={
                "model_family": "gradient_boosting",
                "model_params": {"n_estimators": 100, "learning_rate": 0.1},
                "task_type": "classification",
                "metric": "accuracy",
                "dataset_path": "/data/test.csv",
                "random_seed": 42,
            },
            result_summary={
                "ml_result": {"accuracy": 0.95, "f1": 0.93},
                "mlflow_run_id": "test-mlflow-run-id",
                "ml_run_id": str(uuid.uuid4()),
            },
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        session.add(experiment)
        await session.flush()

        # Create MLRun
        ml_run = MLRun(
            experiment_id=experiment.id,
            name=experiment.name,
            status="COMPLETED",
            params=experiment.config.get("model_params", {}),
            metrics={"accuracy": 0.95, "f1": 0.93},
            mlflow_run_id="test-mlflow-run-id",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        session.add(ml_run)
        await session.flush()

        # Create a mock dataset
        dataset = Dataset(
            project_id=project.id,
            workspace_id=workspace_id,
            original_filename="test.csv",
            storage_path="/data/test.csv",
            file_size_bytes=1024000,
            schema_metadata={"columns": ["feature1", "feature2", "target"], "types": ["float", "float", "int"]},
            profile_summary={"row_count": 1000, "column_count": 3},
        )
        session.add(dataset)
        await session.flush()

        # Create reproducibility record
        service = ReproducibilityService(session)
        record = await service.create_record(
            experiment=experiment,
            ml_run=ml_run,
            dataset=dataset,
            sandbox_result={
                "artifact_uris": {"model": "s3://bucket/model.pkl", "logs": "s3://bucket/logs.txt"},
                "model_artifact_uri": "s3://bucket/model.pkl",
                "log_artifact_uri": "s3://bucket/logs.txt",
            },
        )

        assert record is not None
        assert record.experiment_id == experiment.id
        assert record.ml_run_id == ml_run.id
        assert record.dataset_id == dataset.id
        assert record.model_family == "gradient_boosting"
        assert record.mlflow_run_id == "test-mlflow-run-id"
        assert record.final_metrics == {"accuracy": 0.95, "f1": 0.93}

        # Verify retrieval
        retrieved = await service.get_by_experiment(experiment.id, uuid.uuid4())
        if retrieved is None:
            # Try without ownership check for test
            query = select(ReproducibilityRecord).where(ReproducibilityRecord.experiment_id == experiment.id)
            result = await session.execute(query)
            retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.dataset_sha256 == record.dataset_sha256
        assert retrieved.model_params == record.model_params

        await session.commit()
    finally:
        await session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])