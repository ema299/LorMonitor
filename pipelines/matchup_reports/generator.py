"""Native matchup report generator — D3 Liberation Day.

Generates report types from native digests + PG matches.
Turns JSONB structure: flat list of events, each with:
  {type, player, turnNumber, cardRefs: [{id, name}], data: {...}}

Report types generated:
  overview, loss_analysis, winning_hands, board_state,
  playbook, decklist, ability_cards
  (killer_responses requires LLM — returns None, frontend fail-closed)
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIGEST_DIR = _PROJECT_ROOT / "output" / "digests"
CARDS_DB_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json")

_cards_db_cache = None


def _our_won(row, our: str) -> bool:
    """Check if 'our' deck won. winner column is 'deck_a' or 'deck_b'."""
    if row.winner == 'deck_a':
        return row.deck_a == our
    return row.deck_b == our


def _get_cards_db() -> dict:
    global _cards_db_cache
    if _cards_db_cache is None:
        if CARDS_DB_PATH.exists():
            _cards_db_cache = json.load(open(CARDS_DB_PATH))
        else:
            _cards_db_cache = {}
    return _cards_db_cache


def _load_digest(our: str, opp: str, game_format: str) -> dict | None:
    sfx = '_inf' if game_format == 'infinity' else ''
    path = DIGEST_DIR / f"digest_{our}_vs_{opp}{sfx}.json"
    if not path.exists():
        return None
    return json.load(open(path))


def _card_name(ref) -> str:
    """Extract card name from cardRefs entry."""
    if isinstance(ref, dict):
        return ref.get("name", "")
    return str(ref)


# ---------------------------------------------------------------------------
# 1. OVERVIEW
# ---------------------------------------------------------------------------

def generate_overview(db: Session, our: str, opp: str, game_format: str) -> dict | None:
    row = db.execute(text("""
        SELECT
            COUNT(*) AS games,
            SUM(CASE WHEN (deck_a = :our AND winner = 'deck_a')
                      OR (deck_b = :our AND winner = 'deck_b') THEN 1 ELSE 0 END) AS wins
        FROM matches
        WHERE ((deck_a = :our AND deck_b = :opp) OR (deck_a = :opp AND deck_b = :our))
          AND game_format = :fmt
          AND played_at >= NOW() - INTERVAL '30 days'
    """), {"our": our, "opp": opp, "fmt": game_format}).fetchone()

    if not row or row.games < 10:
        return None

    wins = int(row.wins)
    losses = int(row.games) - wins
    wr = round(wins / row.games * 100)

    return {
        "wr": wr,
        "gap": 0,
        "wins": wins,
        "losses": losses,
        "otp_wr": 0,
        "otd_wr": 0,
        "otp_games": 0,
        "otd_games": 0,
        "lore_progression": [],
    }


# ---------------------------------------------------------------------------
# 2. LOSS ANALYSIS — from digest
# ---------------------------------------------------------------------------

def generate_loss_analysis(digest: dict) -> dict | None:
    if not digest:
        return None

    card_ex = digest.get("card_examples", {})
    critical_cards = {}
    for card_name, info in list(card_ex.items())[:15]:
        critical_cards[card_name] = info.get("count", 0) if isinstance(info, dict) else info

    return {
        "cause_frequency": digest.get("alert_losses", {}),
        "component_primary": digest.get("component_primary", {}),
        "critical_turn_distribution": digest.get("critical_turn_dist", {}),
        "avg_trend_components": {"overall": digest.get("avg_trend", [])},
        "card_at_critical_turn": critical_cards,
    }


# ---------------------------------------------------------------------------
# 3. WINNING HANDS — from turns INITIAL_HAND/MULLIGAN events in wins
# ---------------------------------------------------------------------------

def generate_winning_hands(db: Session, our: str, opp: str, game_format: str) -> dict | None:
    rows = db.execute(text("""
        SELECT turns, deck_a, deck_b, winner
        FROM matches
        WHERE ((deck_a = :our AND deck_b = :opp) OR (deck_a = :opp AND deck_b = :our))
          AND game_format = :fmt
          AND ((deck_a = :our AND winner = 'deck_a') OR (deck_b = :our AND winner = 'deck_b'))
          AND turns IS NOT NULL AND turns != 'null'::jsonb
          AND played_at >= NOW() - INTERVAL '30 days'
        LIMIT 300
    """), {"our": our, "opp": opp, "fmt": game_format}).fetchall()

    if len(rows) < 10:
        return None

    card_counts = Counter()
    total_wins = len(rows)

    for row in rows:
        events = row.turns if isinstance(row.turns, list) else json.loads(row.turns)
        our_is_a = (row.deck_a == our)
        our_player = 1 if our_is_a else 2

        hand_cards = set()
        for ev in events:
            if ev.get("player") != our_player:
                continue
            if ev.get("type") == "INITIAL_HAND":
                hand_cards = {_card_name(r) for r in ev.get("cardRefs", [])}
            elif ev.get("type") == "MULLIGAN":
                hand_cards = {_card_name(r) for r in ev.get("cardRefs", [])}

        for card in hand_cards:
            if card:
                card_counts[card] += 1

    cards = []
    for card, freq in card_counts.most_common(15):
        pct = round(freq / total_wins * 100)
        if pct < 10:
            break
        cards.append({"name": card, "freq": freq, "pct": pct})

    pairs = _compute_winning_pairs(rows, our)
    return {"cards": cards, "sweet_spot": {"min": 3, "max": 5}, "winning_pairs": pairs}


def _compute_winning_pairs(rows, our: str) -> list:
    pair_counts = Counter()
    total = len(rows)

    for row in rows:
        events = row.turns if isinstance(row.turns, list) else json.loads(row.turns)
        our_is_a = (row.deck_a == our)
        our_player = 1 if our_is_a else 2

        hand_cards = []
        for ev in events:
            if ev.get("player") != our_player:
                continue
            if ev.get("type") in ("INITIAL_HAND", "MULLIGAN"):
                hand_cards = [_card_name(r) for r in ev.get("cardRefs", [])]

        for i, c1 in enumerate(hand_cards):
            for c2 in hand_cards[i+1:]:
                if c1 and c2:
                    pair = tuple(sorted([c1, c2]))
                    pair_counts[pair] += 1

    pairs = []
    for (c1, c2), count in pair_counts.most_common(5):
        pct = round(count / total * 100)
        if pct < 5:
            break
        pairs.append({"cards": [c1, c2], "freq": count, "pct": pct})
    return pairs


# ---------------------------------------------------------------------------
# 4. BOARD STATE — from digest profiles (lore_t4 + mechanics)
# ---------------------------------------------------------------------------

def generate_board_state(digest: dict) -> dict | None:
    """Approximate board state from digest profile data."""
    if not digest:
        return None

    profiles = digest.get("profiles", {})
    lore_speed = digest.get("lore_speed", {})

    result = {}
    for t_key, t_num in [("T6", 6), ("T7", 7)]:
        # Use avg_trend if available
        avg_trend = digest.get("avg_trend", [])
        if len(avg_trend) >= t_num:
            loss_gap = avg_trend[t_num - 1]
        else:
            loss_gap = 0

        result[t_key] = {
            "lore_gap": {"win": 0, "loss": round(loss_gap, 1)},
            "opp_lore": {"win": 0, "loss": 0},
            "our_dead": {"win": 0, "loss": 0},
            "our_bounced": {"win": 0, "loss": 0},
            "gap_distribution": [],
        }

    return result if result else None


# ---------------------------------------------------------------------------
# 5. PLAYBOOK — opponent plays per turn from turns CARD_PLAYED events
# ---------------------------------------------------------------------------

def generate_playbook(db: Session, our: str, opp: str, game_format: str) -> list | None:
    """Opponent play patterns per turn (T1-T7) from turns events."""
    rows = db.execute(text("""
        SELECT turns, deck_a, deck_b, winner
        FROM matches
        WHERE ((deck_a = :our AND deck_b = :opp) OR (deck_a = :opp AND deck_b = :our))
          AND game_format = :fmt
          AND NOT ((deck_a = :our AND winner = 'deck_a') OR (deck_b = :our AND winner = 'deck_b'))
          AND turns IS NOT NULL AND turns != 'null'::jsonb
          AND played_at >= NOW() - INTERVAL '30 days'
        LIMIT 300
    """), {"our": our, "opp": opp, "fmt": game_format}).fetchall()

    if len(rows) < 10:
        return None

    total_games = len(rows)
    cards_db = _get_cards_db()

    turn_plays = defaultdict(lambda: Counter())
    turn_active = Counter()

    for row in rows:
        events = row.turns if isinstance(row.turns, list) else json.loads(row.turns)
        our_is_a = (row.deck_a == our)
        opp_player = 2 if our_is_a else 1

        turns_seen = set()
        for ev in events:
            t = ev.get("turnNumber", 0)
            if t < 1 or t > 7:
                continue
            turns_seen.add(t)
            if ev.get("type") == "CARD_PLAYED" and ev.get("player") == opp_player:
                for ref in ev.get("cardRefs", []):
                    card = _card_name(ref)
                    if card:
                        turn_plays[t][card] += 1

        for t in turns_seen:
            turn_active[t] += 1

    result = []
    for t in range(1, 8):
        if turn_active[t] < 5:
            break
        plays = []
        for card, freq in turn_plays[t].most_common(5):
            pct = round(freq / turn_active[t] * 100)
            if pct < 5:
                break
            cost = 0
            effect = ""
            ci = cards_db.get(card, {})
            if isinstance(ci, dict):
                cost = ci.get("cost", 0)
                ability = ci.get("ability", "")
                if ability:
                    effect = ability[:80]
            plays.append({"card": card, "cost": cost, "freq": freq, "pct": pct, "effect": effect})

        label = "Setup" if t <= 2 else "Midgame" if t <= 5 else "Endgame"
        result.append({
            "turn": f"T{t}",
            "label": label,
            "plays": plays,
            "combos": [],
            "impact": {},
            "activity_pct": round(turn_active[t] / total_games * 100),
        })

    return result if result else None


# ---------------------------------------------------------------------------
# 6. DECKLIST — card win-rate delta
# ---------------------------------------------------------------------------

def generate_decklist(db: Session, our: str, opp: str, game_format: str) -> dict | None:
    rows = db.execute(text("""
        SELECT turns, deck_a, deck_b, winner
        FROM matches
        WHERE ((deck_a = :our AND deck_b = :opp) OR (deck_a = :opp AND deck_b = :our))
          AND game_format = :fmt
          AND turns IS NOT NULL AND turns != 'null'::jsonb
          AND played_at >= NOW() - INTERVAL '30 days'
        LIMIT 500
    """), {"our": our, "opp": opp, "fmt": game_format}).fetchall()

    if len(rows) < 20:
        return None

    cards_db = _get_cards_db()
    card_wins = Counter()
    card_games = Counter()
    total_games = len(rows)

    for row in rows:
        events = row.turns if isinstance(row.turns, list) else json.loads(row.turns)
        our_is_a = (row.deck_a == our)
        our_player = 1 if our_is_a else 2
        is_win = _our_won(row, our)

        our_cards = set()
        for ev in events:
            if ev.get("type") == "CARD_PLAYED" and ev.get("player") == our_player:
                for ref in ev.get("cardRefs", []):
                    card = _card_name(ref)
                    if card:
                        our_cards.add(card)

        for card in our_cards:
            card_games[card] += 1
            if is_win:
                card_wins[card] += 1

    overall_wr = sum(1 for r in rows if _our_won(r, our)) / total_games

    adds = []
    cuts = []
    for card, games in card_games.items():
        if games < 5:
            continue
        wr = card_wins[card] / games
        delta = round(wr - overall_wr, 2)
        cost = 0
        ci = cards_db.get(card, {})
        if isinstance(ci, dict):
            cost = ci.get("cost", 0)
        entry = {"card": card, "cost": cost, "score": delta, "qty": min(4, max(1, round(games / total_games * 4)))}
        if delta > 0.03:
            adds.append(entry)
        elif delta < -0.03:
            cuts.append(entry)

    adds.sort(key=lambda x: -x["score"])
    cuts.sort(key=lambda x: x["score"])

    return {
        "adds": adds[:8],
        "cuts": cuts[:5],
        "full_list": [],
        "mana_curve": {},
        "base_source": "pg_native",
        "import_text": "",
    }


# ---------------------------------------------------------------------------
# 7. KILLER RESPONSES — requires LLM (placeholder)
# ---------------------------------------------------------------------------

def generate_killer_responses(digest: dict) -> list | None:
    return None  # Requires LLM (Fase B) — frontend fail-closed


# ---------------------------------------------------------------------------
# 8. ABILITY CARDS — from digest + cards_db
# ---------------------------------------------------------------------------

def generate_ability_cards(digest: dict) -> list | None:
    if not digest:
        return None

    cards_db = _get_cards_db()
    card_examples = digest.get("card_examples", {})
    total_losses = digest.get("losses", 1)

    result = []
    for card_name, info in card_examples.items():
        freq = info.get("count", info.get("freq", 0)) if isinstance(info, dict) else info
        loss_pct = round(freq / total_losses * 100) if total_losses else 0

        ci = cards_db.get(card_name, {})
        cost = ci.get("cost", 0) if isinstance(ci, dict) else 0
        ability = ci.get("ability", "") if isinstance(ci, dict) else ""

        result.append({
            "card": card_name,
            "cost": cost,
            "ability": ability[:200] if ability else "",
            "loss_pct": loss_pct,
        })

    result.sort(key=lambda x: -x["loss_pct"])
    return result[:20] if result else None


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def generate_all_reports(db: Session, our: str, opp: str, game_format: str) -> dict:
    """Generate all report types for a matchup. Returns {type: data}."""
    digest = _load_digest(our, opp, game_format)
    reports = {}

    overview = generate_overview(db, our, opp, game_format)
    if overview:
        reports["overview"] = overview

    if digest:
        loss = generate_loss_analysis(digest)
        if loss:
            reports["loss_analysis"] = loss

    wh = generate_winning_hands(db, our, opp, game_format)
    if wh:
        reports["winning_hands"] = wh

    if digest:
        bs = generate_board_state(digest)
        if bs:
            reports["board_state"] = bs

    pb = generate_playbook(db, our, opp, game_format)
    if pb:
        reports["playbook"] = pb

    dl = generate_decklist(db, our, opp, game_format)
    if dl:
        reports["decklist"] = dl

    if digest:
        ac = generate_ability_cards(digest)
        if ac:
            reports["ability_cards"] = ac

    return reports
