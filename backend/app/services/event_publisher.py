"""Event publishing service (Phase 15).

Central hub for publishing experiment execution events to WebSocket clients.
All components (workers, agents, MLflow, Evidence, Memory) use this interface.

Design:
- Async, non-blocking publish (fire-and-forget)
- Structured event schemas (see app.schemas.websocket)
- Integrates with ConnectionManager for broadcast
- Safe to call from sync code (Celery tasks) via run_coro_sync
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from uuid import UUID

from app.schemas.websocket import (
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    ExperimentCompleted,
    ExperimentEvent,
    ExperimentFailed,
    ExperimentStarted,
    MLCompleted,
    MLStarted,
    VerificationCompleted,
    VerificationStarted,
)
from app.services.websocket_manager import get_connection_manager

logger = logging.getLogger("autosage.events")


class EventPublisher:
    """Publishes experiment events to subscribed WebSocket clients."""

    def __init__(self) -> None:
        self._manager = get_connection_manager()

    # ---- Core publish ----

    async def publish(self, experiment_id: UUID, event: ExperimentEvent) -> int:
        """Publish an event to all connections for an experiment.

        Returns number of connections that received the event.
        Never raises — failures are logged only.
        """
        try:
            sent = await self._manager.broadcast(experiment_id, event)
            return sent
        except Exception as exc:
            logger.warning(
                "event_publish_failed",
                extra={
                    "experiment_id": str(experiment_id),
                    "event_type": event.event_type,
                    "error": str(exc),
                },
            )
            return 0

    def publish_sync(self, experiment_id: UUID, event: ExperimentEvent) -> int:
        """Sync wrapper for Celery/tasks — runs async publish in a helper thread.

        Safe to call from synchronous Celery task code.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.publish(experiment_id, event))

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, self.publish(experiment_id, event))
            return future.result()

    # ---- Experiment lifecycle ----

    async def experiment_started(
        self,
        experiment_id: UUID,
        experiment_name: str,
        workspace_id: UUID,
        config: Optional[Dict[str, Any]] = None,
    ) -> int:
        event = ExperimentStarted(
            experiment_id=experiment_id,
            payload={
                "experiment_name": experiment_name,
                "workspace_id": workspace_id,
                "config": config or {},
            },
        )
        return await self.publish(experiment_id, event)

    async def experiment_completed(
        self,
        experiment_id: UUID,
        result_summary: Optional[Dict[str, Any]] = None,
        mlflow_run_id: Optional[str] = None,
        ml_run_id: Optional[str] = None,
    ) -> int:
        event = ExperimentCompleted(
            experiment_id=experiment_id,
            payload={
                "result_summary": result_summary,
                "mlflow_run_id": mlflow_run_id,
                "ml_run_id": ml_run_id,
            },
        )
        return await self.publish(experiment_id, event)

    async def experiment_failed(
        self,
        experiment_id: UUID,
        error_detail: str,
        retry_count: int = 0,
        max_retries: int = 0,
        will_retry: bool = False,
    ) -> int:
        event = ExperimentFailed(
            experiment_id=experiment_id,
            payload={
                "error_detail": error_detail,
                "retry_count": retry_count,
                "max_retries": max_retries,
                "will_retry": will_retry,
            },
        )
        return await self.publish(experiment_id, event)

    # ---- Agent lifecycle ----

    async def agent_started(
        self,
        experiment_id: UUID,
        agent_name: str,
        stage: str,
        attempt: int = 0,
    ) -> int:
        event = AgentStarted(
            experiment_id=experiment_id,
            payload={"agent_name": agent_name, "stage": stage, "attempt": attempt},
        )
        return await self.publish(experiment_id, event)

    async def agent_completed(
        self,
        experiment_id: UUID,
        agent_name: str,
        stage: str,
        output_summary: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> int:
        event = AgentCompleted(
            experiment_id=experiment_id,
            payload={
                "agent_name": agent_name,
                "stage": stage,
                "output_summary": output_summary or {},
                "duration_ms": duration_ms,
            },
        )
        return await self.publish(experiment_id, event)

    async def agent_failed(
        self,
        experiment_id: UUID,
        agent_name: str,
        stage: str,
        error: str,
        error_type: Optional[str] = None,
        will_retry: bool = False,
    ) -> int:
        event = AgentFailed(
            experiment_id=experiment_id,
            payload={
                "agent_name": agent_name,
                "stage": stage,
                "error": error,
                "error_type": error_type,
                "will_retry": will_retry,
            },
        )
        return await self.publish(experiment_id, event)

    # ---- Verification ----

    async def verification_started(
        self,
        experiment_id: UUID,
        attempt: int,
        max_attempts: int,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> int:
        event = VerificationStarted(
            experiment_id=experiment_id,
            payload={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "metrics": metrics or {},
            },
        )
        return await self.publish(experiment_id, event)

    async def verification_completed(
        self,
        experiment_id: UUID,
        attempt: int,
        max_attempts: int,
        passed: bool,
        metrics: Optional[Dict[str, Any]] = None,
        gate_decision: str = "complete",
    ) -> int:
        event = VerificationCompleted(
            experiment_id=experiment_id,
            payload={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "passed": passed,
                "metrics": metrics or {},
                "gate_decision": gate_decision,
            },
        )
        return await self.publish(experiment_id, event)

    # ---- ML Training ----

    async def ml_started(
        self,
        experiment_id: UUID,
        model_family: str,
        model_params: Optional[Dict[str, Any]] = None,
        mlflow_run_id: Optional[str] = None,
        ml_run_id: Optional[str] = None,
    ) -> int:
        event = MLStarted(
            experiment_id=experiment_id,
            payload={
                "model_family": model_family,
                "model_params": model_params or {},
                "mlflow_run_id": mlflow_run_id,
                "ml_run_id": ml_run_id,
            },
        )
        return await self.publish(experiment_id, event)

    async def ml_completed(
        self,
        experiment_id: UUID,
        success: bool,
        metrics: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        mlflow_run_id: Optional[str] = None,
        ml_run_id: Optional[str] = None,
    ) -> int:
        event = MLCompleted(
            experiment_id=experiment_id,
            payload={
                "success": success,
                "metrics": metrics or {},
                "error": error,
                "mlflow_run_id": mlflow_run_id,
                "ml_run_id": ml_run_id,
            },
        )
        return await self.publish(experiment_id, event)


# Global instance
_publisher: Optional[EventPublisher] = None


def get_event_publisher() -> EventPublisher:
    """Get the global event publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher


# Convenience sync functions for Celery tasks
def publish_experiment_started(
    experiment_id: UUID,
    experiment_name: str,
    workspace_id: UUID,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        ExperimentStarted(
            experiment_id=experiment_id,
            payload={
                "experiment_name": experiment_name,
                "workspace_id": workspace_id,
                "config": config or {},
            },
        ),
    )


def publish_experiment_completed(
    experiment_id: UUID,
    result_summary: Optional[Dict[str, Any]] = None,
    mlflow_run_id: Optional[str] = None,
    ml_run_id: Optional[str] = None,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        ExperimentCompleted(
            experiment_id=experiment_id,
            payload={
                "result_summary": result_summary,
                "mlflow_run_id": mlflow_run_id,
                "ml_run_id": ml_run_id,
            },
        ),
    )


def publish_experiment_failed(
    experiment_id: UUID,
    error_detail: str,
    retry_count: int = 0,
    max_retries: int = 0,
    will_retry: bool = False,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        ExperimentFailed(
            experiment_id=experiment_id,
            payload={
                "error_detail": error_detail,
                "retry_count": retry_count,
                "max_retries": max_retries,
                "will_retry": will_retry,
            },
        ),
    )


def publish_agent_started(
    experiment_id: UUID,
    agent_name: str,
    stage: str,
    attempt: int = 0,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        AgentStarted(
            experiment_id=experiment_id,
            payload={"agent_name": agent_name, "stage": stage, "attempt": attempt},
        ),
    )


def publish_agent_completed(
    experiment_id: UUID,
    agent_name: str,
    stage: str,
    output_summary: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        AgentCompleted(
            experiment_id=experiment_id,
            payload={
                "agent_name": agent_name,
                "stage": stage,
                "output_summary": output_summary or {},
                "duration_ms": duration_ms,
            },
        ),
    )


def publish_agent_failed(
    experiment_id: UUID,
    agent_name: str,
    stage: str,
    error: str,
    error_type: Optional[str] = None,
    will_retry: bool = False,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        AgentFailed(
            experiment_id=experiment_id,
            payload={
                "agent_name": agent_name,
                "stage": stage,
                "error": error,
                "error_type": error_type,
                "will_retry": will_retry,
            },
        ),
    )


def publish_verification_started(
    experiment_id: UUID,
    attempt: int,
    max_attempts: int,
    metrics: Optional[Dict[str, Any]] = None,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        VerificationStarted(
            experiment_id=experiment_id,
            payload={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "metrics": metrics or {},
            },
        ),
    )


def publish_verification_completed(
    experiment_id: UUID,
    attempt: int,
    max_attempts: int,
    passed: bool,
    metrics: Optional[Dict[str, Any]] = None,
    gate_decision: str = "complete",
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        VerificationCompleted(
            experiment_id=experiment_id,
            payload={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "passed": passed,
                "metrics": metrics or {},
                "gate_decision": gate_decision,
            },
        ),
    )


def publish_ml_started(
    experiment_id: UUID,
    model_family: str,
    model_params: Optional[Dict[str, Any]] = None,
    mlflow_run_id: Optional[str] = None,
    ml_run_id: Optional[str] = None,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        MLStarted(
            experiment_id=experiment_id,
            payload={
                "model_family": model_family,
                "model_params": model_params or {},
                "mlflow_run_id": mlflow_run_id,
                "ml_run_id": ml_run_id,
            },
        ),
    )


def publish_ml_completed(
    experiment_id: UUID,
    success: bool,
    metrics: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    mlflow_run_id: Optional[str] = None,
    ml_run_id: Optional[str] = None,
) -> int:
    return get_event_publisher().publish_sync(
        experiment_id,
        MLCompleted(
            experiment_id=experiment_id,
            payload={
                "success": success,
                "metrics": metrics or {},
                "error": error,
                "mlflow_run_id": mlflow_run_id,
                "ml_run_id": ml_run_id,
            },
        ),
    )