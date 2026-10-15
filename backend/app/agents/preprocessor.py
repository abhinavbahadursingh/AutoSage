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
        schema = state.get("dataset_schema") or {}
        columns = schema.get("columns") or []
        # Build a column list with kinds and stats
        col_lines = []
        for c in columns:
            name = c.get("name", "unknown")
            kind = c.get("kind", "unknown")
            null_rate = c.get("null_rate", 0.0)
            n_unique = c.get("n_unique", 0)
            col_lines.append(f"- {name} (kind={kind}, null_rate={null_rate}, n_unique={n_unique})")
        user = (
            "Design preprocessing for this dataset.\n"
            f"profile={profile}\n"
            f"columns:\n" + "\n".join(col_lines) + "\n"
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        profile = state.get("profile") or {}
        dataset = state.get("dataset_info") or {}
        schema = state.get("dataset_schema") or {}
        task_type = profile.get("task_type", "classification")
        target = profile.get("target_column", "")

        columns = schema.get("columns") or []
        # Determine column types from the schema
        numeric_cols = []
        categorical_cols = []
        id_cols = []
        for c in columns:
            name = c.get("name", "")
            kind = c.get("kind", "unknown")
            null_rate = c.get("null_rate", 0.0)
            if kind == "numeric":
                numeric_cols.append(name)
            elif kind in ("categorical", "boolean"):
                categorical_cols.append(name)
            elif kind == "unknown" and null_rate > 0.8:
                id_cols.append(name)  # likely an identifier

        # Default preprocessing based on task type and data characteristics
        imputation = "median" if numeric_cols else "most_frequent"
        encoding = "one-hot" if categorical_cols else "none"
        scaling = "standard" if numeric_cols else "none"
        outlier_handling = "iqr"
        feature_engineering = []
        drop_columns = id_cols  # drop likely identifiers

        rationale = (
            f"Defaults for {task_type} task "
            f"with {len(numeric_cols)} numeric and {len(categorical_cols)} categorical features."
        )

        return PreprocessingSpecOutput(
            source="heuristic",
            imputation=imputation,
            encoding=encoding,
            scaling=scaling,
            outlier_handling=outlier_handling,
            feature_engineering=feature_engineering,
            drop_columns=drop_columns,
            rationale=rationale,
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