"""add match_log_features table

Revision ID: e84c3f7a1b22
Revises: d1e4c66a7f11
Create Date: 2026-04-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e84c3f7a1b22"
down_revision: Union[str, None] = "d1e4c66a7f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_log_features",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("extractor_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("match_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("player1_features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("player2_features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("viewer_public_log", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id"),
    )
    op.create_index("idx_match_log_features_match_id", "match_log_features", ["match_id"], unique=True)
    op.create_index(
        "idx_match_log_features_computed_at",
        "match_log_features",
        [sa.literal_column("computed_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_match_log_features_computed_at", table_name="match_log_features")
    op.drop_index("idx_match_log_features_match_id", table_name="match_log_features")
    op.drop_table("match_log_features")
