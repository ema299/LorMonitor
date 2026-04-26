"""team_roster — Coach Workspace foundation columns (B.7.2)

Revision ID: d5a8f3e1c2b9
Revises: c4f9e1d8a2b6
Create Date: 2026-04-26 12:00:00.000000

Extends ``team_roster`` to support the Coach Workspace (B.7) tab Team
end-to-end. Additive migration only — legacy rows (coach_id NULL) remain
accessible to admin via the existing roster endpoints.

New columns:
- ``coach_id UUID NULL`` FK ``users(id) ON DELETE CASCADE`` — owner coach.
  NULL = legacy team-wide roster (admin-only access).
- ``student_user_id UUID NULL`` FK ``users(id) ON DELETE SET NULL`` — link to
  user account when student has signed up. NULL = student exists only as
  roster row (no metamonitor account yet).
- ``display_name VARCHAR(100)`` — coach-visible name (private, not analytics
  data). Backfilled from legacy ``name`` for existing rows.
- ``status_admin VARCHAR(20)`` NOT NULL DEFAULT 'active' — lifecycle:
  'invited' | 'active' | 'paused' | 'archived'.
- ``duels_nick VARCHAR(100)`` — duels.ink nickname for analytics binding.
- ``duels_nick_status VARCHAR(20)`` NOT NULL DEFAULT 'missing' — validation
  state: 'missing' | 'unverified' | 'linked' | 'conflict'. Updated by daily
  validation cron (B.7.3 task).
- ``discord_username VARCHAR(50)``, ``discord_id VARCHAR(30)`` — for B.7.9
  Discord integration (Fase 2 opzionale). Nullable.
- ``notes TEXT`` — coach-private notes about the student (e.g. tournament
  schedule, deck preferences). Distinct from session notes.
- ``revoked_at TIMESTAMPTZ`` — set when student revokes coach access (B.7.7).

Constraints:
- Drops legacy ``UNIQUE (name)`` (was team-wide; impossible at multi-coach scale).
- Adds partial unique index ``(coach_id, display_name)`` WHERE both NOT NULL —
  one coach can't list the same student twice.
- Index ``(coach_id)`` partial WHERE NOT NULL — fast lookup of "my students".
- Index ``(student_user_id)`` partial WHERE NOT NULL — fast lookup of "my
  coaches" from student side (B.7.7 GDPR).

ENUM-as-VARCHAR pattern matches existing ``users.tier`` to avoid Postgres
ENUM type ALTER complications when adding values later.

Heads after: 2 parallel — ``7894044b7dd3`` Set12 cassetto dormant + this.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision: str = "d5a8f3e1c2b9"
down_revision: Union[str, None] = "c4f9e1d8a2b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("team_roster", sa.Column(
        "coach_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    ))
    op.add_column("team_roster", sa.Column(
        "student_user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ))
    op.add_column("team_roster", sa.Column("display_name", sa.String(length=100), nullable=True))
    op.add_column("team_roster", sa.Column(
        "status_admin",
        sa.String(length=20),
        nullable=False,
        server_default=sa.text("'active'"),
    ))
    op.add_column("team_roster", sa.Column("duels_nick", sa.String(length=100), nullable=True))
    op.add_column("team_roster", sa.Column(
        "duels_nick_status",
        sa.String(length=20),
        nullable=False,
        server_default=sa.text("'missing'"),
    ))
    op.add_column("team_roster", sa.Column("discord_username", sa.String(length=50), nullable=True))
    op.add_column("team_roster", sa.Column("discord_id", sa.String(length=30), nullable=True))
    op.add_column("team_roster", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("team_roster", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

    # Backfill display_name from legacy name for existing rows. duels_nick
    # not backfilled — admin will populate explicitly when promoting legacy
    # roster rows to coach-managed students.
    op.execute("UPDATE team_roster SET display_name = name WHERE display_name IS NULL")

    # Drop legacy team-wide unique on name. Prior data integrity (no two
    # legacy rows with same name) preserved — composite constraint below
    # only restricts coached rows.
    op.execute("ALTER TABLE team_roster DROP CONSTRAINT IF EXISTS team_roster_name_key")

    op.create_index(
        "uq_team_roster_coach_displayname",
        "team_roster",
        ["coach_id", "display_name"],
        unique=True,
        postgresql_where=sa.text("coach_id IS NOT NULL AND display_name IS NOT NULL"),
    )
    op.create_index(
        "idx_team_roster_coach_id",
        "team_roster",
        ["coach_id"],
        postgresql_where=sa.text("coach_id IS NOT NULL"),
    )
    op.create_index(
        "idx_team_roster_student_user",
        "team_roster",
        ["student_user_id"],
        postgresql_where=sa.text("student_user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_team_roster_student_user", table_name="team_roster")
    op.drop_index("idx_team_roster_coach_id", table_name="team_roster")
    op.drop_index("uq_team_roster_coach_displayname", table_name="team_roster")
    # Restore legacy team-wide unique on name. If new data conflicts, fail
    # loudly so operator can decide (downgrade is dev-only anyway).
    op.execute("ALTER TABLE team_roster ADD CONSTRAINT team_roster_name_key UNIQUE (name)")
    op.drop_column("team_roster", "revoked_at")
    op.drop_column("team_roster", "notes")
    op.drop_column("team_roster", "discord_id")
    op.drop_column("team_roster", "discord_username")
    op.drop_column("team_roster", "duels_nick_status")
    op.drop_column("team_roster", "duels_nick")
    op.drop_column("team_roster", "status_admin")
    op.drop_column("team_roster", "display_name")
    op.drop_column("team_roster", "student_user_id")
    op.drop_column("team_roster", "coach_id")
