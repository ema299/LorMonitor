#!/usr/bin/env python3
"""Daily cron health report — checks all App_tool scheduled jobs ran successfully.

Reads log files and PG timestamps to determine if each job:
  - Ran today (or within expected window)
  - Produced output / updated data
  - Had errors

Usage:
    python3 scripts/cron_health_report.py          # print to stdout
    python3 scripts/cron_health_report.py --mail    # send email if any FAIL/STALE

Cron: daily 08:00 (after all nightly jobs complete)
"""
from __future__ import annotations

import argparse
import os
import sys
import smtplib
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

LOG_DIR = Path("/var/log")
DIGEST_DIR = _PROJECT_ROOT / "output" / "digests"
SMTP_PASS_FILE = Path("/tmp/.smtp_pass")
MAIL_FROM = "monitorteamfe@gmail.com"
MAIL_TO = os.getenv("CRON_REPORT_MAIL", "alexander9.ed@gmail.com")


def _log_last_line(log_path: Path, max_age_hours: int = 26) -> tuple[str, str]:
    """Read last non-empty line from log. Returns (status, detail)."""
    if not log_path.exists():
        return "MISSING", f"log file not found: {log_path}"
    age_hours = (datetime.now().timestamp() - log_path.stat().st_mtime) / 3600
    if age_hours > max_age_hours:
        return "STALE", f"last modified {age_hours:.0f}h ago"
    try:
        lines = log_path.read_text().strip().splitlines()
        last = lines[-1] if lines else "(empty)"
        has_error = any(w in last.lower() for w in ["error", "fail", "traceback", "exception"])
        if has_error:
            return "ERROR", last[-120:]
        return "OK", last[-80:]
    except Exception as e:
        return "ERROR", str(e)


def _pg_freshness(query: str, label: str, max_age_hours: int = 26) -> tuple[str, str]:
    """Check PG table freshness."""
    try:
        from backend.models import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        row = db.execute(text(query)).fetchone()
        db.close()
        if not row or not row[0]:
            return "EMPTY", f"no data in {label}"
        ts = row[0]
        if hasattr(ts, 'timestamp'):
            age_hours = (datetime.now().timestamp() - ts.timestamp()) / 3600
        else:
            age_hours = (date.today() - ts).days * 24
        if age_hours > max_age_hours:
            return "STALE", f"{label}: last update {age_hours:.0f}h ago"
        return "OK", f"{label}: {ts}"
    except Exception as e:
        return "ERROR", f"{label}: {e}"


def run_checks() -> list[dict]:
    """Run all cron health checks. Returns list of {job, status, detail}."""
    checks = []
    today_weekday = datetime.now().weekday()  # 0=Mon, 1=Tue

    # 1. Match import (every 2h)
    s, d = _pg_freshness(
        "SELECT MAX(imported_at) FROM matches", "matches.imported_at", max_age_hours=4
    )
    checks.append({"job": "import_matches (*/2h)", "status": s, "detail": d})

    # 2. Backup (daily 03:00)
    s, d = _log_last_line(LOG_DIR / "lorcana-backup.log")
    checks.append({"job": "backup (03:00)", "status": s, "detail": d})

    # 3. KC Spy import (daily 04:05)
    s, d = _log_last_line(LOG_DIR / "lorcana-import.log")
    checks.append({"job": "import_kc_spy (04:05)", "status": s, "detail": d})

    # 4. Matchup reports (daily 05:30)
    s, d = _log_last_line(LOG_DIR / "lorcana-reports.log")
    checks.append({"job": "matchup_reports (05:30)", "status": s, "detail": d})

    # 5. Snapshot assembler (daily 05:35)
    s, d = _log_last_line(LOG_DIR / "lorcana-import.log")
    checks.append({"job": "assemble_snapshot (05:35)", "status": s, "detail": d})

    # 6. KC freshness monitor (daily 07:00)
    s, d = _log_last_line(LOG_DIR / "lorcana-kc-freshness.log")
    checks.append({"job": "kc_freshness (07:00)", "status": s, "detail": d})

    # 7. Health check (every 5min)
    s, d = _log_last_line(LOG_DIR / "lorcana-health.log", max_age_hours=1)
    checks.append({"job": "healthcheck (*/5min)", "status": s, "detail": d})

    # 8. API alive
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://127.0.0.1:8100/api/v1/health", timeout=5)
        import json
        data = json.loads(resp.read())
        checks.append({"job": "API /health", "status": "OK", "detail": f"matches={data.get('tables',{}).get('matches','?')}"})
    except Exception as e:
        checks.append({"job": "API /health", "status": "DOWN", "detail": str(e)[:80]})

    # --- Weekly checks (only on expected days) ---

    # 9. Digest refresh (Tue 00:00)
    s, d = _log_last_line(LOG_DIR / "lorcana-digest.log", max_age_hours=7*24+2)
    n_digests = len(list(DIGEST_DIR.glob("digest_*.json"))) if DIGEST_DIR.exists() else 0
    checks.append({"job": f"digests (Tue 00:00) [{n_digests} files]", "status": s, "detail": d})

    # 10. Playbooks (Tue 01:00)
    s, d = _log_last_line(LOG_DIR / "lorcana-playbook.log", max_age_hours=7*24+2)
    checks.append({"job": "playbooks (Tue 01:00)", "status": s, "detail": d})

    # 11. Killer curves (Tue 01:30)
    s, d = _log_last_line(LOG_DIR / "lorcana-kc.log", max_age_hours=7*24+2)
    checks.append({"job": "killer_curves (Tue 01:30)", "status": s, "detail": d})

    # 12. Decks DB builder (daily 04:30)
    s, d = _log_last_line(Path("/root/finanza/Lor/decks_db_builder_cron.log"))
    checks.append({"job": "decks_db_builder (04:30)", "status": s, "detail": d})

    # 13. PG killer_curves freshness
    s, d = _pg_freshness(
        "SELECT MAX(generated_at) FROM killer_curves WHERE is_current = true",
        "killer_curves.generated_at",
        max_age_hours=8*24  # weekly, so 8 days tolerance
    )
    checks.append({"job": "PG killer_curves freshness", "status": s, "detail": d})

    # 14. PG matchup_reports freshness
    s, d = _pg_freshness(
        "SELECT MAX(generated_at) FROM matchup_reports WHERE is_current = true",
        "matchup_reports.generated_at",
        max_age_hours=26
    )
    checks.append({"job": "PG matchup_reports freshness", "status": s, "detail": d})

    return checks


def format_report(checks: list[dict]) -> str:
    """Format checks into a text report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"=== Cron Health Report — {now} ===\n"]

    ok = sum(1 for c in checks if c["status"] == "OK")
    fail = sum(1 for c in checks if c["status"] not in ("OK",))
    lines.append(f"Summary: {ok} OK, {fail} issues\n")

    for c in checks:
        icon = "OK" if c["status"] == "OK" else f"**{c['status']}**"
        lines.append(f"  [{icon:>8}] {c['job']}")
        if c["status"] != "OK":
            lines.append(f"           {c['detail']}")

    lines.append("")
    return "\n".join(lines)


def send_mail(subject: str, body: str):
    """Send alert email via Gmail SMTP."""
    if not SMTP_PASS_FILE.exists():
        print(f"SMTP password not found at {SMTP_PASS_FILE}, skipping mail")
        return
    password = SMTP_PASS_FILE.read_text().strip()
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(MAIL_FROM, password)
        server.send_message(msg)
    print(f"Mail sent to {MAIL_TO}")


def main():
    p = argparse.ArgumentParser(description="Cron health report")
    p.add_argument("--mail", action="store_true", help="Send email if any issues")
    args = p.parse_args()

    checks = run_checks()
    report = format_report(checks)
    print(report)

    has_issues = any(c["status"] not in ("OK",) for c in checks)
    if args.mail and has_issues:
        send_mail(
            f"[MetaMonitor] Cron Health: {sum(1 for c in checks if c['status'] != 'OK')} issues",
            report
        )


if __name__ == "__main__":
    main()
