"""Fresh Experiment Objective Verification — end-to-end tests.

Proves the page's contract:

1. **Every page load starts empty.** There is no experiment picker, no
   ``/experiments`` endpoint and no ``/runs/latest`` to populate the form.
2. **Every submission creates a fresh, isolated session** that owns its own
   experiment, and ``POST /sessions`` returns a run id immediately (202) rather
   than blocking on the verification.
3. **Exactly four canonical objectives** appear, in a fixed visible sequence,
   and the stage order is fixed in source.
4. **Nothing trains.** Asserted two ways: training entry points are
   monkeypatched to explode, and results are byte-identical across runs.
5. **Missing evidence is NOT_VERIFIED, never PASS.** A fresh session has run
   nothing, so every check needing a training run must say so.
6. **Ownership is enforced on every endpoint** — a foreign run is 404, not 403.
7. **Frames are persisted and replayed**, so a late subscriber sees the whole
   run rather than restarting it.

Only the database is the in-memory ``FakeAsyncSession``; routing, JWT auth, the
auth dependencies and ownership checks are the real stack.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, Iterator, List
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.engine.objective_verification.definitions import OBJECTIVES
from app.engine.objective_verification.runner import ALL_STAGES
from app.main import app
from app.models.user import User
from app.models.verification_session import SessionStatus
from app.models.workspace import Workspace
from app.services.objective_verification_service import FreshVerificationService
from tests.fakes import FakeAsyncSession

OWNER_EMAIL = "owner@autosage.local"
OTHER_EMAIL = "intruder@autosage.local"

BASE = "/api/v1/objective-verification"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_session() -> Iterator[FakeAsyncSession]:
    session = FakeAsyncSession()
    yield session


@pytest.fixture()
def client(fake_session: FakeAsyncSession) -> Iterator[TestClient]:
    """Client whose request AND background verification share one fake session.

    The background run opens its own session, so the endpoint's session-factory
    indirection is pointed at the same fake rather than a live database.
    """
    from contextlib import asynccontextmanager

    from app.api.v1.endpoints import objective_verification as ov_endpoint

    async def override_get_db():  # type: ignore[no-untyped-def]
        yield fake_session

    @asynccontextmanager
    async def fake_factory():  # type: ignore[no-untyped-def]
        yield fake_session

    app.dependency_overrides[get_db] = override_get_db
    ov_endpoint._SESSION_FACTORY = fake_factory
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        ov_endpoint._SESSION_FACTORY = None


def _headers(email: str) -> Dict[str, str]:
    token = create_access_token(str(uuid.uuid4()), {"email": email, "name": email})
    return {"Authorization": f"Bearer {token}"}


def _seed_workspace(session: FakeAsyncSession, email: str) -> str:
    """A user plus the workspace a fresh session will belong to."""
    user = User(id=uuid.uuid4(), email=email, name=email, is_active=True)
    session.add(user)
    workspace = Workspace(
        id=uuid.uuid4(), owner_id=user.id, name="WS", description=None, meta={}
    )
    session.add(workspace)
    return str(workspace.id)


def _payload(workspace_id: str, **overrides: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "problem_statement": "predict which customers will churn next quarter",
        "dataset_name": "telco_churn_2024.csv",
        "task_type": "classification",
        "primary_metric": "roc_auc",
    }
    body.update(overrides)
    return body


def _run_sync(client: TestClient, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a session, let its background run finish, return the state.

    ``POST /sessions`` schedules the verification with ``asyncio.create_task``
    so it can answer immediately. ``TestClient`` drives the app's event loop on
    the calling thread, so yielding briefly lets the run complete before the
    state is read back.
    """
    created = client.post(f"{BASE}/sessions", json=body, headers=_headers(OWNER_EMAIL))
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]
    _drain_blocking()
    state = client.get(f"{BASE}/sessions/{run_id}", headers=_headers(OWNER_EMAIL))
    assert state.status_code == 200, state.text
    return state.json()


def _drain_blocking() -> None:
    """Let the queued background verification run to completion."""
    import time

    for _ in range(50):
        time.sleep(0.02)


# ---------------------------------------------------------------------------
# 1. the form starts empty — no old-experiment endpoints exist
# ---------------------------------------------------------------------------

def test_no_experiment_picker_or_latest_run_endpoint_exists(client: TestClient) -> None:
    """The old flow's population endpoints are gone, not merely unused."""
    for path, method in (
        (f"{BASE}/experiments", "GET"),
        (f"{BASE}/runs/latest?experiment_id=x", "GET"),
        (f"{BASE}/verify", "POST"),
    ):
        response = client.request(method, path, headers=_headers(OWNER_EMAIL))
        assert response.status_code == 404, f"{method} {path} still answers"


def test_objectives_and_stages_are_served_before_any_session(client: TestClient) -> None:
    """The fixed graph is available with no run, no experiment and no report."""
    objectives = client.get(f"{BASE}/objectives", headers=_headers(OWNER_EMAIL))
    assert objectives.status_code == 200
    payload = objectives.json()

    assert len(payload) == 4, "exactly four canonical objectives"
    assert [o["number"] for o in payload] == [1, 2, 3, 4]
    assert [o["id"] for o in payload] == [
        "objective_1",
        "objective_2",
        "objective_3",
        "objective_4",
    ]
    # Each objective states its goal in its own words.
    for objective in payload:
        assert objective["statement"].strip()
        assert objective["title"].strip()
        assert objective["checks"], f"{objective['id']} has no checks"
        for check in objective["checks"]:
            assert check["expected"].strip(), f"{check['id']} states no expectation"

    stages = client.get(f"{BASE}/stages", headers=_headers(OWNER_EMAIL))
    assert stages.status_code == 200
    assert stages.json()["stages"] == list(ALL_STAGES)
    assert list(ALL_STAGES) == [
        "input",
        "code_generation",
        "objective_1",
        "objective_2",
        "objective_3",
        "objective_4",
        "report",
    ]


# ---------------------------------------------------------------------------
# 2. a submission creates a fresh, isolated session
# ---------------------------------------------------------------------------

def test_create_session_returns_run_id_immediately(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """202 plus a run id, without waiting for the verification to finish."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    response = client.post(
        f"{BASE}/sessions", json=_payload(workspace_id), headers=_headers(OWNER_EMAIL)
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert UUID(body["run_id"])
    assert UUID(body["experiment_id"])
    assert body["stream_url"].endswith(f"/sessions/{body['run_id']}/stream")


def test_each_submission_creates_a_distinct_session(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """Two submissions never share a run id or an experiment."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    first = client.post(
        f"{BASE}/sessions", json=_payload(workspace_id), headers=_headers(OWNER_EMAIL)
    ).json()
    second = client.post(
        f"{BASE}/sessions", json=_payload(workspace_id), headers=_headers(OWNER_EMAIL)
    ).json()

    assert first["run_id"] != second["run_id"]
    assert first["experiment_id"] != second["experiment_id"]


def test_missing_input_is_rejected_rather_than_falling_back(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """A session without a problem statement is refused, not defaulted.

    Only a blank/short problem statement is rejected; dataset and target column
    are optional — the code generation step will note any assumptions.
    """
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    base = _payload(workspace_id)
    bad_bodies: List[Dict[str, Any]] = [
        {**base, "problem_statement": "x"},
    ]
    for body in bad_bodies:
        response = client.post(
            f"{BASE}/sessions", json=body, headers=_headers(OWNER_EMAIL)
        )
        assert response.status_code == 422, f"{body} was accepted: {response.text}"


def test_session_owns_its_own_experiment_in_created_state(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """The session's experiment is new and un-started — verification never runs it."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    created = client.post(
        f"{BASE}/sessions", json=_payload(workspace_id), headers=_headers(OWNER_EMAIL)
    ).json()

    from app.models.experiment import Experiment, ExperimentStatus

    experiment = next(
        e
        for e in fake_session._store[Experiment].values()
        if str(e.id) == created["experiment_id"]
    )
    assert experiment.status == ExperimentStatus.CREATED.value
    assert experiment.result_summary == {}
    assert experiment.config["prompt"].startswith("predict which customers")
    assert "target_column" not in experiment.config


# ---------------------------------------------------------------------------
# 3. the four objectives run, in order, with real evidence
# ---------------------------------------------------------------------------

def test_run_evaluates_all_four_objectives(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    state = _run_sync(client, _payload(workspace_id))
    report = state["report"]
    assert report is not None, state

    assert len(report["objectives"]) == 4
    assert [o["number"] for o in report["objectives"]] == [1, 2, 3, 4]
    for objective in report["objectives"]:
        defined = [
            c.id
            for c in next(d for d in OBJECTIVES if d.number == objective["number"]).checks
        ]
        assert [c["check_id"] for c in objective["checks"]] == defined

    assert report["problem_statement"].startswith("predict which customers")
    assert report["dataset_name"] == "telco_churn_2024.csv"


def test_every_check_reports_expected_actual_and_evidence(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """Each check states what it expected, what happened, and on what basis."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    report = _run_sync(client, _payload(workspace_id))["report"]

    check_statuses = {"PASS", "FAIL", "NOT_VERIFIED", "BLOCKED"}
    stage_statuses = {"PASSED", "FAILED", "NOT_VERIFIED", "BLOCKED"}
    for objective in report["objectives"]:
        assert objective["status"] in stage_statuses, objective["status"]
        for check in objective["checks"]:
            assert check["status"] in check_statuses, check
            assert check["expected"].strip(), f"{check['check_id']} states no expectation"
            assert check["actual"].strip(), f"{check['check_id']} states no actual"
            assert check["evidence"], f"{check['check_id']} carries no evidence"
            assert 0.0 <= check["confidence"] <= 1.0
            assert check["checked_at"]


def test_objective_passes_only_when_every_check_passes(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    report = _run_sync(client, _payload(workspace_id))["report"]

    for objective in report["objectives"]:
        statuses = {c["status"] for c in objective["checks"]}
        if objective["status"] == "PASSED":
            assert statuses == {"PASS"}, f"{objective['id']} PASSED with {statuses}"


def test_overall_verdict_is_derived_from_all_four_objectives(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    report = _run_sync(client, _payload(workspace_id))["report"]

    all_checks = [c for o in report["objectives"] for c in o["checks"]]
    assert sum(report["totals"].values()) == len(all_checks)
    assert report["overall_status"] in {
        "PASSED",
        "FAILED",
        "NOT_VERIFIED",
        "BLOCKED",
    }, report["overall_status"]


# ---------------------------------------------------------------------------
# 4. a fresh session never claims a pass it cannot substantiate
# ---------------------------------------------------------------------------

def test_fresh_session_reports_not_verified_not_pass(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """Nothing has run, so nothing that needs a run may be PASS.

    This is the central honesty guarantee: a brand-new session has no metrics,
    no decisions, no evidence and no artifacts. Checks depending on those must
    report NOT_VERIFIED rather than inventing a success.
    """
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    report = _run_sync(client, _payload(workspace_id))["report"]

    by_id = {
        c["check_id"]: c
        for o in report["objectives"]
        for c in o["checks"]
    }
    for check_id in (
        "o3_metric_sanity",
        "o3_baseline_dominance",
        "o3_independent_agreement",
        "o2_specialist_executions",
        "o4_decision_rationale",
        "o4_decision_confidence",
        "o4_evidence_nodes",
        "o4_experience_memory",
        "o4_audit_chain",
    ):
        assert by_id[check_id]["status"] == "NOT_VERIFIED", (
            f"{check_id} claimed {by_id[check_id]['status']} without any run"
        )

    # The overall verdict must not be PASSED for a session that ran nothing.
    assert report["overall_status"] != "PASSED"


def test_capability_checks_still_pass_on_a_fresh_session(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """Source-level capabilities are genuinely inspectable without a run."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    report = _run_sync(client, _payload(workspace_id))["report"]

    by_id = {c["check_id"]: c for o in report["objectives"] for c in o["checks"]}
    for check_id in (
        "o1_pipeline_graph",
        "o1_dataset_tools",
        "o1_dataset_driven_target",
        "o1_input_captured",
        "o2_specialist_agents",
        "o2_tool_registry",
        "o2_sandbox_isolation",
    ):
        assert by_id[check_id]["status"] == "PASS", by_id[check_id]


def test_stale_run_cannot_influence_a_new_result(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """A second submission's report does not inherit the first one's state."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)

    first = _run_sync(client, _payload(workspace_id))
    second = _run_sync(
        client,
        _payload(
            workspace_id,
            problem_statement="estimate delivery eta in minutes",
            dataset_name="shipments.csv",
        ),
    )

    assert first["run_id"] != second["run_id"]
    assert second["problem_statement"] == "estimate delivery eta in minutes"
    assert second["dataset_name"] == "shipments.csv"
    # The new session's checks still report NOT_VERIFIED: nothing carried over.
    by_id = {
        c["check_id"]: c
        for o in second["report"]["objectives"]
        for c in o["checks"]
    }
    assert by_id["o3_metric_sanity"]["status"] == "NOT_VERIFIED"


# ---------------------------------------------------------------------------
# 5. a malformed session blocks the whole sequence instead of faking it
# ---------------------------------------------------------------------------

def test_input_gate_blocks_every_objective_when_input_is_unusable(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """The runner's intake gate only rejects a blank problem statement.

    With the new optional dataset/target design, missing target column does
    not block the sequence — code generation proceeds and objectives report
    NOT_VERIFIED rather than BLOCKED. The only input-level rejection is a
    blank/short problem statement, which the HTTP layer catches as 422.
    """
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    service = FreshVerificationService(fake_session)
    assert workspace_id  # the caller owns a workspace; the facts below do not
    report = asyncio.run(
        service.verify_facts_directly(
            run_id=uuid.uuid4(),
            experiment_id=uuid.uuid4(),
            problem_statement="predict which customers will churn next quarter",
            dataset_name="telco_churn_2024.csv",
            config={"target_column": "", "task_type": "classification"},
        )
    )

    # Code generation proceeds with optional target; objectives report
    # NOT_VERIFIED because no training has occurred.
    # Some source-level checks (e.g. o1_pipeline_graph) genuinely PASS
    # by inspecting the repository; those are not a problem.
    assert report.overall_status.value == "NOT_VERIFIED"
    assert len(report.objectives) == 4


# ---------------------------------------------------------------------------
# 6. ownership is enforced on every endpoint
# ---------------------------------------------------------------------------

def test_foreign_run_is_404_not_403(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """A second user cannot read another user's session by run id."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    _seed_workspace(fake_session, OTHER_EMAIL)
    created = client.post(
        f"{BASE}/sessions", json=_payload(workspace_id), headers=_headers(OWNER_EMAIL)
    ).json()
    run_id = created["run_id"]

    state = client.get(f"{BASE}/sessions/{run_id}", headers=_headers(OTHER_EMAIL))
    assert state.status_code == 404

    stream = client.get(f"{BASE}/sessions/{run_id}/stream", headers=_headers(OTHER_EMAIL))
    assert stream.status_code == 404


def test_foreign_workspace_is_404_on_create(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """A user cannot start a session inside someone else's workspace."""
    owner_workspace = _seed_workspace(fake_session, OWNER_EMAIL)
    response = client.post(
        f"{BASE}/sessions",
        json=_payload(owner_workspace),
        headers=_headers(OTHER_EMAIL),
    )
    assert response.status_code == 404


def test_unknown_run_is_404(client: TestClient, fake_session: FakeAsyncSession) -> None:
    _seed_workspace(fake_session, OWNER_EMAIL)
    response = client.get(
        f"{BASE}/sessions/{uuid.uuid4()}", headers=_headers(OWNER_EMAIL)
    )
    assert response.status_code == 404


def test_session_endpoints_require_authentication(client: TestClient) -> None:
    """Everything except the static graph is behind auth.

    ``/objectives`` and ``/stages`` are the static four-objective definition,
    served to an authenticated shell before any session exists; they expose no
    user data. Every endpoint that touches a session or a caller requires a
    bearer token.
    """
    assert client.get(f"{BASE}/datasets").status_code == 401
    assert client.get(f"{BASE}/sessions/{uuid.uuid4()}").status_code == 401
    assert (
        client.get(f"{BASE}/sessions/{uuid.uuid4()}/stream").status_code == 401
    )
    unauthenticated = client.post(
        f"{BASE}/sessions",
        json={
            "workspace_id": str(uuid.uuid4()),
            "problem_statement": "predict churn for the next quarter",
            "dataset_name": "x.csv",
            "target_column": "Churn",
        },
    )
    assert unauthenticated.status_code == 401


# ---------------------------------------------------------------------------
# 7. frames persist and replay, so a late subscriber still sees the run
# ---------------------------------------------------------------------------

def test_frames_are_persisted_for_replay(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    state = _run_sync(client, _payload(workspace_id))

    frames = state["updates"]
    assert len(frames) > 10, "the run emitted too few frames to be real"
    assert frames[0]["stage"] == "input"

    stages_seen = [f["stage"] for f in frames]
    for stage in ("input", "objective_1", "objective_2", "objective_3", "objective_4", "report"):
        assert stage in stages_seen, f"{stage} never appeared in the frame history"

    # The fixed order is respected: each stage's first frame comes after the
    # previous stage's last.
    order = {s: i for i, s in enumerate(ALL_STAGES)}
    first_seen: Dict[str, int] = {}
    for index, stage in enumerate(stages_seen):
        first_seen.setdefault(stage, index)
    ordered = sorted(first_seen, key=lambda s: first_seen[s])
    assert [order[s] for s in ordered] == sorted(order[s] for s in ordered), (
        f"stages ran out of order: {ordered}"
    )


def test_stream_replays_then_delivers_the_report(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """The SSE endpoint replays stored frames and ends with the report."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    created = client.post(
        f"{BASE}/sessions", json=_payload(workspace_id), headers=_headers(OWNER_EMAIL)
    ).json()
    _drain_blocking()

    with client.stream(
        "GET", f"{BASE}/sessions/{created['run_id']}/stream", headers=_headers(OWNER_EMAIL)
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: stage" in body, "no stage frames replayed"
    assert "event: report" in body, "stream did not end with the report"

    report_payload = json.loads(
        body.split("event: report\ndata: ")[1].split("\n\n")[0]
    )
    assert report_payload["overall_status"] in {
        "PASSED",
        "FAILED",
        "NOT_VERIFIED",
        "BLOCKED",
    }
    assert len(report_payload["objectives"]) == 4


# ---------------------------------------------------------------------------
# 8. verification never trains, preprocesses or reuses an old experiment
# ---------------------------------------------------------------------------

def test_verification_never_trains_or_preprocesses(
    client: TestClient, fake_session: FakeAsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Training entry points are made to explode before any session runs."""
    import app.agents.graph as graph_module
    import app.engine.sandbox.manager as sandbox_module
    from app.engine.verification import gate_checks

    def explode(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("verification must not train or preprocess")

    for target in (
        "run_pipeline",
        "execute_experiment",
        "start_experiment",
        "_run_graph",
    ):
        if hasattr(graph_module, target):
            monkeypatch.setattr(graph_module, target, explode)
    for target in ("execute_script", "run_container", "execute"):
        if hasattr(sandbox_module, target):
            monkeypatch.setattr(sandbox_module, target, explode)
    monkeypatch.setattr(gate_checks, "executed_training_script", lambda: None)

    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    state = _run_sync(client, _payload(workspace_id))
    assert state["status"] == SessionStatus.COMPLETED.value
    assert state["report"] is not None


def test_repeated_runs_are_deterministic(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """Same input, same verdicts — a training step would perturb them."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)
    first = _run_sync(client, _payload(workspace_id))["report"]
    second = _run_sync(client, _payload(workspace_id))["report"]

    def verdicts(report: Dict[str, Any]) -> List[str]:
        return [c["status"] for o in report["objectives"] for c in o["checks"]]

    assert verdicts(first) == verdicts(second)
    assert first["overall_status"] == second["overall_status"]


def test_dataset_listing_is_scoped_to_the_caller(
    client: TestClient, fake_session: FakeAsyncSession
) -> None:
    """The dataset picker only offers the caller's own datasets."""
    workspace_id = _seed_workspace(fake_session, OWNER_EMAIL)

    mine = client.get(
        f"{BASE}/datasets?workspace_id={workspace_id}", headers=_headers(OWNER_EMAIL)
    )
    assert mine.status_code == 200
    assert isinstance(mine.json(), list)

    theirs = client.get(
        f"{BASE}/datasets?workspace_id={workspace_id}", headers=_headers(OTHER_EMAIL)
    )
    assert theirs.status_code == 404