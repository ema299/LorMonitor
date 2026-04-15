"""Import deck_playbook_*.json (analisidef bridge) into deck_playbooks PG table.

Mossa A Sprint-1 Liberation Day: backfill iniziale dei 24 playbook gia'
generati dal batch settimanale di analisidef. Mossa B sostituira' questo
script con la generazione nativa via OpenAI dentro App_tool.

Uso:
    python scripts/import_playbooks.py                  # importa tutti
    python scripts/import_playbooks.py --deck RS        # solo RS (entrambi formati)
    python scripts/import_playbooks.py --dry-run        # parse + report, no DB
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import SessionLocal
from backend.services.playbook_service import upsert_playbook

# Bridge: i playbook li produce il batch settimanale in analisidef (martedi 01:00).
# Quando Mossa B sara' completa, questo path non servira' piu'.
ANALISIDEF_OUTPUT = Path("/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/output")

# Filename: deck_playbook_<DECK>.json (core) o deck_playbook_<DECK>_inf.json (infinity)
_PATTERN = re.compile(r"^deck_playbook_([A-Za-z]+?)(_inf)?\.json$")


def parse_filename(name: str) -> tuple[str, str] | None:
    """Estrae (deck, format) dal nome file. None se non matcha."""
    m = _PATTERN.match(name)
    if not m:
        return None
    deck = m.group(1)
    game_format = "infinity" if m.group(2) else "core"
    return deck, game_format


def import_file(db, fpath: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Importa un singolo JSON. Returns (ok, message)."""
    parsed = parse_filename(fpath.name)
    if not parsed:
        return False, f"skip (filename doesn't match): {fpath.name}"
    deck, game_format = parsed

    try:
        with open(fpath) as f:
            payload = json.load(f)
    except Exception as exc:
        return False, f"FAIL parse {fpath.name}: {exc}"

    if not isinstance(payload, dict) or "playbook" not in payload:
        return False, f"skip (no playbook key): {fpath.name}"

    pb = payload.get("playbook") or {}
    if pb.get("error"):
        return False, f"skip (LLM error): {fpath.name} -> {pb.get('error')}"

    if dry_run:
        meta = payload.get("meta") or {}
        return True, (
            f"  [dry] {deck:6} {game_format:8} games={meta.get('total_games', '?')} "
            f"digests={meta.get('digest_count', '?')}"
        )

    try:
        row_id = upsert_playbook(db, deck, game_format, payload)
    except Exception as exc:
        db.rollback()
        return False, f"FAIL upsert {fpath.name}: {exc}"

    return True, f"  [ok] {deck:6} {game_format:8} -> id={row_id}"


def main():
    p = argparse.ArgumentParser(description="Import deck_playbook_*.json bridge")
    p.add_argument("--deck", help="Limita ad un singolo deck (es. RS)")
    p.add_argument("--dry-run", action="store_true", help="Parse + report, niente scrittura DB")
    args = p.parse_args()

    if not ANALISIDEF_OUTPUT.exists():
        print(f"ERR: source dir not found: {ANALISIDEF_OUTPUT}")
        sys.exit(1)

    files = sorted(ANALISIDEF_OUTPUT.glob("deck_playbook_*.json"))
    if args.deck:
        files = [f for f in files if f.name.startswith(f"deck_playbook_{args.deck}.")
                 or f.name.startswith(f"deck_playbook_{args.deck}_")]

    if not files:
        print("No playbook files found.")
        return

    print(f"Found {len(files)} playbook file(s) to import (dry_run={args.dry_run})")

    db = None if args.dry_run else SessionLocal()
    ok_count = 0
    fail_count = 0
    t0 = time.time()

    try:
        for fpath in files:
            ok, msg = import_file(db, fpath, dry_run=args.dry_run)
            print(msg)
            if ok:
                ok_count += 1
            else:
                fail_count += 1
    finally:
        if db:
            db.close()

    print(f"\nDone in {time.time() - t0:.1f}s — ok: {ok_count}, fail/skip: {fail_count}")


if __name__ == "__main__":
    main()
