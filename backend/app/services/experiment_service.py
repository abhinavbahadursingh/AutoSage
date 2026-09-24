"""Experiment service: ownership isolation + lifecycle (Phase 4).

Lifecycle enforced here (invalid transitions -> 409 ``ConflictError``)::

    CREATED -> QUEUED -> RUNNING -> COMPLETED
    RUNNING -> FAILED -> RETRYING -> RUNNING
    CREATED/QUEUED/RUNNING/RETRYING/FAILED -> CANCELLED

The HTTP layer exposes ``start`` (``CREATED -> QUEUED``) and ``cancel``;
``QUEUED -> RUNNING`` and the failure path are driven by workers in later
phases through :func:`transition_experiment`.

Ownership: an experiment is visible iff its workspace is owned by the
caller; otherwise :class:`NotFoundError` (404).
"""
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.experiment import Experiment, ExperimentStatus
from app.repositories.experiment_repository import ExperimentRepository
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.services import workspace_service

# Allowed outgoing transitions per state (worker + API transitions alike).
TRANSITIONS: Dict[str, Set[str]] = {
    ExperimentStatus.CREATED.value: {
        ExperimentStatus.QUEUED.value,
        ExperimentStatus.CANCELLED.value,
    },
    ExperimentStatus.QUEUED.value: {
        ExperimentStatus.RUNNING.value,
        ExperimentStatus.CANCELLED.value,
    },
    ExperimentStatus.RUNNING.value: {
        ExperimentStatus.COMPLETED.value,
        ExperimentStatus.FAILED.value,
        ExperimentStatus.CANCELLED.value,
    },
    ExperimentStatus.FAILED.value: {
        ExperimentStatus.RETRYING.value,
        ExperimentStatus.CANCELLED.value,
    },
    ExperimentStatus.RETRYING.value: {
        ExperimentStatus.RUNNING.value,
        ExperimentStatus.CANCELLED.value,
    },
    ExperimentStatus.COMPLETED.value: set(),
    ExperimentStatus.CANCELLED.value: set(),
}


def validate_transition(from_status: str, to_status: str) -> None:
    """Raise :class:`ConflictError` when ``from_status -> to_status`` is illegal."""
    allowed = TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ConflictError(
            f"Cannot transition experiment from {from_status} to {to_status}"
        )


async def transition_experiment(
    session: AsyncSession, experiment: Experiment, to_status: str
) -> Experiment:
    """Apply a lifecycle transition (used by API actions and future workers)."""
    validate_transition(experiment.status, to_status)
    experiment.status = to_status
    now = datetime.utcnow()
    if to_status == ExperimentStatus.QUEUED.value and experiment.started_at is None:
        experiment.started_at = now
    if to_status in (
        ExperimentStatus.COMPLETED.value,
        ExperimentStatus.CANCELLED.value,
    ):
        experiment.completed_at = now
    if to_status == ExperimentStatus.RETRYING.value:
        experiment.retry_count = (experiment.retry_count or 0) + 1
        experiment.error_detail = None
    repo = ExperimentRepository(session)
    return await repo.save(experiment)


async def create_for_user(
    session: AsyncSession, owner_id: UUID, payload: ExperimentCreate
) -> Experiment:
    # 404 when the workspace does not exist OR belongs to someone else.
    await workspace_service.get_for_user(session, payload.workspace_id, owner_id)
    repo = ExperimentRepository(session)
    experiment = Experiment(
        workspace_id=payload.workspace_id,
        name=payload.name,
        description=payload.description,
        status=ExperimentStatus.CREATED.value,
        config=payload.config,
        max_retries=payload.max_retries,
    )
    return await repo.add(experiment)


async def list_for_user(
    session: AsyncSession,
    owner_id: UUID,
    workspace_id: Optional[UUID],
    status: Optional[str],
    page: int,
    page_size: int,
) -> Tuple[List[Experiment], int]:
    if workspace_id is not None:
        await workspace_service.get_for_user(session, workspace_id, owner_id)
        workspace_ids = [workspace_id]
    else:
        workspace_ids = await workspace_service.list_ids_for_user(session, owner_id)
        if not workspace_ids:
            return [], 0
    repo = ExperimentRepository(session)
    offset = (page - 1) * page_size
    items = await repo.list_in_workspaces(
        workspace_ids, status=status, limit=page_size, offset=offset
    )
    total = await repo.count_in_workspaces(workspace_ids, status=status)
    return items, total


async def get_for_user(
    session: AsyncSession, experiment_id: UUID, owner_id: UUID
) -> Experiment:
    """Fetch one experiment from the caller's workspaces or raise 404."""
    workspace_ids = await workspace_service.list_ids_for_user(session, owner_id)
    repo = ExperimentRepository(session)
    experiment = await repo.get_in_workspaces(experiment_id, workspace_ids)
    if experiment is None:
        raise NotFoundError(f"Experiment {experiment_id} not found")
    return experiment


async def update_for_user(
    session: AsyncSession, experiment_id: UUID, owner_id: UUID, payload: ExperimentUpdate
) -> Experiment:
    experiment = await get_for_user(session, experiment_id, owner_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(experiment, field, value)
    repo = ExperimentRepository(session)
    return await repo.save(experiment)


async def delete_for_user(
    session: AsyncSession, experiment_id: UUID, owner_id: UUID
) -> None:
    experiment = await get_for_user(session, experiment_id, owner_id)
    repo = ExperimentRepository(session)
    await repo.delete(experiment)


async def start_for_user(
    session: AsyncSession, experiment_id: UUID, owner_id: UUID
) -> Experiment:
    """Enqueue a created experiment (``CREATED -> QUEUED``); else 409."""
    experiment = await get_for_user(session, experiment_id, owner_id)
    return await transition_experiment(session, experiment, ExperimentStatus.QUEUED.value)


async def cancel_for_user(
    session: AsyncSession, experiment_id: UUID, owner_id: UUID
) -> Experiment:
    """Cancel a non-terminal experiment; 409 when already terminal."""
    experiment = await get_for_user(session, experiment_id, owner_id)
    return await transition_experiment(
        session, experiment, ExperimentStatus.CANCELLED.value
    )
