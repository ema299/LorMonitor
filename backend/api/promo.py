"""Promo code routes — admin creates, user redeems."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db, require_admin
from backend.models.user import User
from backend.services import promo_service

router = APIRouter()


# --- Schemas ---

class CreatePromoRequest(BaseModel):
    code: str = Field(max_length=50)
    type: str = Field(pattern="^(tier_upgrade|discount)$")
    granted_tier: str | None = None
    duration_days: int | None = None
    discount_percent: int | None = Field(None, ge=1, le=100)
    discount_months: int | None = None
    max_uses: int | None = None
    expires_at: datetime | None = None


class RedeemRequest(BaseModel):
    code: str


class PromoResponse(BaseModel):
    id: int
    code: str
    type: str
    granted_tier: str | None
    duration_days: int | None
    discount_percent: int | None
    discount_months: int | None
    max_uses: int | None
    times_used: int
    is_active: bool
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class RedemptionResponse(BaseModel):
    detail: str
    granted_tier: str | None
    expires_at: datetime | None


# --- Admin routes ---

@router.post("/create", response_model=PromoResponse, status_code=201)
def create_promo(body: CreatePromoRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        promo = promo_service.create_promo(
            db,
            code=body.code,
            type=body.type,
            created_by=admin.id,
            granted_tier=body.granted_tier,
            duration_days=body.duration_days,
            discount_percent=body.discount_percent,
            discount_months=body.discount_months,
            max_uses=body.max_uses,
            expires_at=body.expires_at,
        )
    except ValueError as e:
        if str(e) == "code_exists":
            raise HTTPException(status_code=409, detail="Promo code already exists")
        raise
    return promo


@router.get("/list", response_model=list[PromoResponse])
def list_promos(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return promo_service.get_active_promos(db)


@router.post("/deactivate/{code}", status_code=200)
def deactivate_promo(code: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    promo_service.deactivate_promo(db, code)
    return {"detail": f"Promo {code.upper()} deactivated"}


# --- User route ---

@router.post("/redeem", response_model=RedemptionResponse)
def redeem_promo(body: RedeemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    error_messages = {
        "invalid_code": "Invalid or inactive promo code",
        "code_expired": "This promo code has expired",
        "code_exhausted": "This promo code has reached its usage limit",
        "already_redeemed": "You have already redeemed this code",
    }
    try:
        redemption = promo_service.redeem_promo(db, body.code, user)
    except ValueError as e:
        detail = error_messages.get(str(e), str(e))
        raise HTTPException(status_code=400, detail=detail)

    return RedemptionResponse(
        detail="Promo code redeemed successfully",
        granted_tier=redemption.granted_tier,
        expires_at=redemption.expires_at,
    )
