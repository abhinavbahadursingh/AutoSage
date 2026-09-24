"""Rate limiting middleware for API protection (Phase 20A).

Implements token bucket rate limiting with in-memory storage (dev) or Redis (production).
"""
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.config import settings
from app.core.observability import log_with_context

logger = logging.getLogger("autosage.ratelimit")


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_allowance: int = 10


class RateLimiter:
    """Token bucket rate limiter with sliding window."""

    def __init__(self, config: RateLimitConfig, redis_client: Optional[object] = None):
        self.config = config
        self.redis = redis_client
        # In-memory fallback for development
        self._memory_store: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "minute": 0.0,
            "hour": 0.0,
            "minute_count": 0,
            "hour_count": 0,
        })

    def _get_client_key(self, request: Request) -> str:
        """Extract client identifier from request."""
        # Prefer authenticated user ID
        if hasattr(request.state, "user_id") and request.state.user_id:
            return f"user:{request.state.user_id}"
        # Fall back to IP address
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    async def check_limit(self, request: Request) -> tuple[bool, dict[str, int]]:
        """Check if request is within rate limits.
        
        Returns:
            Tuple of (allowed, headers_dict)
        """
        key = self._get_client_key(request)
        now = time.time()
        
        if self.redis:
            # Redis-based rate limiting for production
            return await self._check_redis(key, now)
        else:
            # In-memory rate limiting for development
            return self._check_memory(key, now)

    def _check_memory(self, key: str, now: float) -> tuple[bool, dict[str, int]]:
        """In-memory rate limit check."""
        entry = self._memory_store[key]
        
        # Reset minute window
        if now - entry["minute"] >= 60:
            entry["minute"] = now
            entry["minute_count"] = 0
        
        # Reset hour window
        if now - entry["hour"] >= 3600:
            entry["hour"] = now
            entry["hour_count"] = 0
        
        # Check limits
        minute_limit = self.config.requests_per_minute + self.config.burst_allowance
        hour_limit = self.config.requests_per_hour
        
        if entry["minute_count"] >= minute_limit:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(60 - (now - entry["minute"]))),
                "Retry-After": str(int(60 - (now - entry["minute"])) + 1),
            }
        
        if entry["hour_count"] >= hour_limit:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_hour),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(3600 - (now - entry["hour"]))),
                "Retry-After": str(int(3600 - (now - entry["hour"])) + 1),
            }
        
        # Increment counters
        entry["minute_count"] += 1
        entry["hour_count"] += 1
        
        return True, {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(max(0, minute_limit - entry["minute_count"])),
            "X-RateLimit-Reset": str(int(60 - (now - entry["minute"]))),
        }

    async def _check_redis(self, key: str, now: float) -> tuple[bool, dict[str, int]]:
        """Redis-based rate limit check using sliding window."""
        # Use sorted sets for sliding window
        minute_key = f"ratelimit:{key}:minute"
        hour_key = f"ratelimit:{key}:hour"
        
        pipe = self.redis.pipeline()
        
        # Clean old entries
        minute_ago = now - 60
        hour_ago = now - 3600
        pipe.zremrangebyscore(minute_key, 0, minute_ago)
        pipe.zremrangebyscore(hour_key, 0, hour_ago)
        
        # Count current requests
        pipe.zcard(minute_key)
        pipe.zcard(hour_key)
        
        results = await pipe.execute()
        minute_count = results[2]
        hour_count = results[3]
        
        minute_limit = self.config.requests_per_minute + self.config.burst_allowance
        hour_limit = self.config.requests_per_hour
        
        if minute_count >= minute_limit:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "60",
                "Retry-After": "61",
            }
        
        if hour_count >= hour_limit:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_hour),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "3600",
                "Retry-After": "3601",
            }
        
        # Add current request
        pipe = self.redis.pipeline()
        pipe.zadd(minute_key, {str(now): now})
        pipe.zadd(hour_key, {str(now): now})
        pipe.expire(minute_key, 120)
        pipe.expire(hour_key, 7200)
        await pipe.execute()
        
        return True, {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(max(0, minute_limit - minute_count - 1)),
            "X-RateLimit-Reset": str(int(60 - (now - minute_ago))),
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        config = RateLimitConfig(
            requests_per_minute=getattr(settings, "RATE_LIMIT_PER_MINUTE", 60),
            requests_per_hour=getattr(settings, "RATE_LIMIT_PER_HOUR", 1000),
            burst_allowance=getattr(settings, "RATE_LIMIT_BURST", 10),
        )
        _rate_limiter = RateLimiter(config)
    return _rate_limiter


def set_rate_limiter(limiter: Optional[RateLimiter]) -> None:
    """Set the global rate limiter (for testing)."""
    global _rate_limiter
    _rate_limiter = limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    # Paths excluded from rate limiting
    EXCLUDED_PATHS = {
        "/health",
        "/api/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    def __init__(self, app, limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or get_rate_limiter()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip rate limiting for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        # Skip for internal service-to-service calls (if configured)
        if request.headers.get("x-internal-service") == "true":
            return await call_next(request)
        
        allowed, headers = await self.limiter.check_limit(request)
        
        if not allowed:
            log_with_context(
                logger, logging.WARNING, "rate_limit_exceeded",
                path=request.url.path, client=self.limiter._get_client_key(request)
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "path": request.url.path,
                },
                headers=headers,
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value
        
        return response