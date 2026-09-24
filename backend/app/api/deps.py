"""Authentication dependencies — the single enforcement point (Phase 2).

Usage on any protected route::

    from app.api.deps import CurrentUser, DbSession

    @router.get("/projects")
    async def list_projects(user: CurrentUser, session: DbSession):
        ...

- Missing / invalid / expired bearer tokens -> **401** (never 403, never 500).
- The verified JWT ``sub`` identifies the user; the local ``users`` row is
  lazily provisioned on first sight (see :mod:`app.services.user_service`).
- Public routes (``/health``, ``/api/v1/health``)
  take no user dependency and stay reachable without credentials.
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError

from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
    extract_user_id,
)
from app.db.session import get_db
from app.models.project import Project
from app.models.run import PipelineRun
from app.models.user import User
from app.models.workspace import Workspace

bearer_scheme = HTTPBearer(auto_error=False, description="Supabase Auth JWT (Authorization: Bearer <token>)")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> "User":
    """Require a valid bearer token and return the identified user."""
    from app.services import user_service  # local import: keeps dep graph acyclic

    if credentials is None or not credentials.credentials:
        raise _unauthorized("Not authenticated")
    try:
        claims = await decode_access_token(credentials.credentials)
        user_id = extract_user_id(claims)
    except TokenExpiredError:
        raise _unauthorized("Token has expired") from None
    except TokenInvalidError as exc:
        raise _unauthorized(str(exc)) from None

    user = await user_service.get_or_create_user_from_claims(session, user_id, claims)
    if not user.is_active:
        raise _unauthorized("User account is disabled")
    return user


async def get_current_user_optional(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Optional["User"]:
    """Like :func:`get_current_user` but returns ``None`` when anonymous."""
    from app.services import user_service

    if credentials is None or not credentials.credentials:
        return None
    try:
        claims = await decode_access_token(credentials.credentials)
        user_id = extract_user_id(claims)
    except (TokenExpiredError, TokenInvalidError):
        return None
    user = await user_service.get_or_create_user_from_claims(session, user_id, claims)
    if not user.is_active:
        return None
    return user


async def require_owned_project(
    project_id: UUID,
    user: Annotated["User", Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    """Dependency returning the project iff it belongs to the caller (else 404)."""
    from app.services import project_service

    return await project_service.get_for_user(session, project_id, user.id)


async def require_owned_workspace(
    workspace_id: UUID,
    user: Annotated["User", Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Workspace:
    """Dependency returning the workspace iff it belongs to the caller (else 404)."""
    from app.services import workspace_service

    return await workspace_service.get_for_user(session, workspace_id, user.id)


async def require_owned_run(
    run_id: UUID,
    user: Annotated["User", Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PipelineRun:
    """Dependency returning the run iff its project belongs to the caller."""
    run = await session.get(PipelineRun, run_id)
    if run is None:
        raise NotFoundError(f"Run {run_id} not found")
    project = await session.get(Project, run.project_id)
    if project is None or project.user_id != user.id:
        # 404 (not 403): do not reveal whether the run exists.
        raise NotFoundError(f"Run {run_id} not found")
    return run


# Convenient type aliases for endpoint signatures.
CurrentUser = Annotated["User", Depends(get_current_user)]
OptionalUser = Annotated[Optional["User"], Depends(get_current_user_optional)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
OwnedProject = Annotated[Project, Depends(require_owned_project)]
OwnedWorkspace = Annotated[Workspace, Depends(require_owned_workspace)]
OwnedRun = Annotated[PipelineRun, Depends(require_owned_run)]


# --- WebSocket authentication (Phase 15) ---

async def get_current_user_ws(
    token: Optional[str],
    session: AsyncSession,
) -> User:
    """Authenticate a WebSocket connection using token from query param or header.

    Raises HTTPException on failure (FastAPI converts to WS 1008).
    """
    from app.services import user_service
    from app.core.security import (
        TokenExpiredError,
        TokenInvalidError,
        decode_access_token,
        extract_user_id,
    )

    if not token:
        raise _unauthorized("Not authenticated")
    try:
        claims = await decode_access_token(token)
        user_id = extract_user_id(claims)
    except TokenExpiredError:
        raise _unauthorized("Token has expired") from None
    except TokenInvalidError as exc:
        raise _unauthorized(str(exc)) from None

    user = await user_service.get_or_create_user_from_claims(session, user_id, claims)
    if not user.is_active:
        raise _unauthorized("User account is disabled")
    return user
