"""B.6 Fase 1 — user_feedback + ops_incidents tables

Adds two related but separate tables:

- ``user_feedback``: user-submitted bug reports / feature requests / general
  feedback / coach issues. Captured via POST /api/v1/feedback. Rate-limited
  upstream; persisted regardless of digest status for audit.

- ``ops_incidents``: cron / pipeline failures reported via the
  ``backend.services.incident_reporter.report_incident()`` helper. Severity
  tagged so the daily digest mail (07:30 UTC) can show only ``>=warn``.

Both tables are additive, do not touch existing schemas, and are independent
of the Set12 dormant cassette (`7894044b7dd3`). Down_revision is the current
B.7 head ``d5a8f3e1c2b9``.

Revision ID: a3f8e2c91b4d
Revises: d5a8f3e1c2b9
Create Date: 2026-04-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a3f8e2c91b4d"
down_revision: Union[str, None] = "d5a8f3e1c2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── user_feedback ──────────────────────────────────────────────────
    op.create_table(
        "user_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "kind",
            sa.String(20),
            nullable=False,
            server_default="general",
            comment="bug | request | general | coach_issue",
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page_url", sa.String(500), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "ip_hash",
            sa.String(64),
            nullable=True,
            comment="SHA256 of client IP (anti-spam, never raw IP)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="new",
            comment="new | digested | triaged | resolved | spam",
        ),
        sa.Column("triage_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_user_feedback_status_created",
        "user_feedback",
        ["status", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_user_feedback_kind",
        "user_feedback",
        ["kind"],
    )

    # ── ops_incidents ──────────────────────────────────────────────────
    op.create_table(
        "ops_incidents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source",
            sa.String(80),
            nullable=False,
            comment="cron name / worker module emitting the incident",
        ),
        sa.Column(
            "severity",
            sa.String(20),
            nullable=False,
            server_default="warn",
            comment="info | warn | error | critical",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="new",
            comment="new | digested | resolved | acknowledged",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("digested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_ops_incidents_severity_created",
        "ops_incidents",
        ["severity", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_ops_incidents_status",
        "ops_incidents",
        ["status"],
    )
    op.create_index(
        "idx_ops_incidents_source",
        "ops_incidents",
        ["source"],
    )


def downgrade() -> None:
    op.drop_index("idx_ops_incidents_source", table_name="ops_incidents")
    op.drop_index("idx_ops_incidents_status", table_name="ops_incidents")
    op.drop_index("idx_ops_incidents_severity_created", table_name="ops_incidents")
    op.drop_table("ops_incidents")

    op.drop_index("idx_user_feedback_kind", table_name="user_feedback")
    op.drop_index("idx_user_feedback_status_created", table_name="user_feedback")
    op.drop_table("user_feedback")
