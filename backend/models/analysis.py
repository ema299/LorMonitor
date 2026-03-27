from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class KillerCurve(Base):
    __tablename__ = "killer_curves"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    generated_at: Mapped[date] = mapped_column(Date, nullable=False)
    game_format: Mapped[str] = mapped_column(String(20), nullable=False)
    our_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    opp_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    curves: Mapped[dict] = mapped_column(JSONB, nullable=False)
    match_count: Mapped[int | None] = mapped_column(Integer)
    loss_count: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    is_current: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        UniqueConstraint("game_format", "our_deck", "opp_deck", "generated_at"),
        Index(
            "idx_kc_lookup",
            "game_format", "our_deck", "opp_deck", "is_current",
            postgresql_where=text("is_current = true"),
        ),
    )


class Archive(Base):
    __tablename__ = "archives"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    generated_at: Mapped[date] = mapped_column(Date, nullable=False)
    game_format: Mapped[str] = mapped_column(String(20), nullable=False)
    our_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    opp_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    aggregates: Mapped[dict] = mapped_column(JSONB, nullable=False)
    match_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("game_format", "our_deck", "opp_deck", "generated_at"),
    )


class ThreatLLM(Base):
    __tablename__ = "threats_llm"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    generated_at: Mapped[date] = mapped_column(Date, nullable=False)
    game_format: Mapped[str] = mapped_column(String(20), nullable=False)
    our_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    opp_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    threats: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        UniqueConstraint("game_format", "our_deck", "opp_deck", "generated_at"),
    )


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    perimeter: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_date", "perimeter"),
        Index("idx_snapshots_date", snapshot_date.desc()),
    )
