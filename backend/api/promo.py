"""Promo code routes — admin creates, user redeems."""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.deps import get_current_user, get_db, require_admin
from backend.models.promo import PromoCode
from backend.models.user import User
from backend.services import promo_service

logger = logging.getLogger(__name__)

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

_REDEEM_ERRORS = {
    "invalid_code": "Invalid or inactive promo code",
    "code_expired": "This promo code has expired",
    "code_exhausted": "This promo code has reached its usage limit",
    "already_redeemed": "You have already redeemed this code",
}


@router.post("/redeem", response_model=RedemptionResponse)
def redeem_promo(body: RedeemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        redemption = promo_service.redeem_promo(db, body.code, user)
    except ValueError as e:
        detail = _REDEEM_ERRORS.get(str(e), str(e))
        raise HTTPException(status_code=400, detail=detail)

    return RedemptionResponse(
        detail="Promo code redeemed successfully",
        granted_tier=redemption.granted_tier,
        expires_at=redemption.expires_at,
    )


@router.post("/redeem-beta", response_model=RedemptionResponse)
def redeem_beta_code(
    body: RedeemRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Beta program redemption — Coach tier preview pre-Stripe.

    B.7.0 row 217. Reuses ``promo_service.redeem_promo`` but constrains the
    code's ``granted_tier`` to ``coach`` (rejects pro/team/discount codes).
    Distributable to 5-10 power-coach for dogfooding before Stripe live.
    Codes expire after N days or never (param on creation, see /create).
    Emits an audit log line per redemption with caller ip + ua.
    """
    code = (body.code or "").upper().strip()
    if not code:
        raise HTTPException(status_code=400, detail="missing code")

    promo = (
        db.query(PromoCode)
        .filter(PromoCode.code == code, PromoCode.is_active == True)
        .first()
    )
    if not promo or promo.type != "tier_upgrade" or promo.granted_tier != "coach":
        # Same opaque error as invalid_code — don't leak existence of non-beta codes.
        raise HTTPException(status_code=400, detail=_REDEEM_ERRORS["invalid_code"])

    try:
        redemption = promo_service.redeem_promo(db, code, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_REDEEM_ERRORS.get(str(e), str(e)))

    ip = request.client.host if request.client else "?"
    ua = (request.headers.get("user-agent") or "?")[:120]
    logger.info(
        "beta_redemption code=%s user=%s tier=%s expires=%s ip=%s ua=%s",
        code, user.id, redemption.granted_tier,
        redemption.expires_at.isoformat() if redemption.expires_at else "never",
        ip, ua,
    )

    return RedemptionResponse(
        detail="Beta code redeemed — Coach tier active",
        granted_tier=redemption.granted_tier,
        expires_at=redemption.expires_at,
    )
