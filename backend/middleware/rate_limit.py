"""Per-IP, per-tier rate limiting middleware using Redis."""
import logging

from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.services.cache import _get_redis
from backend.services.auth_service import decode_access_token

logger = logging.getLogger(__name__)

TIER_LIMITS = {
    "free": 100,    # per minute
    "pro": 500,
    # B.7.0 — coach + team share the same rate ceiling (team is alias).
    "coach": 1000,
    "team": 1000,
    "admin": 5000,
}
LOGIN_LIMIT = 5       # per 15 minutes
LOGIN_WINDOW = 900    # 15 min

# Replay upload bucket — stricter than global API limit because each upload
# can reach 500KB and triggers parsing. Free tier conservative; admin uncapped.
UPLOAD_REPLAY_LIMITS = {
    "free": 5,      # per minute
    "pro": 30,
    # B.7.0 — coach inherits team's upload bucket (alias).
    "coach": 60,
    "team": 60,
    "admin": 300,
}
UPLOAD_REPLAY_WINDOW = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        ip = request.client.host if request.client else "unknown"

        request.state.user_tier = self._extract_user_tier(request)

        # Login rate limit
        if path == "/api/v1/auth/login" and request.method == "POST":
            if self._is_rate_limited(f"rl:login:{ip}", LOGIN_LIMIT, LOGIN_WINDOW):
                return JSONResponse(
                    {"detail": "Too many login attempts. Try again later."},
                    status_code=429,
                )

        # Replay upload bucket — stricter, per-tier (B.3 hardening)
        if path == "/api/v1/team/replay/upload" and request.method == "POST":
            tier = getattr(request.state, "user_tier", "free")
            up_limit = UPLOAD_REPLAY_LIMITS.get(tier, 5)
            if self._is_rate_limited(f"rl:upload_replay:{ip}", up_limit, UPLOAD_REPLAY_WINDOW):
                return JSONResponse(
                    {"detail": f"Replay upload limit reached ({up_limit}/min). Slow down or upgrade tier."},
                    status_code=429,
                )

        # General API rate limit
        if path.startswith("/api/"):
            tier = getattr(request.state, "user_tier", "free")
            limit = TIER_LIMITS.get(tier, 100)
            if self._is_rate_limited(f"rl:api:{ip}", limit, 60):
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Upgrade tier for higher limits."},
                    status_code=429,
                )

        return await call_next(request)

    def _extract_user_tier(self, request: Request) -> str:
        """Best-effort tier extraction from bearer JWT, without DB access."""
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return "free"

        token = auth_header[7:].strip()
        if not token:
            return "free"

        try:
            payload = decode_access_token(token)
        except JWTError:
            return "free"
        except Exception:
            logger.debug("JWT tier extraction failed", exc_info=True)
            return "free"

        if payload.get("is_admin"):
            return "admin"

        tier = str(payload.get("tier") or "free").strip().lower()
        return tier if tier in TIER_LIMITS else "free"

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
