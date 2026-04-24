"""team_replays ownership — add user_id, is_private, consent_version, uploaded_via, shared_with

Revision ID: 9a1e47b3f0c2
Revises: 8890033ea91a
Create Date: 2026-04-24 09:30:00.000000

GDPR ownership layer for Board Lab replay uploads (privacy layer V3 — M1).

Additive migration — zero downtime, non-destructive:
- ``user_id UUID NULL`` FK a ``users(id) ON DELETE CASCADE`` — ownership del replay
- ``is_private BOOLEAN NOT NULL DEFAULT true`` — default private (V3 non espone mai public uploads al lancio)
- ``consent_version VARCHAR(10) NULL`` — versione del consenso accettato al momento upload
- ``uploaded_via VARCHAR(20) NULL`` — 'team_lab' | 'board_lab' | 'api'
- ``shared_with JSONB NOT NULL DEFAULT '[]'::jsonb`` — array di user_id UUID con cui l'owner ha condiviso

Indici:
- ``idx_team_replays_user`` su ``user_id`` (partial WHERE user_id IS NOT NULL) — lookup owner
- ``idx_team_replays_private`` su ``(is_private, user_id)`` — filtro access-control

Backfill strategy:
- Nessun backfill automatico. Record pre-M1 restano user_id=NULL.
- Access-control nega accesso a orphan (user_id IS NULL) tranne admin.
- Dopo 30gg: decisione manuale hard-delete orphan o backfill via player_name.
- NOT NULL su user_id rimandato a M2 post-backfill.

Vedi ARCHITECTURE.md §24 "Sensitive Data & Privacy Architecture — V3 Launch Layer".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision: str = "9a1e47b3f0c2"
down_revision: Union[str, None] = "8890033ea91a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_replays",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "team_replays",
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "team_replays",
        sa.Column("consent_version", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "team_replays",
        sa.Column("uploaded_via", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "team_replays",
        sa.Column(
            "shared_with",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.create_index(
        "idx_team_replays_user",
        "team_replays",
        ["user_id"],
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "idx_team_replays_private",
        "team_replays",
        ["is_private", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_team_replays_private", table_name="team_replays")
    op.drop_index("idx_team_replays_user", table_name="team_replays")
    op.drop_column("team_replays", "shared_with")
    op.drop_column("team_replays", "uploaded_via")
    op.drop_column("team_replays", "consent_version")
    op.drop_column("team_replays", "is_private")
    op.drop_column("team_replays", "user_id")
