"""Promo code service — create, validate, redeem."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.models.promo import PromoCode, PromoRedemption
from backend.models.user import User


def create_promo(
    db: Session,
    code: str,
    type: str,
    created_by: uuid.UUID,
    granted_tier: str | None = None,
    duration_days: int | None = None,
    discount_percent: int | None = None,
    discount_months: int | None = None,
    max_uses: int | None = None,
    expires_at: datetime | None = None,
) -> PromoCode:
    existing = db.query(PromoCode).filter(PromoCode.code == code.upper()).first()
    if existing:
        raise ValueError("code_exists")

    promo = PromoCode(
        code=code.upper().strip(),
        type=type,
        granted_tier=granted_tier,
        duration_days=duration_days,
        discount_percent=discount_percent,
        discount_months=discount_months,
        max_uses=max_uses,
        expires_at=expires_at,
        created_by=created_by,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


def redeem_promo(db: Session, code: str, user: User) -> PromoRedemption:
    """Validate and redeem a promo code for a user."""
    now = datetime.now(timezone.utc)

    promo = db.query(PromoCode).filter(
        PromoCode.code == code.upper().strip(),
        PromoCode.is_active == True,
    ).first()

    if not promo:
        raise ValueError("invalid_code")

    # Check expiry
    if promo.expires_at and promo.expires_at < now:
        raise ValueError("code_expired")

    # Check max uses
    if promo.max_uses is not None and promo.times_used >= promo.max_uses:
        raise ValueError("code_exhausted")

    # Check if user already redeemed this code
    already = db.query(PromoRedemption).filter(
        PromoRedemption.promo_code_id == promo.id,
        PromoRedemption.user_id == user.id,
    ).first()
    if already:
        raise ValueError("already_redeemed")

    # Apply
    original_tier = user.tier
    upgrade_expires = None

    if promo.type == "tier_upgrade":
        user.tier = promo.granted_tier or "team"
        if promo.duration_days:
            upgrade_expires = now + timedelta(days=promo.duration_days)
        db.add(user)

    # Record redemption
    redemption = PromoRedemption(
        promo_code_id=promo.id,
        user_id=user.id,
        original_tier=original_tier,
        granted_tier=promo.granted_tier if promo.type == "tier_upgrade" else None,
        expires_at=upgrade_expires,
    )
    db.add(redemption)

    # Increment usage
    promo.times_used += 1
    db.commit()
    db.refresh(redemption)
    return redemption


def get_active_promos(db: Session) -> list[PromoCode]:
    return db.query(PromoCode).filter(PromoCode.is_active == True).all()


def deactivate_promo(db: Session, code: str) -> None:
    promo = db.query(PromoCode).filter(PromoCode.code == code.upper()).first()
    if promo:
        promo.is_active = False
        db.commit()


def expire_upgrades(db: Session) -> int:
    """Revert expired tier upgrades. Run via cron daily."""
    now = datetime.now(timezone.utc)
    expired = db.query(PromoRedemption).filter(
        PromoRedemption.expires_at != None,
        PromoRedemption.expires_at < now,
        PromoRedemption.granted_tier != None,
    ).all()

    reverted = 0
    for r in expired:
        user = db.query(User).filter(User.id == r.user_id).first()
        if user and user.tier == r.granted_tier:
            user.tier = r.original_tier
            reverted += 1
        # Clear expires_at so we don't process again
        r.expires_at = None

    db.commit()
    return reverted
