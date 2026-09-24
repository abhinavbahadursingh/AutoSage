"""Workspace repository (Phase 3/4)."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workspace)

    async def list_for_owner(
        self, owner_id: UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[Workspace]:
        return await self.list(
            Workspace.owner_id == owner_id,
            order_by=Workspace.created_at.desc(),
            limit=limit,
            offset=offset,
        )

    async def count_for_owner(self, owner_id: UUID) -> int:
        return await self.count(Workspace.owner_id == owner_id)

    async def get_owned(self, workspace_id: UUID, owner_id: UUID) -> Optional[Workspace]:
        rows = await self.list(
            Workspace.id == workspace_id, Workspace.owner_id == owner_id
        )
        return rows[0] if rows else None
