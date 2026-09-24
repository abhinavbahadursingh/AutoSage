"""Verification SQLAlchemy Model (Phase 3 data layer).

Records the outcome of one empirical verification gate check (AST security
analysis, data-leakage detection, metric sanity, baseline dominance, ...).
The checks themselves run in later phases; here we persist gate results so
acceptance of a pipeline/run is auditable.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Verification(Base):
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
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    details = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship(
        "Experiment", back_populates="verifications", lazy="selectin"
    )
    ml_run = relationship("MLRun", back_populates="verifications", lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Verification id={self.id} check={self.check_name!r} status={self.status!r}>"
