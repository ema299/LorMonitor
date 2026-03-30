"""Authentication service — password hashing, JWT, session management."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    BCRYPT_ROUNDS,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from backend.models.user import User, UserSession

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)


# --- Password ---

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# --- JWT ---

def create_access_token(user_id: uuid.UUID, tier: str, is_admin: bool) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tier": tier,
        "is_admin": is_admin,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


# --- Refresh Token ---

def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


# --- User Operations ---

def register_user(db: Session, email: str, password: str, display_name: str | None = None) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ValueError("email_exists")

    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(
        User.email == email.lower().strip(),
        User.is_active == True,
    ).first()

    if not user or not verify_password(password, user.password_hash):
        return None

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    return user


# --- Session Operations ---

def create_session(
    db: Session, user: User, ip: str | None = None, device_info: str | None = None
) -> tuple[str, str]:
    """Create a new session. Returns (access_token, refresh_token)."""
    raw_refresh = create_refresh_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw_refresh),
        ip_address=ip,
        device_info=device_info,
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    db.commit()

    access_token = create_access_token(user.id, user.tier, user.is_admin)
    return access_token, raw_refresh


def refresh_session(db: Session, raw_refresh_token: str) -> tuple[str, str, User]:
    """Validate refresh token, rotate it. Returns (new_access, new_refresh, user)."""
    token_hash = hash_refresh_token(raw_refresh_token)
    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == token_hash,
        UserSession.revoked_at == None,
    ).first()

    if not session:
        raise ValueError("invalid_refresh_token")

    if session.expires_at < datetime.now(timezone.utc):
        raise ValueError("refresh_token_expired")

    user = db.query(User).filter(User.id == session.user_id, User.is_active == True).first()
    if not user:
        raise ValueError("user_not_found")

    # Revoke old session
    session.revoked_at = datetime.now(timezone.utc)

    # Create new session (token rotation)
    new_raw_refresh = create_refresh_token()
    new_session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(new_raw_refresh),
        ip_address=session.ip_address,
        device_info=session.device_info,
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_session)
    db.commit()

    access_token = create_access_token(user.id, user.tier, user.is_admin)
    return access_token, new_raw_refresh, user


def revoke_session(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == token_hash,
        UserSession.revoked_at == None,
    ).first()
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> int:
    now = datetime.now(timezone.utc)
    count = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.revoked_at == None,
    ).update({"revoked_at": now})
    db.commit()
    return count


def delete_user(db: Session, user_id: uuid.UUID) -> None:
    """Soft delete: deactivate + schedule for permanent deletion in 30 days."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_active = False
        user.deletion_requested_at = datetime.now(timezone.utc)
        revoke_all_sessions(db, user_id)
        db.commit()
