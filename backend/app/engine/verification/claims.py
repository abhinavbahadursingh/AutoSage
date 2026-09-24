"""Claim Extraction Models (Phase 12).

Claims are verifiable assertions extracted from agent decisions. Each claim
can be independently verified against evidence sources.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.engine.evidence.source import EvidencePiece, EvidenceSearchResult


class ClaimType(str, Enum):
    """Types of claims that can be extracted from agent decisions."""
    METRIC_PERFORMANCE = "metric_performance"      # "Model achieves 0.95 accuracy"
    DATA_QUALITY = "data_quality"                  # "Dataset has no missing values"
    METHOD_VALIDITY = "method_validity"            # "Target encoding prevents leakage"
    BASELINE_COMPARISON = "baseline_comparison"    # "Model beats random baseline by 15%"
    FEASIBILITY = "feasibility"                    # "Training completes in < 5 min"
    SAFETY = "safety"                              # "No PII in features"
    BEST_PRACTICE = "best_practice"                # "Stratified CV used for imbalanced data"


class ClaimStatus(str, Enum):
    """Verification status of a claim."""
    VERIFIED = "VERIFIED"          # Evidence supports the claim
    CONFLICT = "CONFLICT"          # Evidence contradicts the claim
    REJECTED = "REJECTED"          # Claim is false/impossible
    UNVERIFIED = "UNVERIFIED"      # Insufficient evidence either way


@dataclass
class ExtractedClaim:
    """A claim extracted from an agent decision, ready for verification."""
    claim_id: UUID
    claim_type: ClaimType
    text: str                          # Human-readable claim
    structured: Dict[str, Any]         # Structured representation for matching
    source_agent: str                  # Agent that made the claim
    source_decision_id: UUID           # Decision this claim came from
    confidence: float = 1.0            # Agent's confidence in the claim
    context: Dict[str, Any] = None     # Additional context from the decision


class ClaimExtractor(ABC):
    """Abstract claim extractor for different decision types."""

    @property
    @abstractmethod
    def supported_decision_types(self) -> List[str]:
        """Decision types this extractor handles."""
        ...

    @abstractmethod
    def extract(self, decision: "DecisionRecord") -> List[ExtractedClaim]:
        """Extract verifiable claims from a decision record."""
        ...


class DecisionRecord(BaseModel):
    """Decision record passed to claim extractors."""
    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    experiment_id: UUID
    agent_execution_id: Optional[UUID]
    agent_name: str
    decision_type: str
    rationale: str
    confidence: Optional[float]
    payload: Dict[str, Any]
    created_at: datetime


class VerificationResult(BaseModel):
    """Result of verifying a single claim."""
    model_config = ConfigDict(extra="forbid")

    claim_id: UUID
    claim_text: str
    claim_type: ClaimType
    status: ClaimStatus
    confidence_score: float = 0.0              # 0.0 - 1.0
    supporting_evidence: List[EvidencePiece] = []
    contradicting_evidence: List[EvidencePiece] = []
    reasoning: str = ""
    verified_at: datetime
    engine_version: str = "1.0"


class ClaimVerificationRequest(BaseModel):
    """Request to verify a set of claims."""
    model_config = ConfigDict(extra="forbid")

    claims: List[ExtractedClaim]
    sources: Optional[List[str]] = None  # Source IDs to use (None = all)
    min_credibility: float = 0.5


class ClaimVerificationResponse(BaseModel):
    """Response from the verification engine."""
    model_config = ConfigDict(extra="forbid")

    results: List[VerificationResult]
    overall_status: ClaimStatus
    overall_confidence: float
    total_claims: int
    verified_count: int
    conflict_count: int
    rejected_count: int
    unverified_count: int