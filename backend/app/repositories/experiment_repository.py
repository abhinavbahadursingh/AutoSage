"""Experiment repository (Phase 3/4)."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import Experiment
from app.repositories.base import BaseRepository


class ExperimentRepository(BaseRepository[Experiment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Experiment)

    async def list_in_workspaces(
        self,
        workspace_ids: List[UUID],
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Experiment]:
        filters = [Experiment.workspace_id.in_(workspace_ids)]
        if status is not None:
            filters.append(Experiment.status == status)
        return await self.list(
            *filters,
            order_by=Experiment.created_at.desc(),
            limit=limit,
            offset=offset,
        )

    async def count_in_workspaces(
        self, workspace_ids: List[UUID], status: Optional[str] = None
    ) -> int:
        filters = [Experiment.workspace_id.in_(workspace_ids)]
        if status is not None:
            filters.append(Experiment.status == status)
        return await self.count(*filters)

    async def get_in_workspace(
        self, experiment_id: UUID, workspace_id: UUID
    ) -> Optional[Experiment]:
        rows = await self.list(
            Experiment.id == experiment_id, Experiment.workspace_id == workspace_id
        )
        return rows[0] if rows else None

    async def get_in_workspaces(
        self, experiment_id: UUID, workspace_ids: List[UUID]
    ) -> Optional[Experiment]:
        """Fetch one experiment scoped to any of ``workspace_ids`` (or None)."""
        if not workspace_ids:
            return None
        rows = await self.list(
            Experiment.id == experiment_id,
            Experiment.workspace_id.in_(workspace_ids),
        )
        return rows[0] if rows else None
