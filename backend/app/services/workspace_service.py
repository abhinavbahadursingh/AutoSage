"""Workspace service with owner isolation (Phase 3/4).

A workspace belongs to exactly one user. Every function scopes by
``owner_id``; cross-user access raises :class:`NotFoundError` (404, so ids
cannot be enumerated).
"""
from typing import List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.workspace import Workspace
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceCreate


async def create_for_user(
    session: AsyncSession, owner_id: UUID, payload: WorkspaceCreate
) -> Workspace:
    repo = WorkspaceRepository(session)
    workspace = Workspace(
        owner_id=owner_id,
        name=payload.name,
        description=payload.description,
        meta=payload.meta,
    )
    return await repo.add(workspace)


async def list_for_user(
    session: AsyncSession, owner_id: UUID, page: int, page_size: int
) -> Tuple[List[Workspace], int]:
    repo = WorkspaceRepository(session)
    offset = (page - 1) * page_size
    items = await repo.list_for_owner(owner_id, limit=page_size, offset=offset)
    total = await repo.count_for_owner(owner_id)
    return items, total


async def get_for_user(
    session: AsyncSession, workspace_id: UUID, owner_id: UUID
) -> Workspace:
    """Fetch one workspace owned by ``owner_id`` or raise 404."""
    repo = WorkspaceRepository(session)
    workspace = await repo.get_owned(workspace_id, owner_id)
    if workspace is None:
        raise NotFoundError(f"Workspace {workspace_id} not found")
    return workspace


async def list_ids_for_user(session: AsyncSession, owner_id: UUID) -> List[UUID]:
    """All workspace ids owned by ``owner_id`` (experiment scoping helper)."""
    repo = WorkspaceRepository(session)
    workspaces = await repo.list_for_owner(owner_id)
    return [workspace.id for workspace in workspaces]
