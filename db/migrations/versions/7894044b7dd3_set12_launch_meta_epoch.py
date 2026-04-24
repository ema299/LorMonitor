"""set12 launch — close Set11 settled, open Set12 epoch (in cassetto)

Revision ID: 7894044b7dd3
Revises: 7dec24a98839
Create Date: 2026-04-22 07:05:00.000000

DO NOT RUN THIS MIGRATION until Ravensburger announces the official Set 12
release date and rotation. It is kept as a dormant template so the cutover
at S1.1 is a single one-liner rather than writing fresh SQL under time
pressure.

Required env vars at upgrade time:
  SET12_RELEASE_DATE      — ISO date, e.g. "2026-05-15"
  SET12_LEGAL_SETS        — comma-separated int list, e.g. "3,4,5,6,7,8,9,10,11,12"
  SET12_EPOCH_NAME        — optional, defaults to "Set12 launch"

Effect:
  1. Close the currently-open Set11 settled epoch at (SET12_RELEASE_DATE - 1 day).
  2. Insert a new meta_epochs row with ended_at=NULL and the provided legal_sets.

The upgrade aborts loudly if the env vars are missing, so an accidental
``alembic upgrade head`` without the context won't half-apply the cutover.
"""
from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op


revision: str = "7894044b7dd3"
down_revision: Union[str, None] = "7dec24a98839"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _parse_legal_sets(raw: str) -> list[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise RuntimeError(
            f"SET12_LEGAL_SETS must be a comma-separated list of integers; got {raw!r}"
        ) from exc


def upgrade() -> None:
    release_date = os.environ.get("SET12_RELEASE_DATE", "").strip()
    legal_sets_raw = os.environ.get("SET12_LEGAL_SETS", "").strip()
    epoch_name = os.environ.get("SET12_EPOCH_NAME", "Set12 launch").strip()

    if not release_date or not legal_sets_raw:
        raise RuntimeError(
            "Set12 launch migration requires SET12_RELEASE_DATE and "
            "SET12_LEGAL_SETS env vars. Aborting to avoid half-applying the "
            "cutover. Re-run like: "
            "SET12_RELEASE_DATE=YYYY-MM-DD SET12_LEGAL_SETS=... alembic upgrade head"
        )

    legal_sets = _parse_legal_sets(legal_sets_raw)
    legal_sets_sql = "ARRAY[" + ",".join(str(n) for n in legal_sets) + "]"

    op.execute(
        f"""
        UPDATE meta_epochs
           SET ended_at = DATE '{release_date}' - INTERVAL '1 day'
         WHERE name = 'Set11 settled' AND ended_at IS NULL;
        """
    )
    op.execute(
        f"""
        INSERT INTO meta_epochs (name, started_at, ended_at, legal_sets, notes)
        VALUES (
            '{epoch_name}',
            DATE '{release_date}',
            NULL,
            {legal_sets_sql},
            'Set 12 release epoch (migration 7894044b7dd3)'
        );
        """
    )


def downgrade() -> None:
    epoch_name = os.environ.get("SET12_EPOCH_NAME", "Set12 launch").strip()
    op.execute(
        f"""
        DELETE FROM meta_epochs WHERE name = '{epoch_name}' AND ended_at IS NULL;
        """
    )
    op.execute(
        """
        UPDATE meta_epochs SET ended_at = NULL
         WHERE name = 'Set11 settled';
        """
    )
