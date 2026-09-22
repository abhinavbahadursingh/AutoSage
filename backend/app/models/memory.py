"""Verified Memory SQLAlchemy Model with pgvector."""
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from app.models.base import Base

class VerifiedMemory(Base):
    __tablename__ = "verified_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    task_type = Column(String(100), nullable=False)
    dataset_fingerprint = Column(JSONB, nullable=False)
    solution_strategy = Column(String, nullable=False)
    achieved_metric_value = Column(Float, nullable=False)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)
