"""Transactional email sender — Gmail SMTP via /tmp/.smtp_pass.

Used for user-facing transactional flows (password reset, account events).
For ops alerts (cron failures, KC drift), keep using the inline pattern in
``scripts/cron_health_report.py`` — those are operator-only, run from cron,
and don't share runtime context with FastAPI.

Configuration (env, overridable for tests):
- ``LM_MAIL_FROM`` — sender address. Default ``monitorteamfe@gmail.com``.
- ``LM_SMTP_PASS_FILE`` — path to Gmail app password. Default ``/tmp/.smtp_pass``.
- ``LM_BASE_URL`` — public origin used in email links. Default
  ``https://metamonitor.app``.
- ``LM_SMTP_DISABLED`` — when set to ``1``/``true``, send_* functions log
  intent and skip the network call (handy in dev/CI).

Failure mode: log + return ``False``. Callers (e.g. forgot-password) should
NOT propagate failures to the client — anti-enumeration policy returns 200
regardless.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)


def _config():
    return {
        "from": os.getenv("LM_MAIL_FROM", "monitorteamfe@gmail.com"),
        "pass_file": Path(os.getenv("LM_SMTP_PASS_FILE", "/tmp/.smtp_pass")),
        "base_url": os.getenv("LM_BASE_URL", "https://metamonitor.app").rstrip("/"),
        "disabled": (os.getenv("LM_SMTP_DISABLED", "") or "").lower() in ("1", "true", "yes"),
    }


def _send(to_addr: str, subject: str, body: str) -> bool:
    """Low-level send. Returns True on success, False otherwise."""
    cfg = _config()
    if cfg["disabled"]:
        logger.info("smtp disabled by env, skipping send to=%s subject=%s", to_addr, subject)
        return False
    if not cfg["pass_file"].exists():
        logger.warning("smtp password file missing at %s, cannot send mail", cfg["pass_file"])
        return False
    try:
        password = cfg["pass_file"].read_text().strip()
    except OSError as exc:
        logger.warning("smtp password unreadable: %s", exc)
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to_addr
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(cfg["from"], password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("smtp send failed to=%s subject=%s err=%s", to_addr, subject, exc)
        return False
    logger.info("smtp send ok to=%s subject=%s", to_addr, subject)
    return True


def send_password_reset_email(email: str, raw_token: str) -> bool:
    """Send the password reset link to ``email``. Best-effort.

    The link points at ``<LM_BASE_URL>/dashboard.html?reset_token=<token>``,
    which auth_signin.js auto-detects and opens the reset modal.
    """
    cfg = _config()
    link = f"{cfg['base_url']}/dashboard.html?reset_token={raw_token}"
    subject = "Reset your Lorcana Monitor password"
    body = (
        "Hi,\n\n"
        "We received a request to reset your password for Lorcana Monitor.\n\n"
        f"Click the link below to choose a new password (valid for 1 hour):\n{link}\n\n"
        "If you didn't request this, you can ignore this email — your password\n"
        "will not change.\n\n"
        "— Lorcana Monitor (metamonitor.app)\n"
    )
    return _send(email, subject, body)
