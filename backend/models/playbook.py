from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class DeckPlaybook(Base):
    """Blind deck playbook (Sprint-1 Liberation Day).

    Una row per (deck, game_format, generated_at). Solo l'ultima e' is_current=true
    per evitare di servire playbook stantii al frontend.
    """
    __tablename__ = "deck_playbooks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    deck: Mapped[str] = mapped_column(String(10), nullable=False)
    game_format: Mapped[str] = mapped_column(String(20), nullable=False)
    generated_at: Mapped[date] = mapped_column(Date, nullable=False)

    playbook: Mapped[dict] = mapped_column(JSONB, nullable=False)
    strategic_frame: Mapped[dict | None] = mapped_column(JSONB)
    weekly_tech: Mapped[dict | None] = mapped_column(JSONB)
    pro_references: Mapped[dict | None] = mapped_column(JSONB)
    aggregated: Mapped[dict | None] = mapped_column(JSONB)
    meta: Mapped[dict | None] = mapped_column(JSONB)

    model: Mapped[str | None] = mapped_column(String(40))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    digest_count: Mapped[int | None] = mapped_column(Integer)
    total_games: Mapped[int | None] = mapped_column(Integer)
    elapsed_sec: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))

    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("deck", "game_format", "generated_at",
                         name="uq_deck_playbooks_deck_format_date"),
        Index(
            "idx_deck_playbooks_lookup",
            "deck", "game_format", "is_current",
            postgresql_where=text("is_current = true"),
        ),
    )
