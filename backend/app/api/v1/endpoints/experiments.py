"""Experiment endpoints (Phase 4 API).

Lifecycle::

    POST   /experiments                    create (status CREATED)            -> 201
    GET    /experiments                    list mine (paginated + filters)    -> 200
    GET    /experiments/{id}               read one                           -> 200/404
    PATCH  /experiments/{id}               update name/desc/config            -> 200/404
    DELETE /experiments/{id}               delete (any status)                -> 204/404
    POST   /experiments/{id}/start         enqueue (CREATED -> QUEUED)        -> 200/404/409
    POST   /experiments/{id}/cancel        cancel (non-terminal -> CANCELLED) -> 200/404/409

Every route requires authentication and is scoped to the caller's
workspaces: foreign ids return 404 (never 403, so ids cannot be enumerated).
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.experiment import ExperimentStatus
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentRead,
    ExperimentUpdate,
)
from app.services import experiment_service

router = APIRouter()


@router.post(
    "",
    response_model=ExperimentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an experiment",
)
async def create_experiment(
    payload: ExperimentCreate, user: CurrentUser, session: DbSession
) -> ExperimentRead:
    experiment = await experiment_service.create_for_user(session, user.id, payload)
    return ExperimentRead.model_validate(experiment)


@router.get("", response_model=ExperimentListResponse, summary="List my experiments")
async def list_experiments(
    user: CurrentUser,
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    workspace_id: Optional[UUID] = Query(default=None),
    status: Optional[ExperimentStatus] = Query(default=None),
) -> ExperimentListResponse:
    items, total = await experiment_service.list_for_user(
        session,
        user.id,
        workspace_id=workspace_id,
        status=status.value if status is not None else None,
        page=page,
        page_size=page_size,
    )
    return ExperimentListResponse(
        items=[ExperimentRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{experiment_id}", response_model=ExperimentRead, summary="Get my experiment")
async def get_experiment(
    experiment_id: UUID, user: CurrentUser, session: DbSession
) -> ExperimentRead:
    experiment = await experiment_service.get_for_user(session, experiment_id, user.id)
    return ExperimentRead.model_validate(experiment)


@router.patch(
    "/{experiment_id}", response_model=ExperimentRead, summary="Update my experiment"
)
async def update_experiment(
    experiment_id: UUID,
    payload: ExperimentUpdate,
    user: CurrentUser,
    session: DbSession,
) -> ExperimentRead:
    experiment = await experiment_service.update_for_user(
        session, experiment_id, user.id, payload
    )
    return ExperimentRead.model_validate(experiment)


@router.delete("/{experiment_id}", summary="Delete my experiment")
async def delete_experiment(
    experiment_id: UUID, user: CurrentUser, session: DbSession
) -> Response:
    await experiment_service.delete_for_user(session, experiment_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{experiment_id}/start",
    response_model=ExperimentRead,
    summary="Enqueue my experiment (CREATED -> QUEUED)",
)
async def start_experiment(
    experiment_id: UUID, user: CurrentUser, session: DbSession
) -> ExperimentRead:
    from app.core.exceptions import ServiceUnavailableError
    from app.services import execution_service

    experiment = await experiment_service.start_for_user(session, experiment_id, user.id)
    # Publish-only dispatch: returns after enqueue, never waits for the run.
    try:
        task_id = execution_service.enqueue_experiment(experiment.id)
    except Exception as exc:
        raise ServiceUnavailableError(
            "Experiment queued but the task broker is unreachable; "
            "retry start once the worker is back"
        ) from exc
    experiment = await execution_service.attach_task_id(session, experiment.id, task_id)
    return ExperimentRead.model_validate(experiment)


@router.post(
    "/{experiment_id}/cancel",
    response_model=ExperimentRead,
    summary="Cancel my experiment (-> CANCELLED)",
)
async def cancel_experiment(
    experiment_id: UUID, user: CurrentUser, session: DbSession
) -> ExperimentRead:
    from app.services import execution_service

    experiment = await experiment_service.get_for_user(session, experiment_id, user.id)
    # Best-effort revoke first: a queued/running worker task is terminated;
    # the DB transition below is authoritative either way (never fails here).
    execution_service.revoke_experiment_task(experiment.celery_task_id)
    experiment = await experiment_service.cancel_for_user(
        session, experiment_id, user.id
    )
    return ExperimentRead.model_validate(experiment)
