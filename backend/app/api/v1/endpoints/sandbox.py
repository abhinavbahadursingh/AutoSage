"""Sandbox execution endpoint (Phase 10+).

Provides direct API access to the Docker sandbox for ML job execution.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.config import settings
from app.engine.sandbox.manager import ExecutionResult, SandboxError, get_sandbox_manager
from app.models.user import User

router = APIRouter()


class SandboxExecuteRequest(BaseModel):
    """Request to execute a script in the sandbox."""
    script: str = Field(..., description="Python training script to execute")
    dataset_path: Optional[str] = Field(None, description="Optional path to dataset CSV")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    mlflow_run_id: Optional[str] = Field(None, description="Optional MLflow run ID")


class SandboxExecuteResponse(BaseModel):
    """Response from sandbox execution."""
    success: bool
    job_id: str
    metrics: Dict[str, Any] = {}
    artifacts: list[str] = []
    stdout: str = ""
    stderr: str = ""
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_sec: float = 0.0
    exit_code: Optional[int] = None


@router.post("/execute", response_model=SandboxExecuteResponse, summary="Execute script in Docker sandbox")
async def execute_sandbox_job(
    request: SandboxExecuteRequest,
    current_user: User = Depends(get_current_user),
) -> SandboxExecuteResponse:
    """Execute a Python training script in the isolated Docker sandbox.

    The sandbox provides:
    - CPU/memory limits
    - Execution timeout
    - Read-only filesystem (except /workspace)
    - No network access
    - Non-root user execution
    - Capability dropping
    - PIDs limit
    - Automatic cleanup
    """
    if not settings.SANDBOX_ENABLED:
        raise HTTPException(status_code=503, detail="Sandbox execution is disabled")

    sandbox = get_sandbox_manager()

    # Check availability
    available, err = sandbox.is_available()
    if not available:
        raise HTTPException(status_code=503, detail=f"Docker sandbox unavailable: {err}")

    # Generate job ID
    import uuid
    job_id = f"sandbox-{uuid.uuid4().hex[:12]}"

    try:
        result: ExecutionResult = await sandbox.execute_job(
            job_id=job_id,
            script=request.script,
            dataset_path=request.dataset_path,
            env_vars=request.env_vars,
            mlflow_run_id=request.mlflow_run_id,
        )

        return SandboxExecuteResponse(**result.to_dict())

    except SandboxError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Sandbox execution failed: {e}")


@router.get("/status", summary="Get sandbox status")
async def sandbox_status(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Get Docker sandbox availability and configuration."""
    sandbox = get_sandbox_manager()
    available, err = sandbox.is_available()

    return {
        "available": available,
        "error": err,
        "config": {
            "image_tag": sandbox.image_tag,
            "cpu_limit": sandbox.cpu_limit,
            "memory_limit": sandbox.memory_limit,
            "timeout_sec": sandbox.timeout_sec,
            "workspace_size": sandbox.workspace_size,
            "pids_limit": sandbox.pids_limit,
            "readonly_rootfs": sandbox.readonly_rootfs,
        },
    }