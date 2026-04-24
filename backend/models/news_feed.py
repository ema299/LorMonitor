"""News feed items for the Meta Ticker."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class NewsFeedItem(Base):
    __tablename__ = "news_feed"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    label: Mapped[str] = mapped_column(String(10), nullable=False)       # NEWS, EVENT, VIDEO, BUZZ
    source: Mapped[str] = mapped_column(String(20), nullable=False)      # youtube, reddit, manual
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"), nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False,
    )

    __table_args__ = (
        Index("idx_news_feed_active_published", "is_active", published_at.desc()),
        Index("idx_news_feed_source_url", "source", "url", unique=True,
              postgresql_where=text("url IS NOT NULL")),
    )
