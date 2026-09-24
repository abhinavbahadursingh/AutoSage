"""Profiler Agent (Phase 7).

Responsibility: turn the discovered dataset into a statistical/semantic
profile (task type, balance, missingness, feature types).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, DatasetDiscoveryOutput, ProfileOutput
from app.agents.state import ExperimentWorkflowState

STAGE = "profiler"

_SYSTEM = (
    "You are the AutoSage Profiler Agent. "
    "Infer task type, target, and dataset statistics from discovery output. "
    "Return JSON matching the provided schema."
)


class ProfilerAgent(BaseAgent):
    """Profiles the dataset discovered upstream."""

    stage = STAGE
    output_model = ProfileOutput

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        dataset = state.get("dataset_info") or {}
        user = (
            "Profile this dataset.\n"
            f"dataset={dataset}\n"
            f"experiment_id={state.get('experiment_id')}"
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        dataset = state.get("dataset_info") or {}
        columns = list(dataset.get("columns") or ["feature_a", "feature_b", "target"])
        target = dataset.get("target_column") or "target"
        n_features = max(len([c for c in columns if c != target]), 0)

        profile = self.call_tool(
            "profile_dataset",
            dataset_name=dataset.get("name") or "unknown",
            rows=int(dataset.get("rows") or 0),
            columns=columns,
            target_column=target,
        )
        if profile.success and profile.data:
            data = profile.data
            return ProfileOutput(
                source="heuristic",
                task_type=data.get("task_type", "classification"),
                target_column=str(data.get("target_column") or target),
                n_rows=int(data.get("n_rows") or 0),
                n_features=int(data.get("n_features") or n_features),
                missing_rate=float(data.get("missing_rate") or 0.0),
                feature_types=dict(data.get("feature_types") or {}),
                summary=str(data.get("summary") or ""),
            )

        return ProfileOutput(
            source="heuristic",
            task_type="classification",
            target_column=target,
            n_rows=int(dataset.get("rows") or 0),
            n_features=n_features,
            missing_rate=0.0,
            feature_types={c: "numeric" for c in columns if c != target},
            summary="Heuristic profile: balanced classification table.",
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, ProfileOutput)
        return {
            "profile": {
                "task_type": output.task_type,
                "target_column": output.target_column,
                "n_rows": output.n_rows,
                "n_features": output.n_features,
                "missing_rate": output.missing_rate,
                "class_balance": output.class_balance,
                "feature_types": output.feature_types,
                "summary": output.summary,
                "source": output.source,
                # Legacy key used by Phase 6 tests / result summaries:
                "rows": output.n_rows,
            }
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, ProfileOutput)
        return f"dataset profiled ({output.task_type})"


def profiler_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`ProfilerAgent`."""
    return ProfilerAgent().node_update(state)
