"""Target-column resolution regression tests.

These lock in the behaviour that used to be broken: the pipeline guessed the
target (``"target"``) and only discovered the mistake inside the trainer, where
it became a silent ``0.0`` and an exhausted retry loop.

Coverage:
  * target names that differ from any hardcoded convention (``Churn``,
    ``readmitted_30d``, ``is_fraud_flag``)
  * casing/whitespace/punctuation differences between request and file
  * column *types*: categorical labels vs continuous numerics
  * classification vs regression objectives
  * ambiguous datasets -> ask the user, never guess
  * unresolved targets -> actionable error, no training, no fabricated score
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from app.engine.targeting import (
    normalize_name,
    read_schema,
    resolve_and_validate,
    resolve_target,
    validate_target,
)


def write_csv(tmp_path: Path, name: str, header: str, rows: List[str]) -> str:
    path = tmp_path / name
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------
# Fixtures: deliberately varied shapes, casing, types and objectives.
# --------------------------------------------------------------------------

CHURN_CSV = (
    "CustomerID,tenure,MonthlyCharges,Churn",
    ["C1,5,70.0,No", "C2,3,80.5,Yes", "C3,9,60.0,No", "C4,1,95.0,Yes"],
)

READMIT_CSV = (
    "patient_id,los_days,age,readmitted_30d",
    ["p1,4,67,0", "p2,1,45,0", "p3,9,80,1", "p4,2,73,1"],
)

FRAUD_CSV = (
    "txn_id,amount,merchant_category,IS_FRAUD_FLAG",
    ["t1,10.5,grocery,0", "t2,900.0,travel,1", "t3,44.0,grocery,0", "t4,120.0,gas,1"],
)

REGRESSION_CSV = (
    "rooms,age,dist_to_station,Sale_Price",
    ["1,5,0.3,210.5", "2,7,1.2,305.0", "3,4,0.8,188.25", "4,9,2.1,450.75"],
)

TWO_LABEL_CSV = (
    "id,tenure,labelA,labelB",
    ["1,5,x,p", "2,3,y,q", "3,9,x,p", "4,1,y,q"],
)


@pytest.fixture()
def churn(tmp_path: Path) -> str:
    return write_csv(tmp_path, "churn.csv", *CHURN_CSV)


@pytest.fixture()
def readmit(tmp_path: Path) -> str:
    return write_csv(tmp_path, "readmissions.csv", *READMIT_CSV)


@pytest.fixture()
def fraud(tmp_path: Path) -> str:
    return write_csv(tmp_path, "fraud.csv", *FRAUD_CSV)


@pytest.fixture()
def regression(tmp_path: Path) -> str:
    return write_csv(tmp_path, "houses.csv", *REGRESSION_CSV)


@pytest.fixture()
def two_labels(tmp_path: Path) -> str:
    return write_csv(tmp_path, "ambiguous.csv", *TWO_LABEL_CSV)


# --------------------------------------------------------------------------
# Schema reading reflects the real file
# --------------------------------------------------------------------------

def test_schema_reads_real_columns(churn: str) -> None:
    schema = read_schema(churn)
    assert schema.names() == ["CustomerID", "tenure", "MonthlyCharges", "Churn"]
    assert schema.n_rows == 4


def test_schema_classifies_kinds(churn: str, regression: str) -> None:
    """Numeric vs categorical is read from the data, not assumed."""
    churn_schema = read_schema(churn)
    assert churn_schema.get("Churn").kind == "categorical"
    assert churn_schema.get("MonthlyCharges").kind == "numeric"

    reg_schema = read_schema(regression)
    assert reg_schema.get("Sale_Price").kind == "numeric"


def test_schema_rejects_unreadable_file(tmp_path: Path) -> None:
    from app.engine.targeting import TargetResolutionError

    bad = tmp_path / "not.csv"
    bad.write_text("", encoding="utf-8")
    with pytest.raises(TargetResolutionError):
        read_schema(str(bad))


# --------------------------------------------------------------------------
# Casing / punctuation tolerance -- the core reported bug
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "requested,expected",
    [
        ("churn", "Churn"),
        ("Churn", "Churn"),
        ("CHURN", "Churn"),
        ("  churn  ", "Churn"),
    ],
)
def test_hint_casing_resolves_to_real_column(churn: str, requested: str, expected: str) -> None:
    schema = read_schema(churn)
    resolution = resolve_and_validate(schema, hint=requested)
    assert resolution.status == "resolved"
    assert resolution.column == expected


def test_objective_casing_resolves_target(churn: str) -> None:
    """No hint at all: the objective names the column in different casing."""
    schema = read_schema(churn)
    resolution = resolve_and_validate(
        schema, objective="Predict whether a customer will CHURN this month"
    )
    assert resolution.status == "resolved"
    assert resolution.column == "Churn"


def test_mixed_case_objective_for_uppercase_column(fraud: str) -> None:
    schema = read_schema(fraud)
    resolution = resolve_and_validate(
        schema, objective="flag transactions that are is fraud", task_type="classification"
    )
    assert resolution.status == "resolved"
    assert resolution.column == "IS_FRAUD_FLAG"


def test_normalize_name_is_punctuation_insensitive() -> None:
    assert normalize_name("Churn Rate") == normalize_name("churn_rate")
    assert normalize_name("readmitted-30d") == normalize_name("Readmitted_30D")


# --------------------------------------------------------------------------
# Different target names / conventions
# --------------------------------------------------------------------------

def test_readmission_target_named_differently(readmit: str) -> None:
    """A target that follows no convention the resolver knows about."""
    schema = read_schema(readmit)
    resolution = resolve_and_validate(
        schema, objective="predict 30 day readmission", task_type="classification"
    )
    assert resolution.status == "resolved"
    assert resolution.column == "readmitted_30d"


def test_fraud_target_with_flag_suffix(fraud: str) -> None:
    schema = read_schema(fraud)
    resolution = resolve_and_validate(
        schema, objective="detect fraudulent transactions", task_type="classification"
    )
    assert resolution.status == "resolved"
    assert resolution.column == "IS_FRAUD_FLAG"


# --------------------------------------------------------------------------
# Classification vs regression
# --------------------------------------------------------------------------

def test_regression_prefers_continuous_numeric(regression: str) -> None:
    schema = read_schema(regression)
    resolution = resolve_and_validate(
        schema, objective="estimate the sale price", task_type="regression"
    )
    assert resolution.status == "resolved"
    assert resolution.column == "Sale_Price"


def test_classification_rejects_text_target(tmp_path: Path) -> None:
    """A free-text column is not a usable class label."""
    notes = [
        "customer called about a billing issue on monday morning",
        "agent followed up with the shipping delay complaint",
        "user reported the mobile app crashed during checkout",
        "support closed the duplicate ticket raised last week",
        "customer wanted to update their payment method details",
        "escalated the outage to engineering for further review",
    ]
    path = write_csv(
        tmp_path,
        "free_text.csv",
        "id,notes,label",
        [f"{i},{text},{label}" for i, (text, label) in enumerate(zip(notes, "ynynyn"))],
    )
    schema = read_schema(path)
    assert schema.get("notes").kind == "text"
    validation = validate_target(schema, "notes", task_type="classification")
    assert validation.ok is False
    assert validation.column == "notes"
    assert any("free text" in p for p in validation.problems)


def test_regression_rejects_categorical_target(churn: str) -> None:
    schema = read_schema(churn)
    validation = validate_target(schema, "Churn", task_type="regression")
    assert validation.ok is False
    assert any("cannot be a regression target" in p for p in validation.problems)


# --------------------------------------------------------------------------
# Ambiguity -> ask the user
# --------------------------------------------------------------------------

def test_ambiguous_dataset_is_not_guessed(two_labels: str) -> None:
    """Two equally plausible targets must surface a choice, not a coin flip."""
    schema = read_schema(two_labels)
    resolution = resolve_and_validate(schema, task_type="classification")
    assert resolution.status == "ambiguous"
    assert resolution.needs_user_choice is True
    assert resolution.column is None
    assert "labelA" in resolution.candidate_names
    assert "labelB" in resolution.candidate_names


def test_ambiguous_resolution_raises_actionable_error(two_labels: str) -> None:
    from app.engine.targeting import TargetResolutionError

    schema = read_schema(two_labels)
    resolution = resolve_and_validate(schema, task_type="classification")
    with pytest.raises(TargetResolutionError) as excinfo:
        resolution.raise_for_status(dataset="ambiguous.csv")
    message = str(excinfo.value)
    assert "labelA" in message and "labelB" in message
    assert "select one" in message


def test_explicit_hint_resolves_ambiguity(two_labels: str) -> None:
    """When the user does choose, the same dataset resolves cleanly."""
    schema = read_schema(two_labels)
    assert resolve_and_validate(schema, task_type="classification").status == "ambiguous"
    chosen = resolve_and_validate(schema, hint="labelB")
    assert chosen.status == "resolved"
    assert chosen.column == "labelB"


# --------------------------------------------------------------------------
# Failure modes: actionable, never silently substituted
# --------------------------------------------------------------------------

def test_missing_hint_is_unresolved_not_substituted(churn: str) -> None:
    """A requested column that does not exist must not be swapped for another."""
    schema = read_schema(churn)
    resolution = resolve_and_validate(schema, hint="not_a_column")
    assert resolution.status == "unresolved"
    assert resolution.column is None
    assert "not_a_column" in resolution.reason
    # The real columns are offered so the user can correct the request.
    assert "Churn" in resolution.reason


def test_all_constant_columns_are_unresolvable(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "flat.csv", "a,b,c", ["1,1,1", "1,1,1", "1,1,1"])
    schema = read_schema(path)
    resolution = resolve_and_validate(schema, task_type="classification")
    assert resolution.status == "unresolved"


def test_empty_dataset_is_unresolvable(tmp_path: Path) -> None:
    from app.engine.targeting import TargetResolutionError

    path = tmp_path / "empty.csv"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(TargetResolutionError):
        read_schema(str(path))


def test_hint_with_wrong_casing_still_validates(churn: str) -> None:
    schema = read_schema(churn)
    assert validate_target(schema, "churn", task_type="classification").ok is True
    assert validate_target(schema, "CHURN", task_type="classification").column == "Churn"


def test_model_proposal_outside_schema_is_rejected(churn: str) -> None:
    """A hallucinated proposal cannot become the target."""
    schema = read_schema(churn)
    resolution = resolve_target(schema, proposal="hallucinated_col", task_type="classification")
    assert resolution.column != "hallucinated_col"


def test_model_proposal_inside_schema_is_used(churn: str) -> None:
    schema = read_schema(churn)
    resolution = resolve_target(schema, proposal="MonthlyCharges", task_type="classification")
    assert resolution.column == "MonthlyCharges"


# --------------------------------------------------------------------------
# End-to-end through the workflow state
# --------------------------------------------------------------------------

def test_workflow_parks_when_target_unresolved(churn: str, two_labels: str) -> None:
    """An ambiguous real dataset parks the graph before training."""
    from app.agents.graph import route_after_profiling

    assert route_after_profiling({"target_required": False}) == "preprocessor"
    assert (
        route_after_profiling(
            {"target_required": True, "target_resolution": {"status": "ambiguous"}}
        )
        == "awaiting_target"
    )


def test_experimenter_refuses_to_train_without_target() -> None:
    """No resolved target => no tool call, no score."""
    from app.agents.experimenter import MLExperimentAgent

    agent = MLExperimentAgent()
    state: Dict[str, Any] = {
        "config": {"dataset_name": "x.csv"},
        "dataset_info": {"name": "x.csv"},
        "profile": {},
        "target_column": None,
        "target_resolution": {"status": "unresolved", "reason": "nothing plausible"},
    }
    data, reason = agent._measure(state)
    assert data is None
    assert "target column" in reason.lower()


def test_experimenter_uses_validated_target() -> None:
    from app.agents.experimenter import MLExperimentAgent

    inputs = MLExperimentAgent()._training_inputs(  # type: ignore[arg-type]
        {
            "config": {"dataset_name": "x.csv", "target_column": "ignored_by_design"},
            "dataset_info": {"name": "x.csv"},
            "profile": {"target_column": "also_ignored"},
            "target_column": "Churn",
        }
    )
    assert inputs["target_column"] == "Churn"


def test_retry_fingerprint_detects_unchanged_target_error() -> None:
    """Identical target errors must not consume the retry budget again."""
    from app.workers.tasks import _target_error_is_unchanged, _target_fingerprint

    resolution = {"status": "unresolved", "candidate_names": ["b", "a"], "reason": "x"}
    config = {"dataset_name": "d.csv", "target_column": "nope"}

    class _Exp:
        def __init__(self, summary):
            self.config = config
            self.result_summary = summary

    fingerprint = _target_fingerprint(config, resolution)
    unchanged = _Exp(
        {"awaiting_target": True, "target_error_fingerprint": fingerprint, "target_resolution": resolution}
    )
    assert _target_error_is_unchanged(unchanged) is True

    # Same dataset, different candidate ordering -> still the same problem.
    reordered = {"status": "unresolved", "candidate_names": ["a", "b"], "reason": "y"}
    assert _target_error_is_unchanged(_Exp({
        "awaiting_target": True,
        "target_error_fingerprint": fingerprint,
        "target_resolution": reordered,
    })) is True

    # A different verdict is real progress and must be retried.
    resolved = {"status": "resolved", "candidate_names": ["Churn"], "reason": "ok"}
    assert _target_error_is_unchanged(_Exp({
        "awaiting_target": True,
        "target_error_fingerprint": fingerprint,
        "target_resolution": resolved,
    })) is False

    # No prior fingerprint -> always retry.
    assert _target_error_is_unchanged(_Exp({"awaiting_target": True})) is False