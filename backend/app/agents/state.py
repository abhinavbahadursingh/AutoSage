"""AutoSage workflow state schema for LangGraph (Phase 6).

Single shared ``ExperimentWorkflowState`` threaded through every node of the
experiment pipeline::

    orchestrator -> discovery -> profiler -> preprocessor -> model_selector
        -> ml_experiment -> verification -> (complete | retry | fail)

Reducers (``operator.add``) merge per-node ``events`` / ``errors`` /
``tool_calls`` across steps so the full lifecycle trail survives
checkpointing. Each pipeline stage is a specialized agent (Phase 7) that
returns a structured Pydantic output through the provider-independent LLM
layer (Phase 8) — or a deterministic heuristic when no provider is
configured. Agents may invoke registered tools (Phase 9); each call is
appended to ``tool_calls`` for observability.
"""
from typing import Annotated, Any, Dict, List, Optional, TypedDict
import operator


class ExperimentWorkflowState(TypedDict, total=False):
    """Shared typed state for one experiment run."""

    # Identity / control
    experiment_id: str
    workspace_id: str
    attempt: int  # ml_experiment visits so far (drives verification routing)
    max_attempts: int  # verification passes allowed before failing the run
    current_stage: str  # last completed node name
    status: str  # mirrors Experiment.status for DB sync (RUNNING/COMPLETED/FAILED)

    # Lifecycle trail (append-only across nodes, survives checkpoints)
    stages_completed: Annotated[List[str], operator.add]
    events: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
    # Phase 9: Agent -> Tool -> Result audit trail (one entry per tool call)
    tool_calls: Annotated[List[Dict[str, Any]], operator.add]

    # Artefacts produced stage by stage by specialized agents
    # (structured Pydantic outputs — see app/agents/schemas.py).
    dataset_info: Dict[str, Any]
    profile: Dict[str, Any]
    preprocessing_spec: Dict[str, Any]
    model_spec: Dict[str, Any]
    ml_result: Dict[str, Any]
    verification: Dict[str, Any]
    verification_passed: bool

    # Test/ops hook: name of the stage that must raise (simulates failure).
    fail_stage: Optional[str]


def initial_workflow_state(
    *,
    experiment_id: str,
    workspace_id: str,
    max_attempts: int,
    fail_stage: Optional[str] = None,
) -> ExperimentWorkflowState:
    """Build the entry state for a fresh workflow run."""
    return {
        "experiment_id": experiment_id,
        "workspace_id": workspace_id,
        "attempt": 0,
        "max_attempts": max_attempts,
        "current_stage": "queued",
        "status": "RUNNING",
        "stages_completed": [],
        "events": [f"experiment {experiment_id} queued"],
        "errors": [],
        "tool_calls": [],
        "dataset_info": {},
        "profile": {},
        "preprocessing_spec": {},
        "model_spec": {},
        "ml_result": {},
        "verification": {},
        "verification_passed": False,
        "fail_stage": fail_stage,
    }
