"""add replay_archives table

Revision ID: c3f9a0a6e2bd
Revises: b7c2e9d41058
Create Date: 2026-04-15 23:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3f9a0a6e2bd"
down_revision: Union[str, None] = "b7c2e9d41058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "replay_archives",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("generated_at", sa.Date(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("game_format", sa.String(length=20), nullable=False),
        sa.Column("our_deck", sa.String(length=10), nullable=False),
        sa.Column("opp_deck", sa.String(length=10), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("games", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_format", "our_deck", "opp_deck", "generated_at"),
    )
    op.create_index(
        "idx_replay_archives_lookup",
        "replay_archives",
        ["game_format", "our_deck", "opp_deck"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_replay_archives_lookup", table_name="replay_archives")
    op.drop_table("replay_archives")
