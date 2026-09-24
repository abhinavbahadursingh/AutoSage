"""Built-in Claim Extractors (Phase 12).

Extract verifiable claims from agent decisions based on decision type.
Each extractor handles specific decision patterns.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.engine.verification.claims import (
    ClaimExtractor,
    ClaimType,
    DecisionRecord,
    ExtractedClaim,
)


class MetricClaimExtractor(ClaimExtractor):
    """Extract metric performance claims from experimenter/model_selector decisions."""

    supported_decision_types = ["model_selection", "training_complete", "hyperparameter_tuning"]

    # Patterns to find metric claims
    METRIC_PATTERNS = [
        (r"(\w+(?:_\w+)?)\s*(?:of|is|=|:)\s*([0-9]*\.?[0-9]+)", "metric_value"),
        (r"(accuracy|f1|precision|recall|roc_auc|r2|mse|rmse|mae)\s*(?:of|is|=|:)\s*([0-9]*\.?[0-9]+)", "named_metric"),
    ]

    def extract(self, decision: DecisionRecord) -> List[ExtractedClaim]:
        claims = []
        rationale = decision.rationale.lower()
        payload = decision.payload or {}

        # Extract from rationale text
        for pattern, _ in self.METRIC_PATTERNS:
            matches = re.finditer(pattern, rationale, re.IGNORECASE)
            for match in matches:
                metric_name = match.group(1).strip()
                value_str = match.group(2)
                try:
                    value = float(value_str)
                    claims.append(
                        ExtractedClaim(
                            claim_id=UUID(int=hash(f"{decision.decision_id}-{metric_name}-{value}") % (2**128)),
                            claim_type=ClaimType.METRIC_PERFORMANCE,
                            text=f"{metric_name} = {value}",
                            structured={
                                "metric": metric_name,
                                "value": value,
                                "operator": "=",
                            },
                            source_agent=decision.agent_name,
                            source_decision_id=decision.decision_id,
                            confidence=decision.confidence or 0.8,
                            context={"payload": payload},
                        )
                    )
                except ValueError:
                    continue

        # Extract from payload if structured
        if "metrics" in payload and isinstance(payload["metrics"], dict):
            for metric, value in payload["metrics"].items():
                if isinstance(value, (int, float)):
                    claims.append(
                        ExtractedClaim(
                            claim_id=UUID(int=hash(f"{decision.decision_id}-{metric}-{value}") % (2**128)),
                            claim_type=ClaimType.METRIC_PERFORMANCE,
                            text=f"{metric} = {value}",
                            structured={"metric": metric, "value": float(value)},
                            source_agent=decision.agent_name,
                            source_decision_id=decision.decision_id,
                            confidence=decision.confidence or 0.9,
                            context={"payload": payload},
                        )
                    )

        return claims


class DataQualityClaimExtractor(ClaimExtractor):
    """Extract data quality claims from discovery/profiler decisions."""

    supported_decision_types = ["data_discovery", "data_profiling", "data_validation"]

    def extract(self, decision: DecisionRecord) -> List[ExtractedClaim]:
        claims = []
        rationale = decision.rationale.lower()
        payload = decision.payload or {}

        # Missing values
        if "missing" in rationale or "null" in rationale:
            claims.append(
                ExtractedClaim(
                    claim_id=UUID(int=hash(f"{decision.decision_id}-missing") % (2**128)),
                    claim_type=ClaimType.DATA_QUALITY,
                    text="Dataset has missing values" if "missing" in rationale else "Dataset has null values",
                    structured={"check": "missing_values", "detected": True},
                    source_agent=decision.agent_name,
                    source_decision_id=decision.decision_id,
                    confidence=decision.confidence or 0.7,
                )
            )

        # Class imbalance
        if "imbalance" in rationale or "skew" in rationale:
            claims.append(
                ExtractedClaim(
                    claim_id=UUID(int=hash(f"{decision.decision_id}-imbalance") % (2**128)),
                    claim_type=ClaimType.DATA_QUALITY,
                    text="Dataset has class/target imbalance",
                    structured={"check": "class_imbalance", "detected": True},
                    source_agent=decision.agent_name,
                    source_decision_id=decision.decision_id,
                    confidence=decision.confidence or 0.8,
                )
            )

        # High cardinality
        if "cardinality" in rationale or "unique" in rationale:
            claims.append(
                ExtractedClaim(
                    claim_id=UUID(int=hash(f"{decision.decision_id}-cardinality") % (2**128)),
                    claim_type=ClaimType.DATA_QUALITY,
                    text="Features have high cardinality",
                    structured={"check": "high_cardinality", "detected": True},
                    source_agent=decision.agent_name,
                    source_decision_id=decision.decision_id,
                    confidence=decision.confidence or 0.7,
                )
            )

        # From payload
        if "missing_rate" in payload:
            claims.append(
                ExtractedClaim(
                    claim_id=UUID(int=hash(f"{decision.decision_id}-missing-rate") % (2**128)),
                    claim_type=ClaimType.DATA_QUALITY,
                    text=f"Missing rate: {payload['missing_rate']}",
                    structured={"check": "missing_rate", "value": payload["missing_rate"]},
                    source_agent=decision.agent_name,
                    source_decision_id=decision.decision_id,
                    confidence=0.9,
                )
            )

        return claims


class MethodValidityClaimExtractor(ClaimExtractor):
    """Extract method validity claims from preprocessor/model_selector decisions."""

    supported_decision_types = ["preprocessing", "feature_engineering", "model_selection", "encoding"]

    METHOD_KEYWORDS = {
        "target encoding": ("Target encoding used", ClaimType.METHOD_VALIDITY),
        "one-hot": ("One-hot encoding used", ClaimType.METHOD_VALIDITY),
        "label encoding": ("Label encoding used", ClaimType.METHOD_VALIDITY),
        "imputer": ("Imputation applied", ClaimType.METHOD_VALIDITY),
        "scaler": ("Feature scaling applied", ClaimType.METHOD_VALIDITY),
        "stratified": ("Stratified sampling used", ClaimType.METHOD_VALIDITY),
        "cross-validation": ("Cross-validation used", ClaimType.METHOD_VALIDITY),
        "pipeline": ("Pipeline constructed", ClaimType.METHOD_VALIDITY),
        "leakage": ("Leakage prevention mentioned", ClaimType.SAFETY),
    }

    def extract(self, decision: DecisionRecord) -> List[ExtractedClaim]:
        claims = []
        rationale = decision.rationale.lower()
        payload = decision.payload or {}

        for keyword, (text, ctype) in self.METHOD_KEYWORDS.items():
            if keyword in rationale:
                claims.append(
                    ExtractedClaim(
                        claim_id=UUID(int=hash(f"{decision.decision_id}-{keyword}") % (2**128)),
                        claim_type=ctype,
                        text=text,
                        structured={"method": keyword, "claimed": True},
                        source_agent=decision.agent_name,
                        source_decision_id=decision.decision_id,
                        confidence=decision.confidence or 0.8,
                    )
                )

        # From payload
        if "encoding" in payload:
            claims.append(
                ExtractedClaim(
                    claim_id=UUID(int=hash(f"{decision.decision_id}-encoding") % (2**128)),
                    claim_type=ClaimType.METHOD_VALIDITY,
                    text=f"Encoding method: {payload['encoding']}",
                    structured={"method": "encoding", "value": payload["encoding"]},
                    source_agent=decision.agent_name,
                    source_decision_id=decision.decision_id,
                    confidence=0.9,
                )
            )

        return claims


class BaselineComparisonExtractor(ClaimExtractor):
    """Extract baseline comparison claims from experimenter/verifier decisions."""

    supported_decision_types = ["baseline_comparison", "model_evaluation", "verification_gate"]

    def extract(self, decision: DecisionRecord) -> List[ExtractedClaim]:
        claims = []
        rationale = decision.rationale.lower()
        payload = decision.payload or {}

        # Look for baseline/improvement language
        improvement_patterns = [
            (r"beat[s]?\s+(?:the\s+)?baseline", "beats_baseline"),
            (r"outperform[s]?\s+(?:the\s+)?baseline", "outperforms_baseline"),
            (r"beat[s]?\s+(?:the\s+)?baseline\s+by\s+([0-9]*\.?[0-9]+)", "beats_baseline_by"),
            (r"outperform[s]?\s+(?:the\s+)?baseline\s+by\s+([0-9]*\.?[0-9]+)", "outperforms_baseline_by"),
            (r"improv(?:e|ement)\s+(?:of|by)\s+([0-9]*\.?[0-9]+)", "improvement_value"),
            (r"(?:over|above)\s+(?:the\s+)?baseline", "above_baseline"),
        ]

        for pattern, claim_subtype in improvement_patterns:
            match = re.search(pattern, rationale, re.IGNORECASE)
            if match:
                claims.append(
                    ExtractedClaim(
                        claim_id=UUID(int=hash(f"{decision.decision_id}-{claim_subtype}") % (2**128)),
                        claim_type=ClaimType.BASELINE_COMPARISON,
                        text=f"Model {claim_subtype.replace('_', ' ')}",
                        structured={
                            "comparison": "baseline",
                            "result": claim_subtype,
                            "value": float(match.group(1)) if match.groups() else None,
                        },
                        source_agent=decision.agent_name,
                        source_decision_id=decision.decision_id,
                        confidence=decision.confidence or 0.7,
                    )
                )

        return claims


class SafetyClaimExtractor(ClaimExtractor):
    """Extract safety/security claims from verification/preprocessor decisions."""

    supported_decision_types = ["ast_security", "leakage_check", "privacy_check", "verification_gate"]

    SAFETY_KEYWORDS = {
        "no eval": ("No eval() calls detected", ClaimType.SAFETY),
        "no exec": ("No exec() calls detected", ClaimType.SAFETY),
        "no import os": ("No os imports detected", ClaimType.SAFETY),
        "no subprocess": ("No subprocess calls detected", ClaimType.SAFETY),
        "no socket": ("No socket operations detected", ClaimType.SAFETY),
        "no requests": ("No external HTTP calls detected", ClaimType.SAFETY),
        "no leakage": ("No target leakage detected", ClaimType.SAFETY),
        "pii": ("PII check performed", ClaimType.SAFETY),
        "privacy": ("Privacy check performed", ClaimType.SAFETY),
    }

    def extract(self, decision: DecisionRecord) -> List[ExtractedClaim]:
        claims = []
        rationale = decision.rationale.lower()

        for keyword, (text, ctype) in self.SAFETY_KEYWORDS.items():
            if keyword in rationale:
                claims.append(
                    ExtractedClaim(
                        claim_id=UUID(int=hash(f"{decision.decision_id}-{keyword}") % (2**128)),
                        claim_type=ctype,
                        text=text,
                        structured={"check": keyword.replace(" ", "_"), "passed": True},
                        source_agent=decision.agent_name,
                        source_decision_id=decision.decision_id,
                        confidence=decision.confidence or 0.9,
                    )
                )

        # From payload
        if "checks" in payload and isinstance(payload["checks"], list):
            for check in payload["checks"]:
                if isinstance(check, str) and "pass" in check.lower():
                    claims.append(
                        ExtractedClaim(
                            claim_id=UUID(int=hash(f"{decision.decision_id}-check-{check}") % (2**128)),
                            claim_type=ClaimType.SAFETY,
                            text=f"Check passed: {check}",
                            structured={"check": check, "passed": True},
                            source_agent=decision.agent_name,
                            source_decision_id=decision.decision_id,
                            confidence=0.9,
                        )
                    )

        return claims


# Registry of all claim extractors
_CLAIM_EXTRACTORS: List[ClaimExtractor] = [
    MetricClaimExtractor(),
    DataQualityClaimExtractor(),
    MethodValidityClaimExtractor(),
    BaselineComparisonExtractor(),
    SafetyClaimExtractor(),
]


def get_extractors_for_decision(decision_type: str) -> List[ClaimExtractor]:
    """Get all claim extractors that support a given decision type."""
    return [e for e in _CLAIM_EXTRACTORS if decision_type in e.supported_decision_types]


def extract_all_claims(decision: DecisionRecord) -> List[ExtractedClaim]:
    """Extract all claims from a decision using all relevant extractors."""
    extractors = get_extractors_for_decision(decision.decision_type)
    all_claims = []
    for extractor in extractors:
        all_claims.extend(extractor.extract(decision))
    return all_claims