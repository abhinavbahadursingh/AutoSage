"""Pydantic schemas for reproducibility records (Phase 17)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReproducibilityRecordBase(BaseModel):
    """Base schema with common fields."""

    model_config = ConfigDict(extra="forbid")

    # Dataset fingerprint
    dataset_sha256: str = Field(min_length=64, max_length=64)
    dataset_size_bytes: Optional[int] = Field(default=None, ge=0)
    dataset_rows: Optional[int] = Field(default=None, ge=0)
    dataset_columns: Optional[int] = Field(default=None, ge=0)
    dataset_schema: Optional[Dict[str, Any]] = None

    # Code / version information
    code_version: Optional[str] = Field(default=None, max_length=255)
    code_repository: Optional[str] = Field(default=None, max_length=500)
    code_branch: Optional[str] = Field(default=None, max_length=255)
    code_dirty: Optional[str] = Field(default=None, pattern="^(true|false)$")

    # Dependency versions
    python_version: str = Field(min_length=1, max_length=50)
    platform: Optional[str] = Field(default=None, max_length=100)
    pip_freeze: Optional[Dict[str, str]] = None
    conda_env: Optional[Dict[str, Any]] = None

    # Model & experiment configuration
    model_family: str = Field(min_length=1, max_length=100)
    model_name: Optional[str] = Field(default=None, max_length=255)
    model_params: Dict[str, Any] = Field(default_factory=dict)
    experiment_config: Dict[str, Any] = Field(default_factory=dict)
    random_seed: Optional[int] = Field(default=None, ge=0)

    # MLflow linkage
    mlflow_run_id: Optional[str] = Field(default=None, max_length=255)
    mlflow_experiment_id: Optional[str] = Field(default=None, max_length=255)
    mlflow_experiment_name: Optional[str] = Field(default=None, max_length=255)

    # Runtime environment
    runtime_type: Optional[str] = Field(default=None, max_length=50)
    docker_image: Optional[str] = Field(default=None, max_length=500)
    docker_image_id: Optional[str] = Field(default=None, max_length=255)
    container_id: Optional[str] = Field(default=None, max_length=255)
    hardware_info: Optional[Dict[str, Any]] = None

    # Artifact references
    artifact_uris: Optional[Dict[str, str]] = None
    model_artifact_uri: Optional[str] = Field(default=None, max_length=500)
    log_artifact_uri: Optional[str] = Field(default=None, max_length=500)

    # Metrics snapshot
    final_metrics: Optional[Dict[str, Any]] = None


class ReproducibilityRecordCreate(ReproducibilityRecordBase):
    """Schema for creating a reproducibility record."""

    experiment_id: UUID
    ml_run_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None


class ReproducibilityRecordRead(ReproducibilityRecordBase):
    """Schema for reading a reproducibility record."""

    id: UUID
    experiment_id: UUID
    ml_run_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReproducibilityRecordListResponse(BaseModel):
    """Paginated list of reproducibility records."""

    items: List[ReproducibilityRecordRead]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)