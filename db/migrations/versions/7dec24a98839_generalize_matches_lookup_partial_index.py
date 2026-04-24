"""generalize matches_lookup partial index for future sets

Revision ID: 7dec24a98839
Revises: f1a2b3c4d5e6
Create Date: 2026-04-22 07:00:00.000000

The original ``idx_matches_lookup`` partial index was pinned to
``perimeter IN ('set11', 'top', 'pro', 'friends')``. Post-Set-12 cutover
matches with ``perimeter='set12'`` would fall OUT of that index and force a
sequential scan over ~200K rows, degrading core-format lookups from <150ms to
1-5s.

This migration recreates the index with a future-proof predicate —
``perimeter NOT IN ('other')`` — so any present or future setNN perimeter
continues to use the index without schema churn at every set rotation.

The index is rebuilt with ``CREATE INDEX CONCURRENTLY`` so the rewrite does
not lock the matches table under production traffic.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7dec24a98839"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_matches_lookup_new")
        op.execute(
            """
            CREATE INDEX CONCURRENTLY idx_matches_lookup_new
            ON matches (game_format, deck_a, deck_b, played_at DESC)
            WHERE perimeter NOT IN ('other')
            """
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_matches_lookup")
        op.execute("ALTER INDEX idx_matches_lookup_new RENAME TO idx_matches_lookup")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_matches_lookup_old")
        op.execute(
            """
            CREATE INDEX CONCURRENTLY idx_matches_lookup_old
            ON matches (game_format, deck_a, deck_b, played_at DESC)
            WHERE perimeter IN ('set11', 'top', 'pro', 'friends')
            """
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_matches_lookup")
        op.execute("ALTER INDEX idx_matches_lookup_old RENAME TO idx_matches_lookup")
