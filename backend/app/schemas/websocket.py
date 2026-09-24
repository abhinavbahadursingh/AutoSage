"""WebSocket event schemas (Phase 15).

Stable event interface for real-time experiment execution updates.
Future components (Evidence, Memory, MLflow, Frontend) publish/consume via EventPublisher.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EventBase(BaseModel):
    """Base event envelope — all events share these fields."""

    event_type: str = Field(..., description="Event type, e.g. 'experiment.started'")
    experiment_id: UUID = Field(..., description="Experiment this event belongs to")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")


# ---- Experiment lifecycle events ----

class ExperimentStartedPayload(BaseModel):
    experiment_name: str
    workspace_id: UUID
    config: Dict[str, Any] = Field(default_factory=dict)


class ExperimentStarted(EventBase):
    event_type: Literal["experiment.started"] = "experiment.started"
    payload: ExperimentStartedPayload


class ExperimentCompletedPayload(BaseModel):
    result_summary: Optional[Dict[str, Any]] = None
    mlflow_run_id: Optional[str] = None
    ml_run_id: Optional[str] = None


class ExperimentCompleted(EventBase):
    event_type: Literal["experiment.completed"] = "experiment.completed"
    payload: ExperimentCompletedPayload


class ExperimentFailedPayload(BaseModel):
    error_detail: str
    retry_count: int = 0
    max_retries: int = 0
    will_retry: bool = False


class ExperimentFailed(EventBase):
    event_type: Literal["experiment.failed"] = "experiment.failed"
    payload: ExperimentFailedPayload


# ---- Agent lifecycle events ----

class AgentStartedPayload(BaseModel):
    agent_name: str
    stage: str
    attempt: int = 0


class AgentStarted(EventBase):
    event_type: Literal["agent.started"] = "agent.started"
    payload: AgentStartedPayload


class AgentCompletedPayload(BaseModel):
    agent_name: str
    stage: str
    output_summary: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[int] = None


class AgentCompleted(EventBase):
    event_type: Literal["agent.completed"] = "agent.completed"
    payload: AgentCompletedPayload


class AgentFailedPayload(BaseModel):
    agent_name: str
    stage: str
    error: str
    error_type: Optional[str] = None
    will_retry: bool = False


class AgentFailed(EventBase):
    event_type: Literal["agent.failed"] = "agent.failed"
    payload: AgentFailedPayload


# ---- Verification events ----

class VerificationStartedPayload(BaseModel):
    attempt: int
    max_attempts: int
    metrics: Dict[str, Any] = Field(default_factory=dict)


class VerificationStarted(EventBase):
    event_type: Literal["verification.started"] = "verification.started"
    payload: VerificationStartedPayload


class VerificationCompletedPayload(BaseModel):
    attempt: int
    max_attempts: int
    passed: bool
    metrics: Dict[str, Any] = Field(default_factory=dict)
    gate_decision: Literal["complete", "retry", "fail"]


class VerificationCompleted(EventBase):
    event_type: Literal["verification.completed"] = "verification.completed"
    payload: VerificationCompletedPayload


# ---- ML training events ----

class MLStartedPayload(BaseModel):
    model_family: str
    model_params: Dict[str, Any] = Field(default_factory=dict)
    mlflow_run_id: Optional[str] = None
    ml_run_id: Optional[str] = None


class MLStarted(EventBase):
    event_type: Literal["ml.started"] = "ml.started"
    payload: MLStartedPayload


class MLCompletedPayload(BaseModel):
    success: bool
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    mlflow_run_id: Optional[str] = None
    ml_run_id: Optional[str] = None


class MLCompleted(EventBase):
    event_type: Literal["ml.completed"] = "ml.completed"
    payload: MLCompletedPayload


# ---- Union of all event types for type-safe handling ----

ExperimentEvent = (
    ExperimentStarted
    | ExperimentCompleted
    | ExperimentFailed
    | AgentStarted
    | AgentCompleted
    | AgentFailed
    | VerificationStarted
    | VerificationCompleted
    | MLStarted
    | MLCompleted
)


# ---- Client message (subscribe/unsubscribe) ----

class ClientMessage(BaseModel):
    """Messages from client to server."""

    type: Literal["subscribe", "unsubscribe", "ping"]
    experiment_id: Optional[UUID] = None


class ServerMessage(BaseModel):
    """Messages from server to client."""

    type: Literal["event", "ack", "error", "pong"]
    event: Optional[EventBase] = None
    message: Optional[str] = None
    request_id: Optional[str] = None