"""The SSE stream must re-read the row, not the object it first loaded.

A verification run commits from a *different* session (a FastAPI background
task). The streaming endpoint holds one session open for the whole run and
re-reads the row every tick — but ``AsyncSession.get()`` serves the instance
from its identity map, so without an explicit expiry the client waits forever
on a run that already finished.

``FakeAsyncSession.get()`` hands back the live object every time and therefore
cannot see this bug: the object mutates under the stream, so the stale read
looks fresh. ``_IdentityMapSession`` below reproduces the real semantics —
a snapshot that only refreshes when ``expire_all()`` is called — and the test
drives the endpoint's own generator tick by tick.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any, AsyncIterator, Optional, Tuple, Type

import pytest

from app.api.v1.endpoints.objective_verification import stream_session
from app.models.user import User
from app.models.verification_session import SessionStatus, VerificationSession
from app.models.workspace import Workspace
from tests.fakes import FakeAsyncSession


class _IdentityMapSession:
    """AsyncSession-shaped wrapper whose ``get()`` serves a cached snapshot.

    Mirrors the one behaviour that matters here: an instance already loaded is
    returned as-is until ``expire_all()`` drops it from the identity map.
    """

    def __init__(self, inner: FakeAsyncSession) -> None:
        self._inner = inner
        self._snapshot: dict[Tuple[Type, Any], Any] = {}

    async def get(self, entity: Type, pk: Any) -> Optional[Any]:
        key = (entity, pk)
        if key not in self._snapshot:
            row = await self._inner.get(entity, pk)
            if row is None:
                return None
            row = copy.copy(row)
            row.events = list(row.events or [])
            self._snapshot[key] = row
        return self._snapshot[key]

    def expire_all(self) -> None:
        self._snapshot.clear()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


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


@pytest.mark.asyncio
async def test_stream_sees_progress_made_after_it_subscribed() -> None:
    """Frames committed while the stream is open still reach the client."""
    fake = FakeAsyncSession()
    owner = User(id=uuid.uuid4(), email="owner@autosage.local", name="o", is_active=True)
    workspace = Workspace(
        id=uuid.uuid4(), owner_id=owner.id, name="WS", description=None, meta={}
    )
    fake.add(owner)
    fake.add(workspace)

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

    response = await stream_session(run_id=run_id, user=owner, session=_IdentityMapSession(fake))
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
    owner = User(id=uuid.uuid4(), email="owner@autosage.local", name="o", is_active=True)
    workspace = Workspace(
        id=uuid.uuid4(), owner_id=owner.id, name="WS", description=None, meta={}
    )
    fake.add(owner)
    fake.add(workspace)

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

    response = await stream_session(run_id=run_id, user=owner, session=_IdentityMapSession(fake))
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
    owner = User(id=uuid.uuid4(), email="owner@autosage.local", name="o", is_active=True)
    workspace = Workspace(
        id=uuid.uuid4(), owner_id=owner.id, name="WS", description=None, meta={}
    )
    fake.add(owner)
    fake.add(workspace)

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

    response = await stream_session(run_id=run_id, user=owner, session=_IdentityMapSession(fake))
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
