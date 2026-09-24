"""Verification API Endpoints (Phase 12).

REST endpoints for verification operations.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.services.verification_service import VerificationService
from app.schemas.verification import (
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    EvidenceSourceInfo,
    VerificationResponse,
    VerifyDecisionRequest,
    VerifyExperimentRequest,
)

router = APIRouter(prefix="/verification", tags=["Verification"])


@router.post(
    "/decision",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a specific agent decision",
)
async def verify_decision(
    payload: VerifyDecisionRequest,
    user: CurrentUser,
    session: DbSession,
) -> VerificationResponse:
    """Extract claims from a decision and verify against evidence sources."""
    service = VerificationService(session)
    return await service.verify_decision(
        decision_id=payload.decision_id,
        source_ids=payload.source_ids,
    )


@router.post(
    "/experiment",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify all decisions in an experiment",
)
async def verify_experiment(
    payload: VerifyExperimentRequest,
    user: CurrentUser,
    session: DbSession,
) -> VerificationResponse:
    """Verify all decisions for an experiment (optionally filtered by agent)."""
    service = VerificationService(session)
    return await service.verify_experiment(
        experiment_id=payload.experiment_id,
        agent_name=payload.agent_name,
    )


@router.post(
    "/evidence/search",
    response_model=EvidenceSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search evidence sources",
)
async def search_evidence(
    payload: EvidenceSearchRequest,
    user: CurrentUser,
    session: DbSession,
) -> EvidenceSearchResponse:
    """Search across registered evidence sources."""
    service = VerificationService(session)
    return await service.search_evidence(payload)


@router.get(
    "/sources",
    response_model=List[EvidenceSourceInfo],
    status_code=status.HTTP_200_OK,
    summary="List registered evidence sources",
)
async def list_evidence_sources(
    user: CurrentUser,
    session: DbSession,
) -> List[EvidenceSourceInfo]:
    """List all registered evidence sources with metadata."""
    service = VerificationService(session)
    return await service.list_evidence_sources()