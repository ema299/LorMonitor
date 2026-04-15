"""MetaEpoch — reference row for a rotation window.

Consumed by the native digest generator (Sprint P1) to:
  * bound the 30-day lookback to `max(started_at, NOW() - window_days)`;
  * reject matches that contain any card whose `set` falls outside
    `legal_sets` when we start gating on set legality.

Typical read path:
    from backend.services.meta_epoch_service import get_current_epoch
    epoch = get_current_epoch(db)
    if epoch is None:
        ...  # no epoch row: treat as open-ended (no filter)
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class MetaEpoch(Base):
    __tablename__ = "meta_epochs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[date] = mapped_column(Date, nullable=False)
    ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    legal_sets: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
