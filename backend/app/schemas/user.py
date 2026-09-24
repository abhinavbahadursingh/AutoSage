"""Pydantic schemas for the User model (Phase 2)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """Public user representation returned by the API."""

    id: UUID
    email: str
    name: Optional[str] = None
    image: Optional[str] = None
    email_verified: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Attributes used when lazily provisioning a user from JWT claims."""

    id: UUID
    email: str
    name: Optional[str] = None
    image: Optional[str] = None
    email_verified: bool = False


class TokenPayload(BaseModel):
    """Decoded JWT claims relevant to the backend."""

    sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    image: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
