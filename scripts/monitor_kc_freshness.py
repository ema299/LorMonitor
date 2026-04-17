#!/usr/bin/env python3
"""P0 freshness monitor — daily check that killer_curves table has fresh data.

Exit codes:
  0 = OK (no mail sent)
  2 = STALE (data problem — mail sent)
  3 = ERROR (monitor itself failed — mail sent)

Two-signal check (both must hold for OK):
  fresh_7d  >= THRESHOLD_FRESH_7D   (catches totally missed Tuesday batch)
  age_days  <= MAX_NEWEST_AGE_DAYS  (catches "stuck at same date forever")

Baseline 2026-04-15: total=610, current=582, fresh_7d=313 (inflated by bulk 07-08/04).
Steady-state weekly batch: ~50 rows (e.g. 14/04=53, 31/03=54).
"""
import sys
import smtplib
import traceback
from datetime import datetime, date, timezone
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool")

THRESHOLD_FRESH_7D = 20
MAX_NEWEST_AGE_DAYS = 10
SMTP_USER = "alexander9.ed@gmail.com"
SMTP_PASS_FILE = "/tmp/.smtp_pass"
MAIL_TO = "monitorteamfe@gmail.com"


def send_alert(subject: str, body: str) -> None:
    try:
        pwd = Path(SMTP_PASS_FILE).read_text().strip()
    except Exception as e:
        print(f"ALERT_SEND_FAILED cannot_read_pass_file={SMTP_PASS_FILE} err={e}",
              file=sys.stderr)
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = MAIL_TO
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
            s.starttls()
            s.login(SMTP_USER, pwd)
            s.sendmail(SMTP_USER, [MAIL_TO], msg.as_string())
        print(f"ALERT_SENT to={MAIL_TO} subject={subject!r}", file=sys.stderr)
    except Exception as e:
        print(f"ALERT_SEND_FAILED smtp_err={e}", file=sys.stderr)


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "--test-mail" in sys.argv:
        send_alert(
            "[metamonitor] KC freshness monitor TEST",
            f"[{ts}] This is a test email from monitor_kc_freshness.py — "
            f"if you received it, SMTP works.",
        )
        return 0
    try:
        from backend.models import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            r = db.execute(text("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE is_current=true) AS current_rows,
                       COUNT(*) FILTER (WHERE is_current=true AND generated_at >= CURRENT_DATE - 7) AS fresh_7d,
                       COUNT(*) FILTER (WHERE is_current=true AND generated_at >= CURRENT_DATE - 14) AS fresh_14d,
                       MAX(generated_at) AS newest
                FROM killer_curves
            """)).fetchone()
        finally:
            db.close()
    except Exception:
        body = f"[{ts}] kc_freshness=ERROR\n\n{traceback.format_exc()}"
        print(body)
        send_alert("[metamonitor] KC freshness monitor ERROR", body)
        return 3

    newest = r.newest
    age_days = (date.today() - newest).days if newest else 999
    stale_count = r.fresh_7d < THRESHOLD_FRESH_7D
    stale_date = age_days > MAX_NEWEST_AGE_DAYS
    status = "STALE" if (stale_count or stale_date) else "OK"

    line = (
        f"[{ts}] kc_freshness={status} total={r.total} current={r.current_rows} "
        f"fresh_7d={r.fresh_7d} fresh_14d={r.fresh_14d} newest={newest} age_days={age_days} "
        f"threshold_7d={THRESHOLD_FRESH_7D} max_age_days={MAX_NEWEST_AGE_DAYS}"
    )
    print(line)

    if status == "STALE":
        reasons = []
        if stale_count:
            reasons.append(f"fresh_7d={r.fresh_7d} below threshold {THRESHOLD_FRESH_7D}")
        if stale_date:
            reasons.append(f"newest={newest} is {age_days} days old (>{MAX_NEWEST_AGE_DAYS})")
        body = f"{line}\n\nReasons:\n- " + "\n- ".join(reasons)
        send_alert("[metamonitor] KC freshness STALE", body)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
