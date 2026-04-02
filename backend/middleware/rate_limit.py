"""Per-IP, per-tier rate limiting middleware using Redis."""
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.services.cache import _get_redis

logger = logging.getLogger(__name__)

TIER_LIMITS = {
    "free": 100,    # per minute
    "pro": 500,
    "team": 1000,
    "admin": 5000,
}
LOGIN_LIMIT = 5       # per 15 minutes
LOGIN_WINDOW = 900    # 15 min


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        ip = request.client.host if request.client else "unknown"

        # Login rate limit
        if path == "/api/v1/auth/login" and request.method == "POST":
            if self._is_rate_limited(f"rl:login:{ip}", LOGIN_LIMIT, LOGIN_WINDOW):
                return JSONResponse(
                    {"detail": "Too many login attempts. Try again later."},
                    status_code=429,
                )

        # General API rate limit
        if path.startswith("/api/"):
            tier = getattr(request.state, "user_tier", "free") if hasattr(request.state, "user_tier") else "free"
            limit = TIER_LIMITS.get(tier, 100)
            if self._is_rate_limited(f"rl:api:{ip}", limit, 60):
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Upgrade tier for higher limits."},
                    status_code=429,
                )

        return await call_next(request)

    def _is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        r = _get_redis()
        if not r:
            return False  # fail-open
        try:
            current = r.incr(key)
            if current == 1:
                r.expire(key, window)
            return current > limit
        except Exception:
            return False
