"""Dependency injection for FastAPI endpoints."""
import hmac
import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from backend.config import TEAM_API_REQUIRE_JWT
from backend.models import SessionLocal
from backend.models.team import TeamReplay
from backend.models.user import User
from backend.services.auth_service import decode_access_token

security = HTTPBearer(auto_error=False)

APPTOOL_ADMIN_TOKEN = os.environ.get("APPTOOL_ADMIN_TOKEN", "").strip()

TIER_LEVEL = {"free": 0, "pro": 1, "team": 2, "admin": 3}


def get_db():
    """Yield a DB session, auto-close on request end."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Best-effort auth dependency for transitional endpoints."""
    if not credentials:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def require_tier(min_tier: str):
    """Returns a dependency that enforces minimum subscription tier."""
    def checker(user: User = Depends(get_current_user)):
        if TIER_LEVEL.get(user.tier, 0) < TIER_LEVEL[min_tier]:
            raise HTTPException(
                status_code=403,
                detail={"error": "upgrade_required", "required_tier": min_tier},
            )
        return user
    return checker


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_admin_or_server_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Admin gate that also accepts a shared-secret header for server-to-self.

    Used by cron wrappers that need to invalidate caches after a static-data
    refresh. When ``APPTOOL_ADMIN_TOKEN`` env var is set, a matching
    ``X-Admin-Token`` header bypasses JWT auth. Otherwise behaves like
    ``require_admin``.
    """
    header_token = (request.headers.get("x-admin-token") or "").strip()
    if APPTOOL_ADMIN_TOKEN and header_token and hmac.compare_digest(header_token, APPTOOL_ADMIN_TOKEN):
        return None  # server-to-self call; no user context needed

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_team_access(user: User | None = Depends(get_optional_current_user)) -> User | None:
    """Transitional access gate for Team API.

    Current production path is still protected by nginx basic auth.
    When TEAM_API_REQUIRE_JWT=true, enforce team/admin JWT as intended target state.
    """
    if not TEAM_API_REQUIRE_JWT:
        return user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if user.is_admin or TIER_LEVEL.get(user.tier, 0) >= TIER_LEVEL["team"]:
        return user

    raise HTTPException(
        status_code=403,
        detail={"error": "upgrade_required", "required_tier": "team"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# Privacy layer V3 — replay access control (ARCHITECTURE.md §24.5)
# ═══════════════════════════════════════════════════════════════════════════


def require_replay_access(
    game_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamReplay:
    """Return replay if user can access it (owner, shared, or admin).

    Raises:
        404 — replay not found
        403 — replay access denied (not owner, not in shared_with, not admin,
              or orphan legacy record with user_id IS NULL)

    Orphan replays (pre-M1 data without user_id) are accessible only by admin.
    Used by GET endpoints that read a specific replay.
    """
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if replay is None:
        raise HTTPException(status_code=404, detail="replay not found")
    if user.is_admin:
        return replay
    if replay.user_id is None:
        raise HTTPException(status_code=403, detail="replay access denied")
    if replay.user_id == user.id:
        return replay
    shared = replay.shared_with or []
    if str(user.id) in shared:
        return replay
    raise HTTPException(status_code=403, detail="replay access denied")


def require_replay_owner(
    game_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamReplay:
    """Return replay only if user is owner (or admin).

    Stricter than require_replay_access — rejects shared users.
    Used by destructive actions (DELETE) and sharing configuration (POST share).
    """
    replay = db.query(TeamReplay).filter(TeamReplay.game_id == game_id).first()
    if replay is None:
        raise HTTPException(status_code=404, detail="replay not found")
    if user.is_admin:
        return replay
    if replay.user_id != user.id:
        raise HTTPException(status_code=403, detail="replay access denied — not owner")
    return replay
