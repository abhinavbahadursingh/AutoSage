"""Application error model + global exception handlers.

All API errors share one envelope::

    {"detail": ..., "code": "NOT_FOUND", "path": "/api/v1/..."}

Register via ``register_exception_handlers(app)`` in ``app.main``.
"""
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger("autosage")


def _cors_headers(request: Request) -> dict[str, str]:
    """CORS headers for responses produced OUTSIDE CORSMiddleware.

    Starlette's ServerErrorMiddleware (which renders unhandled exceptions
    via the ``Exception`` handler below) sits outside every user middleware,
    so those responses never pass through CORSMiddleware. Without these
    headers the browser reports a CORS block instead of the real 500.
    """
    origin = request.headers.get("origin")
    if not origin:
        return {}
    allowed = settings.BACKEND_CORS_ORIGINS
    if "*" in allowed:
        return {"Access-Control-Allow-Origin": "*", "Vary": "Origin"}
    if origin in allowed:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


class AppError(Exception):
    """Base class for expected application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str = "Unexpected error", **extra: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"


class UnauthorizedError(AppError):
    """Authentication failed (missing/invalid/expired credentials). -> 401."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    """Authenticated but not allowed to access this resource. -> 403."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"


def _envelope(detail: Any, code: str, path: str) -> dict[str, Any]:
    return {"detail": detail, "code": code, "path": path}


def _json_safe_errors(errors: list) -> list[dict[str, Any]]:
    """Make ``RequestValidationError.errors()`` JSON-serializable.

    Pydantic puts the original exception object in ``ctx`` (e.g.
    ``{"error": ValueError(...)``) for value errors — handing that straight
    to ``json.dumps`` raises ``TypeError`` and turns a 422 into a 500.
    """
    safe: list[dict[str, Any]] = []
    for err in errors:
        item = dict(err)
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            item["ctx"] = {
                k: (f"{type(v).__name__}: {v}" if isinstance(v, BaseException) else v)
                for k, v in ctx.items()
            }
        loc = item.get("loc")
        if isinstance(loc, tuple):
            item["loc"] = list(loc)
        safe.append(item)
    return safe


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global handlers. Order matters: specific first."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", extra={"code": exc.code, "path": request.url.path})
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.detail, exc.code, request.url.path),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.detail, f"HTTP_{exc.status_code}", request.url.path),
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("validation_error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(_json_safe_errors(exc.errors()), "VALIDATION_ERROR", request.url.path),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("Internal server error", "INTERNAL_ERROR", request.url.path),
            headers=_cors_headers(request),
        )
