"""Pipeline Run SQLAlchemy Model."""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.models.base import Base

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Optional link into the Phase 3+ experiment world; Phase 2 runs keep NULL.
    experiment_id = Column(
        UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    user_prompt = Column(Text, nullable=False)
    final_metrics = Column(JSONB, default={})
    artifact_uri = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="pipeline_runs", lazy="selectin")
