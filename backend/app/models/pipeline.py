"""Pipeline SQLAlchemy Model (Phase 3 data layer).

A pipeline is the generated, versionable ML workflow attached to an
experiment: an ordered DAG of stages (ingest -> profile -> preprocess ->
train -> verify -> export) stored as JSON. Execution of pipeline stages is a
later phase (Celery/LangGraph); here we persist definitions and status only.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="DRAFT", index=True)
    definition = Column(JSONB, nullable=False, default=dict)
    meta = Column("meta", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship("Experiment", back_populates="pipelines", lazy="selectin")
    agent_executions = relationship(
        "AgentExecution", back_populates="pipeline", lazy="selectin"
    )
    artifacts = relationship(
        "Artifact", back_populates="pipeline", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Pipeline id={self.id} status={self.status!r}>"
