"""Community models — videos and tournaments."""
import uuid
from datetime import date

from sqlalchemy import String, Boolean, Date, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import mapped_column

from backend.models import Base


class Video(Base):
    __tablename__ = "videos"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = mapped_column(String(200), nullable=False)
    url = mapped_column(String(500), nullable=False)
    platform = mapped_column(String(20), nullable=True)  # youtube, twitch
    topic = mapped_column(String(50), nullable=True)      # tutorial, tournament, review
    tags = mapped_column(JSONB, default=[])
    is_live = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tournament(Base):
    __tablename__ = "tournaments"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = mapped_column(String(200), nullable=False)
    date = mapped_column(Date, nullable=False)
    location = mapped_column(String(200), nullable=True)
    format = mapped_column(String(20), nullable=True)  # core, infinity
    region = mapped_column(String(50), nullable=True)
    url = mapped_column(String(500), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
