"""Promo codes — tier upgrades and discounts."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # tier_upgrade | discount
    # Tier upgrade fields
    granted_tier: Mapped[str | None] = mapped_column(String(20))  # pro, team
    duration_days: Mapped[int | None] = mapped_column(Integer)    # durata accesso
    # Discount fields
    discount_percent: Mapped[int | None] = mapped_column(Integer)  # 10, 20, 50...
    discount_months: Mapped[int | None] = mapped_column(Integer)   # mesi di sconto
    # Limits
    max_uses: Mapped[int | None] = mapped_column(Integer)          # None = illimitato
    times_used: Mapped[int] = mapped_column(Integer, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # admin user_id


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    promo_code_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    original_tier: Mapped[str] = mapped_column(String(20), nullable=False)  # tier prima del riscatto
    granted_tier: Mapped[str | None] = mapped_column(String(20))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # quando scade l'upgrade
