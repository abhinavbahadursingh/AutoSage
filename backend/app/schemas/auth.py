"""Pydantic schemas for auth endpoints (Phase 2).

Signup/login/session-cookie management is owned by Better Auth in the
frontend. The backend exposes identity helpers over verified JWTs plus a
development-only token minter (disabled in production).
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserRead


class MeResponse(UserRead):
    """Current-user profile (GET /auth/me)."""


class SessionResponse(BaseModel):
    """Session introspection (GET /auth/session)."""

    user: UserRead
    authenticated: bool = True

    model_config = ConfigDict(from_attributes=True)


class DevTokenRequest(BaseModel):
    """Mint a local JWT for development/testing (POST /auth/dev-token)."""

    user_id: Optional[UUID] = Field(
        default=None, description="Fixed user id; generated when omitted."
    )
    email: str = Field(default="dev@autosage.local", description="Identity email.")
    name: Optional[str] = Field(default="Dev User")
    expires_in_minutes: int = Field(default=60, ge=1, le=60 * 24 * 7)


class DevTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
