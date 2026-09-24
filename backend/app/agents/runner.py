"""Workflow runner — bridge between Celery tasks and LangGraph (Phases 6-7).

Owns: initial-state construction, graph invocation with per-experiment
checkpoint threads, checkpoint inspection (lifecycle tracking), and
JSON-safe result extraction for DB sync. Agent intelligence lives in the
node modules; LLM access is resolved per-agent via
:func:`app.engine.llm.client.get_llm_client` (injectable in tests with
:func:`set_llm_client`).
"""
import logging
from typing import Any, Dict, Optional

from app.agents.graph import build_experiment_graph, thread_id_for
from app.agents.state import ExperimentWorkflowState, initial_workflow_state
from app.core.config import settings
from app.core.observability import (
    TimingContext,
    experiment_context,
    log_with_context,
    trace_operation,
)

logger = logging.getLogger("autosage.workflow")


def run_experiment_workflow(
    *,
    experiment_id: str,
    workspace_id: str,
    max_attempts: Optional[int] = None,
    fail_stage: Optional[str] = None,
    checkpointer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute the full workflow synchronously; return the final state.

    Raises whatever the failing node raised (the Celery task maps it to
    FAILED/RETRYING + backoff). ``fail_stage`` injects a mock failure and is
    honored from explicit arg or ``config["mock_fail_stage"]`` by callers.
    """
    graph = build_experiment_graph(checkpointer=checkpointer)
    initial: ExperimentWorkflowState = initial_workflow_state(
        experiment_id=experiment_id,
        workspace_id=workspace_id,
        max_attempts=max_attempts or settings.WORKFLOW_MAX_ATTEMPTS,
        fail_stage=fail_stage,
    )
    config = {"configurable": {"thread_id": thread_id_for(experiment_id)}}
    
    with experiment_context(experiment_id):
        with TimingContext("workflow_execution", extra_fields={"experiment": experiment_id}):
            with trace_operation("langgraph.workflow", attributes={"experiment_id": experiment_id}):
                log_with_context(logger, logging.INFO, "workflow_start", experiment=experiment_id)
                final_state = graph.invoke(initial, config=config)
                log_with_context(
                    logger, logging.INFO, "workflow_done",
                    experiment=experiment_id, status=final_state.get("status")
                )
    return dict(final_state)


def get_workflow_snapshot(graph: Any, experiment_id: str) -> Dict[str, Any]:
    """Read the latest checkpoint for an experiment (lifecycle tracking).

    Returns ``{"values": ..., "next": [...], "checkpoint_id": ...}`` or an
    empty dict when nothing was checkpointed yet.
    """
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id_for(experiment_id)}})
    if snapshot is None or not snapshot.values:
        return {}
    return {
        "values": dict(snapshot.values),
        "next": list(snapshot.next),
        "checkpoint_id": str(snapshot.config.get("configurable", {}).get("checkpoint_id")),
    }
