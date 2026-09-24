"""Experience Memory SQLAlchemy Model with pgvector."""
import enum
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from app.models.base import Base


class MemoryType(str, enum.Enum):
    """Types of experience memories."""
    VERIFIED_CLAIM = "verified_claim"
    SUCCESSFUL_EXPERIMENT = "successful_experiment"
    FAILED_EXPERIMENT = "failed_experiment"
    DATASET_INSIGHT = "dataset_insight"
    MODEL_SELECTION_EXPERIENCE = "model_selection_experience"
    PREPROCESSING_EXPERIENCE = "preprocessing_experience"
    AGENT_DECISION = "agent_decision"


class MemoryStatus(str, enum.Enum):
    """Lifecycle status of a memory entry."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    PENDING_VERIFICATION = "pending_verification"


class ExperienceMemory(Base):
    __tablename__ = "experience_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    experiment_id = Column(
        UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    source_run_id = Column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    memory_type = Column(String(50), nullable=False, index=True)
    status = Column(String(30), nullable=False, default=MemoryStatus.ACTIVE.value, index=True)
    task_type = Column(String(100), nullable=False, index=True)
    dataset_fingerprint = Column(JSONB, nullable=False)
    solution_strategy = Column(Text, nullable=False)
    achieved_metric_value = Column(Float, nullable=True)
    metric_name = Column(String(100), nullable=True)
    memory_metadata = Column(JSONB, nullable=False, default={})
    embedding = Column(Vector(1536), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    access_count = Column(Integer, nullable=False, default=0)
    last_accessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    archived_at = Column(DateTime, nullable=True)
