"""user_consents — append-only audit trail for consent acceptances (B.3)

Revision ID: c4f9e1d8a2b6
Revises: b8e72d4a9c3f
Create Date: 2026-04-26 10:00:00.000000

Promotes consents from JSONB ``users.preferences.consents.<kind>`` (overwrite
semantics) to a dedicated append-only table with full history. The JSONB cache
stays for fast UI checks ("did the user accept the latest TOS?") but the table
is the legal source of truth for audit / GDPR access.

Schema:
- ``id UUID PK`` default gen_random_uuid()
- ``user_id UUID NOT NULL`` FK ``users(id) ON DELETE CASCADE``
- ``kind VARCHAR(40)`` — 'tos' | 'privacy' | 'replay_upload' | 'marketing'
  (enforced at API layer with regex, table accepts any kind for forward-compat)
- ``version VARCHAR(20)`` — accepted T&C version
- ``accepted_at TIMESTAMPTZ NOT NULL DEFAULT now()``
- ``ip VARCHAR(45)`` — IPv4 max 15 / IPv6 max 45 chars; nullable
- ``user_agent VARCHAR(500)`` — nullable, truncated at 500 chars at API layer

Indexes:
- ``idx_user_consents_user_kind`` on ``(user_id, kind, accepted_at DESC)`` —
  fast "latest acceptance per kind" lookup

Append-only by convention: API never UPDATEs or DELETEs rows. CASCADE on user
deletion handles GDPR right-to-erase.

Heads after this migration: 2 parallel
- ``7894044b7dd3`` Set12 cassetto dormant (unchanged)
- ``c4f9e1d8a2b6`` current
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision: str = "c4f9e1d8a2b6"
down_revision: Union[str, None] = "b8e72d4a9c3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_consents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "idx_user_consents_user_kind",
        "user_consents",
        ["user_id", "kind", sa.text("accepted_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_user_consents_user_kind", table_name="user_consents")
    op.drop_table("user_consents")
