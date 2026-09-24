"""MLRun SQLAlchemy Model (Phase 3 data layer).

Tracks one model-training run inside an experiment: hyperparameters, metrics,
and (in later phases) the pointer to the MLflow run. No MLflow calls happen
here — this is the relational record that MLflow tracking will enrich later.
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class MLRun(Base):
    __tablename__ = "ml_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    params = Column(JSONB, nullable=False, default=dict)
    metrics = Column(JSONB, nullable=False, default=dict)
    # Populated by the MLflow integration in a later phase; plain id for now.
    mlflow_run_id = Column(String(255), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship("Experiment", back_populates="ml_runs", lazy="selectin")
    artifacts = relationship("Artifact", back_populates="ml_run", lazy="selectin")
    verifications = relationship(
        "Verification", back_populates="ml_run", lazy="selectin"
    )
    files = relationship(
        "FileMetadata", back_populates="ml_run", cascade="all, delete-orphan", lazy="selectin"
    )
    reproducibility_records = relationship(
        "ReproducibilityRecord", back_populates="ml_run", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<MLRun id={self.id} status={self.status!r}>"
