from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

class EvidenceNodeResponse(BaseModel):
    id: UUID
    parent_node_id: Optional[UUID] = None
    agent_name: str
    decision_type: str
    rationale: str
    empirical_evidence: Dict[str, Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
