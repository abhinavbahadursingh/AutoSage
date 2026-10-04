"""Verification Service (Phase 12).

Service layer for verification operations: decision verification,
experiment verification, evidence search, and source management.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.evidence.source import (
    EvidenceSource,
    get_evidence_source,
    list_evidence_sources,
    register_evidence_source,
)
from app.engine.evidence.sources import register_builtin_sources
from app.engine.metrics import score_from_metrics
from app.engine.verification.claims import ClaimStatus
from app.engine.verification.engine import VerificationEngine
from app.engine.verification.extractors import DecisionRecord
from app.engine.verification.gate_checks import failed_checks, run_static_gate_checks
from app.models.decision import Decision
from app.models.agent_execution import AgentExecution
from app.models.verification import Verification
from app.schemas.verification import (
    EvidencePieceResponse,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    EvidenceSourceInfo,
    StaticCheckResponse,
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
            .options(selectinload(Decision.agent_execution))
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

        # Store per-decision verification results in the Verification model
        from app.models.decision import Decision
        from sqlalchemy.orm import selectinload

        stmt = (
            select(Decision)
            .where(Decision.experiment_id == experiment_id)
            .options(selectinload(Decision.agent_execution))
        )
        if agent_name:
            from app.models.agent_execution import AgentExecution
            stmt = stmt.join(AgentExecution).where(AgentExecution.agent_name == agent_name)

        result = await self.session.execute(stmt)
        decisions = result.scalars().all()

        # Build per-decision status map from engine results
        # The engine processes all claims from all decisions; we map back by
        # tracking which claims came from which decision (via extract_all_claims)
        decision_statuses: Dict[str, Dict[str, Any]] = {}
        claim_idx = 0

        for d in decisions:
            from app.engine.verification.extractors import extract_all_claims as _ea

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
            claims = _ea(record)

            # Collect this decision's claim statuses from engine results
            decision_claim_statuses = []
            for _c in claims:
                if claim_idx < len(engine_response.results):
                    r = engine_response.results[claim_idx]
                    decision_claim_statuses.append(
                        {
                            "claim_id": str(r.claim_id),
                            "status": r.status,
                            "confidence": r.confidence_score,
                            "reasoning": r.reasoning,
                        }
                    )
                    claim_idx += 1
                else:
                    break

            # Determine decision-level status (majority, with abstain priority)
            if decision_claim_statuses:
                statuses = [s["status"] for s in decision_claim_statuses]
                from collections import Counter

                majority = Counter(statuses).most_common(1)[0][0] if statuses else "UNVERIFIED"

                # Abstention rule: if any claim abstained, decision abstains
                if "ABSTAIN" in statuses:
                    majority = "ABSTAIN"
                # Conflict rule: if any claim conflicted and no verified, conflict
                elif "CONFLICT" in statuses and "VERIFIED" not in statuses:
                    majority = "CONFLICT"
                # Rejected rule: if any claim rejected and no verified, rejected
                elif "REJECTED" in statuses and "VERIFIED" not in statuses:
                    majority = "REJECTED"
                # No verified means unverified/abstain
                elif not any(s == "VERIFIED" for s in statuses):
                    majority = "ABSTAIN" if "ABSTAIN" in statuses else "UNVERIFIED"

                decision_statuses[str(d.id)] = {
                    "status": majority,
                    "confidence": sum(
                        s.get("confidence", 0) for s in decision_claim_statuses
                    )
                    / max(len(decision_claim_statuses), 1),
                    "reasoning": f"{len(decision_claim_statuses)} claims → {majority}",
                    "claim_details": decision_claim_statuses,
                }
            else:
                decision_statuses[str(d.id)] = {
                    "status": "UNVERIFIED",
                    "confidence": 0.0,
                    "reasoning": "No claims extracted",
                    "claim_details": [],
                }

        # Load the experiment: the static gate reads the measured result from
        # its result summary, and the outcome is written back to it.
        from app.models.experiment import Experiment

        exp_stmt = select(Experiment).where(Experiment.id == experiment_id)
        exp_result = await self.session.execute(exp_stmt)
        experiment = exp_result.scalars().first()
        if experiment is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(f"Experiment {experiment_id} not found")

        prior_summary = dict(experiment.result_summary or {})
        ml_result = dict(prior_summary.get("ml_result") or {})
        metrics = dict(prior_summary.get("metrics") or ml_result.get("metrics") or {})
        primary_metric = str(
            prior_summary.get("primary_metric") or ml_result.get("primary_metric") or ""
        )
        baseline = dict(prior_summary.get("baseline") or ml_result.get("baseline") or {})
        baseline_score = baseline.get("score")
        if baseline_score is None:
            baseline_score = score_from_metrics(baseline.get("metrics"), primary_metric)
        primary_score = prior_summary.get("primary_score")
        if primary_score is None:
            primary_score = ml_result.get("primary_score")

        # Static gate: AST/security, data leakage, metric sanity and baseline
        # dominance over the measured result. Any failed check rejects the run
        # regardless of what the claim/evidence pass found.
        static_checks = run_static_gate_checks(
            metrics=metrics,
            task_type=str(
                dict(prior_summary.get("profile") or {}).get("task_type")
                or (experiment.config or {}).get("task_type")
                or "classification"
            ),
            primary_metric=primary_metric,
            primary_score=primary_score,
            baseline_score=baseline_score,
        )
        static_failures = failed_checks(static_checks)
        final_status = (
            ClaimStatus.REJECTED if static_failures else engine_response.overall_status
        )

        # Update or create verification record
        stmt = select(Verification).where(Verification.experiment_id == experiment_id)
        ver_result = await self.session.execute(stmt)
        verification = ver_result.scalars().first()

        if not verification:
            verification = Verification(
                experiment_id=experiment_id,
                check_name="experiment_gate",
                overall_status=final_status,
                overall_confidence=engine_response.overall_confidence,
                decisions=decision_statuses,
            )
            self.session.add(verification)
        else:
            verification.check_name = "experiment_gate"
            verification.overall_status = final_status
            verification.overall_confidence = engine_response.overall_confidence
            verification.decisions = decision_statuses
            verification.updated_at = datetime.utcnow()

        # Update experiment result summary and status based on decision statuses
        dec_statuses_list = list(decision_statuses.values())

        has_verified = any(d.get("status") == "VERIFIED" for d in dec_statuses_list)
        has_abstained = any(d.get("status") == "ABSTAIN" for d in dec_statuses_list)
        has_conflict = any(d.get("status") == "CONFLICT" for d in dec_statuses_list)
        has_rejected = any(d.get("status") == "REJECTED" for d in dec_statuses_list)

        if static_failures:
            # The static gate is authoritative: a failed check means the run
            # cannot be verified, whatever the evidence pass concluded.
            experiment_status = "FAILED"
            experiment_summary = {
                "overall_status": "REJECTED",
                "overall_confidence": engine_response.overall_confidence,
                "static_check_failures": [c["name"] for c in static_failures],
            }
        elif has_verified and not has_abstained and not has_conflict and not has_rejected:
            experiment_status = "COMPLETED"
            experiment_summary = {
                "overall_status": "VERIFIED",
                "overall_confidence": engine_response.overall_confidence,
                "verified_decisions": sum(
                    1 for d in dec_statuses_list if d.get("status") == "VERIFIED"
                ),
            }
        elif has_abstained:
            experiment_status = "RETRYING"
            experiment_summary = {
                "overall_status": "ABSTAIN",
                "overall_confidence": engine_response.overall_confidence,
                "abstained_decisions": sum(
                    1 for d in dec_statuses_list if d.get("status") == "ABSTAIN"
                ),
            }
        elif has_conflict:
            experiment_status = "FAILED"
            experiment_summary = {
                "overall_status": "CONFLICT",
                "overall_confidence": engine_response.overall_confidence,
            }
        elif has_rejected:
            experiment_status = "FAILED"
            experiment_summary = {
                "overall_status": "REJECTED",
                "overall_confidence": engine_response.overall_confidence,
            }
        else:
            experiment_status = "FAILED"
            experiment_summary = {
                "overall_status": "UNVERIFIED",
                "overall_confidence": engine_response.overall_confidence,
            }

        # Update experiment. The run's own result summary is preserved -- the
        # gate only records its outcome alongside it.
        experiment.status = experiment_status
        experiment.result_summary = {
            **prior_summary,
            **experiment_summary,
            "static_checks": static_checks,
        }
        await self.session.commit()

        return self._engine_to_response(
            engine_response,
            static_checks=static_checks,
            overall_status=final_status,
        )

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

    def _engine_to_response(
        self,
        engine_response,
        *,
        static_checks: Optional[List[Dict[str, Any]]] = None,
        overall_status: Optional[ClaimStatus] = None,
    ) -> VerificationResponse:
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
            overall_status=overall_status or engine_response.overall_status,
            overall_confidence=engine_response.overall_confidence,
            total_claims=engine_response.total_claims,
            verified_count=engine_response.verified_count,
            conflict_count=engine_response.conflict_count,
            rejected_count=engine_response.rejected_count,
            unverified_count=engine_response.unverified_count,
            static_checks=[
                StaticCheckResponse(
                    name=c["name"],
                    passed=bool(c["passed"]),
                    skipped=bool(c.get("skipped")),
                    details=list(c.get("details") or []),
                    artifact=str(c.get("artifact") or ""),
                )
                for c in (static_checks or [])
            ],
        )