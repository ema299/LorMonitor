from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class MatchLogFeature(Base):
    __tablename__ = "match_log_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    extractor_version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    match_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    player1_features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    player2_features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    viewer_public_log: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("match_id"),
        Index("idx_match_log_features_match_id", "match_id", unique=True),
        Index("idx_match_log_features_computed_at", computed_at.desc()),
    )
