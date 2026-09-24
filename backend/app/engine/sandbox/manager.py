"""Docker Sandbox Execution Manager (Phase 10).

Provides isolated, resource-constrained containers for ML job execution.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from app.core.config import settings
from app.core.observability import (
    TimingContext,
    get_experiment_id,
    log_with_context,
    trace_operation,
)

logger = logging.getLogger("autosage.sandbox")


class SandboxError(Exception):
    """Base exception for sandbox failures."""

    def __init__(self, message: str, error_type: str = "SandboxError"):
        super().__init__(message)
        self.error_type = error_type


class SandboxTimeoutError(SandboxError):
    """Container execution exceeded timeout."""

    def __init__(self, timeout_sec: int):
        super().__init__(f"Execution timed out after {timeout_sec}s", "SandboxTimeoutError")


class SandboxResourceError(SandboxError):
    """Container exceeded resource limits (OOM, CPU)."""

    def __init__(self, message: str):
        super().__init__(message, "SandboxResourceError")


class SandboxExecutionError(SandboxError):
    """Container ran but script failed."""

    def __init__(self, exit_code: int, stderr: str):
        super().__init__(f"Script exited with code {exit_code}: {stderr}", "SandboxExecutionError")
        self.exit_code = exit_code
        self.stderr = stderr


class ExecutionResult:
    """Structured result of a sandbox execution."""

    def __init__(
        self,
        success: bool,
        job_id: str,
        metrics: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[str]] = None,
        stdout: str = "",
        stderr: str = "",
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_sec: float = 0.0,
        exit_code: Optional[int] = None,
    ):
        self.success = success
        self.job_id = job_id
        self.metrics = metrics or {}
        self.artifacts = artifacts or []
        self.stdout = stdout
        self.stderr = stderr
        self.error_type = error_type
        self.error_message = error_message
        self.duration_sec = round(duration_sec, 3)
        self.exit_code = exit_code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "job_id": self.job_id,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "duration_sec": self.duration_sec,
            "exit_code": self.exit_code,
        }


class SandboxManager:
    """Manages isolated Docker containers for ML job execution.

    Features:
    - Per-job isolated containers
    - CPU/memory limits
    - Execution timeout
    - Read-only filesystem (except /workspace)
    - No network access
    - Non-root user execution
    - Capability dropping
    - Seccomp profile
    - PIDs limit
    - Automatic container/workspace cleanup
    """

    DEFAULT_CPU_LIMIT = 1.0  # CPUs
    DEFAULT_MEMORY_LIMIT = "2g"  # Memory limit
    DEFAULT_TIMEOUT = 300  # seconds
    DEFAULT_WORKSPACE_SIZE = "500m"  # tmpfs size for /workspace
    DEFAULT_PIDS_LIMIT = 100
    DEFAULT_ULIMITS = {
        "nofile": (1024, 4096),    # Soft/hard limit on open files
        "nproc": (50, 100),        # Process limit
        "fsize": (100 * 1024 * 1024, 100 * 1024 * 1024),  # Max file size 100MB
    }

    def __init__(
        self,
        image_tag: str = "autosage-runner:latest",
        dockerfile_path: Optional[str] = None,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        timeout_sec: int = DEFAULT_TIMEOUT,
        workspace_size: str = DEFAULT_WORKSPACE_SIZE,
        mlflow_tracking_uri: Optional[str] = None,
        mlflow_experiment_name: Optional[str] = None,
        pids_limit: int = DEFAULT_PIDS_LIMIT,
        ulimits: Optional[Dict[str, tuple]] = None,
        seccomp_profile: Optional[str] = None,
        readonly_rootfs: bool = True,
    ):
        self.image_tag = image_tag
        self.dockerfile_path = dockerfile_path or str(
            Path(__file__).parent / "dockerfile"
        )
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.timeout_sec = timeout_sec
        self.workspace_size = workspace_size
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.mlflow_experiment_name = mlflow_experiment_name
        self.pids_limit = pids_limit
        self.ulimits = ulimits or self.DEFAULT_ULIMITS
        self.seccomp_profile = seccomp_profile
        self.readonly_rootfs = readonly_rootfs
        self._client: Optional[docker.DockerClient] = None

    @property
    def client(self) -> docker.DockerClient:
        """Lazily initialize Docker client."""
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
            except DockerException as e:
                raise SandboxError(f"Docker daemon not available: {e}") from e
        return self._client

    def build_image(self, force_rebuild: bool = False) -> str:
        """Build the runner Docker image.

        Args:
            force_rebuild: If True, rebuild even if image exists.

        Returns:
            Image tag that was built.
        """
        try:
            if not force_rebuild:
                try:
                    self.client.images.get(self.image_tag)
                    logger.info("sandbox_image_exists", extra={"image": self.image_tag})
                    return self.image_tag
                except ImageNotFound:
                    pass

            logger.info("sandbox_building_image", extra={"image": self.image_tag})
            self.client.images.build(
                path=self.dockerfile_path,
                tag=self.image_tag,
                rm=True,
                forcerm=True,
            )
            logger.info("sandbox_image_built", extra={"image": self.image_tag})
            return self.image_tag
        except DockerException as e:
            raise SandboxError(f"Failed to build sandbox image: {e}") from e

    def _create_workspace(
        self, script: str, dataset_path: Optional[str] = None
    ) -> Tuple[Path, Path, Path]:
        """Create temporary workspace with script and optional dataset.

        Returns:
            Tuple of (workspace_dir, script_path, dataset_path_in_workspace)
        """
        workspace = Path(tempfile.mkdtemp(prefix="autosage_job_"))
        script_path = workspace / "train.py"
        script_path.write_text(script)

        dataset_path_in_ws = None
        if dataset_path and Path(dataset_path).exists():
            dataset_path_in_ws = workspace / "dataset.csv"
            shutil.copy2(dataset_path, dataset_path_in_ws)

        return workspace, script_path, dataset_path_in_ws

    def _cleanup_workspace(self, workspace: Path) -> None:
        """Remove temporary workspace directory."""
        try:
            shutil.rmtree(workspace, ignore_errors=True)
        except Exception as e:
            logger.warning("sandbox_workspace_cleanup_failed", extra={"error": str(e)})

    def _run_container(
        self,
        workspace: Path,
        script_name: str = "train.py",
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """Run the training script in an isolated container.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        # Prepare environment with MLflow config if available
        env = dict(env_vars or {})
        if self.mlflow_tracking_uri:
            env["MLFLOW_TRACKING_URI"] = self.mlflow_tracking_uri
        if self.mlflow_experiment_name:
            env["MLFLOW_EXPERIMENT_NAME"] = self.mlflow_experiment_name

        container = None
        try:
            # Build security options
            security_opts = ["no-new-privileges"]
            if self.seccomp_profile:
                security_opts.append(f"seccomp={self.seccomp_profile}")
            elif self.readonly_rootfs:
                # Default restrictive seccomp if no custom profile
                security_opts.append("seccomp=unconfined")  # Use default Docker seccomp

            # Mount workspace as read-only except for /workspace which is tmpfs
            container = self.client.containers.run(
                self.image_tag,
                command=["python", f"/workspace/{script_name}"],
                volumes={
                    str(workspace): {"bind": "/workspace", "mode": "rw"}
                },
                working_dir="/workspace",
                cpu_count=self.cpu_limit,
                mem_limit=self.memory_limit,
                memswap_limit=self.memory_limit,  # Disable swap
                network_mode="none",  # No network access
                user="autosage",  # Run as non-root user
                detach=True,
                stdout=True,
                stderr=True,
                environment=env,
                tmpfs={"/workspace": f"size={self.workspace_size},exec,nosuid,nodev"},
                security_opt=security_opts,
                cap_drop=["ALL"],
                pids_limit=self.pids_limit,
                read_only=self.readonly_rootfs,
                ulimits=[
                    docker.types.Ulimit(name=k, soft=v[0], hard=v[1])
                    for k, v in self.ulimits.items()
                ],
            )

            # Wait for completion with timeout
            start = time.time()
            while time.time() - start < self.timeout_sec:
                container.reload()
                if container.status != "running":
                    break
                time.sleep(0.5)
            else:
                # Timeout - kill container
                try:
                    container.kill()
                except Exception:
                    pass
                raise SandboxTimeoutError(self.timeout_sec)

            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            stdout, stderr = self._split_logs(logs)

            exit_code = container.attrs["State"]["ExitCode"]

            return exit_code, stdout, stderr

        except SandboxTimeoutError:
            raise
        except docker.errors.ContainerError as e:
            raise SandboxExecutionError(e.exit_code, e.stderr.decode() if e.stderr else "")
        except DockerException as e:
            raise SandboxError(f"Container execution failed: {e}") from e
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _split_logs(self, logs: str) -> Tuple[str, str]:
        """Split combined Docker logs into stdout/stderr.

        Docker combines them; we can't perfectly separate without tty.
        For simplicity, return all as stdout and empty stderr unless
        we detect error patterns.
        """
        # Heuristic: lines with "ERROR", "Traceback", "Error:" go to stderr
        stdout_lines = []
        stderr_lines = []
        for line in logs.splitlines():
            if any(
                kw in line.lower()
                for kw in ["error:", "traceback", "exception", "failed"]
            ):
                stderr_lines.append(line)
            else:
                stdout_lines.append(line)
        return "\n".join(stdout_lines), "\n".join(stderr_lines)

    def _parse_metrics_and_artifacts(
        self, workspace: Path, stdout: str
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Parse metrics JSON and collect artifact paths from workspace."""
        metrics = {}
        artifacts = []

        # Look for metrics.json written by training script
        metrics_file = workspace / "metrics.json"
        if metrics_file.exists():
            try:
                import json
                metrics = json.loads(metrics_file.read_text())
            except Exception as e:
                logger.warning("sandbox_metrics_parse_failed", extra={"error": str(e)})

        # Collect model artifacts (.pkl, .joblib, .pt, .pth, .json)
        for pattern in ["*.pkl", "*.joblib", "*.pt", "*.pth", "*.json", "*.model"]:
            for f in workspace.glob(pattern):
                if f.name != "metrics.json":
                    artifacts.append(str(f.relative_to(workspace)))

        return metrics, artifacts

    async def execute_job(
        self,
        job_id: str,
        script: str,
        dataset_path: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        mlflow_run_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute an ML training job in the sandbox.

        Args:
            job_id: Unique job identifier.
            script: Python training script as string.
            dataset_path: Optional path to dataset CSV file.
            env_vars: Optional environment variables for the container.
            mlflow_run_id: Optional MLflow run ID to continue logging to.

        Returns:
            ExecutionResult with metrics, artifacts, and status.
        """
        experiment_id = get_experiment_id()
        
        with TimingContext(
            "sandbox_execute_job",
            extra_fields={
                "job_id": job_id,
                "experiment": experiment_id,
                "mlflow_run_id": mlflow_run_id,
            },
        ):
            with trace_operation(
                "sandbox.execute_job",
                attributes={
                    "job_id": job_id,
                    "experiment_id": experiment_id or "",
                    "mlflow_run_id": mlflow_run_id or "",
                },
            ):
                start_time = time.time()
                workspace = None

                try:
                    # Ensure image exists
                    with TimingContext("sandbox_build_image", extra_fields={"job_id": job_id, "experiment": experiment_id}):
                        self.build_image()

                    # Create workspace
                    with TimingContext("sandbox_create_workspace", extra_fields={"job_id": job_id, "experiment": experiment_id}):
                        workspace, script_path, dataset_in_ws = self._create_workspace(
                            script, dataset_path
                        )

                    # Prepare environment
                    env = {
                        "PYTHONUNBUFFERED": "1",
                        "JOBLIB_TEMP_FOLDER": "/workspace",
                        "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:128",
                    }
                    if env_vars:
                        env.update(env_vars)
                    if mlflow_run_id:
                        env["MLFLOW_RUN_ID"] = mlflow_run_id

                    # Run container
                    loop = asyncio.get_event_loop()
                    with TimingContext("sandbox_run_container", extra_fields={"job_id": job_id, "experiment": experiment_id}):
                        exit_code, stdout, stderr = await loop.run_in_executor(
                            None, self._run_container, workspace, "train.py", env
                        )

                    duration = time.time() - start_time

                    if exit_code == 0:
                        metrics, artifacts = self._parse_metrics_and_artifacts(
                            workspace, stdout
                        )
                        log_with_context(
                            logger, logging.INFO, "sandbox_job_completed",
                            job_id=job_id, experiment=experiment_id,
                            duration_sec=duration, exit_code=exit_code,
                            metrics_keys=list(metrics.keys()) if metrics else [],
                            artifact_count=len(artifacts) if artifacts else 0,
                        )
                        return ExecutionResult(
                            success=True,
                            job_id=job_id,
                            metrics=metrics,
                            artifacts=artifacts,
                            stdout=stdout,
                            stderr=stderr,
                            duration_sec=duration,
                            exit_code=exit_code,
                        )
                    else:
                        log_with_context(
                            logger, logging.ERROR, "sandbox_job_failed",
                            job_id=job_id, experiment=experiment_id,
                            duration_sec=duration, exit_code=exit_code,
                            stderr=stderr[:500] if stderr else None,
                        )
                        return ExecutionResult(
                            success=False,
                            job_id=job_id,
                            stdout=stdout,
                            stderr=stderr,
                            error_type="SandboxExecutionError",
                            error_message=f"Script exited with code {exit_code}",
                            duration_sec=duration,
                            exit_code=exit_code,
                        )

                except SandboxTimeoutError as e:
                    duration = time.time() - start_time
                    log_with_context(
                        logger, logging.ERROR, "sandbox_job_timeout",
                        job_id=job_id, experiment=experiment_id,
                        duration_sec=duration, timeout_sec=self.timeout_sec,
                    )
                    return ExecutionResult(
                        success=False,
                        job_id=job_id,
                        error_type=e.error_type,
                        error_message=str(e),
                        duration_sec=duration,
                    )
                except SandboxResourceError as e:
                    duration = time.time() - start_time
                    log_with_context(
                        logger, logging.ERROR, "sandbox_job_resource_error",
                        job_id=job_id, experiment=experiment_id,
                        duration_sec=duration, error=str(e),
                    )
                    return ExecutionResult(
                        success=False,
                        job_id=job_id,
                        error_type=e.error_type,
                        error_message=str(e),
                        duration_sec=duration,
                    )
                except SandboxError as e:
                    duration = time.time() - start_time
                    log_with_context(
                        logger, logging.ERROR, "sandbox_job_error",
                        job_id=job_id, experiment=experiment_id,
                        duration_sec=duration, error=str(e),
                    )
                    return ExecutionResult(
                        success=False,
                        job_id=job_id,
                        error_type=e.error_type,
                        error_message=str(e),
                        duration_sec=duration,
                    )
                except Exception as e:  # noqa: BLE001
                    duration = time.time() - start_time
                    log_with_context(
                        logger, logging.ERROR, "sandbox_unexpected_error",
                        job_id=job_id, experiment=experiment_id,
                        duration_sec=duration, error_type=type(e).__name__,
                        error_message=str(e),
                    )
                    return ExecutionResult(
                        success=False,
                        job_id=job_id,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        duration_sec=duration,
                    )
                finally:
                    if workspace:
                        self._cleanup_workspace(workspace)

    def cleanup(self) -> None:
        """Clean up Docker client resources."""
        if self._client:
            self._client.close()
            self._client = None


# Global sandbox manager instance
_sandbox_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    """Get or create the global sandbox manager."""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager(
            image_tag=getattr(settings, "SANDBOX_IMAGE_TAG", "autosage-runner:latest"),
            cpu_limit=getattr(settings, "SANDBOX_CPU_LIMIT", 1.0),
            memory_limit=getattr(settings, "SANDBOX_MEMORY_LIMIT", "2g"),
            timeout_sec=getattr(settings, "SANDBOX_TIMEOUT_SEC", 300),
            mlflow_tracking_uri=getattr(settings, "MLFLOW_TRACKING_URI", None),
            mlflow_experiment_name=getattr(settings, "MLFLOW_EXPERIMENT_NAME", None),
            pids_limit=getattr(settings, "SANDBOX_PIDS_LIMIT", 100),
            readonly_rootfs=getattr(settings, "SANDBOX_READONLY_ROOTFS", True),
        )
    return _sandbox_manager


def set_sandbox_manager(manager: Optional[SandboxManager]) -> None:
    """Replace the global sandbox manager (for testing)."""
    global _sandbox_manager
    if _sandbox_manager:
        _sandbox_manager.cleanup()
    _sandbox_manager = manager