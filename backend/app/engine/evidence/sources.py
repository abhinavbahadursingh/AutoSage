"""Built-in Evidence Sources (Phase 12).

Implementations of EvidenceSource for internal systems and stubs for
external systems that will be fleshed out in later phases.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
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


class WebEvidenceSource(EvidenceSource):
    """Real web search evidence source.

    Searches the internet via DuckDuckGo's HTML endpoint (no API key
    required) and returns results as verifiable evidence pieces. Every
    result carries a URL so claims can be independently corroborated.
    """

    source_id = "web_search"
    source_type = "web"
    _BASE_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EvidenceSearchResult:
        """Search the live web via DuckDuckGo HTML."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    self._BASE_URL,
                    data={"q": query},
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0 Safari/537.36",
                    },
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:  # noqa: BLE001 - web search is best-effort
            return EvidenceSearchResult(
                query=query,
                pieces=[],
                total_found=0,
                search_metadata={
                    "source": self.source_id,
                    "error": f"web search unavailable: {type(exc).__name__}",
                },
            )

        pieces = self._parse_results(html, limit)
        return EvidenceSearchResult(
            query=query,
            pieces=pieces,
            total_found=len(pieces),
            search_metadata={"source": self.source_id, "engine": "duckduckgo"},
        )

    def _parse_results(self, html: str, limit: int) -> List[EvidencePiece]:
        """Extract result titles, URLs and snippets from DuckDuckGo HTML."""
        pieces: List[EvidencePiece] = []

        # DuckDuckGo result blocks look like:
        # <a rel="nofollow" class="result__a" href="URL">TITLE</a>
        # <a class="result__snippet" ...>SNIPPET</a>
        result_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        urls = result_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i, (raw_url, raw_title) in enumerate(urls[:limit]):
            title = re.sub(r"<[^>]+>", "", raw_title or "").strip()
            title = re.sub(r"\s+", " ", title)
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[i] or "").strip()
                snippet = re.sub(r"\s+", " ", snippet)
            # DuckDuckGo uses a redirect URL; extract the actual destination.
            url = self._unwrap_ddg_redirect(raw_url)
            if not title or not url:
                continue
            pieces.append(
                EvidencePiece(
                    content=snippet or title,
                    source_id=self.source_id,
                    source_type=self.source_type,
                    title=title,
                    url=url,
                    snippet=snippet or None,
                    credibility_score=0.7,  # web results are corroborative, not authoritative
                    metadata={"engine": "duckduckgo", "result_index": i},
                    retrieved_at=datetime.utcnow(),
                )
            )

        return pieces

    @staticmethod
    def _unwrap_ddg_redirect(url: str) -> str:
        """Extract the destination URL from a DuckDuckGo redirect link."""
        if not url:
            return url
        # DDG links look like //duckduckgo.com/l/?uddg=ENCODED_URL
        m = re.search(r"uddg=([^&]+)", url)
        if m:
            from urllib.parse import unquote

            return unquote(m.group(1))
        return url


# Auto-register session-independent sources at import time so the evidence
# source registry is populated regardless of which code path runs
# (objective verification, Phase 12 verification, etc.). Sources that need a
# database session are still registered via register_builtin_sources().
_auto_registered: List[EvidenceSource] = []
for _src in (MockExternalEvidenceSource(), WebEvidenceSource()):
    register_evidence_source(_src)
    _auto_registered.append(_src)


# Auto-register built-in sources (will be instantiated with session when used)
def register_builtin_sources(session: AsyncSession) -> List[EvidenceSource]:
    """Register all built-in evidence sources with a database session."""
    sources = [
        InternalEvidenceSource(session),
        MockExternalEvidenceSource(),
        WebEvidenceSource(),
        MemoryEvidenceSource(session),
    ]
    for src in sources:
        register_evidence_source(src)
    return sources