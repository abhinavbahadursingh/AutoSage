"""Pydantic schemas for experiments (Phase 4 API)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.experiment import ExperimentStatus
from app.schemas.pagination import PagedResponse


# Allowed model families for validation
ALLOWED_MODEL_FAMILIES = {
    "linear_regression",
    "logistic_regression",
    "random_forest",
    "gradient_boosting",
    "xgboost",
    "lightgbm",
    "catboost",
    "decision_tree",
    "svm",
    "knn",
    "naive_bayes",
    "mlp",
}

# Allowed metrics
ALLOWED_METRICS = {
    "accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
    "log_loss",
    "mse",
    "mae",
    "rmse",
    "r2",
}

# Allowed task types
ALLOWED_TASK_TYPES = {"classification", "regression"}


def validate_model_family(v: str) -> str:
    if v not in ALLOWED_MODEL_FAMILIES:
        raise ValueError(f"Invalid model_family: {v}. Allowed: {sorted(ALLOWED_MODEL_FAMILIES)}")
    return v


def validate_metric(v: str) -> str:
    if v not in ALLOWED_METRICS:
        raise ValueError(f"Invalid metric: {v}. Allowed: {sorted(ALLOWED_METRICS)}")
    return v


def validate_task_type(v: str) -> str:
    """Accept canonical values and common UI display forms.

    The formulation form sends labels like ``"Binary Classification"``;
    workers/train scripts need the canonical ``classification``/``regression``.
    """
    s = str(v).strip().lower()
    if s in ALLOWED_TASK_TYPES:
        return s
    if "regression" in s:
        return "regression"
    if "classif" in s:
        return "classification"
    raise ValueError(f"Invalid task_type: {v}. Allowed: {sorted(ALLOWED_TASK_TYPES)}")


def _validate_config(v: Dict[str, Any]) -> Dict[str, Any]:
    """Validate experiment config for allowed keys/values."""
    if not isinstance(v, dict):
        return v

    if "model_family" in v:
        v["model_family"] = validate_model_family(str(v["model_family"]))
    if "metric" in v:
        v["metric"] = validate_metric(str(v["metric"]))
    if "task_type" in v:
        v["task_type"] = validate_task_type(str(v["task_type"]))

    # Reject unknown config keys to prevent injection
    allowed_keys = {
        "model_family", "metric", "task_type", "model_params",
        "dataset_path", "dataset_name", "target_column",
        "model_name", "random_seed", "random_state",
        "mock_fail_stage",
        # Frontend formulation form (experiment intent/context)
        "prompt", "dataset", "evaluation_metric", "split_strategy",
        "imbalance_handling", "source",
    }
    for key in v:
        if key not in allowed_keys:
            raise ValueError(f"Unknown config key: {key}. Allowed: {sorted(allowed_keys)}")

    # Mirror the UI "dataset" filename to the key workers read.
    if "dataset" in v and v.get("dataset") and "dataset_name" not in v:
        v["dataset_name"] = v["dataset"]

    if "model_params" in v and not isinstance(v["model_params"], dict):
        raise ValueError("model_params must be a dictionary")

    return v


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    workspace_id: UUID
    config: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = Field(default=3, ge=0, le=10)

    @field_validator("config", mode="before")
    @classmethod
    def validate_config(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        return _validate_config(v)

    model_config = ConfigDict(extra="forbid")


class ExperimentUpdate(BaseModel):
    """Mutable fields only — ``status`` transitions go through start/cancel."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)

    @field_validator("config", mode="before")
    @classmethod
    def validate_config(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return v
        return _validate_config(v)

    model_config = ConfigDict(extra="forbid")


class ExperimentRead(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: Optional[str] = None
    status: ExperimentStatus
    config: Dict[str, Any] = Field(default_factory=dict)
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    error_detail: Optional[str] = None
    retry_count: int
    max_retries: int
    celery_task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperimentListResponse(PagedResponse[ExperimentRead]):
    """Paginated experiment list."""

    items: List[ExperimentRead]
