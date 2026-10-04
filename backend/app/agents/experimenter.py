"""ML Experiment Agent (Phase 7).

Responsibility: drive one training attempt and record what was *measured*.

The recorded metric is always the metric the request asked for
(``state["primary_metric"]``), and the value always comes from a real
training/evaluation run through the ``execute_ml_job`` tool. When
``compare_models`` is set, every candidate family is trained and scored, and
the winner is chosen on the requested metric alone. Nothing here estimates a
score: the LLM may only add narrative to an already-measured run, so a run can
never "verify" an expected accuracy it never measured.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, MLExperimentOutput
from app.agents.state import ExperimentWorkflowState
from app.engine.metrics import (
    canonical_result,
    is_higher_is_better,
    secondary_metrics,
)

logger = logging.getLogger("autosage.workflow")

STAGE = "ml_experiment"

_SYSTEM = (
    "You are the AutoSage ML Experiment Agent. "
    "You are given a training run that has ALREADY been executed, with its "
    "measured scores. Summarize what happened in two sentences. "
    "Never state a score that is not in the measured data, and never present a "
    "metric other than the requested one as the objective."
)


class MLExperimentAgent(BaseAgent):
    """Executes one training attempt and records measured results."""

    stage = STAGE
    output_model = MLExperimentOutput
    #: Last measured training result (set by :meth:`run`, read by state_payload).
    _measurement: Optional[Dict[str, Any]] = None

    def model_tier(self) -> str:
        return "reasoning"

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        """Prompt describing the *executed* run (measurement is authoritative)."""
        ml_result = state.get("ml_result") or {}
        model_spec = state.get("model_spec") or {}
        primary_metric = self._primary_metric(state)
        attempt = int(state.get("attempt") or 0) + 1
        user = (
            f"Summarize training attempt #{attempt}.\n"
            f"REQUESTED METRIC (report this one only): {primary_metric}\n"
            f"compare_models: {self._compare_models(state)}\n"
            f"model_spec={model_spec}\n"
            f"measured_result={ml_result or 'pending — the run executes before this summary'}"
        )
        return _SYSTEM, user

    # -- objective helpers ----------------------------------------------------
    def _primary_metric(self, state: ExperimentWorkflowState) -> str:
        return str(state.get("primary_metric") or "accuracy")

    def _compare_models(self, state: ExperimentWorkflowState) -> bool:
        return bool(state.get("compare_models"))

    def _candidates(self, state: ExperimentWorkflowState) -> List[str]:
        model_spec = state.get("model_spec") or {}
        family = str(model_spec.get("family") or "gradient_boosting")
        candidates = [str(c) for c in (model_spec.get("candidates") or []) if str(c).strip()]
        if not self._compare_models(state):
            return [family]
        return candidates or [family]

    def _training_inputs(self, state: ExperimentWorkflowState) -> Dict[str, Any]:
        """Resolve what to train on.

        The request config is authoritative: it is what the user asked for.
        Discovery/profiler output only fills the gaps (and can describe a
        dataset the run never requested).
        """
        config = state.get("config") or {}
        profile = state.get("profile") or {}
        dataset = state.get("dataset_info") or {}
        model_spec = state.get("model_spec") or {}
        return {
            "model_family": str(model_spec.get("family") or "gradient_boosting"),
            "dataset_name": str(
                config.get("dataset_name")
                or config.get("dataset")
                or dataset.get("name")
                or "dataset.csv"
            ),
            "target_column": str(
                config.get("target_column")
                or dataset.get("target_column")
                or profile.get("target_column")
                or "target"
            ),
            "task_type": str(
                config.get("task_type") or profile.get("task_type") or "classification"
            ),
        }

    # -- execution ------------------------------------------------------------
    def _measure(
        self, state: ExperimentWorkflowState
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Run the real training job once; returns (job data, failure reason)."""
        inputs = self._training_inputs(state)
        job = self.call_tool(
            "execute_ml_job",
            model_family=inputs["model_family"],
            dataset_name=inputs["dataset_name"],
            target_column=inputs["target_column"],
            task_type=inputs["task_type"],
            primary_metric=self._primary_metric(state),
            compare_models=self._compare_models(state),
            candidates=self._candidates(state),
            params=dict((state.get("model_spec") or {}).get("params") or {}),
            attempt=int(state.get("attempt") or 0) + 1,
            experiment_id=state.get("experiment_id"),
            dataset_path=(state.get("config") or {}).get("dataset_path"),
        )
        data = job.data if job.success else None
        if data and data.get("selected_model"):
            return data, None
        return None, self._failure_reason(data, job)

    @staticmethod
    def _failure_reason(data: Optional[Dict[str, Any]], job: Any) -> str:
        if data:
            failures = data.get("failures") or {}
            if failures:
                return "; ".join(f"{k}: {v}" for k, v in list(failures.items())[:3])
            for key in ("error_message", "sandbox_error"):
                if data.get(key):
                    return str(data[key])
        return str(getattr(job, "error", None) or "training job did not complete")

    def run(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Measure first, annotate second.

        Overrides :meth:`BaseAgent.run` because the metric and the value must
        come from the training run, never from a model completing a prompt.
        """
        primary_metric = self._primary_metric(state)
        attempt = int(state.get("attempt") or 0) + 1
        data, reason = self._measure(state)
        self._measurement: Optional[Dict[str, Any]] = data

        if data is None:
            logger.warning(
                "ml_experiment_measurement_failed",
                extra={"stage": STAGE, "metric": primary_metric, "reason": reason},
            )
            # No measurement -> no score. Value stays 0.0 so the verification
            # gate abstains instead of "verifying" an unmeasured number.
            return MLExperimentOutput(
                source="heuristic",
                metric=primary_metric,
                value=0.0,
                validation_strategy="none",
                notes=f"Training did not produce a measurable {primary_metric}: {reason}",
                attempt=attempt,
            )

        return MLExperimentOutput(
            source="heuristic",
            metric=str(data.get("primary_metric") or primary_metric),
            value=float(data.get("primary_score") or 0.0),
            validation_strategy=str(data.get("validation_strategy") or "holdout"),
            notes=self._measured_summary(state, data),
            attempt=attempt,
        )

    def _measured_summary(self, state: ExperimentWorkflowState, data: Dict[str, Any]) -> str:
        """Factual summary of the measured run (the recorded ``notes``)."""
        primary_metric = str(data.get("primary_metric") or self._primary_metric(state))
        metrics = dict(data.get("metrics") or {})
        evaluated = int(data.get("models_evaluated") or 1)
        direction = "higher" if is_higher_is_better(primary_metric) else "lower"
        parts = [
            f"Measured {primary_metric}={data.get('primary_score')} on "
            f"{data.get('validation_strategy') or 'holdout'} ({direction} is better).",
            f"Compared {evaluated} model(s); selected {data.get('selected_model')}.",
        ]
        secondary = ", ".join(
            f"{name}={metrics[name]}"
            for name in secondary_metrics(primary_metric)[:3]
            if metrics.get(name) is not None
        )
        if secondary:
            # Accuracy and friends are reported, never promoted over the goal.
            parts.append(f"Secondary metrics: {secondary}.")
        return " ".join(parts)

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Deterministic entry point; measurement is still performed for real."""
        return self.run(state)

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, MLExperimentOutput)
        primary_metric = str(state.get("primary_metric") or output.metric)
        data = getattr(self, "_measurement", None)

        metrics = dict(data.get("metrics") or {}) if data else {}
        comparison = list(data.get("model_comparison") or []) if data else []
        selected_model = data.get("selected_model") if data else None
        # No measurement => no score. 0.0 would read as a real (bad) result.
        primary_score = data.get("primary_score") if data else None
        if primary_score is None and data is not None:
            primary_score = output.value

        result = canonical_result(
            primary_metric=primary_metric,
            primary_score=primary_score,
            metrics=metrics,
            model_comparison=comparison,
            selected_model=selected_model,
        )
        result.update(
            {
                # Aliases consumed by the UI timeline / existing result readers.
                "metric": primary_metric,
                "value": primary_score if primary_score is not None else 0.0,
                "validation_strategy": output.validation_strategy,
                "notes": output.notes,
                "attempt": output.attempt,
                "source": output.source,
                "compare_models": self._compare_models(state),
                "candidates": self._candidates(state),
                "baseline": dict(data.get("baseline") or {}) if data else {},
                "models_evaluated": int(data.get("models_evaluated") or 0) if data else 0,
                "execution_backend": (data or {}).get("execution_backend"),
                "job_id": (data or {}).get("job_id"),
                "failures": dict((data or {}).get("failures") or {}),
                "n_rows": (data or {}).get("n_rows"),
                "n_features": (data or {}).get("n_features"),
            }
        )
        return {
            "attempt": output.attempt,
            "ml_result": result,
            # Keep the resolved objective in state even when training failed,
            # so verification still checks the requested metric.
            "primary_metric": primary_metric,
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, MLExperimentOutput)
        data = getattr(self, "_measurement", None) or {}
        compared = int(data.get("models_evaluated") or 0)
        if compared > 1:
            return (
                f"training attempt {output.attempt} compared {compared} models; "
                f"selected {data.get('selected_model')} on {output.metric}="
                f"{output.value}"
            )
        return (
            f"training attempt {output.attempt} finished "
            f"({output.metric}={output.value})"
        )


def experimenter_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`MLExperimentAgent`."""
    return MLExperimentAgent().node_update(state)
