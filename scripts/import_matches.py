"""
Import match JSON files from /mnt/.../matches/ into PostgreSQL.
Reads from analisidef data without modifying it.

Usage: python scripts/import_matches.py [--dry-run]
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.models import SessionLocal, engine
from backend.config import MATCHES_DIR

# --- Deck color mapping (copied from analisidef/lib/loader.py) ---

DECK_COLORS = {
    'AS':    ('amethyst', 'sapphire'),
    'ES':    ('emerald', 'sapphire'),
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

# Queue prefixes per formato
FORMAT_QUEUE_PREFIXES = {
    'core': ('S11-',),
    'infinity': ('INF-', 'JA-', 'ZH-'),
}


def colors_to_deck(ink_colors: list[str]) -> str | None:
    """Convert ink color list to deck code."""
    key = tuple(sorted(c.lower() for c in ink_colors))
    return _COLORS_TO_DECK.get(key)


def folder_to_perimeter(folder_name: str) -> str:
    """Convert folder name (SET11, TOP, PRO, INF) to perimeter."""
    return folder_name.lower()


def determine_game_format(queue_name: str | None, perimeter: str) -> str:
    """Determine game format from queue name and perimeter."""
    if perimeter == 'inf':
        return 'infinity'
    return 'core'


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


def parse_match_file(filepath: str, perimeter: str) -> dict | None:
    """Parse a single match JSON file into a database row dict."""
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

    # Filter: queue prefix must match format
    valid_prefixes = FORMAT_QUEUE_PREFIXES.get(game_format, ())
    if valid_prefixes and queue_name and not any(queue_name.startswith(p) for p in valid_prefixes):
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
        'cards_a': None,
        'cards_b': None,
    }


def import_all(dry_run: bool = False):
    matches_dir = str(MATCHES_DIR)
    print(f"Scanning {matches_dir} ...")

    all_rows = []
    skipped = 0

    for date_dir in sorted(os.listdir(matches_dir)):
        date_path = os.path.join(matches_dir, date_dir)
        if not os.path.isdir(date_path):
            continue

        for perim_dir in os.listdir(date_path):
            perim_path = os.path.join(date_path, perim_dir)
            if not os.path.isdir(perim_path):
                continue

            perimeter = folder_to_perimeter(perim_dir)

            for fname in os.listdir(perim_path):
                if not fname.endswith('.json'):
                    continue
                filepath = os.path.join(perim_path, fname)
                row = parse_match_file(filepath, perimeter)
                if row:
                    all_rows.append(row)
                else:
                    skipped += 1

    print(f"Parsed {len(all_rows)} matches, skipped {skipped}")

    if dry_run:
        print("[DRY RUN] No data written.")
        return

    # Bulk insert in batches
    BATCH_SIZE = 1000
    db = SessionLocal()
    inserted = 0
    duplicates = 0

    try:
        for i in range(0, len(all_rows), BATCH_SIZE):
            batch = all_rows[i:i + BATCH_SIZE]
            for row in batch:
                try:
                    db.execute(
                        text("""
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
                            ON CONFLICT (external_id) DO NOTHING
                        """),
                        {**row, 'turns': json.dumps(row['turns']),
                         'cards_a': json.dumps(row['cards_a']) if row['cards_a'] else None,
                         'cards_b': json.dumps(row['cards_b']) if row['cards_b'] else None},
                    )
                    inserted += 1
                except Exception as e:
                    duplicates += 1

            db.commit()
            print(f"  Batch {i // BATCH_SIZE + 1}: inserted up to {min(i + BATCH_SIZE, len(all_rows))}")

        print(f"\nDone: {inserted} inserted, {duplicates} duplicates/errors")
    finally:
        db.close()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    t0 = time.time()
    import_all(dry_run=dry_run)
    print(f"Total time: {time.time() - t0:.1f}s")
