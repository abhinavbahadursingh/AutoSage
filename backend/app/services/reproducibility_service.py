"""Reproducibility Service (Phase 17).

Manages creation and retrieval of reproducibility records for completed experiments.
"""
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.ml_run import MLRun
from app.models.reproducibility import ReproducibilityRecord


class ReproducibilityService:
    """Service for managing reproducibility records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_record(
        self,
        experiment: Experiment,
        ml_run: Optional[MLRun] = None,
        dataset: Optional[Dataset] = None,
        sandbox_result: Optional[Dict[str, Any]] = None,
    ) -> ReproducibilityRecord:
        """Create a reproducibility record for a completed experiment."""

        # Gather dataset info
        dataset_sha256 = await self._get_dataset_hash(dataset)
        dataset_size = dataset.file_size_bytes if dataset else None

        # Gather code version info
        code_info = await self._get_code_version()

        # Gather dependency info
        deps_info = self._get_dependencies()

        # Gather runtime info
        runtime_info = self._get_runtime_info()

        # Gather hardware info
        hardware_info = self._get_hardware_info()

        # Build record
        record = ReproducibilityRecord(
            experiment_id=experiment.id,
            ml_run_id=ml_run.id if ml_run else None,
            dataset_id=dataset.id if dataset else None,
            # Dataset fingerprint
            dataset_sha256=dataset_sha256,
            dataset_size_bytes=dataset_size,
            dataset_rows=dataset.profile_summary.get("row_count") if dataset and dataset.profile_summary else None,
            dataset_columns=dataset.profile_summary.get("column_count") if dataset and dataset.profile_summary else None,
            dataset_schema=dataset.schema_metadata if dataset else None,
            # Code / version
            code_version=code_info.get("commit_sha"),
            code_repository=code_info.get("remote_url"),
            code_branch=code_info.get("branch"),
            code_dirty=code_info.get("dirty"),
            # Dependencies
            python_version=deps_info["python_version"],
            platform=deps_info["platform"],
            pip_freeze=deps_info.get("pip_freeze"),
            conda_env=deps_info.get("conda_env"),
            # Model & experiment config
            model_family=experiment.config.get("model_family", "gradient_boosting"),
            model_name=experiment.config.get("model_name"),
            model_params=experiment.config.get("model_params", {}),
            experiment_config=experiment.config,
            random_seed=experiment.config.get("random_seed"),
            # MLflow linkage
            mlflow_run_id=ml_run.mlflow_run_id if ml_run else None,
            mlflow_experiment_id=ml_run.mlflow_run_id if ml_run else None,
            mlflow_experiment_name=settings.MLFLOW_EXPERIMENT_NAME if ml_run else None,
            # Runtime environment
            runtime_type=runtime_info.get("type"),
            docker_image=runtime_info.get("docker_image"),
            docker_image_id=runtime_info.get("docker_image_id"),
            container_id=runtime_info.get("container_id"),
            hardware_info=hardware_info,
            # Artifacts
            artifact_uris=sandbox_result.get("artifact_uris") if sandbox_result else None,
            model_artifact_uri=sandbox_result.get("model_artifact_uri") if sandbox_result else None,
            log_artifact_uri=sandbox_result.get("log_artifact_uri") if sandbox_result else None,
            # Metrics
            final_metrics=ml_run.metrics if ml_run else experiment.result_summary.get("ml_result"),
        )

        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_by_experiment(
        self, experiment_id: UUID, owner_id: UUID
    ) -> Optional[ReproducibilityRecord]:
        """Get reproducibility record by experiment ID (with ownership check)."""
        # First verify experiment ownership
        from app.services import experiment_service

        try:
            await experiment_service.get_for_user(self.session, experiment_id, owner_id)
        except Exception:
            return None

        query = (
            select(ReproducibilityRecord)
            .where(ReproducibilityRecord.experiment_id == experiment_id)
            .options(
                selectinload(ReproducibilityRecord.experiment),
                selectinload(ReproducibilityRecord.ml_run),
                selectinload(ReproducibilityRecord.dataset),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(
        self, record_id: UUID, owner_id: UUID
    ) -> Optional[ReproducibilityRecord]:
        """Get reproducibility record by ID (with ownership check via experiment)."""
        query = (
            select(ReproducibilityRecord)
            .where(ReproducibilityRecord.id == record_id)
            .options(
                selectinload(ReproducibilityRecord.experiment),
                selectinload(ReproducibilityRecord.ml_run),
                selectinload(ReproducibilityRecord.dataset),
            )
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        # Verify ownership via experiment
        from app.services import experiment_service

        try:
            await experiment_service.get_for_user(self.session, record.experiment_id, owner_id)
        except Exception:
            return None

        return record

    async def list_for_user(
        self,
        owner_id: UUID,
        workspace_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[ReproducibilityRecord], int]:
        """List reproducibility records for user's experiments."""
        from app.services import workspace_service

        if workspace_id is not None:
            await workspace_service.get_for_user(self.session, workspace_id, owner_id)
            workspace_ids = [workspace_id]
        else:
            workspace_ids = await workspace_service.list_ids_for_user(self.session, owner_id)
            if not workspace_ids:
                return [], 0

        # Get experiment IDs in user's workspaces
        exp_query = select(Experiment.id).where(Experiment.workspace_id.in_(workspace_ids))
        exp_result = await self.session.execute(exp_query)
        experiment_ids = [row[0] for row in exp_result.fetchall()]

        if not experiment_ids:
            return [], 0

        # Get reproducibility records for those experiments
        query = (
            select(ReproducibilityRecord)
            .where(ReproducibilityRecord.experiment_id.in_(experiment_ids))
            .order_by(ReproducibilityRecord.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
            .options(
                selectinload(ReproducibilityRecord.experiment),
                selectinload(ReproducibilityRecord.ml_run),
                selectinload(ReproducibilityRecord.dataset),
            )
        )
        result = await self.session.execute(query)
        records = list(result.scalars().all())

        # Count
        count_query = select(ReproducibilityRecord).where(
            ReproducibilityRecord.experiment_id.in_(experiment_ids)
        )
        count_result = await self.session.execute(count_query)
        total = len(list(count_result.scalars().all()))

        return records, total

    async def _get_dataset_hash(self, dataset: Optional[Dataset]) -> str:
        """Compute SHA-256 hash of the dataset file."""
        if not dataset:
            return "unknown"

        try:
            from app.engine.storage.service import get_storage_service

            storage = get_storage_service()
            content = await storage.download_file(dataset.storage_path)
            return hashlib.sha256(content).hexdigest()
        except Exception:
            return "unavailable"

    async def _get_code_version(self) -> Dict[str, Any]:
        """Get git version information."""
        info: Dict[str, Any] = {}
        try:
            # Get commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                info["commit_sha"] = result.stdout.strip()

            # Get remote URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                info["remote_url"] = result.stdout.strip()

            # Get branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                info["branch"] = result.stdout.strip()

            # Check if working tree is dirty
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                info["dirty"] = "true" if result.stdout.strip() else "false"
        except Exception:
            pass
        return info

    def _get_dependencies(self) -> Dict[str, Any]:
        """Get Python and dependency versions."""
        info: Dict[str, Any] = {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
        }

        # Get pip freeze
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                packages = {}
                for line in result.stdout.strip().split("\n"):
                    if "==" in line:
                        name, version = line.split("==", 1)
                        packages[name] = version
                info["pip_freeze"] = packages
        except Exception:
            pass

        # Try conda env export
        try:
            result = subprocess.run(
                ["conda", "env", "export", "--no-builds"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import yaml
                conda_env = yaml.safe_load(result.stdout)
                if conda_env and "dependencies" in conda_env:
                    packages = {}
                    for dep in conda_env["dependencies"]:
                        if isinstance(dep, str) and "=" in dep:
                            parts = dep.split("=")
                            if len(parts) >= 2:
                                packages[parts[0]] = "=".join(parts[1:])
                        elif isinstance(dep, dict) and "pip" in dep:
                            for pip_dep in dep["pip"]:
                                if "==" in pip_dep:
                                    name, version = pip_dep.split("==", 1)
                                    packages[name] = version
                    info["conda_env"] = packages
        except Exception:
            pass

        return info

    def _get_runtime_info(self) -> Dict[str, Any]:
        """Get runtime environment information."""
        info: Dict[str, Any] = {}

        # Check if running in Docker
        try:
            with open("/proc/1/cgroup", "r") as f:
                content = f.read()
                if "docker" in content or "containerd" in content:
                    info["type"] = "docker"
                else:
                    info["type"] = "system"
        except Exception:
            info["type"] = "unknown"

        # Docker image info from settings
        info["docker_image"] = settings.DOCKER_SANDBOX_IMAGE

        return info

    def _get_hardware_info(self) -> Dict[str, Any]:
        """Get hardware information."""
        info: Dict[str, Any] = {}

        # CPU info
        try:
            info["cpu_count"] = platform.cpu_count()
            info["cpu_model"] = platform.processor()
        except Exception:
            pass

        # Memory info
        try:
            import psutil
            mem = psutil.virtual_memory()
            info["memory_total_gb"] = round(mem.total / (1024**3), 2)
        except Exception:
            pass

        # GPU info (if nvidia-smi available)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                gpus = []
                for line in result.stdout.strip().split("\n"):
                    name, mem = line.split(", ")
                    gpus.append({"name": name, "memory": mem})
                info["gpus"] = gpus
        except Exception:
            pass

        return info


async def get_reproducibility_service(session: AsyncSession) -> ReproducibilityService:
    """FastAPI dependency for reproducibility service."""
    return ReproducibilityService(session)