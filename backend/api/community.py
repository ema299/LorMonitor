"""Community — videos and tournaments CRUD."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.deps import get_db, require_admin
from backend.models.community import Video, Tournament
from backend.models.user import User

router = APIRouter()


# --- Schemas ---

class VideoCreate(BaseModel):
    title: str
    url: str
    platform: str | None = None
    topic: str | None = None
    tags: list[str] = []
    is_live: bool = False


class TournamentCreate(BaseModel):
    name: str
    date: str  # ISO date
    location: str | None = None
    format: str | None = None
    region: str | None = None
    url: str | None = None


# --- Videos ---

@router.get("/videos")
def list_videos(db: Session = Depends(get_db)):
    videos = db.query(Video).order_by(Video.created_at.desc()).limit(100).all()
    return [
        {
            "id": str(v.id), "title": v.title, "url": v.url,
            "platform": v.platform, "topic": v.topic,
            "tags": v.tags or [], "is_live": v.is_live,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in videos
    ]


@router.post("/videos", status_code=201)
def add_video(body: VideoCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    video = Video(
        title=body.title, url=body.url, platform=body.platform,
        topic=body.topic, tags=body.tags, is_live=body.is_live,
    )
    db.add(video)
    db.commit()
    return {"id": str(video.id), "title": video.title}


@router.delete("/videos/{video_id}", status_code=200)
def delete_video(video_id: UUID, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    db.delete(video)
    db.commit()
    return {"detail": "deleted"}


# --- Tournaments ---

@router.get("/tournaments")
def list_tournaments(db: Session = Depends(get_db)):
    tournaments = db.query(Tournament).order_by(Tournament.date.desc()).limit(100).all()
    return [
        {
            "id": str(t.id), "name": t.name,
            "date": t.date.isoformat() if t.date else None,
            "location": t.location, "format": t.format,
            "region": t.region, "url": t.url,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tournaments
    ]


@router.post("/tournaments", status_code=201)
def add_tournament(body: TournamentCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import date as dt_date
    t = Tournament(
        name=body.name, date=dt_date.fromisoformat(body.date),
        location=body.location, format=body.format,
        region=body.region, url=body.url,
    )
    db.add(t)
    db.commit()
    return {"id": str(t.id), "name": t.name}


@router.delete("/tournaments/{tournament_id}", status_code=200)
def delete_tournament(tournament_id: UUID, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(404, "Tournament not found")
    db.delete(t)
    db.commit()
    return {"detail": "deleted"}
