"""Parity harness for Sprint P1.5 vendored digest modules.

Compares `pipelines.digest.generator.generate_digest()` under two module sets:

1. legacy external analytics tree
2. vendored local copies in `pipelines.digest.vendored`

The digest payload must match exactly after removing `_provenance`.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from contextlib import contextmanager
from itertools import product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_ROOT = Path(
    "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef"
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models import SessionLocal  # noqa: E402
from pipelines.digest import generator as gen  # noqa: E402
from pipelines.digest.vendored import gen_archive as vendored_gen_archive  # noqa: E402
from pipelines.digest.vendored import investigate as vendored_investigate  # noqa: E402
from pipelines.digest.vendored import loader as vendored_loader  # noqa: E402


def _pg_code(code: str) -> str:
    return {"AS": "AmSa", "ES": "EmSa"}.get(code, code)


def _norm_digest(digest: dict | None) -> str:
    payload = None if digest is None else {
        k: v for k, v in digest.items() if k != "_provenance"
    }
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _load_legacy_modules():
    if str(LEGACY_ROOT) not in sys.path:
        sys.path.insert(0, str(LEGACY_ROOT))
    for name in (
        "lib",
        "lib.loader",
        "lib.gen_archive",
        "lib.investigate",
        "lib.cards_dict",
    ):
        sys.modules.pop(name, None)
    loader = importlib.import_module("lib.loader")
    gen_archive = importlib.import_module("lib.gen_archive")
    investigate = importlib.import_module("lib.investigate")
    return loader, gen_archive, investigate


@contextmanager
def _patched_modules(loader_mod, gen_archive_mod, investigate_mod):
    prev = (
        gen._loader,
        gen._build_aggregates,
        gen._build_turn,
        gen.enrich_games,
        gen.classify_losses,
    )
    gen._loader = loader_mod
    gen._build_aggregates = gen_archive_mod._build_aggregates
    gen._build_turn = gen_archive_mod._build_turn
    gen.enrich_games = investigate_mod.enrich_games
    gen.classify_losses = investigate_mod.classify_losses
    try:
        yield
    finally:
        (
            gen._loader,
            gen._build_aggregates,
            gen._build_turn,
            gen.enrich_games,
            gen.classify_losses,
        ) = prev


def _iter_pairs(pair: tuple[str, str] | None, limit: int | None):
    if pair:
        yield (_pg_code(pair[0]), _pg_code(pair[1]))
        return
    count = 0
    for our, opp in product(gen.DECKS, repeat=2):
        if our == opp:
            continue
        yield (our, opp)
        count += 1
        if limit and count >= limit:
            return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("core", "infinity", "all"), default="core")
    parser.add_argument("--pair", nargs=2, metavar=("OUR", "OPP"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--min-games", type=int, default=20)
    args = parser.parse_args()

    legacy_loader, legacy_gen_archive, legacy_investigate = _load_legacy_modules()
    formats = ("core", "infinity") if args.format == "all" else (args.format,)

    checked = 0
    diffs = 0
    legacy_none = 0
    vendored_none = 0

    db = SessionLocal()
    try:
        for fmt in formats:
            for our, opp in _iter_pairs(tuple(args.pair) if args.pair else None, args.limit):
                with _patched_modules(
                    legacy_loader,
                    legacy_gen_archive,
                    legacy_investigate,
                ):
                    legacy_digest = gen.generate_digest(
                        db,
                        our,
                        opp,
                        fmt,
                        window_days=args.window_days,
                        min_games=args.min_games,
                    )
                with _patched_modules(
                    vendored_loader,
                    vendored_gen_archive,
                    vendored_investigate,
                ):
                    vendored_digest = gen.generate_digest(
                        db,
                        our,
                        opp,
                        fmt,
                        window_days=args.window_days,
                        min_games=args.min_games,
                    )

                legacy_norm = _norm_digest(legacy_digest)
                vendored_norm = _norm_digest(vendored_digest)
                same = legacy_norm == vendored_norm
                checked += 1
                if legacy_digest is None:
                    legacy_none += 1
                if vendored_digest is None:
                    vendored_none += 1
                if not same:
                    diffs += 1

                print(
                    f"[P1.5] our={our} opp={opp} fmt={fmt} status={'OK' if same else 'DIFF'} "
                    f"legacy={'none' if legacy_digest is None else legacy_digest.get('losses', '?')} "
                    f"vendored={'none' if vendored_digest is None else vendored_digest.get('losses', '?')}",
                    flush=True,
                )

        print(
            f"\nP1_5_CHECKED={checked} DIFFS={diffs} "
            f"LEGACY_NONE={legacy_none} VENDORED_NONE={vendored_none}",
            flush=True,
        )
        return 0 if diffs == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
