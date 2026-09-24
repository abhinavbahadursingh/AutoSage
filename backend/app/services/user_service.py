"""User service — lookup + lazy provisioning from JWT claims (Phase 2).

On the first authenticated request for a Better Auth identity, no local
``users`` row exists yet. Provision it from the verified token claims so
workspace isolation works without a separate user-sync step. Later requests
hit the indexed primary-key lookup.
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger("autosage")


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def get_or_create_user_from_claims(
    session: AsyncSession, user_id: UUID, claims: Dict[str, Any]
) -> User:
    """Return the local user for ``user_id``, creating it from JWT claims."""
    user = await get_user_by_id(session, user_id)
    if user is not None:
        return user

    email = claims.get("email") or f"user-{user_id}@autosage.local"
    # Guard against a duplicate email owned by a different id (e.g. identity
    # re-created on the Better Auth side): return the existing user instead
    # of re-keying (which would violate FKs on workspaces, projects, etc.).
    user = await get_user_by_email(session, str(email))
    if user is not None:
        logger.info("user_found_by_email", extra={"existing_id": str(user.id), "requested_id": str(user_id)})
        return user

    user = User(
        id=user_id,
        email=str(email),
        name=claims.get("name"),
        image=claims.get("image"),
        email_verified=bool(claims.get("email_verified", False)),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("user_provisioned", extra={"user_id": str(user_id)})
    return user
