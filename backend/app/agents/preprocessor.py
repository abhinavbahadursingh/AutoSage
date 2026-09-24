"""Preprocessor Agent (Phase 7).

Responsibility: propose a concrete cleaning / feature-engineering spec
(imputation, encoding, scaling, drops) from the profile.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, PreprocessingSpecOutput
from app.agents.state import ExperimentWorkflowState

STAGE = "preprocessor"

_SYSTEM = (
    "You are the AutoSage Preprocessor Agent. "
    "Design a preprocessing pipeline for the profiled dataset. "
    "Return JSON matching the provided schema."
)


class PreprocessorAgent(BaseAgent):
    """Builds the preprocessing specification."""

    stage = STAGE
    output_model = PreprocessingSpecOutput

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        profile = state.get("profile") or {}
        dataset = state.get("dataset_info") or {}
        user = (
            "Design preprocessing for this dataset.\n"
            f"profile={profile}\n"
            f"dataset={dataset}"
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        profile = state.get("profile") or {}
        dataset = state.get("dataset_info") or {}
        validation = self.call_tool(
            "validate_dataset",
            dataset_name=dataset.get("name"),
            rows=int(dataset.get("rows") or profile.get("n_rows") or 0),
            columns=list(dataset.get("columns") or []),
            target_column=dataset.get("target_column") or profile.get("target_column"),
        )
        issues = (validation.data or {}).get("issues") if validation.success else []
        issues_note = ""
        if issues:
            issues_note = f" Validation issues: {', '.join(map(str, issues))}."
        return PreprocessingSpecOutput(
            source="heuristic",
            imputation="median",
            encoding="one-hot",
            scaling="standard",
            outlier_handling="iqr",
            feature_engineering=[],
            drop_columns=[],
            rationale=(
                f"Defaults for {profile.get('task_type', 'unknown')} task "
                f"with missing_rate={profile.get('missing_rate', 0.0)}."
                f"{issues_note}"
            ),
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, PreprocessingSpecOutput)
        return {
            "preprocessing_spec": {
                "imputation": output.imputation,
                "encoding": output.encoding,
                "scaling": output.scaling,
                "outlier_handling": output.outlier_handling,
                "feature_engineering": list(output.feature_engineering),
                "drop_columns": list(output.drop_columns),
                "rationale": output.rationale,
                "source": output.source,
            }
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        return "preprocessing spec built"


def preprocessor_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`PreprocessorAgent`."""
    return PreprocessorAgent().node_update(state)
