"""ML job submission tool (Phase 10).

Accepts a job spec and executes training in the Docker sandbox. When the
Docker daemon is unavailable the same training runs in-process, so a run still
produces *measured* metrics instead of a placeholder.

The requested objective travels with the job: ``primary_metric`` names the
metric to optimize and ``compare_models`` asks for a real model comparison.
Selection always happens on ``primary_metric`` -- accuracy is reported as a
secondary metric, never as the objective. ``metric`` is accepted as the legacy
alias of ``primary_metric``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine.sandbox.manager import get_sandbox_manager, ExecutionResult
from app.engine.sandbox.train_script import execute_locally
from app.engine.tools.base import BaseTool
from app.engine.tools.errors import ToolExecutionError


class ExecuteMLJobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_family: str = Field(min_length=1, max_length=128)
    dataset_name: str = Field(min_length=1, max_length=512)
    #: Metric the run must optimize. Carried verbatim to training + selection.
    primary_metric: str = Field(default="accuracy", min_length=1, max_length=64)
    #: When true, train/evaluate every candidate and select on primary_metric.
    compare_models: bool = False
    candidates: List[str] = Field(default_factory=list)
    attempt: int = Field(default=1, ge=1, le=100)
    params: Dict[str, Any] = Field(default_factory=dict)
    experiment_id: Optional[str] = Field(default=None, max_length=64)
    target_column: Optional[str] = Field(default=None, max_length=128)
    task_type: Optional[str] = Field(default=None, max_length=32)
    dataset_path: Optional[str] = Field(default=None, max_length=1024)
    test_size: float = Field(default=0.2, gt=0.0, lt=1.0)
    random_state: int = Field(default=42, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_metric(cls, data: Any) -> Any:
        """Let callers send ``metric`` instead of ``primary_metric``.

        An explicit ``primary_metric`` always wins; the legacy key is dropped
        either way so it never trips ``extra="forbid"``.
        """
        if isinstance(data, dict):
            legacy = data.pop("metric", None)
            if legacy is not None and not data.get("primary_metric"):
                data["primary_metric"] = legacy
        return data

    @property
    def families(self) -> List[str]:
        """Families to train: the comparison shortlist, else the single family."""
        ordered: List[str] = []
        for family in ([*self.candidates, self.model_family] if self.compare_models
                       else [self.model_family]):
            name = str(family).strip()
            if name and name not in ordered:
                ordered.append(name)
        return ordered or [self.model_family]


class DatasetNotFoundError(ToolExecutionError):
    """Raised when the dataset for a job cannot be located on disk."""


def _upload_dir() -> Path:
    from app.core.config import settings

    return Path(settings.UPLOAD_DIR)


def resolve_dataset_path(
    dataset_name: str,
    dataset_path: Optional[str] = None,
    experiment_id: Optional[str] = None,
) -> str:
    """Locate the dataset CSV for a job.

    Resolution order: explicit ``dataset_path`` -> local upload dir -> object
    storage (dataset row for this experiment, else any workspace match).
    Raises :class:`DatasetNotFoundError` rather than inventing a dataset.
    """
    if dataset_path:
        candidate = Path(dataset_path)
        if candidate.exists():
            return str(candidate)
        nested = _upload_dir() / dataset_path
        if nested.exists():
            return str(nested)

    local = _upload_dir() / dataset_name
    if local.exists():
        return str(local)

    stored = _download_from_storage(dataset_name, experiment_id)
    if stored:
        return stored

    raise DatasetNotFoundError(
        f"dataset not available for training: {dataset_name!r} "
        f"(looked in {_upload_dir()} and object storage)"
    )


def _download_from_storage(dataset_name: str, experiment_id: Optional[str]) -> Optional[str]:
    """Fetch the dataset bytes from object storage into the upload dir."""
    try:
        from sqlalchemy import select

        from app.db import session as _db_session
        from app.engine.storage.service import get_storage_service_instance
        from app.models.dataset import Dataset
    except Exception:  # pragma: no cover - optional dependency path
        return None

    async def _fetch() -> Optional[bytes]:
        _db_session.init_engine()
        async with _db_session.AsyncSessionLocal() as session:
            workspace_id = None
            if experiment_id:
                try:
                    from app.models.experiment import Experiment

                    exp = await session.get(Experiment, experiment_id)
                    workspace_id = exp.workspace_id if exp else None
                except Exception:  # noqa: BLE001 - scoping is best-effort
                    workspace_id = None

            def _query(scope: Any) -> Any:
                stmt = select(Dataset).where(Dataset.original_filename == dataset_name)
                if scope is not None:
                    stmt = stmt.where(Dataset.workspace_id == scope)
                return stmt

            row = (await session.execute(_query(workspace_id))).scalars().first()
            if row is None and workspace_id is not None:
                row = (await session.execute(_query(None))).scalars().first()
            if row is None:
                return None
            storage = get_storage_service_instance()
            content = await storage.download_file(row.storage_path)
            return content if isinstance(content, (bytes, bytearray)) else None

    from app.engine.llm.client import run_coro_sync

    try:
        content = run_coro_sync(_fetch())
    except Exception:  # noqa: BLE001 - storage is best-effort resolution
        return None
    if not content:
        return None

    target = _upload_dir() / dataset_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(bytes(content))
    return str(target)


class ExecuteMLJobTool(BaseTool):
    name = "execute_ml_job"
    description = (
        "Execute an ML training job (Docker sandbox, in-process fallback). "
        "Trains every candidate when compare_models is set and selects on "
        "primary_metric."
    )
    input_model = ExecuteMLJobInput

    def _build_training_script(self, params: ExecuteMLJobInput) -> str:
        """Return the self-contained training script for sandbox execution."""
        script_path = Path(__file__).resolve().parent.parent / "sandbox" / "train_script.py"
        return script_path.read_text(encoding="utf-8")

    def _env_vars(self, params: ExecuteMLJobInput) -> Dict[str, str]:
        """Environment for the containerised training script."""
        return {
            "MODEL_FAMILY": params.model_family,
            "METRIC": params.primary_metric,
            "PRIMARY_METRIC": params.primary_metric,
            "COMPARE_MODELS": "1" if params.compare_models else "0",
            "CANDIDATE_MODELS": json.dumps(params.families),
            "DATASET_NAME": params.dataset_name,
            "MODEL_PARAMS": json.dumps(params.params),
            "TARGET_COLUMN": params.target_column or "target",
            "TASK_TYPE": params.task_type or "classification",
            "TEST_SIZE": str(params.test_size),
            "RANDOM_STATE": str(params.random_state),
        }

    def run(self, params: BaseModel) -> Dict[str, Any]:
        assert isinstance(params, ExecuteMLJobInput)

        job_id = (
            f"job-{(params.experiment_id or 'local')[:8]}-"
            f"{params.model_family[:16]}-a{params.attempt}"
        )
        resolved = resolve_dataset_path(
            params.dataset_name, params.dataset_path, params.experiment_id
        )
        candidates = params.families
        task_type = params.task_type or "classification"

        sandbox = get_sandbox_manager()
        available, docker_err = sandbox.is_available()
        if available:
            output = self._run_in_sandbox(job_id, params, resolved, candidates)
            if output.get("success"):
                output["execution_backend"] = "docker_sandbox"
                return output
            # Fall through to in-process training so the run still measures.
            sandbox_error = output.get("error_message")
        else:
            sandbox_error = docker_err

        output = self._run_in_process(job_id, params, resolved, candidates, task_type)
        if sandbox_error:
            output["sandbox_error"] = sandbox_error
        output["execution_backend"] = "in_process"
        return output

    def _run_in_sandbox(
        self,
        job_id: str,
        params: ExecuteMLJobInput,
        dataset_path: str,
        candidates: List[str],
    ) -> Dict[str, Any]:
        """Execute the comparison inside the Docker sandbox."""
        from app.engine.llm.client import run_coro_sync

        sandbox = get_sandbox_manager()
        result: ExecutionResult = run_coro_sync(
            sandbox.execute_job(
                job_id=job_id,
                script=self._build_training_script(params),
                dataset_path=dataset_path,
                env_vars=self._env_vars(params),
            )
        )
        output = result.to_dict()
        metrics = dict(result.metrics or {})
        output["primary_metric"] = params.primary_metric
        output["selected_model"] = metrics.get("selected_model")
        output["primary_score"] = metrics.get("primary_score")
        output["metrics"] = metrics.get("metrics") or {}
        output["model_comparison"] = metrics.get("model_comparison") or []
        output["baseline"] = metrics.get("baseline") or {}
        output["models_evaluated"] = metrics.get("models_evaluated", 0)
        output["candidates"] = candidates
        return output

    def _run_in_process(
        self,
        job_id: str,
        params: ExecuteMLJobInput,
        dataset_path: str,
        candidates: List[str],
        task_type: str,
    ) -> Dict[str, Any]:
        """Train in the API/worker process (no Docker available)."""
        try:
            result = execute_locally(
                dataset_path=dataset_path,
                target_column=params.target_column or "target",
                task_type=task_type,
                candidates=candidates,
                primary_metric=params.primary_metric,
                params=params.params,
                artifact_dir=str(_upload_dir() / "artifacts" / job_id),
                test_size=params.test_size,
                random_state=params.random_state,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a failed tool result
            raise ToolExecutionError(
                f"training failed for {job_id}: {type(exc).__name__}: {exc}"
            ) from exc

        return {
            "success": bool(result.get("selected_model")),
            "job_id": job_id,
            "status": "completed" if result.get("selected_model") else "no_model_selected",
            "dataset_path": dataset_path,
            "dataset_name": params.dataset_name,
            "model_family": params.model_family,
            "candidates": candidates,
            "primary_metric": result.get("primary_metric", params.primary_metric),
            "primary_score": result.get("primary_score"),
            "metrics": result.get("metrics") or {},
            "model_comparison": result.get("model_comparison") or [],
            "selected_model": result.get("selected_model"),
            "baseline": result.get("baseline") or {},
            "models_evaluated": result.get("models_evaluated", 0),
            "models_requested": result.get("models_requested", len(candidates)),
            "failures": result.get("failures") or {},
            "validation_strategy": result.get("validation_strategy", "holdout"),
            "n_rows": result.get("n_rows"),
            "n_features": result.get("n_features"),
            "artifacts": result.get("artifacts") or [],
            "error_type": None if result.get("selected_model") else "NoModelSelected",
            "error_message": None if result.get("selected_model") else "no candidate produced a score",
        }


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
        metrics = {"accuracy": 0.87}
        return {
            "success": True,
            "job_id": job_id,
            "status": "accepted",
            "model_family": params.model_family,
            "dataset_name": params.dataset_name,
            "primary_metric": params.primary_metric,
            "primary_score": metrics.get(params.primary_metric),
            "metrics": metrics,
            "model_comparison": [],
            "selected_model": params.model_family,
            "attempt": params.attempt,
            "params": dict(params.params),
            "artifacts": ["model.joblib"],
            "note": "Stub mode: Docker sandbox not available",
        }
