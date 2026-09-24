"""Unit tests: LangGraph workflow architecture (no infra required).

Covers: shared state construction, every placeholder node, the
fail_stage hook, conditional routing, graph structure (nodes/edges),
checkpointing, and the runner's JSON-safe output.
"""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents import graph as graph_module
from app.agents.discovery import discovery_node
from app.agents.experimenter import experimenter_node
from app.agents.graph import (
    STAGE_ORDER,
    build_experiment_graph,
    route_after_verification,
    thread_id_for,
)
from app.agents.model_selector import model_selector_node
from app.agents.orchestrator import orchestrator_node
from app.agents.preprocessor import preprocessor_node
from app.agents.profiler import profiler_node
from app.agents.runner import get_workflow_snapshot, run_experiment_workflow
from app.agents.state import initial_workflow_state
from app.agents.verifier import verifier_node


def _state(**overrides):  # type: ignore[no-untyped-def]
    base = initial_workflow_state(
        experiment_id="exp-1", workspace_id="ws-1", max_attempts=2
    )
    base.update(overrides)
    return base


# -- state -----------------------------------------------------------------
def test_initial_state_defaults() -> None:
    state = initial_workflow_state(experiment_id="e", workspace_id="w", max_attempts=2)
    assert state["attempt"] == 0
    assert state["status"] == "RUNNING"
    assert state["stages_completed"] == []
    assert state["verification_passed"] is False
    assert state["events"] == ["experiment e queued"]


# -- nodes -----------------------------------------------------------------
def test_nodes_fill_their_slots_in_order() -> None:
    from typing import Any, Dict

    state = _state()
    completed = []

    def visit(node) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
        out = node(state)
        # Plain dict.update would replace reducer lists; accumulate like
        # LangGraph's operator.add reducer does.
        completed.extend(out.get("stages_completed", []))
        state.update(out)
        return out

    visit(orchestrator_node)
    assert state["current_stage"] == "orchestrator"

    visit(discovery_node)
    assert state["dataset_info"]["rows"] == 1000

    visit(profiler_node)
    assert state["profile"]["task_type"] == "classification"

    visit(preprocessor_node)
    assert state["preprocessing_spec"]["scaling"] == "standard"

    visit(model_selector_node)
    assert state["model_spec"]["family"] == "gradient_boosting"

    visit(experimenter_node)
    assert state["attempt"] == 1
    assert state["ml_result"]["value"] == 0.87

    visit(verifier_node)
    assert state["verification_passed"] is True
    assert state["status"] == "COMPLETED"
    assert completed == STAGE_ORDER


@pytest.mark.parametrize(
    "node,stage",
    [
        (orchestrator_node, "orchestrator"),
        (discovery_node, "discovery"),
        (profiler_node, "profiler"),
        (preprocessor_node, "preprocessor"),
        (model_selector_node, "model_selector"),
        (experimenter_node, "ml_experiment"),
        (verifier_node, "verification"),
    ],
)
def test_fail_stage_hook_raises(node, stage) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(RuntimeError, match=stage):
        node(_state(fail_stage=stage))


# -- routing ---------------------------------------------------------------
def test_router_completes_on_pass() -> None:
    assert route_after_verification(_state(verification_passed=True)) == "complete"


def test_router_retries_while_attempts_remain() -> None:
    assert route_after_verification(_state(attempt=1, max_attempts=2)) == "retry"


def test_router_fails_when_exhausted() -> None:
    assert route_after_verification(_state(attempt=2, max_attempts=2)) == "fail"


def test_thread_ids_isolate_experiments() -> None:
    assert thread_id_for("a") == "experiment-a"
    assert thread_id_for("a") != thread_id_for("b")


# -- graph structure ---------------------------------------------------------
def test_graph_has_all_nodes_and_linear_edges() -> None:
    graph = build_experiment_graph()
    structure = graph.get_graph()
    assert set(structure.nodes) >= set(STAGE_ORDER) | {"failed"}
    edge_pairs = {(e.source, e.target) for e in structure.edges}
    linear = [
        ("__start__", "orchestrator"),
        ("orchestrator", "discovery"),
        ("discovery", "profiler"),
        ("profiler", "preprocessor"),
        ("preprocessor", "model_selector"),
        ("model_selector", "ml_experiment"),
        ("ml_experiment", "verification"),
        ("failed", "__end__"),
    ]
    for source, target in linear:
        assert (source, target) in edge_pairs, f"missing edge {source} -> {target}"
    # Conditional fan-out from verification: complete/retry/fail.
    verification_targets = {t for s, t in edge_pairs if s == "verification"}
    assert verification_targets == {"__end__", "ml_experiment", "failed"}


def test_legacy_graph_alias_still_builds() -> None:
    assert graph_module.build_autosage_graph() is not None


# -- checkpointing + runner ----------------------------------------------------
def test_checkpoint_records_lifecycle() -> None:
    saver = MemorySaver()
    graph = build_experiment_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": thread_id_for("ckpt-1")}}
    final = graph.invoke(
        initial_workflow_state(
            experiment_id="ckpt-1", workspace_id="w", max_attempts=2
        ),
        config=config,
    )
    assert final["status"] == "COMPLETED"

    # A second compiled graph over the same saver sees the checkpoint.
    snapshot = get_workflow_snapshot(
        build_experiment_graph(checkpointer=saver), "ckpt-1"
    )
    assert snapshot["values"]["status"] == "COMPLETED"
    assert snapshot["values"]["stages_completed"] == STAGE_ORDER
    assert snapshot["checkpoint_id"]
    assert snapshot["next"] == []  # run finished: nothing scheduled


def test_get_snapshot_empty_without_history() -> None:
    graph = build_experiment_graph(checkpointer=MemorySaver())
    assert get_workflow_snapshot(graph, "never-ran") == {}


def test_runner_happy_path_is_json_safe() -> None:
    import json

    final = run_experiment_workflow(
        experiment_id="run-1", workspace_id="w", max_attempts=2
    )
    assert final["status"] == "COMPLETED"
    assert final["attempt"] == 1
    json.dumps(final)  # must survive the json result backend


def test_runner_propagates_stage_failure() -> None:
    with pytest.raises(RuntimeError, match="profiler"):
        run_experiment_workflow(
            experiment_id="run-2", workspace_id="w", fail_stage="profiler"
        )
