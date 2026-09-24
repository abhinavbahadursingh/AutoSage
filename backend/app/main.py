"""FastAPI application entry point (Phase 1 foundation)."""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.body_limit import BodyLimitMiddleware
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import AuthContextMiddleware, RequestIdMiddleware, SecurityHeadersMiddleware
from app.core.observability import instrument_all, instrument_fastapi
from app.core.ratelimit import RateLimitMiddleware, get_rate_limiter
from app.db.session import check_connection, close_engine, init_engine
from app.services import close_connection_manager

logger = setup_logging(settings.LOG_LEVEL)

# Initialize OpenTelemetry instrumentation
instrument_all()


def _validate_production_config() -> None:
    """Validate critical production configuration."""
    if settings.APP_ENV == "production":
        errors = []
        
        # Check critical secrets
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            errors.append("SUPABASE_SERVICE_ROLE_KEY must be set in production")
        
        if settings.APP_SECRET_KEY == "insecure-default-change-me":
            errors.append("APP_SECRET_KEY must be changed from default in production")
        
        # Check CORS
        if "*" in settings.BACKEND_CORS_ORIGINS:
            errors.append("CORS wildcard '*' not allowed in production")
        
        # Check debug mode
        if settings.DEBUG:
            errors.append("DEBUG must be False in production")
        
        # Check database
        if "postgres:postgres@" in settings.DATABASE_URL:
            errors.append("DATABASE_URL must not use default credentials in production")
        
        if errors:
            raise RuntimeError(
                "Production configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown: logging, engine lifecycle, connectivity probe."""
    # Validate production config early
    _validate_production_config()

    logger.info(
        "startup",
        extra={"service": "autosage-backend", "version": __version__, "env": settings.APP_ENV},
    )
    init_engine()
    # Never block startup on a slow/unreachable DB: a hung probe used to leave
    # uvicorn accepting TCP but serving no HTTP (frontend "Cannot reach API").
    try:
        connected = await asyncio.wait_for(check_connection(), timeout=10.0)
    except Exception as exc:
        connected = False
        logger.warning(
            "postgres_probe_failed",
            extra={"error": f"{type(exc).__name__}: {exc}"},
        )
    if connected:
        logger.info("postgres_connected")
    else:
        # Stay up so /health can report "degraded" instead of crashing.
        logger.warning("postgres_unreachable_on_startup")
    yield
    await close_connection_manager()
    await close_engine()
    logger.info("shutdown")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="A Verified Multi-Agent System for Natural-Language-Driven Automated Machine Learning",
        version=__version__,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Hardened CORS configuration
    cors_origins = settings.BACKEND_CORS_ORIGINS
    # In production, reject wildcard origins
    if settings.APP_ENV == "production" and "*" in cors_origins:
        raise RuntimeError("CORS wildcard '*' not allowed in production. Set specific origins.")
    
    # Body size limit middleware (early to reject quickly)
    app.add_middleware(BodyLimitMiddleware)

    # Rate limiting middleware (early to reject quickly)
    app.add_middleware(RateLimitMiddleware)

    # Request ID middleware (for request tracing)
    app.add_middleware(RequestIdMiddleware)

    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Permissive auth context (populates request.state.user_id when a valid
    # bearer token is present; never rejects — enforcement lives in deps).
    app.add_middleware(AuthContextMiddleware)

    # CORS must be the LAST middleware added so it is the OUTERMOST wrapper:
    # add_middleware() prepends, so only then do ALL responses (including
    # rate-limit/body-limit rejections and auth errors) carry
    # Access-Control-Allow-Origin. Note: unhandled 500s from Starlette's
    # ServerErrorMiddleware sit even further out — those get CORS headers
    # attached manually in core/exceptions.py.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    # Instrument FastAPI with OpenTelemetry
    instrument_fastapi(app)

    @app.get("/health", tags=["Health"], summary="Container liveness probe")
    async def health_check() -> dict[str, str]:
        # Liveness only (no dependencies) — suitable for orchestrator probes
        # and the frontend's reachability check.
        return {"status": "ok"}

    return app


app = create_application()