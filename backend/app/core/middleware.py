"""Auth context middleware (Phase 2) + Request ID middleware (Phase 16) + Security headers (Phase 20A).

Permissive by design: when a request carries a syntactically valid bearer
token, the middleware verifies it and stores ``request.state.user_id``
(plus the raw claims) for logging/telemetry. It **never rejects** requests —
enforcement stays in the route dependencies (:mod:`app.api.deps`), so public
routes such as ``/health`` keep working with or without credentials.

Also adds request ID propagation for observability and security headers.
"""
import logging
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.observability import request_context, set_request_id, clear_request_id
from app.core.security import TokenError, decode_access_token, extract_user_id

logger = logging.getLogger("autosage")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate and propagate request IDs for distributed tracing."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Set context variable for the request duration
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response
        finally:
            clear_request_id(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # CSP - restrictive by default, can be adjusted per needs
        if settings.APP_ENV == "production":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        
        # HSTS in production
        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Attach ``request.state.user_id`` / ``request.state.token_claims`` when possible."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.user_id = None
        request.state.token_claims = None
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            try:
                claims = await decode_access_token(token.strip())
                request.state.user_id = str(extract_user_id(claims))
                request.state.token_claims = claims
            except TokenError:
                # Invalid tokens are handled downstream by dependencies (401).
                logger.debug("auth_middleware_invalid_token", extra={"path": request.url.path, "request_id": getattr(request.state, "request_id", None)})
        return await call_next(request)
