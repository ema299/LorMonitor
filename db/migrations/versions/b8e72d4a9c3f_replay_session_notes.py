"""replay_session_notes — owner-only private notes per Board Lab replay (B.2 MVP A)

Revision ID: b8e72d4a9c3f
Revises: 9a1e47b3f0c2
Create Date: 2026-04-25 18:00:00.000000

Owner-only private notes table for Board Lab replays. Coach tier anchor (BP §6).

Schema:
- ``id UUID PK`` default gen_random_uuid()
- ``replay_id UUID NOT NULL`` FK ``team_replays(id) ON DELETE CASCADE`` (note vanishes when replay deleted)
- ``user_id UUID NOT NULL`` FK ``users(id) ON DELETE CASCADE`` (GDPR right-to-be-forgotten)
- ``body TEXT NOT NULL DEFAULT ''`` (max 50_000 chars enforced at API layer)
- ``body_length_chars INT NOT NULL DEFAULT 0`` (denormalized for cheap has_note badge)
- ``created_at TIMESTAMPTZ NOT NULL DEFAULT now()``
- ``updated_at TIMESTAMPTZ NOT NULL DEFAULT now()``

Constraint:
- UNIQUE ``(replay_id, user_id)`` — one note per (replay, user) pair, UPSERT semantics

Notes:
- No ``is_private`` / ``visibility`` column. By design ALL notes are private to user_id
  in MVP A (no sharing). Future MVP B can add visibility enum without breaking change.
- No append-only history. Single editable note per pair.

Heads after this migration: 2 parallel heads
- ``7894044b7dd3`` — Set12 cassetto dormant (unchanged)
- ``b8e72d4a9c3f`` — current (privacy → notes)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision: str = "b8e72d4a9c3f"
down_revision: Union[str, None] = "9a1e47b3f0c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "replay_session_notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "replay_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("team_replays.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "body_length_chars",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_replay_session_notes_owner",
        "replay_session_notes",
        ["replay_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_replay_session_notes_owner",
        table_name="replay_session_notes",
    )
    op.drop_table("replay_session_notes")
