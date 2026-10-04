"""Model Selector Agent (Phase 7).

Responsibility: choose a model family + hyperparameters given profile and
preprocessing constraints. No training — that is the ML Experiment Agent.

When the run asks for a model comparison (``compare_models``), this agent
proposes the shortlist that will actually be trained, ordered for the
*requested* objective rather than for accuracy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, ModelSpecOutput
from app.agents.state import ExperimentWorkflowState
from app.engine.metrics import is_higher_is_better

STAGE = "model_selector"

_SYSTEM = (
    "You are the AutoSage Model Selector Agent. "
    "Pick a model family and hyperparameters for the profiled task, optimizing "
    "the metric the request asked for. "
    "Return JSON matching the provided schema."
)

# Comparison shortlists per task type, most promising first for the metric
# named in each tuple. Only families the trainer implements are listed.
CLASSIFICATION_CANDIDATES: Dict[str, List[str]] = {
    "accuracy": ["gradient_boosting", "random_forest", "logistic_regression"],
    "recall": ["random_forest", "gradient_boosting", "logistic_regression"],
    "precision": ["logistic_regression", "gradient_boosting", "random_forest"],
    "f1": ["gradient_boosting", "random_forest", "logistic_regression"],
    "roc_auc": ["gradient_boosting", "random_forest", "logistic_regression"],
    "log_loss": ["logistic_regression", "gradient_boosting", "random_forest"],
}

REGRESSION_CANDIDATES: Dict[str, List[str]] = {
    "r2": ["gradient_boosting", "random_forest", "ridge"],
    "rmse": ["gradient_boosting", "random_forest", "ridge"],
    "mae": ["gradient_boosting", "random_forest", "ridge"],
    "mse": ["gradient_boosting", "random_forest", "ridge"],
}

DEFAULT_CLASSIFICATION_CANDIDATES = ["gradient_boosting", "random_forest", "logistic_regression"]
DEFAULT_REGRESSION_CANDIDATES = ["gradient_boosting", "random_forest", "ridge"]


def candidate_shortlist(task_type: str, primary_metric: str) -> List[str]:
    """Ordered candidate families to compare for ``task_type``/``primary_metric``."""
    table = REGRESSION_CANDIDATES if task_type == "regression" else CLASSIFICATION_CANDIDATES
    return list(table.get(primary_metric) or (
        DEFAULT_REGRESSION_CANDIDATES if task_type == "regression"
        else DEFAULT_CLASSIFICATION_CANDIDATES
    ))


def _model_params(task_type: str, primary_metric: str) -> Dict[str, Any]:
    """Neutral starting hyperparameters for the shortlist."""
    if task_type == "regression":
        return {"n_estimators": 100, "max_depth": 4}
    # Tree params shared by every boosting/forest candidate. class weighting is
    # what actually moves recall on imbalanced targets, so it is set when the
    # objective rewards catching the positive class.
    params: Dict[str, Any] = {"n_estimators": 100, "max_depth": 4}
    if primary_metric in {"recall", "f1", "precision"}:
        params["class_weight"] = "balanced"
    return params


class ModelSelectorAgent(BaseAgent):
    """Selects the model family and hyperparameters."""

    stage = STAGE
    output_model = ModelSpecOutput

    def model_tier(self) -> str:
        return "reasoning"

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        profile = state.get("profile") or {}
        spec = state.get("preprocessing_spec") or {}
        primary_metric = state.get("primary_metric") or "accuracy"
        compare_models = bool(state.get("compare_models"))
        direction = "higher" if is_higher_is_better(primary_metric) else "lower"
        candidates = candidate_shortlist(
            str(profile.get("task_type") or "classification"), primary_metric
        )
        compare_note = (
            "The run requests a MODEL COMPARISON: return every family in "
            f"`candidates` ({candidates}) and set `family` to the one you expect "
            "to win on the requested metric. Each candidate will be trained and "
            "measured; the winner is chosen on the requested metric, not accuracy."
            if compare_models
            else "The run trains a single model: set `family` to your pick and "
            "list alternates in `candidates`."
        )
        user = (
            "Select a model for this experiment.\n"
            f"REQUESTED METRIC (must be the optimization target): {primary_metric} "
            f"(higher is better: {direction})\n"
            f"compare_models: {compare_models}\n"
            f"profile={profile}\n"
            f"preprocessing={spec}\n"
            f"{compare_note}\n"
            f"Do not substitute a different metric (e.g. accuracy) for the "
            f"requested one."
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        profile = state.get("profile") or {}
        task = profile.get("task_type", "classification")
        primary_metric = state.get("primary_metric") or "accuracy"
        compare_models = bool(state.get("compare_models"))
        shortlist = candidate_shortlist(str(task), primary_metric)
        params = _model_params(str(task), primary_metric)

        if compare_models:
            return ModelSpecOutput(
                source="heuristic",
                family=shortlist[0],
                params=params,
                candidates=shortlist,
                rationale=(
                    f"Compare {len(shortlist)} classification families and select on "
                    f"{primary_metric} (accuracy kept as a secondary metric)."
                    if task != "regression"
                    else f"Compare {len(shortlist)} regression families and select on {primary_metric}."
                ),
            )

        if task == "regression":
            return ModelSpecOutput(
                source="heuristic",
                family=shortlist[0],
                params=params,
                candidates=shortlist,
                rationale=f"Heuristic: robust default for tabular regression on {primary_metric}.",
            )
        return ModelSpecOutput(
            source="heuristic",
            family=shortlist[0],
            params=params,
            candidates=shortlist,
            rationale=f"Heuristic: strong tabular default optimizing {primary_metric}.",
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, ModelSpecOutput)
        primary_metric = state.get("primary_metric") or "accuracy"
        compare_models = bool(state.get("compare_models"))
        candidates = list(output.candidates)
        # The comparison set is what gets trained; make sure the chosen family
        # is part of it so selection always has a complete shortlist.
        if compare_models and output.family not in candidates:
            candidates = [output.family, *candidates]
        return {
            "model_spec": {
                "family": output.family,
                "params": dict(output.params),
                "candidates": candidates,
                "rationale": output.rationale,
                "source": output.source,
                "primary_metric": primary_metric,
                "compare_models": compare_models,
            }
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, ModelSpecOutput)
        primary_metric = state.get("primary_metric") or "accuracy"
        compare = bool(state.get("compare_models"))
        if compare:
            return (
                f"model comparison planned: {len(output.candidates)} candidates, "
                f"selecting on {primary_metric}"
            )
        return f"model selected: {output.family} (target {primary_metric})"


def model_selector_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`ModelSelectorAgent`."""
    return ModelSelectorAgent().node_update(state)
