from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class MatchupReport(Base):
    __tablename__ = "matchup_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_format: Mapped[str] = mapped_column(String(20), nullable=False)
    our_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    opp_deck: Mapped[str] = mapped_column(String(10), nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        UniqueConstraint("game_format", "our_deck", "opp_deck", "report_type", "generated_at"),
        Index(
            "idx_reports_lookup",
            "game_format", "our_deck", "opp_deck", "report_type", "is_current",
            postgresql_where=text("is_current = true"),
        ),
    )
