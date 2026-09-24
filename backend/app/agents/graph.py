"""LangGraph workflow assembler (Phases 6-7).

Pipeline (each stage is a specialized agent node):

    orchestrator -> discovery -> profiler -> preprocessor -> model_selector
        -> ml_experiment -> verification -> conditional route:
            - "complete" (gate passed)            -> END
            - "retry"    (gate failed, attempts left) -> ml_experiment
            - "fail"     (gate failed, exhausted)     -> END (status FAILED)

State is checkpointed after every node (``MemorySaver`` by default; pass any
LangGraph checkpointer, e.g. Postgres, for durable runs). Thread id is
``experiment-<uuid>`` so each experiment run has an isolated checkpoint
history — see :mod:`app.agents.runner`.
"""
import logging
from typing import Any, Dict, Literal, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.discovery import discovery_node
from app.agents.experimenter import experimenter_node
from app.agents.model_selector import model_selector_node
from app.agents.orchestrator import orchestrator_node
from app.agents.preprocessor import preprocessor_node
from app.agents.profiler import profiler_node
from app.agents.state import ExperimentWorkflowState
from app.agents.verifier import verifier_node
from app.core.observability import (
    TimingContext,
    get_experiment_id,
    log_with_context,
    trace_operation,
)

logger = logging.getLogger("autosage.workflow")

# Canonical stage order (also the happy-path visit sequence).
STAGE_ORDER = [
    "orchestrator",
    "discovery",
    "profiler",
    "preprocessor",
    "model_selector",
    "ml_experiment",
    "verification",
]

RouteDecision = Literal["complete", "retry", "fail"]


def thread_id_for(experiment_id: str) -> str:
    """Checkpoint thread id isolating one experiment run's history."""
    return f"experiment-{experiment_id}"


def route_after_verification(state: ExperimentWorkflowState) -> RouteDecision:
    """Conditional edge: pass -> done, fail+attempts -> retry, else fail."""
    if state.get("verification_passed"):
        return "complete"
    attempt = int(state.get("attempt") or 0)
    max_attempts = int(state.get("max_attempts") or 1)
    if attempt < max_attempts:
        log_with_context(
            logger, logging.INFO, "workflow_verification_retry",
            attempt=attempt, max_attempts=max_attempts
        )
        return "retry"
    return "fail"


def mark_failed(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """Terminal node for exhausted verification retries (status FAILED)."""
    return {
        "current_stage": "failed",
        "stages_completed": ["failed"],
        "events": ["verification retries exhausted"],
        "status": "FAILED",
    }


def _wrap_node_with_observability(node_func, stage: str):
    """Wrap a node function with timing and tracing."""
    def wrapper(state: ExperimentWorkflowState):
        experiment_id = state.get("experiment_id") or get_experiment_id()
        with TimingContext(f"workflow_node.{stage}", extra_fields={"experiment": experiment_id, "stage": stage}):
            with trace_operation(f"langgraph.node.{stage}", attributes={"stage": stage, "experiment_id": experiment_id or ""}):
                log_with_context(logger, logging.INFO, "workflow_node_start", stage=stage, experiment=experiment_id)
                result = node_func(state)
                log_with_context(logger, logging.INFO, "workflow_node_complete", stage=stage, experiment=experiment_id)
                return result
    return wrapper


def build_experiment_graph(checkpointer: Optional[Any] = None):  # type: ignore[no-untyped-def]
    """Assemble + compile the experiment workflow graph.

    Args:
        checkpointer: LangGraph checkpointer (defaults to in-memory
            ``MemorySaver``). Supply a durable checkpointer for production.
    """
    workflow: StateGraph = StateGraph(ExperimentWorkflowState)
    workflow.add_node("orchestrator", _wrap_node_with_observability(orchestrator_node, "orchestrator"))
    workflow.add_node("discovery", _wrap_node_with_observability(discovery_node, "discovery"))
    workflow.add_node("profiler", _wrap_node_with_observability(profiler_node, "profiler"))
    workflow.add_node("preprocessor", _wrap_node_with_observability(preprocessor_node, "preprocessor"))
    workflow.add_node("model_selector", _wrap_node_with_observability(model_selector_node, "model_selector"))
    workflow.add_node("ml_experiment", _wrap_node_with_observability(experimenter_node, "ml_experiment"))
    workflow.add_node("verification", _wrap_node_with_observability(verifier_node, "verification"))
    workflow.add_node("failed", _wrap_node_with_observability(mark_failed, "failed"))

    workflow.add_edge(START, "orchestrator")
    workflow.add_edge("orchestrator", "discovery")
    workflow.add_edge("discovery", "profiler")
    workflow.add_edge("profiler", "preprocessor")
    workflow.add_edge("preprocessor", "model_selector")
    workflow.add_edge("model_selector", "ml_experiment")
    workflow.add_edge("ml_experiment", "verification")
    workflow.add_conditional_edges(
        "verification",
        route_after_verification,
        {"complete": END, "retry": "ml_experiment", "fail": "failed"},
    )
    workflow.add_edge("failed", END)

    return workflow.compile(checkpointer=checkpointer or MemorySaver())


# Backwards-compatible alias for the Phase 1 stub name.
def build_autosage_graph():  # type: ignore[no-untyped-def]
    """Legacy entry point — builds the experiment workflow graph."""
    return build_experiment_graph()
