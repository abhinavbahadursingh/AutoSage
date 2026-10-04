"""Verification SQLAlchemy Model (Phase 12 extended).

Records the outcome of the empirical verification gate for an experiment,
including per-decision details: decision ID, evidence summary, verification
result (VERIFIED/CONFLICT/REJECTED/UNVERIFIED/ABSTAIN), reasoning, and final
status. This enables audit trails and quarantine of unverified experiences.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Verification(Base):
    """Verification of an experiment's decisions via the empirical gate."""

    __tablename__ = "verifications"

    __table_args__ = (
        Index("ix_verifications_experiment_check", "experiment_id", "check_name"),
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
    check_name = Column(String(100), nullable=False, index=True)
    # Per-decision results: maps decision_id -> {status, confidence, reasoning}
    decisions = Column(JSONB, nullable=False, default=dict)
    overall_status = Column(
        String(30), nullable=False, default="UNVERIFIED", index=True
    )
    overall_confidence = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship(
        "Experiment", back_populates="verifications")
    ml_run = relationship("MLRun", back_populates="verifications")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Verification id={self.id} experiment={self.experiment_id} "
            f"status={self.overall_status!r}>"
        )
