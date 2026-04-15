"""add kc_spy_reports table

Revision ID: d1e4c66a7f11
Revises: c3f9a0a6e2bd
Create Date: 2026-04-15 23:58:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d1e4c66a7f11"
down_revision: Union[str, None] = "c3f9a0a6e2bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kc_spy_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_date"),
    )
    op.create_index(
        "idx_kc_spy_reports_date",
        "kc_spy_reports",
        [sa.literal_column("report_date DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_kc_spy_reports_date", table_name="kc_spy_reports")
    op.drop_table("kc_spy_reports")
