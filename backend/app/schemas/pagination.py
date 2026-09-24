"""Shared pagination schemas (Phase 3/4)."""
from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ItemT = TypeVar("ItemT")


class PageParams(BaseModel):
    """Validated list-query pagination (1-based pages)."""

    page: int = Field(default=1, ge=1, description="1-based page number.")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page.")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    model_config = ConfigDict(extra="forbid")


class PagedResponse(BaseModel, Generic[ItemT]):
    """Standard paginated envelope."""

    items: List[ItemT]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
