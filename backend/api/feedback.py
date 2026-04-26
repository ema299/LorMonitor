"""B.6 Fase 1 — POST /api/v1/feedback for user-submitted feedback.

Rate-limited (5/day per authenticated user, 3/day per anon-IP) to discourage
spam. IP is hashed (SHA256) before storage — never raw — and counted via the
ip_hash column.

Anonymous submissions are accepted: feedback button must work even before
sign-in. ``user_id`` is null for anon, the JWT injects it when present.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.deps import get_db, get_optional_current_user
from backend.models.feedback import UserFeedback
from backend.models.user import User

router = APIRouter()

VALID_KINDS = ("bug", "request", "general", "coach_issue")
DAILY_LIMIT_USER = 5
DAILY_LIMIT_ANON = 3


class FeedbackRequest(BaseModel):
    kind: str = Field(default="general")
    message: str = Field(min_length=4, max_length=4000)
    page_url: str | None = Field(default=None, max_length=500)
    user_agent: str | None = Field(default=None, max_length=500)


def _hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str | None:
    # Behind nginx: trust X-Forwarded-For if present (single-hop here).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/feedback", status_code=201)
def submit_feedback(
    body: FeedbackRequest,
    request: Request,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    if body.kind not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"kind must be one of {VALID_KINDS}",
        )

    ip = _client_ip(request)
    ip_hash = _hash_ip(ip)
    one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    if user is not None:
        recent = (
            db.query(func.count(UserFeedback.id))
            .filter(
                UserFeedback.user_id == user.id,
                UserFeedback.created_at >= one_day_ago,
            )
            .scalar()
        )
        if recent and recent >= DAILY_LIMIT_USER:
            raise HTTPException(
                status_code=429,
                detail=f"Daily feedback limit reached ({DAILY_LIMIT_USER}/24h). Try again tomorrow.",
            )
    else:
        if ip_hash:
            recent = (
                db.query(func.count(UserFeedback.id))
                .filter(
                    UserFeedback.user_id.is_(None),
                    UserFeedback.ip_hash == ip_hash,
                    UserFeedback.created_at >= one_day_ago,
                )
                .scalar()
            )
            if recent and recent >= DAILY_LIMIT_ANON:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily feedback limit reached ({DAILY_LIMIT_ANON}/24h). Sign in to send more.",
                )

    row = UserFeedback(
        user_id=user.id if user else None,
        kind=body.kind,
        message=body.message.strip(),
        page_url=body.page_url,
        user_agent=body.user_agent,
        ip_hash=ip_hash,
        status="new",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": str(row.id),
        "kind": row.kind,
        "status": row.status,
        "detail": "Thanks — your feedback has been recorded.",
    }
