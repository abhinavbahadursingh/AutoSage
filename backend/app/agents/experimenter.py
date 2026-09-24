"""ML Experiment Agent (Phase 7).

Responsibility: drive one training attempt. **Actual ML execution is out of
scope** for Phase 7 — this agent plans the attempt via the LLM layer and
records a structured experiment result (metric/value) that the Verification
Agent can gate on. Sandboxed training lands in a later phase.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, MLExperimentOutput
from app.agents.state import ExperimentWorkflowState

STAGE = "ml_experiment"

_SYSTEM = (
    "You are the AutoSage ML Experiment Agent. "
    "Plan one training attempt for the selected model and predict/report the "
    "primary metric. Real training is not executed yet. "
    "Return JSON matching the provided schema."
)


class MLExperimentAgent(BaseAgent):
    """Plans/records a single training attempt (ML execution deferred)."""

    stage = STAGE
    output_model = MLExperimentOutput

    def model_tier(self) -> str:
        return "reasoning"

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        model_spec = state.get("model_spec") or {}
        profile = state.get("profile") or {}
        attempt = int(state.get("attempt") or 0) + 1
        user = (
            "Plan training attempt "
            f"#{attempt}.\nmodel_spec={model_spec}\nprofile={profile}"
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        attempt = int(state.get("attempt") or 0) + 1
        profile = state.get("profile") or {}
        dataset = state.get("dataset_info") or {}
        model_spec = state.get("model_spec") or {}
        metric = "r2" if profile.get("task_type") == "regression" else "accuracy"
        # Stable placeholder score until sandboxed training exists.
        value = 0.87 if metric == "accuracy" else 0.81

        job = self.call_tool(
            "execute_ml_job",
            model_family=str(model_spec.get("family") or "gradient_boosting"),
            dataset_name=str(dataset.get("name") or "mock_dataset.csv"),
            metric=metric,
            attempt=attempt,
            experiment_id=state.get("experiment_id"),
        )
        job_note = ""
        if job.success and job.data.get("job_id"):
            job_note = f" job_id={job.data['job_id']}"

        return MLExperimentOutput(
            source="heuristic",
            metric=metric,
            value=value,
            validation_strategy="holdout",
            notes=(
                "Heuristic result — real training deferred to sandbox phase."
                f"{job_note}"
            ),
            attempt=attempt,
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, MLExperimentOutput)
        return {
            "attempt": output.attempt,
            "ml_result": {
                "metric": output.metric,
                "value": output.value,
                "validation_strategy": output.validation_strategy,
                "notes": output.notes,
                "attempt": output.attempt,
                "source": output.source,
            },
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, MLExperimentOutput)
        return (
            f"training attempt {output.attempt} finished "
            f"({output.metric}={output.value})"
        )


def experimenter_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`MLExperimentAgent`."""
    return MLExperimentAgent().node_update(state)
