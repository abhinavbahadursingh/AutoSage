"""Request body size limit middleware (Phase 20A)."""
from typing import Awaitable, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.config import settings


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Enforce maximum request body size."""
    
    def __init__(self, app, max_size: Optional[int] = None):
        super().__init__(app)
        self.max_size = max_size or settings.MAX_REQUEST_BODY_SIZE
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_size:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large. Maximum size: {self.max_size} bytes",
                            "code": "REQUEST_TOO_LARGE",
                            "path": request.url.path,
                        },
                    )
            except ValueError:
                pass
        
        response = await call_next(request)
        return response