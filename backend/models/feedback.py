"""B.6 — user feedback + ops incidents models.

Two unrelated-but-sibling tables sharing a daily digest mail:

- ``UserFeedback``: user-submitted bug reports / requests / coach issues.
  Captured by ``POST /api/v1/feedback`` (rate-limited).
- ``OpsIncident``: cron / worker failures emitted by
  ``backend.services.incident_reporter.report_incident()``.

Migration: ``a3f8e2c91b4d``.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # bug | request | general | coach_issue
    kind: Mapped[str] = mapped_column(String(20), nullable=False, server_default="general")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # new | digested | triaged | resolved | spam
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    triage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OpsIncident(Base):
    __tablename__ = "ops_incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    # info | warn | error | critical
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="warn")
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # new | digested | resolved | acknowledged
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    digested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
