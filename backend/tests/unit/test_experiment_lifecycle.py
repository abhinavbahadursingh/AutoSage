"""Unit tests: experiment lifecycle transition rules (no database required)."""
import pytest

from app.core.exceptions import ConflictError
from app.models.experiment import ExperimentStatus, TERMINAL_STATUSES
from app.services.experiment_service import TRANSITIONS, validate_transition


def S(name: str) -> str:  # noqa: N802 - tiny helper alias
    return ExperimentStatus[name].value


def test_all_states_present_in_transition_map() -> None:
    assert set(TRANSITIONS) == {s.value for s in ExperimentStatus}


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert TERMINAL_STATUSES == {S("COMPLETED"), S("CANCELLED")}
    assert TRANSITIONS[S("COMPLETED")] == set()
    assert TRANSITIONS[S("CANCELLED")] == set()


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        ("CREATED", "QUEUED"),
        ("CREATED", "CANCELLED"),
        ("QUEUED", "RUNNING"),
        ("QUEUED", "CANCELLED"),
        ("RUNNING", "COMPLETED"),
        ("RUNNING", "FAILED"),
        ("RUNNING", "CANCELLED"),
        ("FAILED", "RETRYING"),
        ("FAILED", "CANCELLED"),
        ("RETRYING", "RUNNING"),
        ("RETRYING", "CANCELLED"),
    ],
)
def test_legal_transitions_pass(from_status: str, to_status: str) -> None:
    validate_transition(S(from_status), S(to_status))  # must not raise


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        ("CREATED", "RUNNING"),  # must queue first
        ("CREATED", "COMPLETED"),  # skip ahead
        ("QUEUED", "COMPLETED"),  # never ran
        ("QUEUED", "FAILED"),  # only RUNNING can fail
        ("RUNNING", "QUEUED"),  # no going back
        ("RUNNING", "RETRYING"),  # must fail first
        ("FAILED", "RUNNING"),  # must go through RETRYING
        ("FAILED", "COMPLETED"),  # skip retry
        ("RETRYING", "COMPLETED"),  # must run again first
        ("RETRYING", "FAILED"),  # already failed
        ("COMPLETED", "CANCELLED"),  # terminal
        ("COMPLETED", "RUNNING"),  # terminal
        ("CANCELLED", "QUEUED"),  # terminal
        ("CANCELLED", "CREATED"),  # terminal
    ],
)
def test_illegal_transitions_raise_conflict(from_status: str, to_status: str) -> None:
    with pytest.raises(ConflictError):
        validate_transition(S(from_status), S(to_status))


def test_unknown_source_state_rejected() -> None:
    with pytest.raises(ConflictError):
        validate_transition("BOGUS", S("QUEUED"))
