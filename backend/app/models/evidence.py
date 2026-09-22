"""Evidence Trail Node SQLAlchemy Model."""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime
from app.models.base import Base

class EvidenceTrailNode(Base):
    __tablename__ = "evidence_trail_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    parent_node_id = Column(UUID(as_uuid=True), ForeignKey("evidence_trail_nodes.id", ondelete="SET NULL"), nullable=True)
    agent_name = Column(String(100), nullable=False)
    decision_type = Column(String(100), nullable=False)
    rationale = Column(Text, nullable=False)
    empirical_evidence = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
