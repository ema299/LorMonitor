"""Schema parity diff between legacy analisidef digests and native P1 digests.

The two sources have different windows by design (legacy is stale, native is
30d fresh) so we never compare numeric values. We only check:

  * schema parity     — every native digest has the 15 legacy top-level fields;
  * no accidental new fields that legacy lacks (flagged but non-fatal);
  * field-presence parity in nested dicts (`avg_trend`, `profiles.fast.*`, ...);
  * type parity where it matters (list vs dict);
  * missing-matchup discrepancies (only one side emitted a file).

Output: per-matchup table plus a final summary line::

    N_MATCHUPS_CHECKED=... SCHEMA_DIFFS=... MISSING_ONE_SIDE=...

Usage: ``venv/bin/python3 scripts/diff_digests.py``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

LEGACY_DIR = Path(
    "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/output"
)
NATIVE_DIR = _PROJECT_ROOT / "output" / "digests"

REQUIRED_FIELDS = [
    "matchup", "games", "wins", "losses", "format",
    "component_primary", "critical_turn_dist", "avg_trend",
    "alert_losses", "lore_speed", "card_examples", "combos",
    "profiles", "example_games", "cards_db",
]

# Fields the native generator adds for provenance — ignored by the diff.
NATIVE_EXTRA = {"_provenance"}

# Optional legacy-only field (combo_intelligence) — not part of the 15.
LEGACY_EXTRA_ALLOWED = {"our_playbook"}

NESTED_KEYS = {
    "avg_trend": {"board", "lore", "lore_pot", "removal", "opp_lore_vel"},
    "lore_speed": {"reach_10", "reach_15", "fast_loss_ids", "top_burst"},
}

PROFILE_KEYS = {
    "count", "pct", "causes", "component", "alerts", "patterns",
    "patterns_cards", "keywords", "keywords_cards", "abilities",
    "abilities_cards", "wipe_rate", "lore_t4", "top_cards", "example_ids",
}

_FILE_RE = re.compile(r"^digest_(?P<our>[A-Za-z]+)_vs_(?P<opp>[A-Za-z]+)(?P<inf>_inf)?\.json$")

# Legacy analisidef used `AS`/`ES`; native uses canonical `AmSa`/`EmSa`.
# Normalise to the canonical form so the two sides align in the diff.
_CODE_ALIAS = {"AS": "AmSa", "ES": "EmSa"}


def _canon(code: str) -> str:
    return _CODE_ALIAS.get(code, code)


def _index(directory: Path) -> dict[tuple[str, str, str], Path]:
    """Return {(our, opp, format): path} for every digest_*.json in directory.

    Deck codes are normalised (`AS` -> `AmSa`, `ES` -> `EmSa`) so the legacy
    and native indexes use the same keys.
    """
    out: dict[tuple[str, str, str], Path] = {}
    if not directory.exists():
        return out
    for p in directory.glob("digest_*.json"):
        m = _FILE_RE.match(p.name)
        if not m:
            continue
        fmt = "infinity" if m.group("inf") else "core"
        key = (_canon(m.group("our")), _canon(m.group("opp")), fmt)
        out[key] = p
    return out


def _check_schema(digest: dict) -> tuple[list[str], list[str]]:
    """Return (missing_fields, extra_fields). Extra excludes the whitelist."""
    keys = set(digest.keys())
    missing = [f for f in REQUIRED_FIELDS if f not in keys]
    extras = sorted(
        keys - set(REQUIRED_FIELDS) - NATIVE_EXTRA - LEGACY_EXTRA_ALLOWED
    )
    return missing, extras


def _check_nested(digest: dict) -> list[str]:
    issues = []
    for top_key, required in NESTED_KEYS.items():
        sub = digest.get(top_key)
        if not isinstance(sub, dict):
            issues.append(f"{top_key}:not-a-dict")
            continue
        for k in required:
            if k not in sub:
                issues.append(f"{top_key}.{k}:missing")
    profiles = digest.get("profiles")
    if isinstance(profiles, dict):
        for bucket in ("fast", "typical", "slow"):
            b = profiles.get(bucket)
            if b is None:
                continue
            if not isinstance(b, dict):
                issues.append(f"profiles.{bucket}:not-a-dict")
                continue
            for k in PROFILE_KEYS:
                if k not in b:
                    issues.append(f"profiles.{bucket}.{k}:missing")
    return issues


def _types_match(a, b) -> bool:
    # We treat list/tuple as equivalent and dict/OrderedDict as equivalent.
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        return True
    return type(a) is type(b)


def _diff_types(legacy: dict, native: dict) -> list[str]:
    issues = []
    for field in REQUIRED_FIELDS:
        if field in legacy and field in native:
            if not _types_match(legacy[field], native[field]):
                issues.append(
                    f"{field}:type-mismatch "
                    f"(legacy={type(legacy[field]).__name__} "
                    f"native={type(native[field]).__name__})"
                )
    return issues


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--legacy-dir", default=str(LEGACY_DIR))
    p.add_argument("--native-dir", default=str(NATIVE_DIR))
    p.add_argument("--format", choices=("core", "infinity", "all"), default="all")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    legacy_idx = _index(Path(args.legacy_dir))
    native_idx = _index(Path(args.native_dir))

    if args.format != "all":
        legacy_idx = {k: v for k, v in legacy_idx.items() if k[2] == args.format}
        native_idx = {k: v for k, v in native_idx.items() if k[2] == args.format}

    # Only diff matchups present on BOTH sides; record the rest.
    only_legacy = sorted(legacy_idx.keys() - native_idx.keys())
    only_native = sorted(native_idx.keys() - legacy_idx.keys())
    common = sorted(legacy_idx.keys() & native_idx.keys())

    n_checked = 0
    schema_diffs = 0

    print(
        f"{'matchup':<30} {'schema':<8} {'nested':<8} {'types':<8} notes",
        flush=True,
    )
    print("-" * 90, flush=True)

    for key in common:
        our, opp, fmt = key
        matchup = f"{our}-vs-{opp}-{fmt}"
        try:
            with open(legacy_idx[key]) as fh:
                legacy = json.load(fh)
            with open(native_idx[key]) as fh:
                native = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{matchup:<30} LOAD_ERR: {exc}", flush=True)
            schema_diffs += 1
            continue

        n_checked += 1
        l_missing, l_extras = _check_schema(legacy)
        n_missing, n_extras = _check_schema(native)
        legacy_nested = _check_nested(legacy)
        native_nested = _check_nested(native)
        type_issues = _diff_types(legacy, native)

        notes_parts = []
        if n_missing:
            notes_parts.append(f"native_missing={n_missing}")
        if l_missing:
            notes_parts.append(f"legacy_missing={l_missing}")
        new_in_native = sorted(set(n_extras) - set(l_extras))
        if new_in_native:
            notes_parts.append(f"new_in_native={new_in_native}")
        # Nested-parity mismatches that exist in native but not in legacy.
        native_nested_only = sorted(set(native_nested) - set(legacy_nested))
        if native_nested_only:
            notes_parts.append(f"nested_only_native={native_nested_only[:3]}")
        if type_issues:
            notes_parts.append(f"types={type_issues}")

        schema_col = "OK" if not (n_missing or new_in_native) else "DIFF"
        nested_col = "OK" if not native_nested_only else "DIFF"
        types_col = "OK" if not type_issues else "DIFF"
        if schema_col != "OK" or nested_col != "OK" or types_col != "OK":
            schema_diffs += 1

        notes = "; ".join(notes_parts)[:60] if notes_parts else ""
        if args.verbose or notes:
            print(
                f"{matchup:<30} {schema_col:<8} {nested_col:<8} {types_col:<8} {notes}",
                flush=True,
            )

    missing_one_side = len(only_legacy) + len(only_native)
    if only_legacy:
        print(f"\nonly_legacy ({len(only_legacy)}):", flush=True)
        for k in only_legacy[:20]:
            print(f"  {k[0]}_vs_{k[1]}_{k[2]}", flush=True)
        if len(only_legacy) > 20:
            print(f"  ... +{len(only_legacy) - 20} more", flush=True)
    if only_native:
        print(f"\nonly_native ({len(only_native)}):", flush=True)
        for k in only_native[:20]:
            print(f"  {k[0]}_vs_{k[1]}_{k[2]}", flush=True)
        if len(only_native) > 20:
            print(f"  ... +{len(only_native) - 20} more", flush=True)

    print(
        f"\nN_MATCHUPS_CHECKED={n_checked} "
        f"SCHEMA_DIFFS={schema_diffs} "
        f"MISSING_ONE_SIDE={missing_one_side}",
        flush=True,
    )
    return 0 if schema_diffs == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
