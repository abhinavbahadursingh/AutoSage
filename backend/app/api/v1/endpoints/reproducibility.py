"""Reproducibility Record endpoints (Phase 17 API).

GET /experiments/{experiment_id}/reproducibility  -> retrieve record
GET /reproducibility                            -> list records (paginated)
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.reproducibility import (
    ReproducibilityRecordListResponse,
    ReproducibilityRecordRead,
)
from app.services import reproducibility_service

router = APIRouter()


@router.get(
    "/experiments/{experiment_id}/reproducibility",
    response_model=ReproducibilityRecordRead,
    summary="Get reproducibility record for an experiment",
)
async def get_reproducibility_for_experiment(
    experiment_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> ReproducibilityRecordRead:
    """Retrieve the reproducibility record for a completed experiment."""
    record = await reproducibility_service.get_by_experiment(session, experiment_id, user.id)
    if record is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Reproducibility record for experiment {experiment_id} not found")
    return ReproducibilityRecordRead.model_validate(record)


@router.get(
    "/reproducibility",
    response_model=ReproducibilityRecordListResponse,
    summary="List reproducibility records for my experiments",
)
async def list_reproducibility_records(
    user: CurrentUser,
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    workspace_id: Optional[UUID] = Query(default=None),
) -> ReproducibilityRecordListResponse:
    """List all reproducibility records for experiments in user's workspaces."""
    items, total = await reproducibility_service.list_for_user(
        session, user.id, workspace_id=workspace_id, page=page, page_size=page_size
    )
    return ReproducibilityRecordListResponse(
        items=[ReproducibilityRecordRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/reproducibility/{record_id}",
    response_model=ReproducibilityRecordRead,
    summary="Get a specific reproducibility record by ID",
)
async def get_reproducibility_record(
    record_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> ReproducibilityRecordRead:
    """Retrieve a specific reproducibility record by ID."""
    record = await reproducibility_service.get_by_id(session, record_id, user.id)
    if record is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Reproducibility record {record_id} not found")
    return ReproducibilityRecordRead.model_validate(record)