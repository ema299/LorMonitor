"""Auth routes — register, login, logout, refresh, profile."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db
from backend.models.user import User
from backend.services import auth_service

router = APIRouter()


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 min


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    tier: str
    is_admin: bool
    created_at: datetime
    last_login: datetime | None

    model_config = {"from_attributes": True}


# --- Routes ---

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user = auth_service.register_user(db, body.email, body.password, body.display_name)
    except ValueError as e:
        if str(e) == "email_exists":
            raise HTTPException(status_code=409, detail="Email already registered")
        raise

    access, refresh = auth_service.create_session(
        db, user,
        ip=request.client.host if request.client else None,
        device_info=request.headers.get("user-agent"),
    )
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access, refresh = auth_service.create_session(
        db, user,
        ip=request.client.host if request.client else None,
        device_info=request.headers.get("user-agent"),
    )
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=200)
def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    auth_service.revoke_session(db, body.refresh_token)
    return {"detail": "Logged out"}


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        access, new_refresh, user = auth_service.refresh_session(db, body.refresh_token)
    except ValueError as e:
        detail = str(e)
        if detail in ("invalid_refresh_token", "refresh_token_expired", "user_not_found"):
            raise HTTPException(status_code=401, detail=detail)
        raise

    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.delete("/me", status_code=200)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service.delete_user(db, user.id)
    return {"detail": "Account scheduled for deletion in 30 days"}
