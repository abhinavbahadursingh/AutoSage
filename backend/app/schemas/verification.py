"""Verification Schemas (Phase 12).

Pydantic models for verification API requests/responses.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.engine.verification.claims import ClaimStatus, ClaimType


class EvidencePieceResponse(BaseModel):
    """Evidence piece in API response."""
    model_config = ConfigDict(from_attributes=True)

    content: str
    source_id: str
    source_type: str
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    credibility_score: float
    metadata: Dict[str, Any] = {}
    retrieved_at: datetime


class VerificationResultResponse(BaseModel):
    """Single claim verification result."""
    model_config = ConfigDict(from_attributes=True)

    claim_id: UUID
    claim_text: str
    claim_type: ClaimType
    status: ClaimStatus
    confidence_score: float
    supporting_evidence: List[EvidencePieceResponse] = []
    contradicting_evidence: List[EvidencePieceResponse] = []
    reasoning: str
    verified_at: datetime


class ClaimExtractionResponse(BaseModel):
    """Claim extracted from a decision."""
    model_config = ConfigDict(from_attributes=True)

    claim_id: UUID
    claim_type: ClaimType
    text: str
    structured: Dict[str, Any]
    source_agent: str
    source_decision_id: UUID
    confidence: float
    context: Dict[str, Any] = {}


class VerifyDecisionRequest(BaseModel):
    """Request to verify a specific decision."""
    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    source_ids: Optional[List[str]] = None


class VerifyExperimentRequest(BaseModel):
    """Request to verify all decisions in an experiment."""
    model_config = ConfigDict(extra="forbid")

    experiment_id: UUID
    agent_name: Optional[str] = None


class VerificationResponse(BaseModel):
    """Full verification response."""
    model_config = ConfigDict(from_attributes=True)

    results: List[VerificationResultResponse]
    overall_status: ClaimStatus
    overall_confidence: float
    total_claims: int
    verified_count: int
    conflict_count: int
    rejected_count: int
    unverified_count: int


class EvidenceSourceInfo(BaseModel):
    """Evidence source information for API."""
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    source_type: str
    credibility_score: float
    last_updated: Optional[datetime] = None


class EvidenceSearchRequest(BaseModel):
    """Request to search evidence sources."""
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    source_ids: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=50)


class EvidenceSearchResponse(BaseModel):
    """Evidence search results."""
    model_config = ConfigDict(from_attributes=True)

    query: str
    pieces: List[EvidencePieceResponse]
    total_found: int
    search_metadata: Dict[str, Any] = {}