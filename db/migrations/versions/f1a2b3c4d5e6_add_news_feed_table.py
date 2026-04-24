"""add news_feed table

Revision ID: f1a2b3c4d5e6
Revises: e84c3f7a1b22
Create Date: 2026-04-16 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e84c3f7a1b22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news_feed",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("label", sa.String(length=10), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=280), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("channel", sa.String(length=100), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_news_feed_active_published",
        "news_feed",
        ["is_active", sa.literal_column("published_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_news_feed_source_url",
        "news_feed",
        ["source", "url"],
        unique=True,
        postgresql_where=sa.text("url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_news_feed_source_url", table_name="news_feed")
    op.drop_index("idx_news_feed_active_published", table_name="news_feed")
    op.drop_table("news_feed")
