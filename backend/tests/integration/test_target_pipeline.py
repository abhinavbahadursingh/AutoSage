"""End-to-end target resolution through the real pipeline.

The unit tests cover the resolver in isolation. These run the *actual*
LangGraph workflow against real CSV files, which is where the original bug lived:
the pipeline guessed the target and only discovered the mistake inside the
trainer, long after the user had left the form.

Each case varies the target name, its casing, its column type, and the ML
objective. None of them share a naming convention with the other.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.agents.graph import route_after_discovery, route_after_profiling
from app.agents.state import initial_workflow_state


def write_dataset(path: str, header: str, rows: List[str]) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join([header, *rows]) + "\n")
    return path


@pytest.fixture()
def casing_dataset(tmp_path: Any) -> Dict[str, Any]:
    """Target uses the OPPOSITE casing from what the request names."""
    path = write_dataset(
        str(tmp_path / "retention.csv"),
        "id,tenure_month,monthly_bill,IS_CHURNING",
        [f"{i},{(i % 40) + 1},{50 + (i % 60)},{i % 2}" for i in range(120)],
    )
    return {
        "path": path,
        "name": "retention.csv",
        # Request spells it the other way round on purpose.
        "hint": "is_churning",
        "objective": "find customers who are about to churn and flag them",
    }


@pytest.fixture()
def regression_dataset(tmp_path: Any) -> Dict[str, Any]:
    """Regression target with a name that shares no prefix with the objective."""
    path = write_dataset(
        str(tmp_path / "listings.csv"),
        "listing_id,bedrooms,floor_area,walk_score,ask",
        [
            f"L{i:04d},{(i % 4) + 1},{40 + (i % 120)},{50 + (i % 60)},{120 + (i % 380)}"
            for i in range(120)
        ],
    )
    return {
        "path": path,
        "name": "listings.csv",
        "hint": None,
        "objective": "estimate the ask for each listing",
    }


@pytest.fixture()
def ambiguous_dataset(tmp_path: Any) -> Dict[str, Any]:
    """Two equally plausible label columns -> must ask, never guess."""
    path = write_dataset(
        str(tmp_path / "fork.csv"),
        "record_id,tenure,left_company,renewed_contract",
        [f"R{i:03d},{i % 30},{(i % 2)},{(i % 2)}" for i in range(120)],
    )
    return {"path": path, "name": "fork.csv", "hint": None, "objective": "predict the outcome"}


def _run(config: Dict[str, Any]) -> Dict[str, Any]:
    from app.agents.runner import run_experiment_workflow
    import uuid

    return run_experiment_workflow(
        experiment_id=str(uuid.uuid4()),
        workspace_id=str(uuid.uuid4()),
        max_attempts=1,
        experiment_config=config,
    )


def _base(config: Dict[str, Any], dataset: Dict[str, Any]) -> Dict[str, Any]:
    merged = {
        "dataset_name": dataset["name"],
        "dataset_path": dataset["path"],
        "task_type": "classification",
        "primary_metric": "f1",
    }
    merged.update(config)
    return merged


# --------------------------------------------------------------------------
# Happy path: the pipeline runs end to end on the resolved target
# --------------------------------------------------------------------------

def test_pipeline_resolves_opposite_casing_target(casing_dataset: Dict[str, Any]) -> None:
    """`is_churning` requested, `IS_CHURNING` in the file -> pipeline trains."""
    config = _base(
        {
            "target_column": casing_dataset["hint"],
            "prompt": casing_dataset["objective"],
        },
        casing_dataset,
    )
    state = _run(config)

    assert state["target_resolution"]["status"] == "resolved"
    # The resolved column keeps the file's real spelling, not the request's.
    assert state["target_column"] == "IS_CHURNING"
    assert state["status"] != "AWAITING_TARGET"
    # Training actually ran, on the right column.
    assert state["ml_result"]["selected_model"]
    assert state["ml_result"]["target_column"] == "IS_CHURNING"
    assert state["ml_result"]["primary_score"] is not None


def test_pipeline_resolves_regression_target_from_objective(
    regression_dataset: Dict[str, Any]
) -> None:
    """No hint at all: the objective names the column in different casing."""
    config = _base(
        {
            "task_type": "regression",
            "primary_metric": "mae",
            "prompt": regression_dataset["objective"],
        },
        regression_dataset,
    )
    state = _run(config)

    assert state["target_resolution"]["status"] == "resolved"
    assert state["target_column"] == "ask"
    assert state["status"] != "AWAITING_TARGET"
    assert state["ml_result"]["selected_model"]
    assert state["ml_result"]["target_column"] == "ask"
    assert state["profile"]["target_column"] == "ask"


# --------------------------------------------------------------------------
# Ambiguity: the pipeline must stop and ask, never guess
# --------------------------------------------------------------------------

def test_pipeline_parks_on_ambiguous_target(ambiguous_dataset: Dict[str, Any]) -> None:
    """Two equally plausible columns, no objective signal -> ask the user."""
    config = _base({"prompt": ambiguous_dataset["objective"]}, ambiguous_dataset)
    state = _run(config)

    assert state["target_resolution"]["status"] == "ambiguous"
    assert state["target_required"] is True
    assert state["status"] == "AWAITING_TARGET"
    # Nothing trained and no fabricated score.
    assert state["ml_result"] == {}
    # Stopped at the target gate; never reached the trainer.
    assert "awaiting_target" in state["stages_completed"]
    assert "ml_experiment" not in state["stages_completed"]
    assert "left_company" in state["target_resolution"]["candidate_names"]
    assert "renewed_contract" in state["target_resolution"]["candidate_names"]

    assert route_after_profiling(state) == "awaiting_target"


def test_user_choice_resolves_an_ambiguous_dataset(ambiguous_dataset: Dict[str, Any]) -> None:
    """The same dataset resolves once the user picks -- no behaviour change."""
    config = _base(
        {"target_column": "renewed_contract", "prompt": "predict the outcome"},
        ambiguous_dataset,
    )
    state = _run(config)

    assert state["target_resolution"]["status"] == "resolved"
    assert state["target_column"] == "renewed_contract"
    assert state["ml_result"]["target_column"] == "renewed_contract"
    route_after_profiling(state) == "preprocessor"


# --------------------------------------------------------------------------
# Unresolvable: actionable error, no training, no fabricated metrics
# --------------------------------------------------------------------------

def test_pipeline_errors_actionably_on_absent_target(casing_dataset: Dict[str, Any]) -> None:
    """Requesting a column that does not exist must not train or substitute."""
    config = _base({"target_column": "no_such_column"}, casing_dataset)
    state = _run(config)

    assert state["target_resolution"]["status"] == "unresolved"
    assert state["target_required"] is True
    assert state["status"] == "AWAITING_TARGET"
    assert state["ml_result"] == {}
    # The message names the missing column and offers the real ones.
    assert "no_such_column" in state["target_resolution"]["reason"]
    assert "IS_CHURNING" in state["target_resolution"]["reason"]


def test_workflow_still_parks_on_missing_dataset(tmp_path: Any) -> None:
    """The earlier dataset-upload gate still holds alongside target resolution."""
    from app.agents.discovery import discovery_node

    state = initial_workflow_state(
        experiment_id="e", workspace_id="w", max_attempts=1,
        experiment_config={"dataset_name": "does_not_exist.csv"},
    )
    state.update(discovery_node(state))
    assert route_after_discovery(state) == "awaiting_dataset"


# --------------------------------------------------------------------------
# Consistency: one target everywhere, trainer/evaluator/verifier included
# --------------------------------------------------------------------------

def test_resolved_target_is_visible_to_every_stage(casing_dataset: Dict[str, Any]) -> None:
    """State, profile, trainer result and dataset_info must agree."""
    config = _base(
        {"target_column": casing_dataset["hint"], "prompt": casing_dataset["objective"]},
        casing_dataset,
    )
    state = _run(config)
    target = state["target_column"]

    assert state["profile"]["target_column"] == target
    assert state["dataset_info"]["target_column"] == target
    assert state["ml_result"]["target_column"] == target
    # Only the real column is ever split on, so it is not listed as a feature.
    assert target not in [
        c for c in state["dataset_info"]["columns"] if c != target
    ]


def test_training_uses_file_spelling_not_request_spelling(
    casing_dataset: Dict[str, Any]
) -> None:
    """The trainer splits on the file's column, which the resolver returns."""
    config = _base(
        {"target_column": casing_dataset["hint"], "prompt": casing_dataset["objective"]},
        casing_dataset,
    )
    state = _run(config)
    # The request asked for lowercase; the file has uppercase.
    assert casing_dataset["hint"] != state["ml_result"]["target_column"]
    assert state["ml_result"]["target_column"] == "IS_CHURNING"