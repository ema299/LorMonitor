"""Batch runner for the native digest generator (Sprint P1 shadow mode).

Writes one JSON per (our, opp, game_format) into
``App_tool/output/digests/digest_{OUR}_vs_{OPP}[_inf].json`` — a NEW directory
that coexists with the legacy analisidef tree for the shadow period.

Usage::

    venv/bin/python3 scripts/generate_digests.py --format all
    venv/bin/python3 scripts/generate_digests.py --format core --limit 3
    venv/bin/python3 scripts/generate_digests.py --pair AmSa AbE --format core

Exit codes:
  0 = at least one digest produced (or --dry-run)
  1 = no digests produced (e.g. all matchups below floor)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import product
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.models import SessionLocal  # noqa: E402
from pipelines.digest.generator import DECKS, generate_digest  # noqa: E402

OUTPUT_DIR = _PROJECT_ROOT / "output" / "digests"
FORMATS = ("core", "infinity")
MIN_GAMES_DEFAULT = 20


def _pg_code(code: str) -> str:
    return {"AS": "AmSa", "ES": "EmSa"}.get(code, code)


def _filename(our: str, opp: str, game_format: str) -> str:
    sfx = "_inf" if game_format == "infinity" else ""
    return f"digest_{our}_vs_{opp}{sfx}.json"


def iter_matchups(pair: tuple[str, str] | None, limit: int | None):
    """Yield (our, opp) pairs — all cross-product or explicit pair."""
    if pair:
        yield (pair[0], pair[1])
        return
    count = 0
    for our, opp in product(DECKS, repeat=2):
        if our == opp:
            continue
        yield (our, opp)
        count += 1
        if limit and count >= limit:
            return


def run(args: argparse.Namespace) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    formats = FORMATS if args.format == "all" else (args.format,)
    pair = (_pg_code(args.pair[0]), _pg_code(args.pair[1])) if args.pair else None

    db = SessionLocal()
    t0 = time.time()
    ok = skip = err = 0
    try:
        for fmt in formats:
            for our, opp in iter_matchups(pair, args.limit):
                our_c = _pg_code(our)
                opp_c = _pg_code(opp)
                try:
                    digest = generate_digest(
                        db, our_c, opp_c, fmt,
                        window_days=args.window_days,
                        min_games=args.min_games,
                    )
                except Exception as exc:  # noqa: BLE001
                    err += 1
                    print(
                        f"[DIGEST] our={our_c} opp={opp_c} fmt={fmt} "
                        f"status=ERROR ({exc.__class__.__name__}: {exc})",
                        flush=True,
                    )
                    continue

                if digest is None:
                    skip += 1
                    print(
                        f"[DIGEST] our={our_c} opp={opp_c} fmt={fmt} "
                        f"status=SKIP_LOW_GAMES games=0",
                        flush=True,
                    )
                    continue

                out_path = OUTPUT_DIR / _filename(our_c, opp_c, fmt)
                if args.dry_run:
                    print(
                        f"[DIGEST] our={our_c} opp={opp_c} fmt={fmt} "
                        f"status=DRY_RUN games={digest.get('games', 0)}",
                        flush=True,
                    )
                    ok += 1
                    continue

                with open(out_path, "w") as fh:
                    json.dump(digest, fh, indent=2, default=str, ensure_ascii=False)
                size_kb = out_path.stat().st_size / 1024
                print(
                    f"[DIGEST] our={our_c} opp={opp_c} fmt={fmt} "
                    f"status=OK games={digest.get('games', 0)} "
                    f"losses={digest.get('losses', 0)} size={size_kb:.0f}KB "
                    f"-> {out_path.name}",
                    flush=True,
                )
                ok += 1
    finally:
        db.close()

    elapsed = time.time() - t0
    print(
        f"\n[DIGEST] done: ok={ok} skip={skip} err={err} "
        f"elapsed={elapsed:.1f}s output_dir={OUTPUT_DIR}",
        flush=True,
    )
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--format", choices=("core", "infinity", "all"), default="all")
    p.add_argument("--pair", nargs=2, metavar=("OUR", "OPP"),
                   help="Run a single (our, opp) pair (accepts AS/AmSa interchangeably)")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap the number of pairs processed per format (smoke tests)")
    p.add_argument("--window-days", type=int, default=30)
    p.add_argument("--min-games", type=int, default=MIN_GAMES_DEFAULT,
                   help="Minimum LOSS count required to emit a digest")
    p.add_argument("--dry-run", action="store_true",
                   help="Generate digests but do not write JSON files")
    args = p.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
