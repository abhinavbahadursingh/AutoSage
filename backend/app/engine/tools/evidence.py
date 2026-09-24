"""Evidence search tool (Phase 9 stub).

Real evidence-DAG queries land with the verification engine — this exposes
the Agent -> Tool contract only.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.engine.tools.base import BaseTool


class SearchEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=512)
    run_id: Optional[str] = Field(default=None, max_length=64)
    limit: int = Field(default=10, ge=1, le=100)


class SearchEvidenceTool(BaseTool):
    name = "search_evidence"
    description = "Search evidence trail nodes for an experiment/run (stub)."
    input_model = SearchEvidenceInput

    def run(self, params: BaseModel) -> Dict[str, object]:
        assert isinstance(params, SearchEvidenceInput)
        nodes: List[Dict[str, object]] = []
        return {
            "query": params.query,
            "run_id": params.run_id,
            "nodes": nodes,
            "total": len(nodes),
            "note": "Phase 9 stub: evidence store not wired yet",
        }
