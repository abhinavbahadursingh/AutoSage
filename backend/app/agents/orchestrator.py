"""Orchestrator node — workflow entry point (Phase 7).

Keeps run bookkeeping (attempt reset, lifecycle event). Planning/delegation
policy lives here in later phases; domain intelligence is delegated to the
six specialized agents downstream.
"""
from __future__ import annotations

from typing import Any, Dict

from app.agents.base import check_fail_stage, stage_update
from app.agents.state import ExperimentWorkflowState
from app.engine.tools import get_default_registry

STAGE = "orchestrator"


def orchestrator_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """Entry bookkeeping before specialized agents run."""
    check_fail_stage(state, STAGE)

    # Phase 9: pull prior memory for this experiment (stub store today).
    memory = get_default_registry().execute(
        "retrieve_memory",
        query=f"experiment {state.get('experiment_id')}",
        limit=5,
        workspace_id=state.get("workspace_id"),
    )
    tool_calls = [
        {
            "tool": "retrieve_memory",
            "stage": STAGE,
            "success": memory.success,
            "error_type": memory.error_type,
            "duration_ms": memory.duration_ms,
        }
    ]

    return stage_update(
        state,
        STAGE,
        f"experiment {state.get('experiment_id')} orchestrated",
        attempt=0,
        tool_calls=tool_calls,
    )
