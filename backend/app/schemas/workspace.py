"""Pydantic schemas for workspaces (Phase 3/4)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pagination import PagedResponse


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class WorkspaceRead(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceListResponse(PagedResponse[WorkspaceRead]):
    """Paginated workspace list."""

    items: List[WorkspaceRead]
