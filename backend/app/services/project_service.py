"""Project service with user/workspace isolation (Phase 2).

Every function scopes by ``owner_id``: a user can only list, read, update,
or delete their own projects. Cross-user access raises :class:`NotFoundError`
(deliberately 404, not 403, so project ids cannot be enumerated).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


async def list_for_user(session: AsyncSession, owner_id: UUID) -> List[Project]:
    result = await session.execute(
        select(Project).where(Project.user_id == owner_id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def create_for_user(
    session: AsyncSession, owner_id: UUID, payload: ProjectCreate
) -> Project:
    project = Project(user_id=owner_id, name=payload.name, description=payload.description)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def get_for_user(
    session: AsyncSession, project_id: UUID, owner_id: UUID
) -> Project:
    """Fetch one project owned by ``owner_id`` or raise 404."""
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.user_id == owner_id)
    )
    project = result.scalars().one_or_none()
    if project is None:
        raise NotFoundError(f"Project {project_id} not found")
    return project


async def update_for_user(
    session: AsyncSession, project_id: UUID, owner_id: UUID, payload: ProjectUpdate
) -> Project:
    project = await get_for_user(session, project_id, owner_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


async def delete_for_user(
    session: AsyncSession, project_id: UUID, owner_id: UUID
) -> None:
    project = await get_for_user(session, project_id, owner_id)
    await session.delete(project)
    await session.commit()
