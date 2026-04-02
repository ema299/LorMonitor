"""Alerting service — Telegram bot notifications."""
import logging
import os

logger = logging.getLogger(__name__)

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")


def send_alert(message: str, level: str = "warn") -> bool:
    """Send alert via Telegram. Returns True if sent."""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        logger.info("Alerting not configured. Message: %s", message)
        return False

    try:
        import requests
        prefix = {"error": "\u274c", "warn": "\u26a0\ufe0f", "info": "\u2139\ufe0f"}.get(level, "")
        text = f"{prefix} Lorcana Monitor: {message}"
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text},
            timeout=10,
        )
        return resp.ok
    except Exception as e:
        logger.error("Telegram alert failed: %s", e)
        return False


def alert_health_degraded(checks: dict):
    send_alert(f"Health degraded: {checks}", level="error")


def alert_disk_low(free_gb: float):
    send_alert(f"Disk space low: {free_gb:.1f} GB free", level="error")


def alert_backup_failed(error: str):
    send_alert(f"Backup failed: {error}", level="error")


def alert_login_failed(ip: str, attempts: int):
    send_alert(f"Login brute force: {attempts} attempts from {ip}", level="warn")
