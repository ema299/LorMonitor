#!/usr/bin/env python3
"""Team Training — modulo isolato per stats per-player.

Chiamato da daily_routine.py con una sola riga:
    from team_training import build_team_data
    data["team"] = build_team_data(all_matches, team_names, pro_matches)

Se fallisce, daily_routine continua senza problemi.
Non modifica nessun dato esterno.
"""

import json
import os
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TEAM_FILE = Path(__file__).parent / "team_roster.json"
"""File JSON con i nomi del team. Formato:
{
  "players": [
    {"name": "PlayerOne", "role": "grinder"},
    {"name": "PlayerTwo", "role": "flex"}
  ]
}
Se non esiste, build_team_data ritorna {} senza errori.
"""


def load_team_roster():
    """Carica la lista giocatori dal file roster. Ritorna [] se mancante."""
    if not TEAM_FILE.exists():
        return []
    try:
        with open(TEAM_FILE) as f:
            roster = json.load(f)
        return roster.get("players", [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Core: per-player stats da match list già caricata
# ---------------------------------------------------------------------------

def _player_matches(matches, player_name):
    """Filtra match dove il giocatore appare (p1 o p2). Case-insensitive."""
    plow = player_name.lower()
    result = []
    for m in matches:
        p1 = m.get("p1_name", "").lower()
        p2 = m.get("p2_name", "").lower()
        if p1 == plow or p2 == plow:
            # Normalizza: il giocatore è sempre "our", l'avversario "opp"
            if p1 == plow:
                result.append({
                    "our_deck": m.get("p1_deck"),
                    "opp_deck": m.get("p2_deck"),
                    "our_mmr": m.get("p1_mmr", 0),
                    "won": m.get("winner") == 1,
                    "otp": m.get("otp") == 1,  # True se il nostro giocatore era first
                    "day": m.get("day", ""),
                    "game_id": m.get("game_id", ""),
                })
            else:
                result.append({
                    "our_deck": m.get("p2_deck"),
                    "opp_deck": m.get("p1_deck"),
                    "our_mmr": m.get("p2_mmr", 0),
                    "won": m.get("winner") == 2,
                    "otp": m.get("otp") == 2,
                    "day": m.get("day", ""),
                    "game_id": m.get("game_id", ""),
                })
    return result


def _wr(wins, total):
    if total == 0:
        return 0.0
    return round(wins / total * 100, 1)


def _build_player_stats(matches, player_name):
    """Calcola stats complete per un singolo giocatore."""
    pmatches = _player_matches(matches, player_name)
    if not pmatches:
        return None

    total = len(pmatches)
    wins = sum(1 for m in pmatches if m["won"])
    losses = total - wins

    # Deck più giocato
    deck_counts = defaultdict(int)
    for m in pmatches:
        if m["our_deck"]:
            deck_counts[m["our_deck"]] += 1
    main_deck = max(deck_counts, key=deck_counts.get) if deck_counts else None

    # MMR più alto
    best_mmr = max((m["our_mmr"] for m in pmatches if m["our_mmr"]), default=0)

    # OTP/OTD split
    otp_games = [m for m in pmatches if m["otp"]]
    otd_games = [m for m in pmatches if not m["otp"]]
    otp_wr = _wr(sum(1 for m in otp_games if m["won"]), len(otp_games))
    otd_wr = _wr(sum(1 for m in otd_games if m["won"]), len(otd_games))

    # WR per matchup (vs ogni deck avversario)
    vs_stats = defaultdict(lambda: {"w": 0, "l": 0})
    for m in pmatches:
        opp = m["opp_deck"]
        if not opp:
            continue
        if m["won"]:
            vs_stats[opp]["w"] += 1
        else:
            vs_stats[opp]["l"] += 1

    matchups = {}
    for opp, s in sorted(vs_stats.items(), key=lambda x: -(x[1]["w"] + x[1]["l"])):
        t = s["w"] + s["l"]
        matchups[opp] = {
            "w": s["w"],
            "l": s["l"],
            "wr": _wr(s["w"], t),
            "games": t,
        }

    # Worst matchup (min 3 games)
    worst_mu = None
    worst_wr = 100
    for opp, s in matchups.items():
        if s["games"] >= 3 and s["wr"] < worst_wr:
            worst_wr = s["wr"]
            worst_mu = opp

    # Best matchup (min 3 games)
    best_mu = None
    best_wr = 0
    for opp, s in matchups.items():
        if s["games"] >= 3 and s["wr"] > best_wr:
            best_wr = s["wr"]
            best_mu = opp

    # WR per giorno (per sparkline trend)
    day_stats = defaultdict(lambda: {"w": 0, "t": 0})
    for m in pmatches:
        d = m["day"]
        day_stats[d]["t"] += 1
        if m["won"]:
            day_stats[d]["w"] += 1
    daily = []
    for d in sorted(day_stats.keys()):
        s = day_stats[d]
        daily.append({
            "day": d,
            "wr": _wr(s["w"], s["t"]),
            "games": s["t"],
        })

    # Alert flags
    alerts = []
    if worst_mu and worst_wr < 40:
        alerts.append({
            "type": "danger",
            "msg": f"WR {worst_wr}% vs {worst_mu} ({matchups[worst_mu]['games']}g)",
        })
    if otp_wr - otd_wr > 15:
        alerts.append({
            "type": "warning",
            "msg": f"OTP/OTD gap: {round(otp_wr - otd_wr, 1)}pp — soffre OTD",
        })
    if total >= 5 and _wr(wins, total) < 45:
        alerts.append({
            "type": "danger",
            "msg": f"WR complessivo {_wr(wins, total)}% su {total} partite",
        })

    return {
        "name": player_name,
        "deck": main_deck,
        "games": total,
        "wins": wins,
        "losses": losses,
        "wr": _wr(wins, total),
        "mmr": best_mmr,
        "otp_wr": otp_wr,
        "otd_wr": otd_wr,
        "otp_otd_gap": round(otp_wr - otd_wr, 1),
        "matchups": matchups,
        "worst_matchup": worst_mu,
        "best_matchup": best_mu,
        "daily": daily,
        "alerts": alerts,
    }


def _build_team_overview(player_stats_list):
    """Genera overview aggregato del team."""
    active = [p for p in player_stats_list if p is not None]
    if not active:
        return {}

    total_games = sum(p["games"] for p in active)
    total_wins = sum(p["wins"] for p in active)
    avg_wr = _wr(total_wins, total_games) if total_games else 0

    best_player = max(active, key=lambda p: p["wr"]) if active else None
    worst_player = min(active, key=lambda p: p["wr"]) if active else None

    # Weakness overlap: per ogni deck avversario, quanti player hanno WR < 45%?
    opp_decks = set()
    for p in active:
        opp_decks.update(p["matchups"].keys())

    weakness_overlap = {}
    for opp in sorted(opp_decks):
        weak_players = []
        for p in active:
            mu = p["matchups"].get(opp)
            if mu and mu["games"] >= 2 and mu["wr"] < 45:
                weak_players.append(p["name"])
        if weak_players:
            weakness_overlap[opp] = weak_players

    # Team alerts
    team_alerts = []
    for opp, players in weakness_overlap.items():
        if len(players) >= 2:
            team_alerts.append({
                "type": "danger",
                "msg": f"{len(players)}/{len(active)} giocatori sotto 45% vs {opp}",
                "players": players,
                "deck": opp,
            })

    return {
        "total_games": total_games,
        "avg_wr": avg_wr,
        "player_count": len(active),
        "best_player": {"name": best_player["name"], "wr": best_player["wr"]} if best_player else None,
        "worst_player": {"name": worst_player["name"], "wr": worst_player["wr"]} if worst_player else None,
        "weakness_overlap": weakness_overlap,
        "alerts": team_alerts,
    }


# ---------------------------------------------------------------------------
# Entry point — chiamato da daily_routine
# ---------------------------------------------------------------------------

def build_team_data(all_matches, pro_matches=None):
    """Genera il blocco 'team' per dashboard_data.json.

    Args:
        all_matches: lista match già caricata (formato daily_routine)
        pro_matches: match PRO per baseline (opzionale)

    Returns:
        dict con overview + per-player stats, o {} se nessun team configurato.
    """
    roster = load_team_roster()
    if not roster:
        return {}

    # Merge tutti i match disponibili per massimizzare sample size
    matches = all_matches
    if pro_matches:
        seen = {m["game_id"] for m in matches}
        for m in pro_matches:
            if m["game_id"] not in seen:
                matches.append(m)
                seen.add(m["game_id"])

    # Build per-player stats
    player_stats = []
    for entry in roster:
        name = entry.get("name", "")
        if not name:
            continue
        stats = _build_player_stats(matches, name)
        if stats:
            stats["role"] = entry.get("role", "")
            player_stats.append(stats)

    if not player_stats:
        return {"overview": {}, "players": [], "roster_count": len(roster)}

    overview = _build_team_overview(player_stats)

    return {
        "overview": overview,
        "players": player_stats,
        "roster_count": len(roster),
    }


# ---------------------------------------------------------------------------
# CLI standalone per test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Team Training — test standalone")
    print(f"Roster file: {TEAM_FILE}")
    roster = load_team_roster()
    if not roster:
        print("Nessun roster trovato. Crea daily/team_roster.json con:")
        print('  {"players": [{"name": "NomeGiocatore", "role": "grinder"}]}')
    else:
        print(f"Roster: {len(roster)} giocatori")
        for p in roster:
            print(f"  - {p.get('name')} ({p.get('role', 'N/A')})")
