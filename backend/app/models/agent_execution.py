"""AgentExecution SQLAlchemy Model (Phase 3 data layer).

Records one attempt of one LangGraph agent (discovery, profiler, preprocessor,
model selector, experimenter, verifier, ...) within an experiment. Agent
orchestration itself is a later phase; here we persist execution history so
the reasoning lineage (Agent -> Decision -> Evidence -> Result) is queryable.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        Index("ix_agent_executions_experiment_agent", "experiment_id", "agent_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pipeline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_name = Column(String(100), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    attempt = Column(Integer, nullable=False, default=1)
    input_payload = Column(JSONB, nullable=False, default=dict)
    output_payload = Column(JSONB, nullable=False, default=dict)
    error_detail = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship(
        "Experiment", back_populates="agent_executions", lazy="selectin"
    )
    pipeline = relationship("Pipeline", back_populates="agent_executions", lazy="selectin")
    decisions = relationship(
        "Decision", back_populates="agent_execution", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<AgentExecution id={self.id} agent={self.agent_name!r} status={self.status!r}>"
