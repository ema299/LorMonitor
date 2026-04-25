"""Team coaching models — replays, roster, and session notes."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Integer, DateTime, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import mapped_column

from backend.models import Base


class TeamReplay(Base):
    __tablename__ = "team_replays"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_name = mapped_column(String(100), nullable=False, index=True)
    game_id = mapped_column(String(100), nullable=False, unique=True)
    perspective = mapped_column(Integer, nullable=True)
    opponent_name = mapped_column(String(100), nullable=True)
    winner = mapped_column(Integer, nullable=True)
    victory_reason = mapped_column(String(50), nullable=True)
    turn_count = mapped_column(Integer, nullable=True)
    replay_data = mapped_column(JSONB, nullable=False)  # compact ~5KB
    created_at = mapped_column(DateTime, server_default=func.now())

    # Privacy layer V3 — M1 (ARCHITECTURE.md §24.4)
    # Migration: 9a1e47b3f0c2_team_replays_ownership.py
    user_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    is_private = mapped_column(Boolean, nullable=False, server_default="true")
    consent_version = mapped_column(String(10), nullable=True)
    uploaded_via = mapped_column(String(20), nullable=True)  # 'team_lab' | 'board_lab' | 'api'
    shared_with = mapped_column(JSONB, nullable=False, server_default="[]")


class TeamRoster(Base):
    __tablename__ = "team_roster"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = mapped_column(String(100), nullable=False, unique=True)
    role = mapped_column(String(50), nullable=True)
    added_at = mapped_column(DateTime, server_default=func.now())


class ReplaySessionNote(Base):
    """Owner-only private note attached to a Board Lab replay (B.2 MVP A).

    By design private to ``user_id``: no sharing, no collaborative editing.
    Migration ``b8e72d4a9c3f``. CASCADE on both FKs (replay deletion = note gone,
    user deletion = note gone, GDPR-clean).
    """

    __tablename__ = "replay_session_notes"
    __table_args__ = (
        UniqueConstraint("replay_id", "user_id", name="uq_replay_session_notes_owner"),
    )

    id = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    replay_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("team_replays.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    body = mapped_column(Text, nullable=False, server_default="")
    body_length_chars = mapped_column(Integer, nullable=False, server_default="0")
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
