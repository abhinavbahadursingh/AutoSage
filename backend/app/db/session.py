"""Async SQLAlchemy 2.0 engine + session management.

The engine is created lazily via :func:`init_engine` (called from the
application lifespan) so importing this module never opens connections.
"""
import logging
import ssl
from typing import AsyncIterator, Optional

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = logging.getLogger("autosage")

engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

_NO_SSL = {"", "disable", "allow", "off", "false", "0"}
# libpq sslmode values that enable TLS without certificate verification
# (require/prefer/allow only encrypt; verification is verify-ca/verify-full).
_UNVERIFIED_SSL = {"require", "prefer", "allow", "1", "true", "yes"}


def _split_ssl_connect_args(database_url: str) -> tuple[str, dict]:
    """Translate ``?ssl[mode]=`` URL params into asyncpg connect args.

    SQLAlchemy's asyncpg dialect forwards unknown query params as
    ``asyncpg.connect()`` kwargs, which rejects ``sslmode``. Supabase (and
    other managed Postgres) requires TLS, so ``?sslmode=require`` becomes an
    unverified ``SSLContext`` — matching libpq, where ``require`` encrypts
    without verifying the chain (Supabase presents a private CA that is not
    in public trust stores). ``verify-ca``/``verify-full`` use a verifying
    context (plus ``sslrootcert`` when provided). The sync URL used by
    Alembic keeps the params — libpq understands them.
    """
    parsed = make_url(database_url)
    query = dict(parsed.query)
    ssl_request = query.pop("sslmode", None)
    if ssl_request is None:
        ssl_request = query.pop("ssl", None)
    else:
        query.pop("ssl", None)
    rootcert = query.pop("sslrootcert", None)
    query.pop("sslcert", None)
    query.pop("sslkey", None)
    connect_args: dict = {}
    if ssl_request is not None:
        mode = str(ssl_request).lower()
        if mode in ("verify-ca", "verify-full"):
            if rootcert:
                ctx = ssl.create_default_context(cafile=str(rootcert))
            else:
                ctx = ssl.create_default_context()
            if mode == "verify-ca":
                ctx.check_hostname = False
            connect_args["ssl"] = ctx
        elif mode not in _NO_SSL and mode in _UNVERIFIED_SSL:
            # require / prefer / allow: encrypt, do not verify (libpq parity).
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ctx
        # str(URL) masks the password as '***'; render unhidden.
        database_url = parsed.set(query=query).render_as_string(hide_password=False)
    elif rootcert is not None or "sslcert" in query or "sslkey" in query:
        # ssl* params without sslmode still must not reach asyncpg.
        database_url = parsed.set(query=query).render_as_string(hide_password=False)
    return database_url, connect_args


def init_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Create the global async engine (idempotent)."""
    global engine, AsyncSessionLocal
    if engine is not None:
        return engine
    url = database_url or settings.DATABASE_URL
    url, connect_args = _split_ssl_connect_args(url)
    engine = create_async_engine(
        url,
        echo=settings.SQL_ECHO,
        future=True,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    logger.info("database_engine_initialized")
    return engine


async def close_engine() -> None:
    """Dispose the global engine (lifespan shutdown)."""
    global engine, AsyncSessionLocal
    if engine is not None:
        await engine.dispose()
        engine = None
        AsyncSessionLocal = None
        logger.info("database_engine_closed")


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async session per request."""
    if AsyncSessionLocal is None:
        init_engine()
    assert AsyncSessionLocal is not None
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_connection() -> bool:
    """Return True when a trivial query succeeds."""
    if engine is None:
        init_engine()
    assert engine is not None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("database_healthcheck_failed")
        return False
