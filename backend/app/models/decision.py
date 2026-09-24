"""Decision SQLAlchemy Model (Phase 3 data layer).

A decision is one architectural choice made by an agent (e.g. "use
gradient boosting with target encoding"), with its rationale and confidence.
Decisions link the reasoning lineage: AgentExecution -> Decision -> Evidence.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision_type = Column(String(100), nullable=False, index=True)
    rationale = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship("Experiment", back_populates="decisions", lazy="selectin")
    agent_execution = relationship(
        "AgentExecution", back_populates="decisions", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Decision id={self.id} type={self.decision_type!r}>"
