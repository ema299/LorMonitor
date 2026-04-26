"""User consent acceptance records (B.3 — append-only audit trail).

Each row = one consent acceptance event. Never UPDATEd, never DELETEd by
application code. CASCADE on user deletion handles GDPR right-to-erase.

Migration: ``c4f9e1d8a2b6_user_consents_table.py``.
"""
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column

from backend.models import Base


class UserConsent(Base):
    __tablename__ = "user_consents"

    id = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind = mapped_column(String(40), nullable=False)
    version = mapped_column(String(20), nullable=False)
    accepted_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ip = mapped_column(String(45), nullable=True)
    user_agent = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index(
            "idx_user_consents_user_kind",
            "user_id",
            "kind",
            "accepted_at",
            postgresql_using="btree",
        ),
    )
