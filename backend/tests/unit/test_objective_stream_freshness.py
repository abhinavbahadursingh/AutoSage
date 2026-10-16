"""The SSE stream must re-read the row, not the object it first loaded.

A verification run commits from a *different* session (a FastAPI background
task). The streaming endpoint opens a fresh session for every poll tick,
so the client always sees newly committed frames.

Each test patches the module-level ``_SESSION_FACTORY`` to return a wrapper
around its own ``FakeAsyncSession`` so the endpoint reads from the same
in-memory store the test mutates.
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

import pytest

import app.api.v1.endpoints.objective_verification as ov
from app.api.v1.endpoints.objective_verification import stream_session
from app.models.user import User
from app.models.verification_session import SessionStatus, VerificationSession
from app.models.workspace import Workspace
from tests.fakes import FakeAsyncSession


class _SessionFactory:
    """async-context-manager factory that returns a shared FakeAsyncSession."""

    def __init__(self, fake: FakeAsyncSession) -> None:
        self._fake = fake

    async def __aenter__(self) -> FakeAsyncSession:
        return self._fake

    async def __aexit__(self, *args: Any) -> None:
        return None


async def _collect(
    iterator: AsyncIterator[str], *, max_ticks: int = 40
) -> str:
    """Join SSE chunks, stopping at the end of the stream.

    Bounded so a regression fails the test instead of hanging it: the generator
    only returns once the run is terminal, so an endless loop of keep-alives
    means the endpoint stopped seeing the row's progress.
    """
    chunks = []
    for _ in range(max_ticks):
        try:
            chunks.append(await iterator.__anext__())
        except StopAsyncIteration:
            break
    else:  # pragma: no cover - only on regression
        raise AssertionError(
            "the stream never terminated: it kept sending keep-alives instead "
            "of noticing that the session row had moved on"
        )
    return "".join(chunks)


def _make_owner_workspace(fake: FakeAsyncSession) -> tuple[User, Workspace]:
    owner = User(id=uuid.uuid4(), email="owner@autosage.local", name="o", is_active=True)
    workspace = Workspace(
        id=uuid.uuid4(), owner_id=owner.id, name="WS", description=None, meta={}
    )
    fake.add(owner)
    fake.add(workspace)
    return owner, workspace


@pytest.fixture(autouse=True)
def _reset_session_factory():
    """Restore the real session factory after each test."""
    prev = ov._SESSION_FACTORY
    yield
    ov._SESSION_FACTORY = prev


@pytest.mark.asyncio
async def test_stream_sees_progress_made_after_it_subscribed() -> None:
    """Frames committed while the stream is open still reach the client."""
    fake = FakeAsyncSession()
    ov._SESSION_FACTORY = lambda: _SessionFactory(fake)  # noqa: E731
    owner, workspace = _make_owner_workspace(fake)

    run_id = uuid.uuid4()
    pending = VerificationSession(
        id=run_id,
        owner_id=owner.id,
        workspace_id=workspace.id,
        experiment_id=uuid.uuid4(),
        problem_statement="predict which customers will churn next quarter",
        dataset_name="telco_churn_2024.csv",
        config={},
        status=SessionStatus.RUNNING.value,
        events=[],
        report=None,
    )
    fake.add(pending)

    response = await stream_session(run_id=run_id, user=owner)
    assert response.media_type == "text/event-stream"
    body_iterator = response.body_iterator

    assert hasattr(body_iterator, "__anext__")

    # Tick once while the run has produced nothing: the client is told to keep
    # waiting, and must not be handed a report.
    first = await body_iterator.__anext__()
    assert first.startswith(": waiting"), first
    assert "event: report" not in first

    # The background run finishes: new frames and the report are committed.
    row = await fake.get(VerificationSession, run_id)
    assert row is not None
    row.events = [
        {"stage": "input", "status": "PASSED", "message": "", "payload": {}},
        {"stage": "report", "status": "PASSED", "message": "", "payload": {}},
    ]
    row.status = SessionStatus.COMPLETED.value
    row.report = {
        "overall_status": "NOT_VERIFIED",
        "totals": {"PASS": 0, "FAILED": 0, "NOT_VERIFIED": 19, "BLOCKED": 0},
        "objectives": [],
    }

    body = first + await _collect(body_iterator)

    assert "event: report" in body, "the stream never noticed the run had finished"
    assert '"overall_status": "NOT_VERIFIED"' in body


@pytest.mark.asyncio
async def test_stream_reports_failure_and_stops() -> None:
    """A run that fails mid-way yields an error frame and terminates."""
    fake = FakeAsyncSession()
    ov._SESSION_FACTORY = lambda: _SessionFactory(fake)  # noqa: E731
    owner, workspace = _make_owner_workspace(fake)

    run_id = uuid.uuid4()
    fake.add(
        VerificationSession(
            id=run_id,
            owner_id=owner.id,
            workspace_id=workspace.id,
            experiment_id=uuid.uuid4(),
            problem_statement="predict churn",
            dataset_name="telco.csv",
            config={},
            status=SessionStatus.RUNNING.value,
            events=[],
            report=None,
        )
    )

    response = await stream_session(run_id=run_id, user=owner)
    iterator = response.body_iterator
    first = await iterator.__anext__()

    row = await fake.get(VerificationSession, run_id)
    assert row is not None
    row.status = SessionStatus.FAILED.value
    row.error = "no LLM provider is configured"

    body = first + await _collect(iterator)
    assert "event: error" in body
    assert "no LLM provider is configured" in body


@pytest.mark.asyncio
async def test_stream_keeps_sending_keepalives_during_a_silent_gap() -> None:
    """An idle tick still emits a comment frame, so proxies see traffic."""
    fake = FakeAsyncSession()
    ov._SESSION_FACTORY = lambda: _SessionFactory(fake)  # noqa: E731
    owner, workspace = _make_owner_workspace(fake)

    run_id = uuid.uuid4()
    fake.add(
        VerificationSession(
            id=run_id,
            owner_id=owner.id,
            workspace_id=workspace.id,
            experiment_id=uuid.uuid4(),
            problem_statement="predict churn",
            dataset_name="telco.csv",
            config={},
            status=SessionStatus.RUNNING.value,
            events=[{"stage": "input", "status": "PASSED", "message": "", "payload": {}}],
            report=None,
        )
    )

    response = await stream_session(run_id=run_id, user=owner)
    iterator = response.body_iterator

    # First tick delivers the stored frame... and then, because the run is
    # silent, a keep-alive too — no idle gap long enough for a proxy to drop.
    chunk = await iterator.__anext__()
    if "event: stage" in chunk:
        chunk = chunk + await iterator.__anext__()
    assert ": waiting" in chunk

    row = await fake.get(VerificationSession, run_id)
    assert row is not None
    row.status = SessionStatus.COMPLETED.value
    row.report = {"overall_status": "PASSED", "totals": {}, "objectives": []}
    body = await _collect(iterator)
    assert "event: report" in body
