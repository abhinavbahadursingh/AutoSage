"""Health-check business logic (Phase 1: liveness + DB reachability)."""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import settings
from app.db.session import check_connection

logger = logging.getLogger("autosage")


async def get_health_status(session: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """Assemble the health payload.

    Uses the request session when available (proves the pool can hand out
    sessions end-to-end); falls back to a raw engine ping otherwise.
    """
    db_ok = await _ping_via_session(session) if session is not None else await check_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "autosage-backend",
        "version": __version__,
        "environment": settings.APP_ENV,
        "checks": {"database": "up" if db_ok else "down"},
    }


async def _ping_via_session(session: AsyncSession) -> bool:
    from sqlalchemy import text

    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("database_healthcheck_failed")
        return False
