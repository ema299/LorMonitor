"""add meta JSONB column to killer_curves for cost + token tracking

Revision ID: 8890033ea91a
Revises: 7dec24a98839
Create Date: 2026-04-22

Additive, zero-risk. Adds a `meta JSONB NOT NULL DEFAULT '{}'` column so that
every LLM-generated curve record persists its cost, tokens, model, duration,
and prompt/digest hashes. Makes "how much am I spending on KC" answerable via
SQL aggregation instead of stdout-scraping.

Parallel branch off 7dec24a98839 (shared with 7894044b7dd3 set12-in-cassetto).
Apply standalone with:

    alembic upgrade 8890033ea91a

It does not require or conflict with the set12 migration.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "8890033ea91a"
down_revision: Union[str, None] = "7dec24a98839"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "killer_curves",
        sa.Column(
            "meta",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("killer_curves", "meta")
