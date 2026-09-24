"""Reproducibility Record SQLAlchemy Model (Phase 17).

Captures a complete reproducibility snapshot for every completed ML experiment,
including dataset hash, code version, dependencies, environment, and MLflow linkage.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class ReproducibilityRecord(Base):
    __tablename__ = "reproducibility_records"
    __table_args__ = (
        Index("ix_reproducibility_experiment_id", "experiment_id"),
        Index("ix_reproducibility_ml_run_id", "ml_run_id"),
        Index("ix_reproducibility_dataset_id", "dataset_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ml_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ml_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Dataset fingerprint
    dataset_sha256 = Column(String(64), nullable=False)  # SHA-256 hex
    dataset_size_bytes = Column(BigInteger, nullable=True)
    dataset_rows = Column(Integer, nullable=True)
    dataset_columns = Column(Integer, nullable=True)
    dataset_schema = Column(JSONB, nullable=True)  # column names + types

    # Code / version information
    code_version = Column(String(255), nullable=True)  # git commit SHA or version tag
    code_repository = Column(String(500), nullable=True)  # git remote URL
    code_branch = Column(String(255), nullable=True)
    code_dirty = Column(String(10), nullable=True)  # "true"/"false" - working tree state

    # Dependency versions
    python_version = Column(String(50), nullable=False)  # e.g., "3.11.9"
    platform = Column(String(100), nullable=True)  # e.g., "linux-x86_64"
    pip_freeze = Column(JSONB, nullable=True)  # {package: version}
    conda_env = Column(JSONB, nullable=True)  # exported conda env if applicable

    # Model & experiment configuration
    model_family = Column(String(100), nullable=False)  # e.g., "gradient_boosting"
    model_name = Column(String(255), nullable=True)  # specific model identifier
    model_params = Column(JSONB, nullable=False, default=dict)  # hyperparameters
    experiment_config = Column(JSONB, nullable=False, default=dict)  # full experiment config
    random_seed = Column(Integer, nullable=True)

    # MLflow linkage
    mlflow_run_id = Column(String(255), nullable=True, index=True)
    mlflow_experiment_id = Column(String(255), nullable=True)
    mlflow_experiment_name = Column(String(255), nullable=True)

    # Runtime environment
    runtime_type = Column(String(50), nullable=True)  # "docker", "conda", "venv", "system"
    docker_image = Column(String(500), nullable=True)  # image digest if Docker
    docker_image_id = Column(String(255), nullable=True)
    container_id = Column(String(255), nullable=True)  # runtime container ID
    hardware_info = Column(JSONB, nullable=True)  # CPU, GPU, memory info

    # Artifact references
    artifact_uris = Column(JSONB, nullable=True)  # {name: uri} for model, logs, etc.
    model_artifact_uri = Column(String(500), nullable=True)
    log_artifact_uri = Column(String(500), nullable=True)

    # Metrics snapshot (for quick reference without MLflow)
    final_metrics = Column(JSONB, nullable=True)  # final metric values

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    experiment = relationship("Experiment", back_populates="reproducibility_records", lazy="selectin")
    ml_run = relationship("MLRun", back_populates="reproducibility_records", lazy="selectin")
    dataset = relationship("Dataset", back_populates="reproducibility_records", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ReproducibilityRecord id={self.id} experiment={self.experiment_id}>"