"""Profiler Agent (Phase 7).

Responsibility: turn the discovered dataset into a statistical/semantic
profile (task type, balance, missingness, feature types) and **resolve the
target column**.

Target resolution lives here because this is the first stage that holds the
real column metadata (Discovery only located the file). The resolved, validated
target is then published to workflow state so the trainer, evaluator and
verifier all work from the same column — none of them re-guesses it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, DatasetDiscoveryOutput, ProfileOutput
from app.agents.state import ExperimentWorkflowState
from app.engine.targeting import (
    DatasetSchema,
    TargetResolution,
    TargetResolutionError,
    resolve_and_validate,
)

logger = logging.getLogger("autosage.workflow")

STAGE = "profiler"

_SYSTEM = (
    "You are the AutoSage Profiler Agent. "
    "Infer task type, target, and dataset statistics from discovery output. "
    "Return JSON matching the provided schema."
)


def _schema_from_state(state: ExperimentWorkflowState) -> Optional[DatasetSchema]:
    """Rebuild the real :class:`DatasetSchema` Discovery published."""
    raw = state.get("dataset_schema") or {}
    columns = raw.get("columns") or []
    if not columns:
        return None
    from app.engine.targeting import ColumnProfile

    profiles = tuple(
        ColumnProfile(
            name=str(c.get("name") or ""),
            kind=str(c.get("kind") or "unknown"),  # type: ignore[arg-type]
            n_unique=int(c.get("n_unique") or 0),
            null_rate=float(c.get("null_rate") or 0.0),
            n_rows=int(raw.get("n_rows") or 0),
        )
        for c in columns
        if c.get("name")
    )
    if not profiles:
        return None
    return DatasetSchema(
        columns=profiles, n_rows=int(raw.get("n_rows") or 0), source=str(raw.get("source") or "")
    )


class ProfilerAgent(BaseAgent):
    """Profiles the dataset discovered upstream."""

    stage = STAGE
    output_model = ProfileOutput

    def model_tier(self) -> str:
        return "reasoning"

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        """Prompt grounded in the real schema, asking for the target column.

        The model is shown the actual columns, their kinds and the user's
        objective. Its answer is a *proposal* that
        :func:`app.engine.targeting.resolve_and_validate` then checks against
        the file — a hallucinated column name cannot survive validation.
        """
        dataset = state.get("dataset_info") or {}
        schema = state.get("dataset_schema") or {}
        config = state.get("config") or {}
        columns = "\n".join(
            f"- {c.get('name')} (kind={c.get('kind')}, distinct={c.get('n_unique')}, "
            f"null_rate={c.get('null_rate')})"
            for c in (schema.get("columns") or [])
        ) or "- (schema unavailable)"
        user = (
            "Profile this dataset and choose the target column.\n"
            f"rows={schema.get('n_rows', dataset.get('rows'))}\n"
            f"task_type={config.get('task_type') or dataset.get('task_hint') or 'classification'}\n"
            f"objective={config.get('prompt') or 'not stated'}\n"
            f"columns:\n{columns}\n"
            f"experiment_id={state.get('experiment_id')}"
        )
        return _SYSTEM, user

    # -- target resolution ----------------------------------------------------
    def _resolve_target(self, state: ExperimentWorkflowState) -> Optional[TargetResolution]:
        """Resolve + validate the target from the real schema.

        Returns None when no schema is available (the caller then reports the
        profile without a target rather than inventing one).

        If the config supplies a ``target_column`` that does not exist in the
        actual dataset schema, the hint is cleared so the resolver falls back
        to the objective/prompt and the real columns — rather than failing with
        a false "column not found" error from a stale config value.
        """
        schema = _schema_from_state(state)
        if schema is None or not schema.columns:
            return None

        config = state.get("config") or {}
        objective = str(config.get("prompt") or "")
        hint = config.get("target_column")
        task_type = str(config.get("task_type") or (state.get("dataset_info") or {}).get("task_hint") or "")

        # --- Validate hint against actual schema --------------------------------
        # Normalize column names the same way resolve_target does, so "Churn"
        # in the file matches "churn" in the hint.
        from app.engine.targeting import normalize_name
        schema_names = {normalize_name(c.name) for c in schema.columns}
        hint_normalized = normalize_name(hint) if hint else None

        # If the hint is present but not found in the schema, clear it.
        # This prevents a stale target_column from a previous experiment
        # (e.g. "churn" from a former dataset) from causing a false "not found"
        # error when a new dataset with different columns is used.
        if hint and hint_normalized not in schema_names:
            # Remove the stale target_column from config so the resolver
            # uses the objective + real columns instead.
            config.pop("target_column", None)
            # Also clear it from the state payload so it doesn't persist
            # back to the experiment record.
            state["config"] = config

        proposal = None
        try:
            proposed = self.run_model_only(state)
            if proposed is not None:
                proposal = proposed
        except Exception:  # noqa: BLE001 - a model opinion is optional evidence
            proposal = None

        return resolve_and_validate(
            schema,
            objective=objective,
            hint=str(hint).strip() if hint else None,
            task_type=task_type,
            proposal=proposal,
        )

    def run_model_only(self, state: ExperimentWorkflowState) -> Optional[str]:
        """Ask the model for a target column; None when no provider is usable."""
        client = self._client()
        if not client.has_providers():
            return None
        try:
            system, user = self.build_prompts(state)
            output = client.complete_structured_sync(
                system=system,
                user=user,
                response_model=self.output_model,
                model_tier=self.model_tier(),
            )
            return str(getattr(output, "target_column", "") or "").strip() or None
        except Exception as exc:  # noqa: BLE001 - optional evidence only
            logger.info("profiler_target_proposal_unavailable", extra={"error": str(exc)})
            return None

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        dataset = state.get("dataset_info") or {}
        schema = _schema_from_state(state)
        columns = list(schema.names()) if schema else list(dataset.get("columns") or [])
        resolution = self._resolve_target(state)
        target = (resolution.column if resolution else None) or dataset.get("target_column") or ""
        n_features = max(len([c for c in columns if c != target]), 0)

        profile = self.call_tool(
            "profile_dataset",
            dataset_name=dataset.get("name") or "unknown",
            rows=int((schema.n_rows if schema else dataset.get("rows")) or 0),
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
            n_rows=int((schema.n_rows if schema else dataset.get("rows")) or 0),
            n_features=n_features,
            missing_rate=0.0,
            feature_types={c: "numeric" for c in columns if c != target},
            summary="Heuristic profile: balanced classification table.",
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, ProfileOutput)
        profile = {
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
        payload: Dict[str, Any] = {"profile": profile}

        # Publish the resolution verdict, not just the column. Downstream
        # stages read `target_column` and must refuse to train unless
        # `target_resolution.status == "resolved"`.
        resolution = self._resolve_target(state)
        if resolution is not None:
            payload["target_resolution"] = resolution.to_dict()
            if resolution.ok and resolution.column:
                profile["target_column"] = resolution.column
                payload["target_column"] = resolution.column
            else:
                # Unresolved/ambiguous: park, never guess.
                profile["target_column"] = None
                payload["target_column"] = None
                payload["target_required"] = True
                payload["errors"] = [resolution.reason]
                payload["events"] = [resolution.reason]
        return payload

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, ProfileOutput)
        return f"dataset profiled ({output.task_type})"


def profiler_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`ProfilerAgent`."""
    return ProfilerAgent().node_update(state)
