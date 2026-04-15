"""KC Spy service — PG-backed reader for dashboard runtime."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.analysis import KCSpyReport


def get_latest_report(db: Session) -> dict:
    stmt = (
        select(KCSpyReport)
        .order_by(KCSpyReport.report_date.desc(), KCSpyReport.imported_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalar_one_or_none()
    return row.report if row else {}
