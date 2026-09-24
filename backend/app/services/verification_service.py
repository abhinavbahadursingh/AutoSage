"""Verification Service (Phase 12).

Service layer for verification operations: decision verification,
experiment verification, evidence search, and source management.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.evidence.source import (
    EvidenceSource,
    get_evidence_source,
    list_evidence_sources,
    register_evidence_source,
)
from app.engine.evidence.sources import register_builtin_sources
from app.engine.verification.claims import ClaimStatus
from app.engine.verification.engine import VerificationEngine
from app.engine.verification.extractors import DecisionRecord
from app.models.decision import Decision
from app.models.agent_execution import AgentExecution
from app.schemas.verification import (
    EvidencePieceResponse,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    EvidenceSourceInfo,
    VerificationResponse,
    VerifyDecisionRequest,
    VerifyExperimentRequest,
)


class VerificationService:
    """Service for verification operations."""

    def __init__(
        self,
        session: AsyncSession,
        min_evidence_credibility: float = 0.5,
    ):
        self.session = session
        self.engine = VerificationEngine(
            session=session,
            min_evidence_credibility=min_evidence_credibility,
        )

    async def _ensure_sources(self) -> None:
        """Ensure evidence sources are registered."""
        from app.engine.evidence.sources import register_builtin_sources
        register_builtin_sources(self.session)

    async def verify_decision(
        self,
        decision_id: UUID,
        source_ids: Optional[List[str]] = None,
    ) -> VerificationResponse:
        """Verify a single decision by ID."""
        await self._ensure_sources()

        # Load decision with relations
        stmt = (
            select(Decision)
            .where(Decision.id == decision_id)
            .join(AgentExecution, Decision.agent_execution_id == AgentExecution.id, isouter=True)
        )
        result = await self.session.execute(stmt)
        decision = result.scalars().first()

        if not decision:
            from app.core.exceptions import NotFoundError
            raise NotFoundError(f"Decision {decision_id} not found")

        record = DecisionRecord(
            decision_id=decision.id,
            experiment_id=decision.experiment_id,
            agent_execution_id=decision.agent_execution_id,
            agent_name=decision.agent_execution.agent_name if decision.agent_execution else "unknown",
            decision_type=decision.decision_type,
            rationale=decision.rationale,
            confidence=decision.confidence,
            payload=decision.payload,
            created_at=decision.created_at,
        )

        engine_response = await self.engine.verify_decision(record, source_ids)
        return self._engine_to_response(engine_response)

    async def verify_experiment(
        self,
        experiment_id: UUID,
        agent_name: Optional[str] = None,
    ) -> VerificationResponse:
        """Verify all decisions for an experiment."""
        await self._ensure_sources()

        engine_response = await self.engine.verify_experiment_decisions(
            experiment_id=experiment_id,
            agent_name=agent_name,
        )
        return self._engine_to_response(engine_response)

    async def search_evidence(
        self,
        request: EvidenceSearchRequest,
    ) -> EvidenceSearchResponse:
        """Search across evidence sources."""
        await self._ensure_sources()

        sources = list_evidence_sources()
        if request.source_ids:
            sources = [s for s in sources if s.source_id in request.source_ids]

        all_pieces = []
        for source in sources:
            try:
                result = await source.search(
                    query=request.query,
                    limit=request.limit,
                )
                all_pieces.extend(result.pieces)
            except Exception as e:
                # Log but continue
                pass

        # Sort by credibility
        all_pieces.sort(key=lambda p: p.credibility_score, reverse=True)

        return EvidenceSearchResponse(
            query=request.query,
            pieces=[
                EvidencePieceResponse(
                    content=p.content,
                    source_id=p.source_id,
                    source_type=p.source_type,
                    title=p.title,
                    url=p.url,
                    snippet=p.snippet,
                    credibility_score=p.credibility_score,
                    metadata=p.metadata,
                    retrieved_at=p.retrieved_at,
                )
                for p in all_pieces[:request.limit]
            ],
            total_found=len(all_pieces),
            search_metadata={"sources_searched": [s.source_id for s in sources]},
        )

    async def list_evidence_sources(self) -> List[EvidenceSourceInfo]:
        """List all registered evidence sources."""
        await self._ensure_sources()
        sources = list_evidence_sources()

        infos = []
        for source in sources:
            meta = source.get_metadata()
            infos.append(
                EvidenceSourceInfo(
                    source_id=meta.source_id,
                    source_type=meta.source_type,
                    credibility_score=meta.credibility_score,
                    last_updated=meta.last_updated,
                )
            )
        return infos

    def _engine_to_response(self, engine_response) -> VerificationResponse:
        """Convert engine response to API response."""
        from app.schemas.verification import VerificationResultResponse

        return VerificationResponse(
            results=[
                VerificationResultResponse(
                    claim_id=r.claim_id,
                    claim_text=r.claim_text,
                    claim_type=r.claim_type,
                    status=r.status,
                    confidence_score=r.confidence_score,
                    supporting_evidence=[
                        EvidencePieceResponse(
                            content=p.content,
                            source_id=p.source_id,
                            source_type=p.source_type,
                            title=p.title,
                            url=p.url,
                            snippet=p.snippet,
                            credibility_score=p.credibility_score,
                            metadata=p.metadata,
                            retrieved_at=p.retrieved_at,
                        )
                        for p in r.supporting_evidence
                    ],
                    contradicting_evidence=[
                        EvidencePieceResponse(
                            content=p.content,
                            source_id=p.source_id,
                            source_type=p.source_type,
                            title=p.title,
                            url=p.url,
                            snippet=p.snippet,
                            credibility_score=p.credibility_score,
                            metadata=p.metadata,
                            retrieved_at=p.retrieved_at,
                        )
                        for p in r.contradicting_evidence
                    ],
                    reasoning=r.reasoning,
                    verified_at=r.verified_at,
                )
                for r in engine_response.results
            ],
            overall_status=engine_response.overall_status,
            overall_confidence=engine_response.overall_confidence,
            total_claims=engine_response.total_claims,
            verified_count=engine_response.verified_count,
            conflict_count=engine_response.conflict_count,
            rejected_count=engine_response.rejected_count,
            unverified_count=engine_response.unverified_count,
        )