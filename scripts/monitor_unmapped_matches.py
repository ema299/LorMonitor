#!/usr/bin/env python3
"""Canary filesystem-level — alert if match files are silent-dropped.

Compares three sources for the last 24h:
  1. Filesystem: match JSON files under MATCHES_DIR/YYMMDD/<folder>/*.json
  2. DB inserts: matches.imported_at >= NOW() - 24h, grouped by perimeter
  3. Skip cache: scripts/.import_skip_cache (persistent parse-failure IDs)

A "silent drop" = file on FS, not in DB, not in skip cache. Typically caused
by legality gate, unmapped folder name, or import bug.

Alerts (mail via SMTP, same channel as monitor_kc_freshness.py):
  - New folder detected (never seen before): INFO
  - Silent drop_rate > 10% for a known folder: WARN
  - Unmapped perimeter 'other' count > 50/day: WARN

Designed to run right after monitor_kc_freshness.py (07:05 UTC).
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
import traceback
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool")

from backend.config import MATCHES_DIR  # noqa: E402

SMTP_USER = "alexander9.ed@gmail.com"
SMTP_PASS_FILE = "/tmp/.smtp_pass"
MAIL_TO = "monitorteamfe@gmail.com"

SKIP_CACHE_PATH = Path(__file__).parent / ".import_skip_cache"
STATE_PATH = Path(__file__).parent / ".unmapped_monitor_state.json"

DROP_RATE_ALERT = 0.10  # 10%
UNMAPPED_PERIMETER_ALERT = 50  # match rows/day flagged 'other'
KNOWN_FOLDERS = {"SET11", "TOP", "PRO", "FRIENDS", "INF", "JA", "ZH", "OTHER", "MYGAME"}


def send_alert(subject: str, body: str) -> None:
    try:
        pwd = Path(SMTP_PASS_FILE).read_text().strip()
    except Exception as e:
        print(
            f"ALERT_SEND_FAILED cannot_read_pass_file={SMTP_PASS_FILE} err={e}",
            file=sys.stderr,
        )
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


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def _load_skip_cache_ids() -> set[str]:
    if not SKIP_CACHE_PATH.exists():
        return set()
    return {line.strip() for line in SKIP_CACHE_PATH.read_text().splitlines() if line.strip()}


def _fs_scan_last_24h() -> tuple[dict[str, int], dict[str, set[str]]]:
    """Return (counts_by_folder, file_ids_by_folder) for files touched in last 24h.

    Folder name = exact sub-folder under YYMMDD/ (SET11, TOP, PRO, INF, ...).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_ts = cutoff.timestamp()

    counts: dict[str, int] = {}
    ids: dict[str, set[str]] = {}
    matches_root = Path(MATCHES_DIR)
    if not matches_root.exists():
        return counts, ids

    # Limit scan to the most recent date folders to keep the sweep cheap.
    date_dirs = sorted(
        (d for d in matches_root.iterdir() if d.is_dir() and d.name.isdigit() and len(d.name) == 6),
        reverse=True,
    )[:3]

    for date_dir in date_dirs:
        for folder in date_dir.iterdir():
            if not folder.is_dir():
                continue
            fname = folder.name.upper()
            for f in folder.glob("*.json"):
                try:
                    if f.stat().st_mtime < cutoff_ts:
                        continue
                except OSError:
                    continue
                counts[fname] = counts.get(fname, 0) + 1
                ids.setdefault(fname, set()).add(f.stem)
            # Occasionally duels.ink layered a deeper subfolder — handle it.
            for sub in folder.iterdir():
                if not sub.is_dir():
                    continue
                for f in sub.glob("*.json"):
                    try:
                        if f.stat().st_mtime < cutoff_ts:
                            continue
                    except OSError:
                        continue
                    counts[fname] = counts.get(fname, 0) + 1
                    ids.setdefault(fname, set()).add(f.stem)

    return counts, ids


def _db_scan_last_24h() -> tuple[dict[str, int], dict[str, set[str]]]:
    """Return (inserts_by_perimeter, ext_ids_by_perimeter) for last 24h."""
    from backend.models import SessionLocal
    from sqlalchemy import text

    counts: dict[str, int] = {}
    ids: dict[str, set[str]] = {}
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT perimeter, external_id
                FROM matches
                WHERE imported_at >= NOW() - INTERVAL '24 hours'
                """
            )
        ).fetchall()
        for r in rows:
            p = r.perimeter or "unknown"
            counts[p] = counts.get(p, 0) + 1
            if r.external_id:
                ids.setdefault(p, set()).add(r.external_id)
    finally:
        db.close()
    return counts, ids


def _folder_to_perim_heuristic(folder: str) -> str:
    """Lowercase mapping used by import_matches.folder_to_perimeter."""
    folder = folder.upper()
    if folder.startswith("SET") and folder[3:].isdigit():
        return f"set{folder[3:]}"
    return folder.lower()


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "--test-mail" in sys.argv:
        send_alert(
            "[metamonitor] unmapped-matches canary TEST",
            f"[{ts}] This is a test email from monitor_unmapped_matches.py — "
            f"if you received it, SMTP works.",
        )
        return 0

    try:
        fs_counts, fs_ids = _fs_scan_last_24h()
        db_counts, db_ids = _db_scan_last_24h()
        skip_ids = _load_skip_cache_ids()
    except Exception:
        body = f"[{ts}] unmapped_matches=ERROR\n\n{traceback.format_exc()}"
        print(body)
        send_alert("[metamonitor] unmapped-matches canary ERROR", body)
        return 3

    state = _load_state()
    # Bootstrap: on the very first run the state file is empty, so every folder
    # would look "new" and spam an alert. Skip NEW-folder detection on first run.
    first_run = not state.get("folders_ever_seen")
    ever_seen: set[str] = set(state.get("folders_ever_seen", []))
    new_folders = [] if first_run else [f for f in fs_counts if f not in ever_seen]

    # Compute silent drops per folder: FS IDs - DB IDs (any perimeter) - skip IDs
    all_db_ids: set[str] = set()
    for s in db_ids.values():
        all_db_ids |= s

    silent_drops: dict[str, int] = {}
    for folder, file_ids in fs_ids.items():
        dropped = file_ids - all_db_ids - skip_ids
        if dropped:
            silent_drops[folder] = len(dropped)

    total_fs = sum(fs_counts.values())
    total_drops = sum(silent_drops.values())
    drop_rate_overall = (total_drops / total_fs) if total_fs else 0.0
    unmapped_other = db_counts.get("other", 0)

    reasons: list[str] = []
    severity = "OK"

    if new_folders:
        reasons.append(f"NEW folders on FS (never seen): {', '.join(sorted(new_folders))}")
        severity = "INFO"

    per_folder_alert = []
    for folder, drops in silent_drops.items():
        fs_n = fs_counts.get(folder, 0)
        rate = (drops / fs_n) if fs_n else 0.0
        if fs_n >= 20 and rate > DROP_RATE_ALERT:
            per_folder_alert.append(
                f"{folder}: {drops}/{fs_n} silent-dropped ({rate:.1%})"
            )
    if per_folder_alert:
        reasons.extend(per_folder_alert)
        severity = "WARN"

    if unmapped_other > UNMAPPED_PERIMETER_ALERT:
        reasons.append(
            f"perimeter='other' inserts in last 24h = {unmapped_other} (>{UNMAPPED_PERIMETER_ALERT})"
        )
        severity = "WARN"

    # Persist folders seen so NEW alerts fire only once per folder
    state["folders_ever_seen"] = sorted(ever_seen | set(fs_counts.keys()))
    state["last_run_ts"] = ts
    state["last_fs_counts"] = fs_counts
    state["last_db_counts"] = db_counts
    state["last_silent_drops"] = silent_drops
    _save_state(state)

    summary = (
        f"[{ts}] unmapped_matches={severity} "
        f"fs_total={total_fs} db_total={sum(db_counts.values())} "
        f"skip_cache={len(skip_ids)} silent_drops={total_drops} "
        f"drop_rate={drop_rate_overall:.2%} "
        f"unmapped_other={unmapped_other}"
    )
    print(summary)
    print("  fs_counts:", fs_counts)
    print("  db_counts:", db_counts)

    if severity != "OK":
        subject_tag = {"INFO": "INFO", "WARN": "WARN"}[severity]
        body = (
            f"{summary}\n\n"
            f"Reasons:\n- " + "\n- ".join(reasons) + "\n\n"
            f"FS counts (last 24h):\n{json.dumps(fs_counts, indent=2, sort_keys=True)}\n\n"
            f"DB counts (last 24h):\n{json.dumps(db_counts, indent=2, sort_keys=True)}\n\n"
            f"Silent drops by folder:\n{json.dumps(silent_drops, indent=2, sort_keys=True)}\n"
        )
        send_alert(f"[metamonitor] unmapped-matches {subject_tag}", body)
        return 2 if severity == "WARN" else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
