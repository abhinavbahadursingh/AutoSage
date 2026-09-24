"""Experiment SQLAlchemy Model + lifecycle states (Phase 3/4).

Lifecycle (enforced in :mod:`app.services.experiment_service`)::

    CREATED -> QUEUED -> RUNNING -> COMPLETED
    RUNNING -> FAILED -> RETRYING -> RUNNING   (failure path)
    CREATED/QUEUED/RUNNING/RETRYING/FAILED -> CANCELLED

``QUEUED -> RUNNING`` and the failure path are driven by workers in later
phases (Celery/LangGraph); the API exposes ``start`` (``CREATED -> QUEUED``)
and ``cancel`` transitions. All other transitions are rejected with 409.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class ExperimentStatus(str, enum.Enum):
    """All experiment lifecycle states (stored as plain strings)."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = frozenset(
    {ExperimentStatus.COMPLETED.value, ExperimentStatus.CANCELLED.value}
)


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        Index("ix_experiments_workspace_status", "workspace_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(20), nullable=False, default=ExperimentStatus.CREATED.value, index=True
    )
    config = Column(JSONB, nullable=False, default=dict)
    result_summary = Column(JSONB, nullable=False, default=dict)
    error_detail = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    # Celery task id tracking the background run (Phase 5). Set on enqueue,
    # used for revoke-on-cancel and task-state inspection.
    celery_task_id = Column(String(255), nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    workspace = relationship("Workspace", back_populates="experiments", lazy="selectin")
    pipelines = relationship(
        "Pipeline", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
    agent_executions = relationship(
        "AgentExecution",
        back_populates="experiment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    decisions = relationship(
        "Decision", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
    verifications = relationship(
        "Verification",
        back_populates="experiment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ml_runs = relationship(
        "MLRun", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
    artifacts = relationship(
        "Artifact", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
    pipeline_runs = relationship(
        "PipelineRun", back_populates="experiment", lazy="selectin"
    )
    files = relationship(
        "FileMetadata", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )
    reproducibility_records = relationship(
        "ReproducibilityRecord", back_populates="experiment", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Experiment id={self.id} status={self.status!r}>"
