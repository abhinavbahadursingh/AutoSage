"""Repository layer: thin async persistence primitives (Phase 3/4).

Repositories own *how* rows are read/written (queries, pagination); services
own *what* is allowed (ownership, lifecycle, validation). Every method uses
only standard ``select`` / ``func.count`` / ``session.get`` shapes so the
logic stays portable and testable.
"""
from typing import Generic, List, Optional, Sequence, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async CRUD over one mapped entity."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, entity_id: object) -> Optional[ModelT]:
        return await self.session.get(self.model, entity_id)

    async def list(
        self,
        *filters: object,
        order_by: object = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[ModelT]:
        stmt = select(self.model)
        if filters:
            stmt = stmt.where(*filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, *filters: object) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.commit()

    async def save(self, entity: ModelT) -> ModelT:
        """Commit in-place mutations made by the service layer."""
        await self.session.commit()
        await self.session.refresh(entity)
        return entity
