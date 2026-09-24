"""Auth endpoints (Phase 2).

Signup / login / session cookies are owned by Better Auth in the frontend.
These routes expose identity helpers over already-verified JWTs:

- ``GET /auth/me`` — current-user profile (protected).
- ``GET /auth/session`` — session introspection (protected).
- ``POST /auth/dev-token`` — mint a local JWT for development and automated
  tests. Disabled unless ``AUTH_DEV_TOKEN_ENABLED`` (never enable in prod).
"""
import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import DevTokenRequest, DevTokenResponse, MeResponse, SessionResponse
from app.schemas.user import UserRead
from app.services import user_service

router = APIRouter()


@router.get("/me", response_model=MeResponse, summary="Current user profile")
async def read_me(user: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(user)


@router.get("/session", response_model=SessionResponse, summary="Session introspection")
async def read_session(user: CurrentUser) -> SessionResponse:
    return SessionResponse(user=UserRead.model_validate(user), authenticated=True)


@router.post(
    "/dev-token",
    response_model=DevTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mint a development JWT (disabled in production)",
)
async def mint_dev_token(payload: DevTokenRequest, session: DbSession) -> DevTokenResponse:
    # Multiple layers of protection for dev token endpoint
    if not settings.AUTH_DEV_TOKEN_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if settings.APP_ENV == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # Additional safety: require explicit dev environment
    if settings.APP_ENV not in ("development", "test", "local"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    user_id = payload.user_id or uuid.uuid4()
    claims = {"email": payload.email, "name": payload.name}
    user = await user_service.get_or_create_user_from_claims(
        session, user_id, {**claims, "sub": str(user_id)}
    )
    token = create_access_token(
        str(user.id),
        extra_claims={"email": user.email, "name": user.name},
        expires_delta=timedelta(minutes=payload.expires_in_minutes),
    )
    return DevTokenResponse(access_token=token, user=UserRead.model_validate(user))
