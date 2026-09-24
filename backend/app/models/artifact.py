"""Artifact SQLAlchemy Model (Phase 3 data layer).

An artifact is any file produced by an experiment: trained models, exported
pipelines, plots, reports, processed datasets. Storage/blob handling lands in
later phases; here we persist the catalog record (what, where, how big).
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ml_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ml_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pipeline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    kind = Column(String(50), nullable=False, default="file", index=True)
    uri = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=True)
    meta = Column("meta", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship("Experiment", back_populates="artifacts", lazy="selectin")
    ml_run = relationship("MLRun", back_populates="artifacts", lazy="selectin")
    pipeline = relationship("Pipeline", back_populates="artifacts", lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Artifact id={self.id} kind={self.kind!r} name={self.name!r}>"
