"""News ticker API — public feed + admin management."""
from datetime import datetime
from enum import Enum
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.deps import get_db, require_admin
from backend.services import news_feed_service

router = APIRouter()


# -- Schemas --

class LabelEnum(str, Enum):
    NEWS = "NEWS"
    EVENT = "EVENT"
    VIDEO = "VIDEO"
    BUZZ = "BUZZ"


class NewsCreate(BaseModel):
    label: LabelEnum
    title: str = Field(..., max_length=280)
    source: str = Field(default="manual", max_length=20)
    url: str | None = Field(default=None, max_length=500)
    channel: str | None = Field(default=None, max_length=100)
    published_at: datetime | None = None
    expires_at: datetime | None = None
    priority: int = Field(default=0, ge=0, le=10)


# -- Endpoints --

@router.get("/ticker")
def get_ticker(db: Session = Depends(get_db), limit: int = Query(default=20, le=30)):
    """Public endpoint: active news items for the scrolling ticker."""
    items = news_feed_service.get_active_items(db, limit=limit)
    return JSONResponse(
        content=items,
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.post("", status_code=201)
def create_news(body: NewsCreate, admin=Depends(require_admin),
                db: Session = Depends(get_db)):
    """Admin: create a manual news item."""
    result = news_feed_service.create_item(
        db,
        label=body.label.value,
        source=body.source,
        title=body.title,
        url=body.url,
        channel=body.channel,
        published_at=body.published_at,
        expires_at=body.expires_at,
        priority=body.priority,
    )
    return result


@router.delete("/{item_id}", status_code=200)
def delete_news(item_id: UUID, admin=Depends(require_admin),
                db: Session = Depends(get_db)):
    """Admin: deactivate a news item."""
    ok = news_feed_service.deactivate_item(db, item_id)
    if not ok:
        raise HTTPException(404, "Item not found")
    return {"ok": True}
