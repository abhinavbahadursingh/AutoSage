"""Discovery-stage dataset gating.

The dataset search agent cannot resolve this run's dataset (it is under
maintenance, or the file was never uploaded). Discovery must then *park* the
run and ask for the dataset instead of quietly training on ``mock_dataset.csv``
— that stand-in is what made missing datasets surface minutes later as a
baffling verification failure.
"""
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from app.agents.discovery import (
    UNNAMED_DATASET_LABEL,
    DiscoveryAgent,
    _dataset_available,
    _requested_dataset_name,
)
from app.agents.graph import route_after_discovery
from app.core.config import settings

CSV = b"feature,target\n1,0\n2,1\n"


@pytest.fixture()
def present_csv() -> str:
    """A dataset that actually exists in the upload dir."""
    name = f"autosage_disc_{uuid.uuid4().hex[:8]}.csv"
    (Path(settings.UPLOAD_DIR) / name).write_bytes(CSV)
    yield name
    (Path(settings.UPLOAD_DIR) / name).unlink(missing_ok=True)


# -- requested name resolution -------------------------------------------
def test_requested_name_prefers_dataset_name() -> None:
    state = {"config": {"dataset_name": "churn.csv", "dataset": "other.csv"}}
    assert _requested_dataset_name(state) == "churn.csv"  # type: ignore[arg-type]


def test_requested_name_falls_back_to_dataset() -> None:
    assert _requested_dataset_name({"config": {"dataset": "x.csv"}}) == "x.csv"  # type: ignore[arg-type]


def test_requested_name_is_empty_when_unspecified() -> None:
    assert _requested_dataset_name({"config": {}}) == ""  # type: ignore[arg-type]


# -- availability ---------------------------------------------------------
def test_dataset_available_true_when_on_disk(present_csv: str) -> None:
    assert _dataset_available({}, present_csv) is True


def test_dataset_available_false_when_absent() -> None:
    assert _dataset_available({}, f"absent_{uuid.uuid4().hex[:8]}.csv") is False


def test_dataset_available_never_raises() -> None:
    """A resolution error means "missing", not an exception out of the stage."""
    assert _dataset_available({"experiment_id": "not-a-uuid"}, "whatever.csv") is False


# -- discovery output -----------------------------------------------------
def test_discovery_parks_when_dataset_missing() -> None:
    """Missing dataset -> source_type 'missing' and no fabricated stand-in."""
    missing = f"absent_{uuid.uuid4().hex[:8]}.csv"
    state: Dict[str, Any] = {"config": {"dataset_name": missing, "target_column": "y"}, "errors": []}
    # `run` (not `heuristic`) is the gate's real entry point — it must hold
    # even when an LLM provider is configured and would otherwise answer.
    out = DiscoveryAgent().run(state)  # type: ignore[arg-type]
    assert out.source_type == "missing"
    assert out.dataset_name == missing
    assert "mock_dataset" not in out.dataset_name


def test_discovery_parks_when_no_dataset_was_named() -> None:
    """A run that named no dataset asks for one instead of using a stand-in.

    This is the default frontend path: the user submits a prompt without
    attaching a file, so discovery is the first place that can ask. Falling
    through to the catalog stub here would hand the pipeline
    ``mock_dataset.csv`` and invent rows that were never read.
    """
    out = DiscoveryAgent().run({"config": {}})  # type: ignore[arg-type]
    assert out.source_type == "missing"
    assert out.dataset_name == UNNAMED_DATASET_LABEL
    assert "mock_dataset" not in out.dataset_name
    assert out.rows == 0


def test_discovery_parks_when_no_dataset_named_even_with_an_llm() -> None:
    """The unnamed-dataset gate is not bypassable by the LLM path either."""

    class _FakeLLM:
        def has_providers(self) -> bool:
            return True

        def complete_structured_sync(self, **kwargs: Any) -> Any:  # pragma: no cover
            raise AssertionError("LLM must not be consulted when no dataset is named")

    out = DiscoveryAgent(llm=_FakeLLM()).run({"config": {}})  # type: ignore[arg-type]
    assert out.source_type == "missing"


def test_unnamed_dataset_state_payload_signals_required() -> None:
    state: Dict[str, Any] = {"config": {}}
    agent = DiscoveryAgent()
    out = agent.run(state)  # type: ignore[arg-type]
    payload = agent.state_payload(out, state)  # type: ignore[arg-type]
    assert payload["dataset_required"] is True
    assert payload["dataset_missing_name"] == UNNAMED_DATASET_LABEL
    assert payload["dataset_info"]["source"] == "missing"


def test_discovery_parks_even_with_an_llm_available() -> None:
    """The gate must not be bypassable by the LLM path."""
    missing = f"absent_{uuid.uuid4().hex[:8]}.csv"
    state: Dict[str, Any] = {"config": {"dataset_name": missing}}

    class _FakeLLM:
        def has_providers(self) -> bool:
            return True

        def complete_structured_sync(self, **kwargs: Any) -> Any:  # pragma: no cover
            raise AssertionError("LLM must not be consulted for a missing dataset")

    out = DiscoveryAgent(llm=_FakeLLM()).run(state)  # type: ignore[arg-type]
    assert out.source_type == "missing"


def test_discovery_proceeds_when_dataset_present(present_csv: str) -> None:
    state: Dict[str, Any] = {"config": {"dataset_name": present_csv}, "errors": []}
    out = DiscoveryAgent().run(state)  # type: ignore[arg-type]
    assert out.source_type != "missing"


# -- state payload signal -------------------------------------------------
def test_state_payload_flags_dataset_required() -> None:
    missing = f"absent_{uuid.uuid4().hex[:8]}.csv"
    state: Dict[str, Any] = {"config": {"dataset_name": missing}}
    agent = DiscoveryAgent()
    out = agent.run(state)  # type: ignore[arg-type]
    payload = agent.state_payload(out, state)  # type: ignore[arg-type]
    assert payload["dataset_required"] is True
    assert payload["dataset_missing_name"] == missing
    assert payload["dataset_info"]["source"] == "missing"


def test_state_payload_normal_when_resolved(present_csv: str) -> None:
    state: Dict[str, Any] = {"config": {"dataset_name": present_csv}}
    agent = DiscoveryAgent()
    out = agent.run(state)  # type: ignore[arg-type]
    payload = agent.state_payload(out, state)  # type: ignore[arg-type]
    assert "dataset_required" not in payload


# -- graph routing --------------------------------------------------------
def test_route_parks_when_dataset_required() -> None:
    assert (
        route_after_discovery({"dataset_required": True, "dataset_missing_name": "x.csv"})
        == "awaiting_dataset"
    )


def test_route_continues_normally() -> None:
    assert route_after_discovery({"dataset_required": False}) == "profiler"
    assert route_after_discovery({}) == "profiler"


def test_unnamed_dataset_run_ends_awaiting_not_failed() -> None:
    """An unnamed-dataset run parks in a resumable state, never a hard failure."""
    from app.agents.graph import mark_awaiting_dataset

    final = mark_awaiting_dataset({  # type: ignore[arg-type]
        "dataset_missing_name": UNNAMED_DATASET_LABEL
    })
    assert final["status"] == "AWAITING_DATASET"
    assert final["stages_completed"] == ["awaiting_dataset"]