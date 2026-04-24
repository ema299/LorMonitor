from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    game_format: Mapped[str] = mapped_column(String(20), nullable=False)
    queue_name: Mapped[str | None] = mapped_column(String(50))
    perimeter: Mapped[str] = mapped_column(String(20), nullable=False)
    deck_a: Mapped[str] = mapped_column(String(10), nullable=False)
    deck_b: Mapped[str] = mapped_column(String(10), nullable=False)
    winner: Mapped[str | None] = mapped_column(String(10))
    player_a_name: Mapped[str | None] = mapped_column(String(100))
    player_b_name: Mapped[str | None] = mapped_column(String(100))
    player_a_mmr: Mapped[int | None] = mapped_column(Integer)
    player_b_mmr: Mapped[int | None] = mapped_column(Integer)
    total_turns: Mapped[int | None] = mapped_column(Integer)
    lore_a_final: Mapped[int | None] = mapped_column(Integer)
    lore_b_final: Mapped[int | None] = mapped_column(Integer)
    turns: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cards_a: Mapped[dict | None] = mapped_column(JSONB)
    cards_b: Mapped[dict | None] = mapped_column(JSONB)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_matches_format", "game_format"),
        Index("idx_matches_perimeter", "perimeter"),
        Index("idx_matches_decks", "deck_a", "deck_b"),
        Index("idx_matches_date", played_at.desc()),
        Index("idx_matches_mmr_a", "player_a_mmr"),
        Index("idx_matches_mmr_b", "player_b_mmr"),
        Index(
            "idx_matches_lookup",
            "game_format", "deck_a", "deck_b", played_at.desc(),
            # Future-proof predicate: matches ``perimeter NOT IN ('other')`` so
            # setNN perimeters (set11, set12, set13, ...) all use the index.
            # Migration 7dec24a98839 rewrote the historic IN-list predicate.
            postgresql_where=text("perimeter NOT IN ('other')"),
        ),
    )
