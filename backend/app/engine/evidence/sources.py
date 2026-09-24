"""Built-in Evidence Sources (Phase 12).

Implementations of EvidenceSource for internal systems and stubs for
external systems that will be fleshed out in later phases.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.evidence.source import (
    EvidencePiece,
    EvidenceSearchResult,
    EvidenceSource,
    register_evidence_source,
)
from app.models.evidence import EvidenceTrailNode


class InternalEvidenceSource(EvidenceSource):
    """Evidence source that queries the internal evidence trail.

    Searches EvidenceTrailNode records for empirical evidence supporting
    or contradicting claims. This is the primary source for Phase 12.
    """

    source_id = "internal_evidence_trail"
    source_type = "internal"

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EvidenceSearchResult:
        """Search internal evidence trail nodes."""
        stmt = select(EvidenceTrailNode).where(
            EvidenceTrailNode.rationale.ilike(f"%{query}%")
        )

        if filters:
            if "run_id" in filters:
                stmt = stmt.where(EvidenceTrailNode.run_id == filters["run_id"])
            if "agent_name" in filters:
                stmt = stmt.where(EvidenceTrailNode.agent_name == filters["agent_name"])

        stmt = stmt.order_by(EvidenceTrailNode.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()

        pieces = []
        for node in nodes:
            empirical = node.empirical_evidence or {}
            pieces.append(
                EvidencePiece(
                    content=node.rationale,
                    source_id=self.source_id,
                    source_type=self.source_type,
                    title=f"{node.agent_name} - {node.decision_type}",
                    snippet=str(empirical.get("summary", ""))[:200] if empirical else None,
                    credibility_score=1.0,  # Internal evidence is fully trusted
                    metadata={
                        "node_id": str(node.id),
                        "agent_name": node.agent_name,
                        "decision_type": node.decision_type,
                        "empirical_evidence": empirical,
                    },
                    retrieved_at=node.created_at,
                )
            )

        return EvidenceSearchResult(
            query=query,
            pieces=pieces,
            total_found=len(pieces),
            search_metadata={"source": self.source_id, "filters": filters},
        )


class MockExternalEvidenceSource(EvidenceSource):
    """Mock external evidence source for testing and development.

    In production, this would connect to web search APIs, paper databases,
    or other external knowledge sources. Phase 13+ will implement real connectors.
    """

    source_id = "mock_external"
    source_type = "external"

    def __init__(self):
        # Mock knowledge base for testing
        self._mock_kb: Dict[str, List[Dict[str, Any]]] = {
            "accuracy": [
                {
                    "title": "Metric Validation Guidelines",
                    "content": "Accuracy should be between 0 and 1. Perfect scores (1.0) are suspicious and may indicate target leakage.",
                    "credibility": 0.9,
                },
                {
                    "title": "Classification Best Practices",
                    "content": "For imbalanced datasets, F1-score or AUC-ROC are preferred over accuracy.",
                    "credibility": 0.85,
                },
            ],
            "target leakage": [
                {
                    "title": "Target Leakage Detection",
                    "content": "Target leakage occurs when training data contains information about the target that won't be available at inference time. Common sources: using future data, using target-derived features.",
                    "credibility": 0.95,
                },
            ],
            "overfitting": [
                {
                    "title": "Overfitting Thresholds",
                    "content": "Train-validation gap > 0.15 for AUC or > 0.1 for accuracy suggests overfitting. Cross-validation helps detect this.",
                    "credibility": 0.9,
                },
            ],
        }

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EvidenceSearchResult:
        """Search mock knowledge base."""
        query_lower = query.lower()
        matched = []

        for topic, entries in self._mock_kb.items():
            if topic.lower() in query_lower or any(kw in query_lower for kw in topic.split()):
                matched.extend(entries)

        # If no topic match, return general entries
        if not matched:
            for entries in self._mock_kb.values():
                matched.extend(entries[:1])

        pieces = []
        for entry in matched[:limit]:
            pieces.append(
                EvidencePiece(
                    content=entry["content"],
                    source_id=self.source_id,
                    source_type=self.source_type,
                    title=entry["title"],
                    credibility_score=entry["credibility"],
                    metadata={},
                    retrieved_at=datetime.utcnow(),
                )
            )

        return EvidenceSearchResult(
            query=query,
            pieces=pieces,
            total_found=len(pieces),
            search_metadata={"source": self.source_id, "mock": True},
        )


class MemoryEvidenceSource(EvidenceSource):
    """Evidence source that queries the verified memory system.

    Stub for Phase 13+ when memory/pgvector is implemented.
    """

    source_id = "memory"
    source_type = "memory"

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EvidenceSearchResult:
        """Search memory system (stub - returns empty for now)."""
        # TODO: Phase 13 - implement pgvector similarity search
        return EvidenceSearchResult(
            query=query,
            pieces=[],
            total_found=0,
            search_metadata={"source": self.source_id, "status": "not_implemented"},
        )


# Auto-register built-in sources (will be instantiated with session when used)
def register_builtin_sources(session: AsyncSession) -> List[EvidenceSource]:
    """Register all built-in evidence sources with a database session."""
    sources = [
        InternalEvidenceSource(session),
        MockExternalEvidenceSource(),
        MemoryEvidenceSource(session),
    ]
    for src in sources:
        register_evidence_source(src)
    return sources