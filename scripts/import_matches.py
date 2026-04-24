"""
Import match JSON files from /mnt/.../matches/ into PostgreSQL.
Reads from analisidef data without modifying it.

Usage: python scripts/import_matches.py [--dry-run]
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.models import SessionLocal, engine
from backend.config import MATCHES_DIR
from backend.services.legality_service import get_checker

# --- Deck color mapping (copied from analisidef/lib/loader.py) ---

DECK_COLORS = {
    'AmSa':  ('amethyst', 'sapphire'),
    'EmSa':  ('emerald', 'sapphire'),
    'AbS':   ('amber', 'sapphire'),
    'AmAm':  ('amber', 'amethyst'),
    'AbE':   ('amber', 'emerald'),
    'AbSt':  ('amber', 'steel'),
    'AmySt': ('amethyst', 'steel'),
    'SSt':   ('sapphire', 'steel'),
    'AbR':   ('amber', 'ruby'),
    'AmyR':  ('amethyst', 'ruby'),
    'AmyE':  ('amethyst', 'emerald'),
    'RS':    ('ruby', 'sapphire'),
    'ER':    ('emerald', 'ruby'),
    'ESt':   ('emerald', 'steel'),
    'RSt':   ('ruby', 'steel'),
}

# Build reverse lookup: sorted color tuple -> deck code
_COLORS_TO_DECK = {}
for code, colors in DECK_COLORS.items():
    key = tuple(sorted(colors))
    _COLORS_TO_DECK[key] = code

def colors_to_deck(ink_colors: list[str]) -> str | None:
    """Convert ink color list to deck code."""
    key = tuple(sorted(c.lower() for c in ink_colors))
    return _COLORS_TO_DECK.get(key)


_SET_FOLDER_RE = re.compile(r'^SET(\d+)$')
_CORE_SET_QUEUE_RE = re.compile(r'^SET\d+$')
# Matches S11-BO1, S11-BO3, S12-EA-BO1, S12-EA-BO3, ...
_CORE_QUEUE_RE = re.compile(r'^S\d+(-EA)?-(BO1|BO3)$')


def folder_to_perimeter(folder_name: str) -> str:
    """Convert folder name to perimeter.

    `SETNN` → `setNN` (accepts SET11, SET12, SET13, ...) so new-set folders
    land in a dedicated perimeter without code change at release-day.
    Everything else lowercased (TOP→top, PRO→pro, INF→inf, FRIENDS→friends).
    """
    m = _SET_FOLDER_RE.match(folder_name)
    if m:
        return f'set{m.group(1)}'
    return folder_name.lower()


INF_QUEUES = {'INF-BO1', 'INF-BO3', 'INF', 'JA-BO1', 'ZH-BO1'}
CARD_OBS_EVENT_TYPES = {'CARD_PLAYED', 'CARD_INKED', 'INITIAL_HAND', 'CARD_DRAWN', 'MULLIGAN'}
# RUSH, SEALED, SEAL-S11, QP, PRO, TOP, ? → not core constructed


def determine_game_format(queue_name: str | None, perimeter: str) -> str:
    """Determine game format from queue name (primary) and perimeter (fallback)."""
    q = (queue_name or '').upper().strip()
    if _CORE_QUEUE_RE.match(q) or _CORE_SET_QUEUE_RE.match(q):
        return 'core'
    if q in INF_QUEUES:
        return 'infinity'
    if perimeter == 'inf' or perimeter == 'infinity':
        return 'infinity'
    # Unknown queue — not core constructed (RUSH, SEALED, QP, etc.)
    return 'other'


def determine_winner(logs: list[dict], p1_deck: str, p2_deck: str) -> str | None:
    """Determine winner deck code from game logs."""
    winner_player = None
    for entry in reversed(logs):
        etype = entry.get('type', '')
        data = entry.get('data', {}) or {}
        if etype == 'GAME_END':
            winner_player = data.get('winner')
            break
        elif etype == 'GAME_CONCEDED':
            winner_player = data.get('winner')
            if not winner_player:
                conceder = data.get('concededBy') or entry.get('player')
                winner_player = 2 if conceder == 1 else 1
            break

    if winner_player == 1:
        return 'deck_a'
    elif winner_player == 2:
        return 'deck_b'
    return None


def extract_cards_seen(logs: list[dict], player_num: int) -> list[str]:
    """Rebuild observed deck cards from public logs."""
    cards = set()
    for event in logs or []:
        if not isinstance(event, dict) or event.get('player') != player_num:
            continue
        if event.get('type') not in CARD_OBS_EVENT_TYPES:
            continue
        for ref in event.get('cardRefs') or []:
            if isinstance(ref, dict):
                name = ref.get('name')
            else:
                name = str(ref) if ref else None
            if name:
                cards.add(name)
    return sorted(cards)


def parse_match_file(filepath: str, perimeter: str,
                     illegal_stats: dict | None = None) -> dict | None:
    """Parse a single match JSON file into a database row dict.

    Applica legality gate per il formato core: se il match contiene carte non
    legali nel formato, ritorna None e registra counter in illegal_stats.
    Infinity non e' gated (set rotation piu' permissiva).
    """
    try:
        with open(filepath) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    gi = data.get('game_info', {})
    logs = data.get('log_data', {}).get('logs', [])

    game_id = gi.get('gameId')
    if not game_id:
        return None

    # Player info
    p1 = gi.get('player1', {})
    p2 = gi.get('player2', {})

    deck_a = colors_to_deck(p1.get('inkColors', []))
    deck_b = colors_to_deck(p2.get('inkColors', []))
    if not deck_a or not deck_b:
        return None

    # Timestamp
    started_ms = gi.get('startedAt')
    if started_ms:
        played_at = datetime.fromtimestamp(started_ms / 1000, tz=timezone.utc)
    else:
        played_at = datetime.now(timezone.utc)

    queue_name = gi.get('queueShortName', '')
    game_format = determine_game_format(queue_name, perimeter)

    # Legality gate (solo core, solo nuovi import). Match con carte illegali -> skip.
    if game_format == 'core':
        checker = get_checker('core')
        if checker.available:
            is_legal, violations = checker.check_match(logs)
            if not is_legal:
                if illegal_stats is not None:
                    illegal_stats['count'] += 1
                    for v in violations:
                        illegal_stats['cards'][v['card']] = (
                            illegal_stats['cards'].get(v['card'], 0) + 1
                        )
                return None

    winner = determine_winner(logs, deck_a, deck_b)
    total_turns = gi.get('currentTurn', 0)

    return {
        'external_id': game_id,
        'played_at': played_at,
        'game_format': game_format,
        'queue_name': queue_name,
        'perimeter': perimeter,
        'deck_a': deck_a,
        'deck_b': deck_b,
        'winner': winner,
        'player_a_name': p1.get('name'),
        'player_b_name': p2.get('name'),
        'player_a_mmr': p1.get('mmr'),
        'player_b_mmr': p2.get('mmr'),
        'total_turns': total_turns,
        'lore_a_final': p1.get('lore'),
        'lore_b_final': p2.get('lore'),
        'turns': logs,
        'cards_a': extract_cards_seen(logs, 1),
        'cards_b': extract_cards_seen(logs, 2),
    }


def iter_json_files(matches_dir: str):
    """Yield (filepath, perimeter) for all match JSON files — no memory buildup."""
    for date_dir in sorted(os.listdir(matches_dir)):
        date_path = os.path.join(matches_dir, date_dir)
        if not os.path.isdir(date_path):
            continue

        for perim_dir in os.listdir(date_path):
            perim_path = os.path.join(date_path, perim_dir)
            if not os.path.isdir(perim_path):
                continue

            perimeter = folder_to_perimeter(perim_dir)

            for entry in os.listdir(perim_path):
                full = os.path.join(perim_path, entry)
                if entry.endswith('.json'):
                    yield full, perimeter
                elif os.path.isdir(full):
                    for sub in os.listdir(full):
                        if sub.endswith('.json'):
                            yield os.path.join(full, sub), perimeter


# Perimeter priority: more specific perimeter wins on conflict
# pro > top > setNN  (PRO ⊂ TOP ⊂ SETNN)
# setNN (set11, set12, ...) receives default priority 1 via _perim_priority()
_PERIM_PRIORITY_STATIC = {'pro': 3, 'top': 2, 'inf': 2, 'infinity': 2, 'friends': 1, 'mygame': 1}


def _perim_priority(perimeter: str) -> int:
    if perimeter in _PERIM_PRIORITY_STATIC:
        return _PERIM_PRIORITY_STATIC[perimeter]
    if perimeter.startswith('set') and perimeter[3:].isdigit():
        return 1
    return 0


# Backwards-compat alias: older code calls `PERIM_PRIORITY.get(p, 0)`.
class _PerimPriorityView(dict):
    def get(self, key, default=0):
        val = _perim_priority(key)
        return val if val else default


PERIM_PRIORITY = _PerimPriorityView(_PERIM_PRIORITY_STATIC)

INSERT_SQL = text("""
    INSERT INTO matches
        (external_id, played_at, game_format, queue_name, perimeter,
         deck_a, deck_b, winner, player_a_name, player_b_name,
         player_a_mmr, player_b_mmr, total_turns, lore_a_final, lore_b_final,
         turns, cards_a, cards_b)
    VALUES
        (:external_id, :played_at, :game_format, :queue_name, :perimeter,
         :deck_a, :deck_b, :winner, :player_a_name, :player_b_name,
         :player_a_mmr, :player_b_mmr, :total_turns, :lore_a_final, :lore_b_final,
         :turns, :cards_a, :cards_b)
    ON CONFLICT (external_id) DO UPDATE
        SET perimeter = CASE
            WHEN EXCLUDED.perimeter = 'pro' THEN 'pro'
            WHEN EXCLUDED.perimeter = 'top' AND matches.perimeter NOT IN ('pro') THEN 'top'
            ELSE matches.perimeter
        END
""")


SKIP_CACHE = Path(__file__).parent / ".import_skip_cache"


def _load_known_ids(db) -> dict[str, str]:
    """Pre-fetch all external_ids + perimeter from PG to skip files without parsing."""
    rows = db.execute(text("SELECT external_id, perimeter FROM matches")).fetchall()
    return {r[0]: r[1] for r in rows}


def _load_skip_cache() -> set[str]:
    """Load IDs of files that failed parsing (won't change, skip on next run)."""
    if SKIP_CACHE.exists():
        return set(SKIP_CACHE.read_text().splitlines())
    return set()


def _save_skip_cache(ids: set[str]):
    SKIP_CACHE.write_text("\n".join(sorted(ids)))


def _extract_id_from_path(filepath: str) -> str | None:
    """Extract game UUID from filename (e.g. '019d6508-...-.json' → '019d6508-...')."""
    basename = os.path.basename(filepath)
    if basename.endswith('.json'):
        return basename[:-5]
    return None


def import_all(dry_run: bool = False):
    matches_dir = str(MATCHES_DIR)
    print(f"Scanning {matches_dir} ...")

    BATCH_SIZE = 500
    batch = []
    parsed = 0
    skipped = 0
    already_known = 0
    inserted = 0
    illegal_stats = {'count': 0, 'cards': {}}

    db = None if dry_run else SessionLocal()

    # Pre-fetch known IDs + skip cache to avoid re-reading unparseable files
    known_ids = set()
    skip_ids = _load_skip_cache()
    if db:
        print("Loading known match IDs from PG...")
        known_ids = _load_known_ids(db)
        print(f"  {len(known_ids)} in DB, {len(skip_ids)} in skip cache")

    try:
        for filepath, perimeter in iter_json_files(matches_dir):
            # Fast skip: if UUID already in DB or known-bad, don't read the file
            # Exception: re-process if new perimeter has higher priority (e.g. PRO > TOP)
            file_id = _extract_id_from_path(filepath)
            if file_id and file_id in skip_ids:
                already_known += 1
                continue
            if file_id and file_id in known_ids:
                existing_perim = known_ids[file_id]
                new_prio = PERIM_PRIORITY.get(perimeter, 0)
                old_prio = PERIM_PRIORITY.get(existing_perim, 0)
                if new_prio <= old_prio:
                    already_known += 1
                    continue

            row = parse_match_file(filepath, perimeter, illegal_stats)
            if not row:
                skipped += 1
                if file_id:
                    skip_ids.add(file_id)
                continue

            parsed += 1

            if dry_run:
                if parsed % 10000 == 0:
                    print(f"  [dry-run] {parsed} parsed, {skipped} skipped...")
                continue

            batch.append({
                **row,
                'turns': json.dumps(row['turns']),
                'cards_a': json.dumps(row['cards_a']) if row['cards_a'] else None,
                'cards_b': json.dumps(row['cards_b']) if row['cards_b'] else None,
            })

            if len(batch) >= BATCH_SIZE:
                for r in batch:
                    db.execute(INSERT_SQL, r)
                db.commit()
                inserted += len(batch)
                batch = []
                print(f"  {inserted} inserted ({skipped} skipped)...")

        # Final batch
        if batch and db:
            for r in batch:
                db.execute(INSERT_SQL, r)
            db.commit()
            inserted += len(batch)

        # Persist skip cache for next run
        _save_skip_cache(skip_ids)

        print(f"\nDone!")
        print(f"  Already in DB: {already_known}")
        print(f"  Parsed:   {parsed}")
        print(f"  Skipped:  {skipped} (cached for next run)")
        print(f"  Inserted: {inserted}")
        if illegal_stats['count']:
            print(f"  Illegal core matches skipped: {illegal_stats['count']}")
            top = sorted(illegal_stats['cards'].items(), key=lambda x: -x[1])[:5]
            for card, n in top:
                print(f"    {card}: {n}x")
    finally:
        if db:
            db.close()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    t0 = time.time()
    import_all(dry_run=dry_run)
    print(f"Total time: {time.time() - t0:.1f}s")
