"""Evidence Trail Node Builder and Lineage Tracker."""
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

class EvidenceBuilder:
    @staticmethod
    def create_node(agent_name: str, decision_type: str, rationale: str, evidence: Dict[str, Any], parent_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "node_id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "agent_name": agent_name,
            "decision_type": decision_type,
            "rationale": rationale,
            "empirical_evidence": evidence,
            "timestamp": datetime.utcnow().isoformat()
        }
