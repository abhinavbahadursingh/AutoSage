"""Fresh Experiment Objective Verification API.

Verifies the four canonical AutoSage objectives against **one freshly created
session**: a brand-new problem statement, a dataset, and a configuration the
user submits on the page. Every submission creates a new isolated session
that owns its own experiment.

**This API never preprocesses a dataset, trains a model, or retrains
anything.** It issues reads and source inspection only.

There is no experiment picker and no resume path. A run id is issued
by ``POST /sessions`` and is valid only for the session it was issued for and
only for the user who created it; every read re-checks ownership and answers
404 rather than 403 so a foreign run is not even acknowledged. The listing
route (``GET /sessions``) only discovers sessions already created that way —
it never selects or reuses an experiment for a new run.

Routes (mounted under ``/api/v1``)::

    GET  /objective-verification/objectives        the fixed four-objective graph
    GET  /objective-verification/stages            the fixed stage order
    GET  /objective-verification/datasets          datasets usable for a session
    GET  /objective-verification/sessions          the caller's recent sessions (listing)
    POST /objective-verification/sessions          create a session, get a run id
    GET  /objective-verification/sessions/{run_id}          status + report
    GET  /objective-verification/sessions/{run_id}/stream  SSE progress

Note: no ``from __future__ import annotations`` here. Under PEP 563 the
``Annotated[..., Depends(...)]`` metadata on ``CurrentUser`` stops being
resolved by FastAPI and the dependency degrades to a query parameter.
"""
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession
from app.engine.objective_verification.definitions import objective_definitions
from app.engine.objective_verification.runner import ALL_STAGES
from app.schemas.objective_verification import (
    FreshSessionAccepted,
    FreshSessionCreate,
    LinkExperimentRequest,
    ObjectiveDefinition,
    ProjectBrief,
    SessionDataset,
    SessionStateResponse,
    SessionSummary,
    StageStatus,
)
from app.services import objective_verification_service as svc

logger = logging.getLogger("autosage.objective_verification")

router = APIRouter(prefix="/objective-verification", tags=["ObjectiveVerification"])

#: Poll cadence while tailing a session's persisted frames.
STREAM_INTERVAL_SECONDS = 0.2

#: Session factory the background run opens its own session from. Indirection
#: so tests can point it at the in-memory fake without patching the engine.
_SESSION_FACTORY: Optional[Any] = None


def _session_factory() -> Any:
    """A callable returning a fresh async session context manager."""
    global _SESSION_FACTORY
    if _SESSION_FACTORY is not None:
        return _SESSION_FACTORY

    from app.db.session import AsyncSessionLocal, init_engine

    if AsyncSessionLocal is None:
        init_engine()
    if AsyncSessionLocal is None:  # pragma: no cover - engine failed to start
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )
    return AsyncSessionLocal


async def _dispatch(
    run_id: uuid.UUID,
    owner_id: uuid.UUID,
    session_factory: Any,
) -> None:
    """Background entry point: execute one session on its own DB session.

    The request's own session is request-scoped and closed by the time this
    runs, so the run opens its own via the injected factory. Failures are
    recorded on the session row rather than raised into a task nobody awaits.
    """
    async with session_factory() as session:
        service = svc.FreshVerificationService(session)
        try:
            row = await service.get_owned_session(run_id, owner_id)
            await service.execute_session(row)
        except Exception:  # noqa: BLE001 - recorded on the session row
            logger.error(
                "objective_verification_background_failed",
                extra={"run_id": str(run_id)},
                exc_info=True,
            )


@router.get(
    "/objectives",
    response_model=List[ObjectiveDefinition],
    summary="The four canonical objectives and their checks (fixed graph definition)",
)
async def list_objectives() -> List[ObjectiveDefinition]:
    """Serve the fixed objective graph so the client never hardcodes it.

    The page renders the complete four-objective sequence from this
    immediately, before a session exists, and then streams real per-stage
    progress.
    """
    return objective_definitions()


@router.get(
    "/stages",
    summary="The fixed stage order for the verification flow",
)
async def list_stages() -> Dict[str, Any]:
    """The order is declared in source, not chosen at runtime.

    ``input -> objective_1 -> objective_2 -> objective_3 -> objective_4 -> report``
    """
    return {"stages": list(ALL_STAGES)}


@router.get(
    "/datasets",
    response_model=List[SessionDataset],
    summary="Datasets the caller may submit for a fresh session",
)
async def list_session_datasets(
    user: CurrentUser,
    session: DbSession,
    workspace_id: Optional[uuid.UUID] = Query(
        None, description="Restrict to one of the caller's workspaces"
    ),
) -> List[SessionDataset]:
    """Only datasets the caller can already resolve; never another tenant's."""
    service = svc.FreshVerificationService(session)
    if workspace_id is not None:
        try:
            await service.require_owned_workspace(workspace_id, user.id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            ) from exc
    return await service.list_session_datasets(user.id, workspace_id)


@router.get(
    "/sessions",
    response_model=List[SessionSummary],
    summary="The caller's recent verification sessions, newest first",
)
async def list_sessions(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(20, ge=1, le=100, description="Max sessions to return"),
) -> List[SessionSummary]:
    """List this user's sessions for discovery (e.g. the Project Summary page).

    Ownership is enforced here exactly like on the single-session read: only
    sessions created by ``user`` are returned, and only cheap listing rows —
    the verbatim problem statement plus lifecycle fields, never the frame
    history or the full report payload.
    """
    service = svc.FreshVerificationService(session)
    rows = await service.list_sessions(user.id, limit=limit)
    return [
        SessionSummary(
            run_id=str(row.id),
            experiment_id=str(row.experiment_id),
            linked_experiment_id=row.linked_experiment_id,
            problem_statement=row.problem_statement,
            dataset_name=row.dataset_name,
            config=row.config or {},
            status=row.status,
            overall_status=row.overall_status,
            overall_confidence=row.overall_confidence,
            decision_count=len(row.decision_records or []),
            stage_count=len(row.events or []),
            created_at=row.created_at,
            completed_at=row.completed_at,
            error=row.error,
        )
        for row in rows
    ]


@router.post(
    "/sessions",
    response_model=FreshSessionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a fresh verification session and return its run id immediately",
)
async def create_session(
    payload: FreshSessionCreate,
    user: CurrentUser,
    session: DbSession,
    background: BackgroundTasks,
) -> FreshSessionAccepted:
    """Start a brand-new verification. Never blocks on the verification itself.

    Creates a new isolated session (and the experiment it owns) then schedules
    the fixed flow as a background task, returning the run id at once so the
    client can subscribe to the stream while it is still running.

    The request schema requires a problem statement and a dataset, so a
    submission that is not a well-formed verification is rejected here rather
    than silently falling back to any previous experiment.
    """
    service = svc.FreshVerificationService(session)
    try:
        row = await service.create_session(
            owner_id=user.id,
            workspace_id=payload.workspace_id,
            problem_statement=payload.problem_statement.strip(),
            dataset_name=payload.dataset_name.strip() if payload.dataset_name else "",
            config=payload.config,
        )
    except KeyError as exc:
        # 404, not 403: never reveal that a foreign workspace exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        ) from exc

    # FastAPI's BackgroundTasks runs after the response is sent, so the client
    # still receives the run id immediately. It is awaited in-process, which
    # also makes the run deterministic under test.
    background.add_task(_dispatch, row.id, user.id, _session_factory())

    return FreshSessionAccepted(
        run_id=str(row.id),
        experiment_id=str(row.experiment_id),
        status=StageStatus.PENDING,
        stream_url=f"/api/v1/objective-verification/sessions/{row.id}/stream",
    )


@router.post(
    "/sessions/{run_id}/link-experiment",
    summary="Link a completed pipeline experiment to this verification session",
)
async def link_experiment(
    run_id: uuid.UUID,
    payload: LinkExperimentRequest,
    user: CurrentUser,
    session: DbSession,
):
    """Link a completed pipeline experiment to this verification session.

    Objective checks (Objective 4 especially) read facts — decisions,
    evidence nodes, metrics, verification status — from the linked
    experiment's records instead of this session's own empty experiment.

    The linked experiment must be COMPLETED and in the same workspace.
    """
    from app.schemas.objective_verification import LinkExperimentRequest as _LER

    assert isinstance(payload, _LER)
    service = svc.FreshVerificationService(session)
    try:
        row = await service.link_experiment(
            run_id=run_id,
            owner_id=user.id,
            linked_experiment_id=payload.experiment_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return {
        "run_id": str(row.id),
        "linked_experiment_id": str(row.linked_experiment_id),
        "status": row.status,
    }


@router.get(
    "/sessions/{run_id}",
    response_model=SessionStateResponse,
    summary="Current state and final report of one session",
)
async def get_session(run_id: uuid.UUID, user: CurrentUser, session: DbSession) -> SessionStateResponse:
    """Ownership-checked read of a session: status, frames and report.

    This is the reconnect path — a client that lost its stream re-reads the
    session and keeps every stage it already completed.
    """
    service = svc.FreshVerificationService(session)
    try:
        row = await service.get_owned_session(run_id, user.id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification session not found",
        ) from exc
    return service.to_state(row)


@router.get(
    "/sessions/{run_id}/brief",
    response_model=ProjectBrief,
    summary="Plain-language project walkthrough of one given project",
)
async def get_session_brief(
    run_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ProjectBrief:
    """The project brief: what was said, what it reads as, how it was framed.

    Built from the session's stored records only — the verbatim request, the
    deterministic interpretation, the pipeline experiment's own decision
    rows, the design record and the measured outcome. It is NOT the
    objective-verification report; the four objectives stay on the Objectives
    page.
    """
    service = svc.FreshVerificationService(session)
    try:
        row = await service.get_owned_session(run_id, user.id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification session not found",
        ) from exc
    return await service.build_project_brief(row)


@router.get(
    "/sessions/{run_id}/stream",
    summary="Server-sent events stream of one session's progress",
)
async def stream_session(run_id: uuid.UUID, user: CurrentUser) -> StreamingResponse:
    """Stream stage transitions and per-check results as they complete.

    SSE is used because the traffic is one-directional (server -> client) and
    it reconnects automatically.

    Frames are read from the session row rather than from an in-memory queue,
    so a client that subscribes late or reconnects still receives every frame
    it missed (they are replayed from the start of the stored history) and the
    stream works regardless of which worker is serving it.

    Each poll opens a *fresh* database session: the verification run commits
    its frames from a background task's own session, and reusing the request's
    session across polls can leave SQLAlchemy's identity map holding a stale
    copy of the row, so the client would never see newly committed frames.
    """
    # Ownership check on the request session before opening the stream.
    session_factory = _session_factory()
    async with session_factory() as check_session:
        service = svc.FreshVerificationService(check_session)
        try:
            await service.get_owned_session(run_id, user.id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification session not found",
            ) from exc

    async def event_source():
        sent = 0
        while True:
            # Fresh session per poll so we always read the latest committed
            # row from the background task's session.
            async with session_factory() as poll_session:
                poll_service = svc.FreshVerificationService(poll_session)
                row = await poll_service.get_owned_session(run_id, user.id)
                frames = list(row.events or [])
                for frame in frames[sent:]:
                    yield f"event: stage\ndata: {json.dumps(frame)}\n\n"
                sent = len(frames)

                if row.status == svc.SessionStatus.FAILED.value:
                    yield (
                        "event: error\ndata: "
                        + json.dumps({"message": row.error or "Verification failed"})
                        + "\n\n"
                    )
                    return

                if row.status == svc.SessionStatus.COMPLETED.value and row.report:
                    yield (
                        "event: report\ndata: "
                        + json.dumps(row.report)
                        + "\n\n"
                    )
                    return

                if len(frames) == sent:
                    # Keep-alive comment frame so proxies don't drop an idle
                    # connection during a long LLM round trip.
                    yield ": waiting\n\n"
            await asyncio.sleep(STREAM_INTERVAL_SECONDS)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )