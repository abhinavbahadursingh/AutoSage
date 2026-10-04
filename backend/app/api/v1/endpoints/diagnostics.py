"""Runtime diagnostics endpoint (Phase 20+).

Surfaces worker/broker, Docker sandbox, MLflow, LLM provider, and the last
experiment execution mode. Never raises on unreachable dependencies — every
probe is bounded and reports its own error.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.core.config import settings
from app.core import runtime as _runtime
from app.engine.llm.config import TIER_FAST, TIER_REASONING, resolve_model

router = APIRouter()


@router.get("/diagnostics", summary="Runtime diagnostics")
async def diagnostics() -> Dict[str, Any]:
    # Celery worker
    worker: Dict[str, Any] = dict(_runtime.embedded_worker)
    worker["broker_url"] = settings.celery_broker_url
    worker["result_backend"] = settings.celery_result_backend
    worker["always_eager"] = settings.CELERY_TASK_ALWAYS_EAGER

    # Docker sandbox
    docker_status: Dict[str, Any] = {"available": False, "error": "not probed"}
    try:
        from app.engine.sandbox.manager import get_sandbox_manager

        available, err = get_sandbox_manager().is_available()
        docker_status = {"available": available, "error": err}
    except Exception as exc:  # noqa: BLE001
        docker_status = {"available": False, "error": str(exc)}

    # MLflow
    mlflow_status: Dict[str, Any] = {"available": False, "error": "not probed"}
    try:
        from app.engine.mlflow.client import mlflow_status as _mlflow_status

        mlflow_status = _mlflow_status()
    except Exception as exc:  # noqa: BLE001
        mlflow_status = {
            "available": False,
            "tracking_uri": settings.MLFLOW_TRACKING_URI,
            "error": str(exc),
        }

    # LLM providers / models
    llm: Dict[str, Any] = {"providers_configured": [], "models": {}}
    try:
        from app.engine.llm.client import get_llm_client

        client = get_llm_client()
        llm["providers_configured"] = sorted(
            name for name, p in client.providers.items() if p.is_configured()
        )
        llm["has_providers"] = client.has_providers()
        llm["models"] = {
            "fast": resolve_model(model_tier=TIER_FAST),
            "reasoning": resolve_model(model_tier=TIER_REASONING),
        }
    except Exception as exc:  # noqa: BLE001
        llm["error"] = str(exc)

    return {
        "worker": worker,
        "sandbox": docker_status,
        "mlflow": mlflow_status,
        "llm": llm,
        "last_execution": _runtime.last_execution,
    }
