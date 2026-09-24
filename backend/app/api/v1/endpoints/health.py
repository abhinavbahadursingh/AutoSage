"""Liveness + dependency health endpoint (Phase 1)."""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.health import HealthResponse
from app.services.health_service import get_health_status

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Returns service status plus PostgreSQL reachability.",
)
async def health_check(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    payload = await get_health_status(session)
    code = status.HTTP_200_OK if payload["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=payload)
