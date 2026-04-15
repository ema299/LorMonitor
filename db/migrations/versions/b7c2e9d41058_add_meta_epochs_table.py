"""add meta_epochs table (Sprint P1 — native digest generator)

Revision ID: b7c2e9d41058
Revises: a3f1c2b8e904
Create Date: 2026-04-15 14:00:00.000000

Introduce meta_epochs, a small reference table that records the rotation
windows (legal set lists + start/end dates) that the native digest generator
uses to bound its 30-day lookback. One row per rotation era; the row whose
ended_at IS NULL is the "current" epoch.

Seed with the two epochs covering the existing PG dataset:
  1. Pre-Set12 (2026-01-01 .. 2026-03-27) — Sets 1..11, pre-rotation.
  2. Set11 settled (2026-03-28 .. NULL)   — Sets 1..11, current epoch.

Adjust legal_sets / bounds here as Set 12 rotates in.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7c2e9d41058"
down_revision: Union[str, None] = "a3f1c2b8e904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meta_epochs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Date(), nullable=False),
        sa.Column("ended_at", sa.Date(), nullable=True),
        sa.Column(
            "legal_sets",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_meta_epochs_current",
        "meta_epochs",
        ["ended_at"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    # Seed two rows covering the existing PG dataset.
    op.execute(
        """
        INSERT INTO meta_epochs (id, name, started_at, ended_at, legal_sets, notes)
        VALUES
          (1, 'Pre-Set12', DATE '2026-01-01', DATE '2026-03-27',
           ARRAY[1,2,3,4,5,6,7,8,9,10,11], 'Pre-rotation epoch'),
          (2, 'Set11 settled', DATE '2026-03-28', NULL,
           ARRAY[1,2,3,4,5,6,7,8,9,10,11], 'Current epoch, post-rotation 28/03')
        """
    )
    # Bump the sequence so future inserts don't collide with the seeded ids.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('meta_epochs', 'id'), "
        "(SELECT MAX(id) FROM meta_epochs))"
    )


def downgrade() -> None:
    op.drop_index(
        "idx_meta_epochs_current",
        table_name="meta_epochs",
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.drop_table("meta_epochs")
