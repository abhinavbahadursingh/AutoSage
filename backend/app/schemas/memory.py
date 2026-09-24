from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    VERIFIED_CLAIM = "verified_claim"
    SUCCESSFUL_EXPERIMENT = "successful_experiment"
    FAILED_EXPERIMENT = "failed_experiment"
    DATASET_INSIGHT = "dataset_insight"
    MODEL_SELECTION_EXPERIENCE = "model_selection_experience"
    PREPROCESSING_EXPERIENCE = "preprocessing_experience"
    AGENT_DECISION = "agent_decision"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    PENDING_VERIFICATION = "pending_verification"


class MemorySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    memory_type: MemoryType
    task_type: str
    solution_strategy: str
    achieved_metric_value: Optional[float] = None
    metric_name: Optional[str] = None
    similarity_score: float
    ranking_score: Optional[float] = None
    rank_factors: Optional[Dict[str, float]] = None
    created_at: Optional[datetime] = None


class MemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    workspace_id: UUID
    experiment_id: Optional[UUID] = None
    source_run_id: Optional[UUID] = None
    memory_type: MemoryType
    status: MemoryStatus
    task_type: str
    dataset_fingerprint: Dict[str, Any]
    solution_strategy: str
    achieved_metric_value: Optional[float] = None
    metric_name: Optional[str] = None
    memory_metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding_model: Optional[str] = None
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None


class StoreMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    experiment_id: Optional[UUID] = None
    memory_type: MemoryType
    task_type: str
    dataset_fingerprint: Dict[str, Any]
    solution_strategy: str
    achieved_metric_value: Optional[float] = None
    metric_name: Optional[str] = None
    memory_metadata: Optional[Dict[str, Any]] = None
    success: bool = True


class MemoryStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    active: int
    archived: int
    deprecated: int
    by_type: Dict[str, int]
