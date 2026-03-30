"""Dependency injection for FastAPI endpoints."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from backend.models import SessionLocal
from backend.models.user import User
from backend.services.auth_service import decode_access_token

security = HTTPBearer(auto_error=False)

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
