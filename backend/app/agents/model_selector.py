"""Model Selector Agent (Phase 7).

Responsibility: choose a model family + hyperparameters given profile and
preprocessing constraints. No training — that is the ML Experiment Agent.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, ModelSpecOutput
from app.agents.state import ExperimentWorkflowState

STAGE = "model_selector"

_SYSTEM = (
    "You are the AutoSage Model Selector Agent. "
    "Pick a model family and hyperparameters for the profiled task. "
    "Return JSON matching the provided schema."
)


class ModelSelectorAgent(BaseAgent):
    """Selects the model family and hyperparameters."""

    stage = STAGE
    output_model = ModelSpecOutput

    def model_tier(self) -> str:
        return "reasoning"

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        profile = state.get("profile") or {}
        spec = state.get("preprocessing_spec") or {}
        user = (
            "Select a model for this experiment.\n"
            f"profile={profile}\n"
            f"preprocessing={spec}"
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        profile = state.get("profile") or {}
        task = profile.get("task_type", "classification")
        if task == "regression":
            return ModelSpecOutput(
                source="heuristic",
                family="gradient_boosting",
                params={"n_estimators": 100, "max_depth": 4, "objective": "regression"},
                candidates=["gradient_boosting", "random_forest", "ridge"],
                rationale="Heuristic: robust default for tabular regression.",
            )
        return ModelSpecOutput(
            source="heuristic",
            family="gradient_boosting",
            params={"n_estimators": 100, "max_depth": 4},
            candidates=["gradient_boosting", "random_forest", "logistic_regression"],
            rationale="Heuristic: strong default for tabular classification.",
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, ModelSpecOutput)
        return {
            "model_spec": {
                "family": output.family,
                "params": dict(output.params),
                "candidates": list(output.candidates),
                "rationale": output.rationale,
                "source": output.source,
            }
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, ModelSpecOutput)
        return f"model selected: {output.family}"


def model_selector_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`ModelSelectorAgent`."""
    return ModelSelectorAgent().node_update(state)
