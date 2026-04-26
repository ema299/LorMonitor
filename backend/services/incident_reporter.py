"""B.6 — operational incident reporter.

Reusable helper for cron jobs and async workers to emit structured incidents
into ``ops_incidents`` PG. The daily digest mail (07:30 UTC) reads this table
and surfaces only ``severity >= warn`` to the operator.

Design notes:
- Each call opens its own short-lived ``SessionLocal`` so callers don't have
  to thread a session through. Safe to invoke from any process context.
- Failures are swallowed and logged: an incident reporter that crashes the
  caller would defeat its own purpose.
- Use as a context manager via ``with capture(source="kc_batch"): ...``
  for try/except style or as a function call ``report_incident(...)``.

Severity ladder:
- ``info``: noteworthy but expected (e.g. "no new digests today").
- ``warn``: degraded behavior, manual review nice to have.
- ``error``: pipeline failed but no user-visible impact yet.
- ``critical``: production-impacting; page operator immediately.

Usage::

    from backend.services.incident_reporter import report_incident

    try:
        do_kc_batch()
    except Exception as exc:
        report_incident(
            source="kc_batch_full",
            severity="error",
            payload={"error": str(exc), "traceback": traceback.format_exc()},
        )
        raise
"""
from __future__ import annotations

import contextlib
import logging
import traceback as tb_module
from typing import Any

from backend.models import SessionLocal
from backend.models.feedback import OpsIncident

logger = logging.getLogger(__name__)

VALID_SEVERITIES = ("info", "warn", "error", "critical")


def report_incident(
    *,
    source: str,
    severity: str = "warn",
    payload: dict[str, Any] | None = None,
) -> bool:
    """Persist one incident row. Returns True on success, False on failure.

    Args:
        source: identifier of the emitting cron/worker (e.g.
                ``"kc_batch_full"``, ``"import_matches"``,
                ``"snapshot_assembler"``). Free-form ≤80 chars.
        severity: one of ``info | warn | error | critical``. Default ``warn``.
        payload: arbitrary JSON-serializable dict with details (error
                 message, traceback, run_id, counts, etc.). Stored as JSONB.
    """
    if severity not in VALID_SEVERITIES:
        logger.warning("incident_reporter: unknown severity %s, coercing to 'warn'", severity)
        severity = "warn"
    safe_payload = payload or {}

    db = SessionLocal()
    try:
        row = OpsIncident(
            source=source[:80] if source else "unknown",
            severity=severity,
            payload=safe_payload,
            status="new",
        )
        db.add(row)
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001 — never raise from the reporter
        logger.warning(
            "incident_reporter failed source=%s severity=%s err=%s",
            source, severity, exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            db.close()
        except Exception:
            pass


@contextlib.contextmanager
def capture(source: str, severity: str = "error"):
    """Context manager that converts a raised exception into an incident.

    Re-raises after reporting. Use to instrument cron entry points::

        with capture(source="monitor_kc_freshness", severity="error"):
            run_check()
    """
    try:
        yield
    except Exception as exc:  # noqa: BLE001 — wrap any failure
        report_incident(
            source=source,
            severity=severity,
            payload={
                "error": str(exc),
                "traceback": tb_module.format_exc(limit=20),
            },
        )
        raise
