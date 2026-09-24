"""Evidence Source Models (Phase 12).

Abstract interface for pluggable evidence sources. New sources (web search, papers,
PDFs, memory systems) implement this interface without changing the verification engine.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


@dataclass
class EvidenceSourceMetadata:
    """Metadata about an evidence source for credibility weighting."""
    source_id: str
    source_type: str  # e.g., "web", "paper", "memory", "internal", "expert"
    credibility_score: float = 1.0  # 0.0 - 1.0
    last_updated: Optional[datetime] = None
    extra: Optional[Dict[str, Any]] = None


class EvidencePiece(BaseModel):
    """A single piece of evidence from a source."""
    model_config = ConfigDict(extra="forbid")

    content: str
    source_id: str
    source_type: str
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    credibility_score: float = 1.0
    metadata: Dict[str, Any] = {}
    retrieved_at: datetime


class EvidenceSearchResult(BaseModel):
    """Result of an evidence search query."""
    model_config = ConfigDict(extra="forbid")

    query: str
    pieces: List[EvidencePiece]
    total_found: int
    search_metadata: Dict[str, Any] = {}


class EvidenceSource(ABC):
    """Abstract base class for evidence sources.

    Each source must implement:
    - search: Find relevant evidence for a query
    - get_metadata: Return source credibility/type info
    """

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this source."""
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Type category: 'web', 'paper', 'memory', 'internal', 'expert', etc."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EvidenceSearchResult:
        """Search for evidence relevant to the query."""
        ...

    def get_metadata(self) -> EvidenceSourceMetadata:
        """Return metadata about this source."""
        return EvidenceSourceMetadata(
            source_id=self.source_id,
            source_type=self.source_type,
        )


# Registry for evidence sources
_evidence_sources: Dict[str, EvidenceSource] = {}


def register_evidence_source(source: EvidenceSource) -> None:
    """Register an evidence source in the global registry."""
    _evidence_sources[source.source_id] = source


def get_evidence_source(source_id: str) -> Optional[EvidenceSource]:
    """Get a registered evidence source by ID."""
    return _evidence_sources.get(source_id)


def list_evidence_sources() -> List[EvidenceSource]:
    """List all registered evidence sources."""
    return list(_evidence_sources.values())


def clear_evidence_sources() -> None:
    """Clear all registered sources (for testing)."""
    _evidence_sources.clear()