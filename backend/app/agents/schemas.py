"""Structured Pydantic outputs for every AutoSage agent (Phase 7).

Agents return these models (never free-form dicts). LangGraph nodes then
``.model_dump()`` them into the workflow state slots that Phase 6 defined.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentOutput(BaseModel):
    """Base for all agent outputs (JSON-safe, extra fields forbidden)."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        default="llm",
        description="Where this output came from: 'llm' or 'heuristic'",
    )


class DatasetDiscoveryOutput(AgentOutput):
    """Dataset Discovery Agent — locate + describe the experiment dataset."""

    dataset_name: str
    rows: int = Field(ge=0)
    columns: List[str] = Field(default_factory=list)
    target_column: Optional[str] = None
    source_type: str = "upload"
    task_hint: Optional[Literal["classification", "regression", "unknown"]] = None


class ProfileOutput(AgentOutput):
    """Profiler Agent — statistical / semantic profile of the dataset."""

    task_type: Literal["classification", "regression", "unknown"] = "unknown"
    target_column: str = "target"
    n_rows: int = Field(ge=0, default=0)
    n_features: int = Field(ge=0, default=0)
    missing_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    class_balance: Optional[Dict[str, float]] = None
    feature_types: Dict[str, str] = Field(default_factory=dict)
    summary: str = ""


class PreprocessingSpecOutput(AgentOutput):
    """Preprocessor Agent — concrete cleaning / feature pipeline spec."""

    imputation: str = "median"
    encoding: str = "one-hot"
    scaling: str = "standard"
    outlier_handling: str = "iqr"
    feature_engineering: List[str] = Field(default_factory=list)
    drop_columns: List[str] = Field(default_factory=list)
    rationale: str = ""


class ModelSpecOutput(AgentOutput):
    """Model Selector Agent — model family + hyperparameter proposal."""

    family: str = "gradient_boosting"
    params: Dict[str, object] = Field(default_factory=dict)
    candidates: List[str] = Field(default_factory=list)
    rationale: str = ""


class MLExperimentOutput(AgentOutput):
    """ML Experiment Agent — plan + (later) record of one training attempt."""

    metric: str = "accuracy"
    value: float = Field(ge=0.0, le=1.0, default=0.0)
    validation_strategy: str = "holdout"
    notes: str = ""
    attempt: int = Field(ge=1, default=1)


class VerificationOutput(AgentOutput):
    """Verification Agent — empirical gate decision + check list."""

    checks: List[str] = Field(default_factory=list)
    passed: bool = False
    failures: List[str] = Field(default_factory=list)
    summary: str = ""
    attempt: int = Field(ge=0, default=0)


class OrchestrationPlanOutput(AgentOutput):
    """Optional orchestrator planning payload (kept minimal in Phase 7)."""

    plan: List[str] = Field(default_factory=list)
    notes: str = ""
