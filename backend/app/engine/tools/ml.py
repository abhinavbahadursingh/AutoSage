"""ML job submission tool (Phase 10).

Accepts a job spec and executes training in the Docker sandbox.
Returns structured results with metrics and artifacts.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.engine.tools.base import BaseTool
from app.engine.sandbox.manager import get_sandbox_manager, ExecutionResult
from app.engine.sandbox.train_script import main as train_main


class ExecuteMLJobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_family: str = Field(min_length=1, max_length=128)
    dataset_name: str = Field(min_length=1, max_length=512)
    metric: str = Field(default="accuracy", min_length=1, max_length=64)
    attempt: int = Field(default=1, ge=1, le=100)
    params: Dict[str, Any] = Field(default_factory=dict)
    experiment_id: Optional[str] = Field(default=None, max_length=64)
    target_column: Optional[str] = Field(default=None, max_length=128)
    task_type: Optional[str] = Field(default=None, max_length=32)
    dataset_path: Optional[str] = Field(default=None, max_length=1024)


class ExecuteMLJobTool(BaseTool):
    name = "execute_ml_job"
    description = "Execute an ML training job in the Docker sandbox."
    input_model = ExecuteMLJobInput

    def _build_training_script(self, params: ExecuteMLJobInput) -> str:
        """Generate the training script with embedded parameters."""
        # The training script reads from environment variables,
        # so we just need to return the script path.
        # The sandbox manager will copy train_script.py and set env vars.
        return "train_script.py"

    def run(self, params: BaseModel) -> Dict[str, Any]:
        assert isinstance(params, ExecuteMLJobInput)

        job_id = (
            f"job-{(params.experiment_id or 'local')[:8]}-"
            f"{params.model_family[:16]}-a{params.attempt}"
        )

        # Build environment variables for the training script
        env_vars = {
            "MODEL_FAMILY": params.model_family,
            "METRIC": params.metric,
            "DATASET_NAME": params.dataset_name,
            "MODEL_PARAMS": json.dumps(params.params),
            "TARGET_COLUMN": params.target_column or "target",
            "TASK_TYPE": params.task_type or "classification",
        }

        # Get sandbox manager and execute
        sandbox = get_sandbox_manager()

        # For now, run synchronously (async not needed in tool context)
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            result: ExecutionResult = loop.run_until_complete(
                sandbox.execute_job(
                    job_id=job_id,
                    script="",  # Script is pre-built in image
                    dataset_path=params.dataset_path,
                    env_vars=env_vars,
                )
            )
        finally:
            loop.close()

        # Convert ExecutionResult to dict for ToolResult
        output = result.to_dict()
        output["note"] = "Phase 10: executed in Docker sandbox"
        return output


# Backwards-compatible stub for testing without Docker
class ExecuteMLJobStubTool(BaseTool):
    """Fallback stub tool when Docker is unavailable."""

    name = "execute_ml_job_stub"
    description = "Stub ML job execution (no sandbox)."
    input_model = ExecuteMLJobInput

    def run(self, params: BaseModel) -> Dict[str, Any]:
        assert isinstance(params, ExecuteMLJobInput)
        job_id = (
            f"job-{(params.experiment_id or 'local')[:8]}-"
            f"{params.model_family[:16]}-a{params.attempt}"
        )
        return {
            "success": True,
            "job_id": job_id,
            "status": "accepted",
            "model_family": params.model_family,
            "dataset_name": params.dataset_name,
            "metric": params.metric,
            "attempt": params.attempt,
            "params": dict(params.params),
            "metrics": {"accuracy": 0.87},
            "artifacts": ["model.joblib"],
            "note": "Stub mode: Docker sandbox not available",
        }