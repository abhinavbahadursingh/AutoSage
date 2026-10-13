"""Dataset Discovery Agent (Phase 7).

Responsibility: locate the experiment dataset and emit a typed description
(name, shape, columns, target hint). No profiling — that is the Profiler.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, DatasetDiscoveryOutput
from app.agents.state import ExperimentWorkflowState
from app.engine.targeting import (
    DatasetSchema,
    TargetResolutionError,
    normalize_name,
    read_schema,
)

logger = logging.getLogger("autosage.workflow")

STAGE = "discovery"

# Shown when a run named no dataset at all. It is a prompt for the user, never
# a filename — the UI renders it verbatim in the upload dialog.
UNNAMED_DATASET_LABEL = "no dataset selected"

_SYSTEM = (
    "You are the AutoSage Dataset Discovery Agent. "
    "Given experiment context, describe the dataset to use. "
    "Return JSON matching the provided schema."
)


def _requested_dataset_name(state: ExperimentWorkflowState) -> str:
    """The dataset filename this run asked for, or '' when unspecified."""
    config = state.get("config") or {}
    name = config.get("dataset_name") or config.get("dataset") or ""
    return str(name).strip()


def _dataset_available(state: ExperimentWorkflowState, name: str) -> bool:
    """Whether the worker can actually open ``name`` for this run.

    Uses the same resolution the ML tool uses, so Discovery and training can
    never disagree about whether the dataset exists. Any resolution error is
    reported as "not available" — this stage must never raise.
    """
    try:
        from app.engine.tools.ml import resolve_dataset_path

        resolve_dataset_path(
            name,
            dataset_path=(state.get("config") or {}).get("dataset_path"),
            experiment_id=state.get("experiment_id"),
        )
        return True
    except Exception:  # noqa: BLE001 - any resolution failure means "missing"
        return False


def _describe_real_dataset(
    state: ExperimentWorkflowState, name: str
) -> Optional[DatasetDiscoveryOutput]:
    """Describe the run's real dataset, or None when it cannot be read.

    Discovery is the first stage that can legitimately touch the file, so this
    is where the true column names enter the workflow. Everything downstream
    (target resolution, preprocessing, training) works from these names rather
    than from a mock catalog.
    """
    config = state.get("config") or {}
    try:
        from app.engine.tools.ml import resolve_dataset_path

        path = resolve_dataset_path(
            name, dataset_path=config.get("dataset_path"), experiment_id=state.get("experiment_id")
        )
        schema = read_schema(path)
    except TargetResolutionError as exc:
        # The file exists but could not be parsed. That is a hard problem the
        # user must fix, not something to paper over with mock columns.
        raise TargetResolutionError(
            f"could not read dataset {name!r}: {exc}", columns=exc.columns
        ) from exc
    except Exception as exc:  # noqa: BLE001 - resolution failure -> fall through
        logger.info("discovery_schema_unavailable", extra={"dataset": name, "error": str(exc)})
        return None

    _SCHEMA_CACHE[_cache_key(name)] = schema

    return DatasetDiscoveryOutput(
        source="heuristic",
        dataset_name=name,
        rows=schema.n_rows,
        columns=schema.names(),
        target_column=config.get("target_column"),
        source_type="upload",
        task_hint=config.get("task_type"),
    )


# Schema cache keyed by dataset name. Profiling re-reads the schema on every
# verification retry, and parsing the file each time is wasted IO.
_SCHEMA_CACHE: Dict[str, Any] = {}


def _cache_key(name: str) -> str:
    return normalize_name(name)


def schema_for(state: ExperimentWorkflowState) -> Optional[DatasetSchema]:
    """Return the run's real schema, reading (and caching) it if needed."""
    name = _requested_dataset_name(state)
    if not name:
        return None
    cached = _SCHEMA_CACHE.get(_cache_key(name))
    if cached is not None:
        return cached
    described = _describe_real_dataset(state, name)
    if described is None:
        return None
    return _SCHEMA_CACHE.get(_cache_key(name))


class DiscoveryAgent(BaseAgent):
    """Finds/registers the dataset for an experiment run."""

    stage = STAGE
    output_model = DatasetDiscoveryOutput

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        user = (
            "Describe the dataset for this experiment.\n"
            f"experiment_id={state.get('experiment_id')}\n"
            f"config={state.get('config') or {}}"
        )
        return _SYSTEM, user

    def run(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Gate on dataset availability before consulting the LLM or catalog.

        The dataset search agent cannot resolve a file that was never uploaded
        (it is under maintenance, or the catalog does not know it). Checking
        here means the gate holds on *both* the LLM and heuristic paths —
        otherwise a hallucinated description would let the pipeline train on a
        dataset that does not exist.

        A run that named *no* dataset parks too. That is the normal path when
        the user starts a run without attaching a file: the pipeline waits here
        and the UI asks for one. Previously an empty name skipped the gate and
        fell through to the catalog stub, which answered with the synthetic
        ``mock_dataset.csv`` — the pipeline then "trained" on rows that were
        never read, and the run surfaced minutes later as a baffling
        verification failure. Asking is always honest; inventing is not.
        """
        requested = _requested_dataset_name(state)
        if not requested or not _dataset_available(state, requested):
            return DatasetDiscoveryOutput(
                source="heuristic",
                dataset_name=requested or UNNAMED_DATASET_LABEL,
                rows=0,
                columns=[],
                target_column=(state.get("config") or {}).get("target_column"),
                source_type="missing",
                task_hint=None,
            )

        # Column names, row counts and dtypes are *facts about the file*, not
        # something a completion model should produce. When the real file can be
        # read we describe it directly and skip the LLM entirely -- otherwise
        # every downstream stage (target resolution, preprocessing, training)
        # would reason about invented columns.
        described = _describe_real_dataset(state, requested)
        if described is not None:
            return described

        # Unreadable file: fall back to the catalog/LLM path rather than fail,
        # so the run still reports something the user can act on.
        return super().run(state)

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        # `run` already described the real file when it could; reaching here
        # means the file was unreadable, so fall back to the catalog.
        # Prefer the registered search/download tools; fall back to defaults.
        query = str(state.get("experiment_id") or "dataset")
        search = self.call_tool("search_dataset", query=query, limit=1)
        matches = (search.data or {}).get("matches") if search.success else None
        if not matches:
            # Broad catalog probe so the tool path stays exercised in tests.
            search = self.call_tool("search_dataset", query="dataset", limit=1)
            matches = (search.data or {}).get("matches") if search.success else None

        if matches:
            match = matches[0]
            self.call_tool("download_dataset", dataset_id=match["dataset_id"])
            return DatasetDiscoveryOutput(
                source="heuristic",
                dataset_name=match["name"],
                rows=int(match["rows"]),
                columns=list(match["columns"]),
                target_column=match.get("target_column"),
                source_type=str(match.get("source") or "upload"),
                task_hint=match.get("task_hint"),
            )

        # Deterministic stand-in until real uploads/connectors land.
        return DatasetDiscoveryOutput(
            source="heuristic",
            dataset_name="mock_dataset.csv",
            rows=1000,
            columns=["feature_a", "feature_b", "target"],
            target_column="target",
            source_type="mock",
            task_hint="classification",
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, DatasetDiscoveryOutput)
        payload: Dict[str, Any] = {
            "dataset_info": {
                "name": output.dataset_name,
                "rows": output.rows,
                "columns": list(output.columns),
                "target_column": output.target_column,
                "source": output.source_type,
                "task_hint": output.task_hint,
                "agent_source": output.source,
            }
        }
        # Carry the real column metadata forward so target resolution and
        # preprocessing work from the file rather than re-reading it.
        schema = _SCHEMA_CACHE.get(_cache_key(output.dataset_name))
        if schema is not None:
            payload["dataset_schema"] = schema.to_dict()
        if output.source_type == "missing":
            # Park the run: the workflow stops here and the UI asks for the
            # file rather than profiling a stand-in dataset.
            missing = output.dataset_name
            payload.update(
                {
                    "dataset_required": True,
                    "dataset_missing_name": missing,
                    "errors": [f"dataset not found by the discovery agent: {missing}"],
                    "events": [f"awaiting dataset upload: {missing}"],
                }
            )
        return payload

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, DatasetDiscoveryOutput)
        if output.source_type == "missing":
            return f"dataset unavailable: {output.dataset_name} — upload required"
        return f"dataset discovered: {output.dataset_name} ({output.rows} rows)"


def discovery_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`DiscoveryAgent`."""
    return DiscoveryAgent().node_update(state)
