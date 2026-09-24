"""Verification Engine (Phase 12).

Core orchestration: Agent Decision -> Claim Extraction -> Evidence Retrieval
-> Verification Engine -> Verification Result -> Evidence Trail

This engine is independent and modular - new evidence sources, extractors,
and verification rules can be plugged in without changing the core.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.evidence.source import (
    EvidencePiece,
    EvidenceSearchResult,
    EvidenceSource,
    get_evidence_source,
    list_evidence_sources,
    register_evidence_source,
)
from app.engine.evidence.sources import register_builtin_sources
from app.engine.verification.claims import (
    ClaimStatus,
    ClaimType,
    ClaimVerificationRequest,
    ClaimVerificationResponse,
    ExtractedClaim,
    VerificationResult,
)
from app.engine.verification.extractors import (
    DecisionRecord,
    extract_all_claims,
)

logger = logging.getLogger("autosage.verification")


class VerificationEngine:
    """Main verification engine coordinating the full pipeline."""

    def __init__(
        self,
        session: AsyncSession,
        min_evidence_credibility: float = 0.5,
        min_supporting_pieces: int = 1,
        conflict_threshold: float = 0.7,
    ):
        self.session = session
        self.min_evidence_credibility = min_evidence_credibility
        self.min_supporting_pieces = min_supporting_pieces
        self.conflict_threshold = conflict_threshold
        self._sources_initialized = False

    async def _ensure_sources(self) -> None:
        """Initialize evidence sources if not already done."""
        if not self._sources_initialized:
            register_builtin_sources(self.session)
            self._sources_initialized = True

    async def _search_evidence(
        self,
        query: str,
        source_ids: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[EvidencePiece]:
        """Search all or specified evidence sources."""
        await self._ensure_sources()

        sources = list_evidence_sources()
        if source_ids:
            sources = [s for s in sources if s.source_id in source_ids]

        all_pieces: List[EvidencePiece] = []
        for source in sources:
            try:
                result: EvidenceSearchResult = await source.search(query, limit=limit)
                # Filter by credibility
                filtered = [
                    p for p in result.pieces
                    if p.credibility_score >= self.min_evidence_credibility
                ]
                all_pieces.extend(filtered)
            except Exception as e:
                logger.warning(
                    "evidence_source_search_failed",
                    extra={"source": source.source_id, "error": str(e)},
                )

        # Sort by credibility score descending
        all_pieces.sort(key=lambda p: p.credibility_score, reverse=True)
        return all_pieces

    def _match_claim_to_evidence(
        self,
        claim: ExtractedClaim,
        evidence: List[EvidencePiece],
    ) -> Tuple[List[EvidencePiece], List[EvidencePiece]]:
        """Match claim against evidence pieces to find supporting/contradicting.

        Uses simple keyword matching for Phase 12. Phase 13+ will use
        semantic similarity via embeddings.
        """
        supporting = []
        contradicting = []

        # Extract key terms from claim
        claim_text = claim.text.lower()
        structured = claim.structured

        for piece in evidence:
            piece_text = (piece.content + " " + (piece.snippet or "")).lower()
            piece_cred = piece.credibility_score

            # Skip low credibility evidence
            if piece_cred < self.min_evidence_credibility:
                continue

            # Match based on claim type
            is_supporting = False
            is_contradicting = False

            if claim.claim_type == ClaimType.METRIC_PERFORMANCE:
                metric = structured.get("metric", "").lower()
                value = structured.get("value")
                if metric and metric in piece_text:
                    if value is not None:
                        # Check if evidence mentions similar values
                        if str(value) in piece_text or f"{value:.2f}" in piece_text:
                            is_supporting = True
                        elif "impossible" in piece_text or "suspicious" in piece_text:
                            is_contradicting = True
                    else:
                        is_supporting = True

            elif claim.claim_type == ClaimType.DATA_QUALITY:
                check = structured.get("check", "").lower()
                if check and check in piece_text:
                    is_supporting = True

            elif claim.claim_type == ClaimType.METHOD_VALIDITY:
                method = structured.get("method", "").lower()
                if method and method in piece_text:
                    is_supporting = True

            elif claim.claim_type == ClaimType.SAFETY:
                check = structured.get("check", "").lower()
                if check and check in piece_text:
                    if "passed" in piece_text or "no " + check in piece_text:
                        is_supporting = True
                    elif "failed" in piece_text or "detected" in piece_text:
                        is_contradicting = True

            elif claim.claim_type == ClaimType.BASELINE_COMPARISON:
                if "baseline" in piece_text and ("beat" in piece_text or "improv" in piece_text):
                    is_supporting = True

            else:
                # Generic keyword overlap
                claim_words = set(claim_text.split())
                piece_words = set(piece_text.split())
                overlap = len(claim_words & piece_words) / max(len(claim_words), 1)
                if overlap > 0.3:
                    is_supporting = True

            if is_supporting:
                supporting.append(piece)
            elif is_contradicting:
                contradicting.append(piece)

        return supporting, contradicting

    def _determine_status(
        self,
        claim: ExtractedClaim,
        supporting: List[EvidencePiece],
        contradicting: List[EvidencePiece],
    ) -> Tuple[ClaimStatus, float, str]:
        """Determine verification status from evidence."""
        n_support = len(supporting)
        n_contra = len(contradicting)

        if n_contra > 0:
            # Has contradicting evidence
            max_contra_cred = max(p.credibility_score for p in contradicting)
            if max_contra_cred >= self.conflict_threshold:
                return (
                    ClaimStatus.CONFLICT,
                    max_contra_cred,
                    f"Found {n_contra} contradicting evidence piece(s) with high credibility"
                )
            return (
                ClaimStatus.CONFLICT,
                max_contra_cred * 0.5,
                f"Found {n_contra} contradicting evidence piece(s)"
            )

        if n_support >= self.min_supporting_pieces:
            # Has enough supporting evidence
            avg_cred = sum(p.credibility_score for p in supporting) / n_support
            return (
                ClaimStatus.VERIFIED,
                avg_cred,
                f"Supported by {n_support} evidence piece(s)"
            )

        if n_support > 0:
            # Some support but not enough
            avg_cred = sum(p.credibility_score for p in supporting) / n_support
            return (
                ClaimStatus.UNVERIFIED,
                avg_cred * 0.5,
                f"Only {n_support} supporting evidence piece(s), need {self.min_supporting_pieces}"
            )

        # No evidence found
        return (
            ClaimStatus.UNVERIFIED,
            0.0,
            "No relevant evidence found"
        )

    async def verify_claims(
        self,
        request: ClaimVerificationRequest,
    ) -> ClaimVerificationResponse:
        """Verify a batch of claims."""
        results = []

        for claim in request.claims:
            # Build search query from claim
            query = claim.text
            if claim.structured.get("metric"):
                query = f"{claim.structured['metric']} {claim.structured.get('value', '')}"
            elif claim.structured.get("method"):
                query = claim.structured["method"]

            # Search evidence
            evidence = await self._search_evidence(
                query=query,
                source_ids=request.sources,
            )

            # Match claim to evidence
            supporting, contradicting = self._match_claim_to_evidence(claim, evidence)

            # Determine status
            status, confidence, reasoning = self._determine_status(
                claim, supporting, contradicting
            )

            result = VerificationResult(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                claim_type=claim.claim_type,
                status=status,
                confidence_score=confidence,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                reasoning=reasoning,
                verified_at=datetime.utcnow(),
            )
            results.append(result)

        # Compute overall stats
        total = len(results)
        verified = sum(1 for r in results if r.status == ClaimStatus.VERIFIED)
        conflict = sum(1 for r in results if r.status == ClaimStatus.CONFLICT)
        rejected = sum(1 for r in results if r.status == ClaimStatus.REJECTED)
        unverified = sum(1 for r in results if r.status == ClaimStatus.UNVERIFIED)

        if conflict > 0:
            overall = ClaimStatus.CONFLICT
        elif rejected > 0:
            overall = ClaimStatus.REJECTED
        elif verified == total and total > 0:
            overall = ClaimStatus.VERIFIED
        else:
            overall = ClaimStatus.UNVERIFIED

        overall_conf = sum(r.confidence_score for r in results) / max(total, 1)

        return ClaimVerificationResponse(
            results=results,
            overall_status=overall,
            overall_confidence=overall_conf,
            total_claims=total,
            verified_count=verified,
            conflict_count=conflict,
            rejected_count=rejected,
            unverified_count=unverified,
        )

    async def verify_decision(
        self,
        decision: DecisionRecord,
        source_ids: Optional[List[str]] = None,
    ) -> ClaimVerificationResponse:
        """Extract claims from a decision and verify them."""
        claims = extract_all_claims(decision)
        if not claims:
            return ClaimVerificationResponse(
                results=[],
                overall_status=ClaimStatus.UNVERIFIED,
                overall_confidence=0.0,
                total_claims=0,
                verified_count=0,
                conflict_count=0,
                rejected_count=0,
                unverified_count=0,
            )

        request = ClaimVerificationRequest(
            claims=claims,
            sources=source_ids,
            min_credibility=self.min_evidence_credibility,
        )
        return await self.verify_claims(request)

    async def verify_experiment_decisions(
        self,
        experiment_id: UUID,
        agent_name: Optional[str] = None,
    ) -> ClaimVerificationResponse:
        """Verify all decisions for an experiment (or specific agent)."""
        from sqlalchemy import select
        from app.models.decision import Decision

        stmt = select(Decision).where(Decision.experiment_id == experiment_id)
        if agent_name:
            from app.models.agent_execution import AgentExecution
            stmt = stmt.join(AgentExecution).where(AgentExecution.agent_name == agent_name)

        result = await self.session.execute(stmt)
        decisions = result.scalars().all()

        all_claims = []
        for d in decisions:
            record = DecisionRecord(
                decision_id=d.id,
                experiment_id=d.experiment_id,
                agent_execution_id=d.agent_execution_id,
                agent_name=d.agent_execution.agent_name if d.agent_execution else "unknown",
                decision_type=d.decision_type,
                rationale=d.rationale,
                confidence=d.confidence,
                payload=d.payload,
                created_at=d.created_at,
            )
            all_claims.extend(extract_all_claims(record))

        if not all_claims:
            return ClaimVerificationResponse(
                results=[],
                overall_status=ClaimStatus.UNVERIFIED,
                overall_confidence=0.0,
                total_claims=0,
                verified_count=0,
                conflict_count=0,
                rejected_count=0,
                unverified_count=0,
            )

        request = ClaimVerificationRequest(
            claims=all_claims,
            sources=None,
            min_credibility=self.min_evidence_credibility,
        )
        return await self.verify_claims(request)