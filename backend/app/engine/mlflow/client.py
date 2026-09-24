"""MLflow Client for AutoSage (Phase 11).

Provides a clean interface for tracking ML experiments, runs, parameters,
metrics, models, and artifacts via MLflow with PostgreSQL backend.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from uuid import UUID

import mlflow
from mlflow.entities import RunStatus
from mlflow.tracking import MlflowClient

from app.core.config import settings

logger = logging.getLogger("autosage.mlflow")


class MLflowTracker:
    """High-level MLflow tracking wrapper for AutoSage experiments."""

    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        experiment_name: Optional[str] = None,
    ):
        """Initialize MLflow tracker.

        Args:
            tracking_uri: MLflow tracking server URI. Defaults to settings.MLFLOW_TRACKING_URI.
            experiment_name: MLflow experiment name. Defaults to settings.MLFLOW_EXPERIMENT_NAME.
        """
        self.tracking_uri = tracking_uri or settings.MLFLOW_TRACKING_URI
        self.experiment_name = experiment_name or getattr(
            settings, "MLFLOW_EXPERIMENT_NAME", "autosage_default"
        )

        mlflow.set_tracking_uri(self.tracking_uri)
        self._client = MlflowClient(tracking_uri=self.tracking_uri)
        self._experiment_id = self._get_or_create_experiment()

    def _get_or_create_experiment(self) -> str:
        """Get existing experiment ID or create new one."""
        experiment = self._client.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            experiment_id = self._client.create_experiment(self.experiment_name)
            logger.info("mlflow_experiment_created", extra={"experiment_id": experiment_id, "name": self.experiment_name})
            return experiment_id
        logger.debug("mlflow_experiment_exists", extra={"experiment_id": experiment.experiment_id, "name": self.experiment_name})
        return experiment.experiment_id

    @property
    def experiment_id(self) -> str:
        """Return the MLflow experiment ID."""
        return self._experiment_id

    @property
    def client(self) -> MlflowClient:
        """Return the underlying MLflow client."""
        return self._client

    def start_run(
        self,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        autosage_experiment_id: Optional[UUID] = None,
    ) -> mlflow.ActiveRun:
        """Start a new MLflow run.

        Args:
            run_name: Human-readable name for the run.
            tags: Additional tags to attach to the run.
            autosage_experiment_id: AutoSage experiment UUID for cross-referencing.

        Returns:
            Active MLflow run context manager.
        """
        run_tags = tags or {}
        if autosage_experiment_id:
            run_tags["autosage_experiment_id"] = str(autosage_experiment_id)
        run_tags.setdefault("source", "autosage-sandbox")

        return mlflow.start_run(
            experiment_id=self.experiment_id,
            run_name=run_name,
            tags=run_tags,
        )

    def log_params(self, params: Dict[str, Any]) -> None:
        """Log parameters to current run."""
        if params:
            mlflow.log_params(params)
            logger.debug("mlflow_params_logged", extra={"count": len(params)})

    def log_metrics(
        self,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics to current run."""
        if metrics:
            mlflow.log_metrics(metrics, step=step)
            logger.debug("mlflow_metrics_logged", extra={"count": len(metrics)})

    def log_metric(
        self,
        key: str,
        value: float,
        step: Optional[int] = None,
    ) -> None:
        """Log a single metric to current run."""
        mlflow.log_metric(key, value, step=step)

    def log_artifacts(self, local_dir: str, artifact_path: Optional[str] = None) -> None:
        """Log artifacts from a local directory."""
        mlflow.log_artifacts(local_dir, artifact_path=artifact_path)
        logger.debug("mlflow_artifacts_logged", extra={"dir": local_dir})

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None) -> None:
        """Log a single artifact file."""
        mlflow.log_artifact(local_path, artifact_path=artifact_path)
        logger.debug("mlflow_artifact_logged", extra={"path": local_path})

    def log_model(
        self,
        model: Any,
        artifact_path: str,
        **kwargs,
    ) -> None:
        """Log an ML model."""
        mlflow.sklearn.log_model(model, artifact_path, **kwargs)
        logger.info("mlflow_model_logged", extra={"artifact_path": artifact_path})

    def set_tags(self, tags: Dict[str, str]) -> None:
        """Set tags on current run."""
        if tags:
            mlflow.set_tags(tags)

    def end_run(self, status: str = "FINISHED") -> None:
        """End the current run."""
        mlflow.end_run(status=status)
        logger.info("mlflow_run_ended", extra={"status": status})

    def get_run(self, run_id: str) -> Optional[mlflow.entities.Run]:
        """Get run by ID."""
        try:
            return self._client.get_run(run_id)
        except Exception as e:
            logger.warning("mlflow_get_run_failed", extra={"run_id": run_id, "error": str(e)})
            return None

    def search_runs(
        self,
        filter_string: Optional[str] = None,
        max_results: int = 100,
    ) -> List[mlflow.entities.Run]:
        """Search runs in the experiment."""
        return self._client.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=filter_string,
            max_results=max_results,
        )


# Global tracker instance
_mlflow_tracker: Optional[MLflowTracker] = None


def get_mlflow_tracker(
    tracking_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> MLflowTracker:
    """Get or create global MLflow tracker."""
    global _mlflow_tracker
    if _mlflow_tracker is None:
        _mlflow_tracker = MLflowTracker(tracking_uri, experiment_name)
    return _mlflow_tracker


def set_mlflow_tracker(tracker: Optional[MLflowTracker]) -> None:
    """Replace global MLflow tracker (for testing)."""
    global _mlflow_tracker
    _mlflow_tracker = tracker


@contextmanager
def mlflow_run_context(
    tracker: MLflowTracker,
    run_name: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    autosage_experiment_id: Optional[UUID] = None,
):
    """Context manager for MLflow run with automatic cleanup."""
    run = tracker.start_run(run_name=run_name, tags=tags, autosage_experiment_id=autosage_experiment_id)
    try:
        yield run
    except Exception:
        tracker.end_run(status="FAILED")
        raise
    else:
        tracker.end_run(status="FINISHED")


def is_mlflow_available() -> bool:
    """Check if MLflow tracking is configured and reachable."""
    try:
        client = MlflowClient(tracking_uri=settings.MLFLOW_TRACKING_URI)
        # Try to get experiment - this works for both server and file-based backends
        client.get_experiment_by_name(getattr(settings, "MLFLOW_EXPERIMENT_NAME", "autosage_default"))
        return True
    except Exception as e:
        logger.warning("mlflow_unavailable", extra={"error": str(e)})
        return False