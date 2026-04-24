"""News feed service — CRUD for editorial ticker items."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_active_items(db: Session, limit: int = 20) -> list[dict]:
    """Return active, non-expired items ordered by priority then recency."""
    rows = db.execute(text("""
        SELECT id, label, source, title, url, channel, thumbnail_url,
               published_at, priority, meta
        FROM news_feed
        WHERE is_active = true
          AND (expires_at IS NULL OR expires_at > now())
        ORDER BY priority DESC, published_at DESC
        LIMIT :lim
    """), {"lim": limit}).fetchall()
    return [
        {
            "id": str(r.id),
            "label": r.label,
            "source": r.source,
            "title": r.title,
            "url": r.url,
            "channel": r.channel,
            "thumbnail_url": r.thumbnail_url,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "priority": r.priority,
            "meta": r.meta or {},
        }
        for r in rows
    ]


def upsert_from_source(db: Session, *, source: str, url: str, label: str,
                        title: str, channel: str | None = None,
                        thumbnail_url: str | None = None,
                        published_at: datetime | None = None,
                        expires_at: datetime | None = None,
                        meta: dict | None = None) -> None:
    """Insert or update an item keyed by (source, url). Used by cron fetcher."""
    import json as _json
    db.execute(text("""
        INSERT INTO news_feed (source, url, label, title, channel, thumbnail_url,
                               published_at, expires_at, meta)
        VALUES (:source, :url, :label, :title, :channel, :thumb,
                :pub, :exp, cast(:metaj as jsonb))
        ON CONFLICT (source, url) WHERE url IS NOT NULL
        DO UPDATE SET title = EXCLUDED.title,
                      thumbnail_url = EXCLUDED.thumbnail_url,
                      meta = EXCLUDED.meta,
                      is_active = true
    """), {
        "source": source, "url": url, "label": label, "title": title,
        "channel": channel, "thumb": thumbnail_url,
        "pub": published_at or datetime.now(timezone.utc),
        "exp": expires_at, "metaj": _json.dumps(meta or {}),
    })
    db.commit()


def create_item(db: Session, *, label: str, source: str, title: str,
                url: str | None = None, channel: str | None = None,
                published_at: datetime | None = None,
                expires_at: datetime | None = None,
                priority: int = 0) -> dict:
    """Create a manual news item. Returns {id, title}."""
    row = db.execute(text("""
        INSERT INTO news_feed (label, source, title, url, channel, published_at, expires_at, priority)
        VALUES (:label, :source, :title, :url, :channel, :pub, :exp, :pri)
        RETURNING id, title
    """), {
        "label": label, "source": source, "title": title,
        "url": url, "channel": channel,
        "pub": published_at or datetime.now(timezone.utc),
        "exp": expires_at, "pri": priority,
    }).fetchone()
    db.commit()
    return {"id": str(row.id), "title": row.title}


def deactivate_item(db: Session, item_id: UUID) -> bool:
    """Soft-delete an item."""
    result = db.execute(text("""
        UPDATE news_feed SET is_active = false WHERE id = :id
    """), {"id": item_id})
    db.commit()
    return result.rowcount > 0


def cleanup_expired(db: Session) -> int:
    """Delete items past their expires_at. Returns count deleted."""
    result = db.execute(text("""
        DELETE FROM news_feed WHERE expires_at IS NOT NULL AND expires_at < now()
    """))
    db.commit()
    count = result.rowcount
    if count:
        logger.info("Cleaned up %d expired news_feed items", count)
    return count
