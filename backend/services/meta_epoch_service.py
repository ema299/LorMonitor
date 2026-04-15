"""Accessor helpers for the meta_epochs reference table.

The native digest generator (Sprint P1) calls `get_current_epoch(db)` to decide:
  * the earliest date to accept for the 30-day lookback; and
  * which card sets are considered legal for the current rotation window.

The "current" epoch is the row with ``ended_at IS NULL``. If several rows match
(shouldn't happen in practice) we pick the one with the largest ``started_at``.
Returns ``None`` when the table is empty so callers can degrade gracefully.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.meta_epoch import MetaEpoch


def get_current_epoch(db: Session) -> MetaEpoch | None:
    """Return the current epoch row (ended_at IS NULL), or None if none exists."""
    stmt = (
        select(MetaEpoch)
        .where(MetaEpoch.ended_at.is_(None))
        .order_by(MetaEpoch.started_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_epoch_by_id(db: Session, epoch_id: int) -> MetaEpoch | None:
    """Fetch a specific epoch by primary key (used for back-filling older windows)."""
    return db.get(MetaEpoch, epoch_id)


def list_epochs(db: Session) -> list[MetaEpoch]:
    """Return every epoch, newest (largest started_at) first."""
    stmt = select(MetaEpoch).order_by(MetaEpoch.started_at.desc())
    return list(db.execute(stmt).scalars())
