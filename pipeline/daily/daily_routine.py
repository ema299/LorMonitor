#!/usr/bin/env python3
"""
Daily Routine — Report giornaliero meta Lorcana.
Genera Daily_routine/output/daily_routine.md e dashboard_data.json.
Perimetri Core: SET11 High ELO (≥1300), TOP, PRO, Community.
Perimetro Infinity: tutti i match INF + top/pro da leaderboard duels.ink.
PRO player list fetched automaticamente da duels.ink leaderboard (4 queue).
"""

import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path("/mnt/HC_Volume_104764377/finanza/Lor")
DAILY_DIR = PROJECT_ROOT / "Analisi_deck" / "analisidef" / "daily"
BASE = PROJECT_ROOT / "matches"
OUTPUT = DAILY_DIR / "output" / "daily_routine.md"
CARDS_DB_PATH = PROJECT_ROOT / "cards_db.json"
SNAPSHOT_DIR = PROJECT_ROOT / "decks_db" / "history"
ANALYZER_BASE = PROJECT_ROOT / "Analisi_deck" / "analisidef"
ANALYZER_REPORTS = ANALYZER_BASE / "reports"
ANALYZER_SCORES = ANALYZER_BASE / "scores"
ANALYZER_OUTPUT = ANALYZER_BASE / "output"

# Build card name → ink color lookup (excludes Dual Ink / Inkless)
_CARD_COLOR_MAP = {}
if CARDS_DB_PATH.exists():
    with open(CARDS_DB_PATH) as _f:
        _db = json.load(_f)
    for _name, _data in _db.items():
        _ink = _data.get("ink", "")
        if _ink and _ink not in ("Dual Ink", "Inkless"):
            _CARD_COLOR_MAP[_name.lower()] = _ink.lower()

MIN_MMR_HIGH = 1300
MIN_GAMES_MATRIX = 3

# Nomi leggibili per tutte le combinazioni colore
COLOR_MAP = {
    frozenset(["amethyst", "sapphire"]): "AmSa",
    frozenset(["emerald", "sapphire"]): "EmSa",
    frozenset(["amber", "sapphire"]): "AbS",
    frozenset(["amber", "amethyst"]): "AmAm",
    frozenset(["amber", "steel"]): "AbSt",
    frozenset(["amber", "emerald"]): "AbE",
    frozenset(["amethyst", "steel"]): "AmySt",
    frozenset(["amethyst", "emerald"]): "AmyE",
    frozenset(["amethyst", "ruby"]): "AmyR",
    frozenset(["emerald", "ruby"]): "ER",
    frozenset(["ruby", "sapphire"]): "RS",
    frozenset(["ruby", "steel"]): "RSt",
    frozenset(["sapphire", "steel"]): "SSt",
    frozenset(["emerald", "steel"]): "ESt",
    frozenset(["amber", "ruby"]): "AbR",
}

# Mono-colore = dato sporco, ignorare
MONO_COLORS = {"amethyst", "amber", "emerald", "ruby", "sapphire", "steel"}

# Friends — lista hardcodata, sempre tracciati
FRIENDS = {
    'macs', 'sbot', 'harry_pelat',
    'tol_vibes', 'tol_barox', 'tol_papavale', 'tol_giorgio',
}
# Prefissi friends: cattura anche nomi futuri (es. TOL_Nuovo)
FRIENDS_PREFIXES = ('tol_',)

# Leaderboard sizes
LEADERBOARD_TOP_N = 70   # TOP = primi 70 in leaderboard
LEADERBOARD_PRO_N = 30   # PRO = primi 30 in leaderboard (sottoinsieme di TOP)

# Dinamiche: aggiornate da fetch_leaderboards() in main()
# Core
TOP_PLAYERS = set()          # top 70 leaderboard core (BO1+BO3 union)
PRO_PLAYERS = set()          # top 30 leaderboard core (sottoinsieme di TOP)
# Infinity
TOP_PLAYERS_INF = set()      # top 70 leaderboard infinity
PRO_PLAYERS_INF = set()      # top 30 leaderboard infinity
ALL_NOTABLE = set(FRIENDS)   # union di tutto (per tag nei report)


def is_notable(name):
    """Check if a player name (lowercase) is in ALL_NOTABLE or matches FRIENDS_PREFIXES."""
    return name in ALL_NOTABLE or any(name.startswith(p) for p in FRIENDS_PREFIXES)


def get_last_n_days(n=2):
    folders = []
    for i in range(n):
        d = datetime.now() - timedelta(days=i)
        folders.append(d.strftime("%d%m%y"))
    return folders


def infer_colors_from_logs(logs, player_num):
    """Infer deck colors from cardRefs in log events for a given player (1 or 2)."""
    colors = set()
    for ev in logs:
        if ev.get("player") != player_num:
            continue
        for ref in ev.get("cardRefs", []):
            name = (ref.get("name") or "").lower()
            if name in _CARD_COLOR_MAP:
                colors.add(_CARD_COLOR_MAP[name])
                if len(colors) >= 2:
                    return frozenset(colors)
    return frozenset(colors) if len(colors) >= 2 else frozenset()


def get_deck(player_info, logs=None, player_num=None):
    # Prefer log-inferred colors (ground truth from actual cards played)
    # inkColors from duels.ink API is unreliable: often 1, 3, or 6 colors
    if logs is not None and player_num is not None:
        colors = infer_colors_from_logs(logs, player_num)
        if len(colors) == 2:
            deck = COLOR_MAP.get(colors, None)
            if deck:
                return deck
    # Fallback to inkColors only if logs didn't yield 2 colors
    colors = frozenset(c.lower() for c in player_info.get("inkColors", []))
    if not colors or len(colors) != 2:
        return None
    return COLOR_MAP.get(colors, None)


def get_winner(match_data):
    logs = match_data.get("log_data", {}).get("logs", [])
    for ev in logs:
        if ev.get("type") in ("GAME_END", "GAME_CONCEDED"):
            return ev.get("data", {}).get("winner")
    return None


def get_otp(match_data):
    """Return player number (1 or 2) who goes first (OTP), or None."""
    logs = match_data.get("log_data", {}).get("logs", [])
    for ev in logs:
        if ev.get("type") == "TURN_START" and ev.get("turnNumber") == 1:
            return ev.get("player")
    return None


def load_matches(folders, subfolder, min_mmr=0):
    matches = []
    for day in folders:
        day_path = BASE / day / subfolder
        if not day_path.exists():
            continue
        for root, _, fnames in os.walk(str(day_path)):
            for fname in fnames:
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                except Exception:
                    continue

                gi = data.get("game_info", {})
                p1 = gi.get("player1", {})
                p2 = gi.get("player2", {})
                m1 = p1.get("mmr") or 0
                m2 = p2.get("mmr") or 0
                avg_mmr = (m1 + m2) / 2 if m1 and m2 else max(m1, m2)

                if avg_mmr < min_mmr:
                    continue

                winner = get_winner(data)
                if winner is None:
                    continue

                logs = data.get("log_data", {}).get("logs", [])
                otp = get_otp(data)
                matches.append({
                    "p1_name": (p1.get("name") or "").strip(),
                    "p2_name": (p2.get("name") or "").strip(),
                    "p1_deck": get_deck(p1, logs, 1),
                    "p2_deck": get_deck(p2, logs, 2),
                    "p1_mmr": m1,
                    "p2_mmr": m2,
                    "avg_mmr": avg_mmr,
                    "winner": winner,
                    "otp": otp,
                    "day": day,
                    "queue": gi.get("queueShortName", ""),
                    "game_id": fname.replace(".json", ""),
                })
    return matches


def _extract_hand(logs, player_num):
    """Extract hand info from raw log events for a given player."""
    init_hand = None
    mulligan = None
    for e in logs:
        ep = e.get('player')
        if ep is not None:
            ep = int(ep)
        t = e.get('type', '')
        if t == 'INITIAL_HAND' and ep == player_num:
            init_hand = e.get('cardRefs', [])
        elif t == 'MULLIGAN' and ep == player_num:
            refs = e.get('cardRefs', [])
            mc = (e.get('data') or {}).get('mulliganCount')
            if mc is None:
                mc = e.get('mulliganCount', 0)
            mulligan = {'count': int(mc), 'refs': refs}

    if init_hand is None and mulligan is None:
        return None

    extract = lambda refs: [c.get('name', c.get('id', '?')) if isinstance(c, dict) else str(c) for c in refs]

    mc = mulligan['count'] if mulligan else 0
    if init_hand and mulligan and mc > 0:
        sb_names = extract(mulligan['refs'][:mc])
        init_names = extract(init_hand)
        recv_names = extract(mulligan['refs'][mc:])
        # Determine kept cards
        sb_ids = [c.get('id', '?') if isinstance(c, dict) else str(c) for c in mulligan['refs'][:mc]]
        init_ids = [c.get('id', '?') if isinstance(c, dict) else str(c) for c in init_hand]
        sb_copy = list(sb_ids)
        kept = []
        for i, cid in enumerate(init_ids):
            if cid in sb_copy:
                sb_copy.remove(cid)
            else:
                kept.append(init_names[i])
        return {'mull': mc, 'initial': init_names, 'sent': sb_names, 'kept': kept,
                'recv': recv_names, 'final': kept + recv_names}
    elif init_hand:
        names = extract(init_hand)
        return {'mull': 0, 'initial': names, 'sent': [], 'kept': names, 'recv': [], 'final': names}
    return None


def load_pro_mulligan_data(folders, game_format=None):
    """Load mulligan data from PRO matches, grouped by deck vs opponent.

    Args:
        folders: list of day folder names to scan
        game_format: 'core', 'infinity', or None (all).
            core  = queue starts with S11- or SEAL-
            infinity = queue starts with INF-
    """
    result = {}  # {deck: {opp: [hand_records]}}
    for day in folders:
        for subfolder in ["PRO", "TOP"]:
            day_path = BASE / day / subfolder
            if not day_path.exists():
                continue
            for root, _, fnames in os.walk(str(day_path)):
                for fname in fnames:
                    if not fname.endswith(".json"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath) as f:
                            data = json.load(f)
                    except Exception:
                        continue

                    gi = data.get("game_info", {})

                    # Filter by game format via queueShortName
                    if game_format:
                        queue = gi.get("queueShortName", "")
                        if game_format == "core" and not (queue.startswith("S11") or queue.startswith("SEAL")):
                            continue
                        if game_format == "infinity" and not queue.startswith("INF"):
                            continue

                    p1 = gi.get("player1", {})
                    p2 = gi.get("player2", {})
                    logs = data.get("log_data", {}).get("logs", [])
                    winner = get_winner(data)
                    if winner is None:
                        continue

                    p1_name = (p1.get("name") or "").strip().lower()
                    p2_name = (p2.get("name") or "").strip().lower()
                    p1_deck = get_deck(p1, logs, 1)
                    p2_deck = get_deck(p2, logs, 2)
                    if not p1_deck or not p2_deck:
                        continue

                    is_pro_1 = is_notable(p1_name) or subfolder == "PRO"
                    is_pro_2 = is_notable(p2_name) or subfolder == "PRO"
                    otp = get_otp(data)  # 1 or 2 (player who goes first)

                    for pnum, pname, pdeck, odeck, is_pro in [
                        (1, p1_name, p1_deck, p2_deck, is_pro_1),
                        (2, p2_name, p2_deck, p1_deck, is_pro_2),
                    ]:
                        if not is_pro:
                            continue
                        hand = _extract_hand(logs, pnum)
                        if not hand or not hand.get('initial'):
                            continue
                        won = (winner == pnum)
                        is_otp = (otp == pnum) if otp else None
                        match_game = gi.get('matchGame')  # 1/2/3 for Bo3, None for ladder
                        rec = {
                            'player': pname.title(),
                            'initial': hand['initial'],
                            'sent': hand['sent'],
                            'final': hand['final'],
                            'mull': hand['mull'],
                            'won': won,
                            'otp': is_otp,
                            'game': match_game,  # None=ladder, 1=G1 blind, 2/3=informed
                        }
                        result.setdefault(pdeck, {}).setdefault(odeck, []).append(rec)
    return result


def build_matrix(matches):
    wins = defaultdict(lambda: defaultdict(int))
    total = defaultdict(lambda: defaultdict(int))
    for m in matches:
        d1, d2 = m["p1_deck"], m["p2_deck"]
        if not d1 or not d2:
            continue
        total[d1][d2] += 1
        total[d2][d1] += 1
        if m["winner"] == 1:
            wins[d1][d2] += 1
        else:
            wins[d2][d1] += 1
    return wins, total


def deck_stats(matches):
    """Returns {deck: {w, l, games}} sorted by games desc."""
    stats = defaultdict(lambda: {"w": 0, "l": 0})
    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            deck = m[f"{pkey}_deck"]
            if not deck:
                continue
            if m["winner"] == pnum:
                stats[deck]["w"] += 1
            else:
                stats[deck]["l"] += 1
    for d in stats:
        stats[d]["games"] = stats[d]["w"] + stats[d]["l"]
        stats[d]["wr"] = stats[d]["w"] / stats[d]["games"] * 100
    return dict(sorted(stats.items(), key=lambda x: -x[1]["games"]))


def format_wr_table(stats, min_games=5):
    lines = ["| Deck | Partite | WR |", "|---|---|---|"]
    for deck, s in stats.items():
        if s["games"] < min_games:
            continue
        wr = s["wr"]
        if wr >= 55:
            lines.append(f"| **{deck}** | {s['games']} | **{wr:.1f}%** |")
        elif wr <= 42:
            lines.append(f"| {deck} | {s['games']} | _{wr:.1f}%_ |")
        else:
            lines.append(f"| {deck} | {s['games']} | {wr:.1f}% |")
    return "\n".join(lines)


def format_matrix(wins, total, top_n=8):
    """Matrix dei top N deck per partite giocate."""
    deck_games = defaultdict(int)
    for d1 in total:
        for d2 in total[d1]:
            deck_games[d1] += total[d1][d2]
    decks = sorted(deck_games.keys(), key=lambda d: -deck_games[d])[:top_n]

    if len(decks) < 2:
        return "Dati insufficienti per matrice.\n"

    lines = []
    header = "| | " + " | ".join(decks) + " |"
    sep = "|---|" + "|".join(["---"] * len(decks)) + "|"
    lines.append(header)
    lines.append(sep)

    for d1 in decks:
        row = f"| **{d1}** |"
        for d2 in decks:
            if d1 == d2:
                row += " - |"
            else:
                t = total[d1][d2]
                if t < MIN_GAMES_MATRIX:
                    row += " · |"
                else:
                    w = wins[d1][d2]
                    wr = w / t * 100
                    if wr >= 60:
                        row += f" **{wr:.0f}%** |"
                    elif wr <= 40:
                        row += f" _{wr:.0f}%_ |"
                    else:
                        row += f" {wr:.0f}% |"
        lines.append(row)

    lines.append("")
    lines.append(f"_**grassetto** ≥60% | _corsivo_ ≤40% | · = <{MIN_GAMES_MATRIX}g_")
    return "\n".join(lines)


def format_matrix_wins(wins, total, top_n=8):
    """Matrice con vittorie assolute W/T per ogni matchup."""
    deck_games = defaultdict(int)
    for d1 in total:
        for d2 in total[d1]:
            deck_games[d1] += total[d1][d2]
    decks = sorted(deck_games.keys(), key=lambda d: -deck_games[d])[:top_n]

    if len(decks) < 2:
        return ""

    lines = []
    header = "| | " + " | ".join(decks) + " |"
    sep = "|---|" + "|".join(["---"] * len(decks)) + "|"
    lines.append(header)
    lines.append(sep)

    for d1 in decks:
        row = f"| **{d1}** |"
        for d2 in decks:
            if d1 == d2:
                row += " - |"
            else:
                t = total[d1][d2]
                w = wins[d1][d2]
                if t == 0:
                    row += " · |"
                else:
                    row += f" {w}/{t} |"
        lines.append(row)

    lines.append("")
    lines.append("_W/T = vittorie / partite totali_")
    return "\n".join(lines)


def format_trend(matches, days):
    """WR per deck, giorno per giorno."""
    day_stats = {d: defaultdict(lambda: {"w": 0, "l": 0}) for d in days}
    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            deck = m[f"{pkey}_deck"]
            if not deck:
                continue
            if m["winner"] == pnum:
                day_stats[m["day"]][deck]["w"] += 1
            else:
                day_stats[m["day"]][deck]["l"] += 1

    # Top deck per volume totale
    overall = deck_stats(matches)
    top_decks = [d for d, s in overall.items() if s["games"] >= 20][:10]

    if not top_decks:
        return ""

    lines = ["| Deck |"]
    for d in days:
        dd = f"{d[:2]}/{d[2:4]}"
        lines[0] += f" {dd} |"
    lines.append("|---|" + "|".join(["---"] * len(days)) + "|")

    for deck in top_decks:
        row = f"| {deck} |"
        for d in days:
            ds = day_stats[d][deck]
            t = ds["w"] + ds["l"]
            if t < 3:
                row += " · |"
            else:
                wr = ds["w"] / t * 100
                row += f" {wr:.0f}% ({t}g) |"
        lines.append(row)

    return "\n".join(lines)


def format_top_players(matches, min_games=4, limit=15):
    stats = defaultdict(lambda: {"wins": 0, "losses": 0, "decks": defaultdict(int), "mmr": 0, "display": ""})
    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            deck = m[f"{pkey}_deck"]
            mmr = m[f"{pkey}_mmr"]
            if not name or not deck:
                continue
            s = stats[name]
            s["display"] = m[f"{pkey}_name"]
            s["mmr"] = max(s["mmr"], mmr)
            s["decks"][deck] += 1
            if m["winner"] == pnum:
                s["wins"] += 1
            else:
                s["losses"] += 1

    ranked = []
    for name, s in stats.items():
        total = s["wins"] + s["losses"]
        if total < min_games:
            continue
        wr = s["wins"] / total * 100
        main_deck = max(s["decks"], key=s["decks"].get)
        is_pro = is_notable(name)
        ranked.append((s["display"], s["wins"], s["losses"], wr, s["mmr"], main_deck, is_pro))

    ranked.sort(key=lambda x: (-x[3], -x[4]))

    lines = ["| Player | W-L | WR | MMR | Deck |", "|---|---|---|---|---|"]
    for name, w, l, wr, mmr, deck, is_pro in ranked[:limit]:
        tag = " **PRO**" if is_pro else ""
        lines.append(f"| {name}{tag} | {w}-{l} | {wr:.0f}% | {mmr} | {deck} |")
    return "\n".join(lines)


def format_pro_detail(all_matches):
    lines = []
    pro_matches = defaultdict(list)
    for m in all_matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            if is_notable(name):
                pro_matches[name].append((m, pnum, pkey))

    if not pro_matches:
        return "Nessun PRO attivo.\n"

    for pro_name in sorted(pro_matches.keys()):
        ml = pro_matches[pro_name]
        display = ml[0][0][f"{ml[0][2]}_name"]
        wins = sum(1 for m, pnum, _ in ml if m["winner"] == pnum)
        losses = len(ml) - wins
        wr = wins / len(ml) * 100

        # Deck breakdown
        deck_r = defaultdict(lambda: {"w": 0, "l": 0})
        for m, pnum, pkey in ml:
            deck = m[f"{pkey}_deck"] or "mono/?"
            if m["winner"] == pnum:
                deck_r[deck]["w"] += 1
            else:
                deck_r[deck]["l"] += 1

        deck_str = ", ".join(
            f"{d} {r['w']}W-{r['l']}L"
            for d, r in sorted(deck_r.items(), key=lambda x: -(x[1]["w"] + x[1]["l"]))
        )

        # Matchup vs opponents
        mu_r = defaultdict(lambda: {"w": 0, "l": 0})
        for m, pnum, pkey in ml:
            opp_key = "p2" if pkey == "p1" else "p1"
            opp_deck = m[f"{opp_key}_deck"] or "mono/?"
            if m["winner"] == pnum:
                mu_r[opp_deck]["w"] += 1
            else:
                mu_r[opp_deck]["l"] += 1

        mu_str = ", ".join(
            f"vs {opp} {r['w']}-{r['l']}"
            for opp, r in sorted(mu_r.items(), key=lambda x: -(x[1]["w"] + x[1]["l"]))
        )

        lines.append(f"- **{display}** ({wins}W-{losses}L, {wr:.0f}%): {deck_str}")
        lines.append(f"  - {mu_str}")

    return "\n".join(lines)


def find_notable_matchups(wins, total, min_games=5):
    """Trova matchup estremi (>= 70% o <= 30%)."""
    notable = []
    seen = set()
    for d1 in total:
        for d2 in total[d1]:
            if d1 >= d2:
                continue
            pair = (d1, d2)
            if pair in seen:
                continue
            seen.add(pair)
            t = total[d1][d2]
            if t < min_games:
                continue
            w = wins[d1][d2]
            wr = w / t * 100
            if wr >= 70:
                notable.append((d1, d2, wr, t, "domina"))
            elif wr <= 30:
                notable.append((d2, d1, 100 - wr, t, "domina"))
    notable.sort(key=lambda x: -x[2])
    return notable


def format_matrix_otp_otd(matches, top_n=8):
    """Matrice matchup splittata OTP/OTD. Mostra WR OTP e OTD per ogni cella."""
    # Count games per deck for ranking
    deck_games = defaultdict(int)
    for m in matches:
        if m["p1_deck"]:
            deck_games[m["p1_deck"]] += 1
        if m["p2_deck"]:
            deck_games[m["p2_deck"]] += 1
    decks = sorted(deck_games.keys(), key=lambda d: -deck_games[d])[:top_n]

    if len(decks) < 2:
        return "Dati insufficienti.\n"

    # Build OTP/OTD wins and totals: stats[deck_a][deck_b] = {otp_w, otp_t, otd_w, otd_t}
    stats = defaultdict(lambda: defaultdict(lambda: {"otp_w": 0, "otp_t": 0, "otd_w": 0, "otd_t": 0}))
    for m in matches:
        d1, d2 = m["p1_deck"], m["p2_deck"]
        otp = m.get("otp")
        if not d1 or not d2 or not otp:
            continue
        w = m["winner"]
        # For p1's perspective
        if otp == 1:
            stats[d1][d2]["otp_t"] += 1
            stats[d2][d1]["otd_t"] += 1
            if w == 1:
                stats[d1][d2]["otp_w"] += 1
            else:
                stats[d2][d1]["otd_w"] += 1
        else:
            stats[d1][d2]["otd_t"] += 1
            stats[d2][d1]["otp_t"] += 1
            if w == 1:
                stats[d1][d2]["otd_w"] += 1
            else:
                stats[d2][d1]["otp_w"] += 1

    lines = []
    header = "| | " + " | ".join(decks) + " |"
    sep = "|---|" + "|".join(["---"] * len(decks)) + "|"
    lines.append(header)
    lines.append(sep)

    for d1 in decks:
        row = f"| **{d1}** |"
        for d2 in decks:
            if d1 == d2:
                row += " - |"
                continue
            s = stats[d1][d2]
            parts = []
            if s["otp_t"] >= 3:
                wr_otp = s["otp_w"] / s["otp_t"] * 100
                parts.append(f"P {wr_otp:.0f}%")
            if s["otd_t"] >= 3:
                wr_otd = s["otd_w"] / s["otd_t"] * 100
                parts.append(f"D {wr_otd:.0f}%")
            if parts:
                row += f" {' / '.join(parts)} |"
            else:
                row += " · |"
        lines.append(row)

    lines.append("")
    lines.append("_P = OTP (play) / D = OTD (draw) | · = <3g_")
    return "\n".join(lines)


def format_meta_share(matches, days):
    """Meta share per deck con delta giornaliero."""
    day_counts = {d: defaultdict(int) for d in days}
    day_totals = {d: 0 for d in days}
    for m in matches:
        for pkey in ("p1", "p2"):
            deck = m[f"{pkey}_deck"]
            if deck:
                day_counts[m["day"]][deck] += 1
                day_totals[m["day"]] += 1

    # Overall share
    overall = defaultdict(int)
    total_all = 0
    for d in days:
        for deck, c in day_counts[d].items():
            overall[deck] += c
        total_all += day_totals[d]

    if total_all == 0:
        return ""

    ranked = sorted(overall.items(), key=lambda x: -x[1])[:12]

    lines = ["| Deck | Share | Partite |"]
    # Add day columns
    for d in reversed(days):
        dd = f"{d[:2]}/{d[2:4]}"
        lines[0] += f" {dd} |"
    lines[0] += " Delta |"

    sep = "|---|---|---|"
    for _ in days:
        sep += "---|"
    sep += "---|"
    lines.append(sep)

    for deck, count in ranked:
        share = count / total_all * 100
        row = f"| {deck} | {share:.1f}% | {count} |"

        day_shares = []
        for d in reversed(days):
            dt = day_totals[d]
            if dt > 0:
                ds = day_counts[d][deck] / dt * 100
                day_shares.append(ds)
                row += f" {ds:.1f}% |"
            else:
                day_shares.append(None)
                row += " · |"

        # Delta: last day - previous day
        if len(day_shares) >= 2 and day_shares[0] is not None and day_shares[1] is not None:
            delta = day_shares[1] - day_shares[0]
            if abs(delta) >= 1.0:
                sign = "+" if delta > 0 else ""
                row += f" **{sign}{delta:.1f}pp** |"
            else:
                row += f" = |"
        else:
            row += " · |"

        lines.append(row)

    lines.append("")
    lines.append("_Share = % del meta totale | Delta = variazione tra i due giorni (pp)_")
    return "\n".join(lines)


def format_scouting_top(matches):
    """Scouting dei TOP player: deck, WR, dettaglio matchup completo."""
    stats = defaultdict(lambda: {
        "display": "", "wins": 0, "losses": 0, "mmr": 0,
        "decks": defaultdict(int), "vs": defaultdict(lambda: {"w": 0, "l": 0})
    })

    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            deck = m[f"{pkey}_deck"]
            mmr = m[f"{pkey}_mmr"]
            if not name or not deck:
                continue

            opp_key = "p2" if pkey == "p1" else "p1"
            opp_deck = m[f"{opp_key}_deck"]

            s = stats[name]
            s["display"] = m[f"{pkey}_name"]
            s["mmr"] = max(s["mmr"], mmr)
            s["decks"][deck] += 1
            if m["winner"] == pnum:
                s["wins"] += 1
                if opp_deck:
                    s["vs"][opp_deck]["w"] += 1
            else:
                s["losses"] += 1
                if opp_deck:
                    s["vs"][opp_deck]["l"] += 1

    # Filter: min 5 games, sort by WR then MMR
    ranked = []
    for name, s in stats.items():
        total = s["wins"] + s["losses"]
        if total < 5:
            continue
        wr = s["wins"] / total * 100
        main_deck = max(s["decks"], key=s["decks"].get)

        # All matchups sorted by games played desc
        all_mu = []
        for opp, r in sorted(s["vs"].items(), key=lambda x: -(x[1]["w"] + x[1]["l"])):
            t = r["w"] + r["l"]
            all_mu.append(f"{opp} {r['w']}-{r['l']}")

        ranked.append({
            "name": s["display"], "w": s["wins"], "l": s["losses"],
            "wr": wr, "mmr": s["mmr"], "deck": main_deck,
            "matchups": ", ".join(all_mu) if all_mu else "-",
        })

    ranked.sort(key=lambda x: (-x["wr"], -x["mmr"]))

    lines = [
        "| Player | W-L | WR | MMR | Deck | Matchup Dettaglio |",
        "|---|---|---|---|---|---|",
    ]
    for p in ranked[:20]:
        lines.append(
            f"| {p['name']} | {p['w']}-{p['l']} | {p['wr']:.0f}% | {p['mmr']} "
            f"| {p['deck']} | {p['matchups']} |"
        )

    lines.append("")
    lines.append("_Matchup = W-L vs ogni archetipo avversario_")
    return "\n".join(lines)


# --- DUELS.INK COMMUNITY STATS ---

SESSION_COOKIE = os.environ.get(
    "DUELS_SESSION",
    "9fNTxXxXcwEvnW8itE9WNkE5puF6hmqN.2wjVeoMu5aC1KLGftbz9%2BSaCuvCdgvdw0sKFDlinKnI%3D"
)

def _ink_short(colors):
    """Convert color list like ['amber','steel'] to short name like 'AbSt'."""
    key = frozenset(c.lower() for c in colors)
    return COLOR_MAP.get(key, "/".join(sorted(colors)))


def fetch_duelsink_stats():
    """Fetch weekly stats from duels.ink /api/stats/meta. Returns dict or None."""
    # Find current week start — duels.ink uses Sunday as week start
    today = datetime.now()
    # weekday(): Mon=0..Sun=6 → days since Sunday = (weekday+1)%7
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    week_start = sunday.strftime("%Y-%m-%d")

    cookie = f"__Secure-better-auth.session_token={SESSION_COOKIE}"
    url = f"https://duels.ink/api/stats/meta?queue=core-set11-bo1-beta&period=week%3A{week_start}"
    try:
        req = urllib.request.Request(url, headers={
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data
    except Exception as e:
        print(f"  duels.ink stats fetch failed: {e}")
        return None


# --- DUELS.INK LEADERBOARD (PRO PLAYER LIST) ---

LEADERBOARD_QUEUES = {
    'core_bo1': 'core-set11-bo1-beta',
    'core_bo3': 'core-set11-bo3-beta',
    'infinity_bo1': 'infinity-bo1-beta',
    'infinity_bo3': 'infinity-bo3-beta',
}


def _names_from_raw(raw_lists, top_n):
    """Estrae i primi top_n nomi unici (per rank) dalla union di più liste raw.

    Ogni lista è già ordinata per rank. Facciamo merge mantenendo il rank migliore
    tra BO1 e BO3 per ogni player, poi prendiamo i primi top_n.
    """
    best_rank = {}  # name_lower → best rank
    for plist in raw_lists:
        for p in plist:
            name = p.get('name')
            if not name:
                continue
            nl = name.lower()
            rank = p.get('rank', 999)
            if nl not in best_rank or rank < best_rank[nl]:
                best_rank[nl] = rank
    # Ordina per rank e prendi i primi top_n
    sorted_names = sorted(best_rank.keys(), key=lambda n: best_rank[n])
    return set(sorted_names[:top_n])


def fetch_leaderboards():
    """Fetch top player lists from duels.ink leaderboard API (4 queue).

    Returns:
        dict with keys:
          'core_top': set lowercase names — top LEADERBOARD_TOP_N (70) core
          'core_pro': set lowercase names — top LEADERBOARD_PRO_N (30) core
          'inf_top': set lowercase names — top 70 infinity
          'inf_pro': set lowercase names — top 30 infinity
          'raw': dict queue_key → list of player dicts (for dashboard export)
    """
    cookie = f"__Secure-better-auth.session_token={SESSION_COOKIE}"
    raw = {}

    for queue_key, queue_id in LEADERBOARD_QUEUES.items():
        url = f"https://duels.ink/api/leaderboard?queue={queue_id}"
        try:
            req = urllib.request.Request(url, headers={
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            players = data.get("leaderboard", [])
            raw[queue_key] = [
                {
                    "rank": p.get("rank", 0),
                    "name": p.get("username") or "",
                    "mmr": p.get("mmr", 0),
                    "peak_mmr": p.get("peakMmr", 0),
                    "wins": p.get("wins", 0),
                    "losses": p.get("losses", 0),
                    "wr": p.get("winRate", 0),
                    "games": p.get("gamesPlayed", 0),
                    "tier": p.get("tier", {}).get("name", ""),
                }
                for p in players
            ]
            print(f"  leaderboard {queue_id}: {len(players)} players")
        except Exception as e:
            print(f"  leaderboard {queue_id} fetch failed: {e}")
            raw[queue_key] = []

    # Build TOP (70) e PRO (30) per formato — union BO1+BO3, ranked by best position
    core_lists = [raw.get('core_bo1', []), raw.get('core_bo3', [])]
    inf_lists = [raw.get('infinity_bo1', []), raw.get('infinity_bo3', [])]

    # Build MMR reference: {name_lower: [mmr1, mmr2, ...]} from leaderboard
    # Keep ALL queue MMRs — BO1 and BO3 ratings differ significantly for some players
    mmr_ref = {}
    for queue_players in [*core_lists, *inf_lists]:
        for p in queue_players:
            name = (p.get('name', '') or '').strip().lower()
            mmr = p.get('mmr', 0) or 0
            if name and mmr:
                mmr_ref.setdefault(name, []).append(mmr)

    return {
        'core_top': _names_from_raw(core_lists, LEADERBOARD_TOP_N),
        'core_pro': _names_from_raw(core_lists, LEADERBOARD_PRO_N),
        'inf_top': _names_from_raw(inf_lists, LEADERBOARD_TOP_N),
        'inf_pro': _names_from_raw(inf_lists, LEADERBOARD_PRO_N),
        'mmr_ref': mmr_ref,
        'raw': raw,
    }


def format_duelsink_section(data):
    """Format duels.ink community stats into markdown."""
    r = []
    activity = data.get("activity", {})
    total = activity.get("totalGames", 0)
    players = activity.get("uniquePlayers", 0)
    period = data.get("meta", {}).get("period", "?")
    play_draw = activity.get("playDrawStats") or {}
    otp_wr = play_draw.get("first", play_draw.get("firstPlayerWinRate", 0)) or 0

    r.append("## Duels.ink Community Stats")
    r.append(f"_Fonte: duels.ink | {period} | {total:,}g | {players:,} giocatori | OTP WR: {otp_wr:.1f}%_\n")

    # Color pair WR table
    cp = sorted(data.get("colorPairs", []), key=lambda x: x.get("games", 0), reverse=True)
    r.append("### Win Rate Community\n")
    r.append("| Deck | Partite | WR | Play% | OTP WR |")
    r.append("|---|---|---|---|---|")
    for c in cp:
        # Skip mono-color entries
        if len(c.get("colors", [])) < 2:
            continue
        name = _ink_short(c["colors"])
        games = c.get("games", 0)
        wr = c.get("winRate", 0)
        play = c.get("playRate", 0)
        first = c.get("firstPlayerWinRate", 0)
        bold = "**" if wr >= 53 else ""
        italic = "_" if wr <= 45 else ""
        r.append(f"| {bold}{italic}{name}{italic}{bold} | {games} | {bold}{italic}{wr:.1f}%{italic}{bold} | {play:.1f}% | {first:.1f}% |")
    r.append("")

    # Matchup matrix
    matchups = data.get("matchups", [])
    if matchups:
        top_cp = [c["colors"] for c in cp[:8]]
        top_names = [_ink_short(c) for c in top_cp]

        r.append("### Matrice Matchup Community\n")
        header = "| | " + " | ".join(f"**{n}**" for n in top_names) + " |"
        sep = "|---|" + "|".join(["---"] * len(top_names)) + "|"
        r.append(header)
        r.append(sep)

        for i, ca in enumerate(top_cp):
            row = [f"**{top_names[i]}**"]
            for j, cb in enumerate(top_cp):
                if i == j:
                    row.append("-")
                    continue
                # Find matchup A vs B
                found = [m for m in matchups if m["colorsA"] == ca and m["colorsB"] == cb]
                if not found:
                    found = [m for m in matchups if m["colorsA"] == cb and m["colorsB"] == ca]
                    if found:
                        wr = 100 - found[0]["winRate"]
                        g = found[0]["games"]
                    else:
                        row.append("·")
                        continue
                else:
                    wr = found[0]["winRate"]
                    g = found[0]["games"]
                cell = f"{wr:.0f}%"
                if wr >= 55:
                    cell = f"**{cell}**"
                elif wr <= 45:
                    cell = f"_{cell}_"
                row.append(cell)
            r.append("| " + " | ".join(row) + " |")
        r.append("")
        r.append("_**grassetto** ≥55% | _corsivo_ ≤45%_\n")

    return "\n".join(r)


def load_snapshot_consensus():
    """Load latest inkdecks snapshot and build consensus card sets per archetype.
    Returns {archetype: {card_name: avg_qty}} for the 'standard' list."""
    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    if not snapshots:
        return {}
    with open(snapshots[-1]) as f:
        data = json.load(f)
    archs = data.get("archetypes", {})
    consensus = {}
    for arch, decks in archs.items():
        if not decks:
            continue
        card_total = defaultdict(int)
        card_count = defaultdict(int)
        for deck in decks:
            for card in deck.get("cards", []):
                name = card["name"]
                card_total[name] += card["qty"]
                card_count[name] += 1
        # Average qty across decks — card is "standard" if in ≥50% of decks
        n = len(decks)
        std = {}
        for name in card_total:
            if card_count[name] >= n * 0.5:  # present in at least half the lists
                std[name] = round(card_total[name] / n, 1)
        consensus[arch] = std
    # Translate legacy deck names to current names
    _LEGACY_NAMES = {"AS": "AmSa", "ES": "EmSa"}
    for old, new in _LEGACY_NAMES.items():
        if old in consensus and new not in consensus:
            consensus[new] = consensus.pop(old)
    return consensus


def extract_player_cards(days, subfolder, min_mmr=0, mmr_ref=None):
    """Extract cards played/inked per player per deck from match logs.

    Args:
        days: list of day folder names
        subfolder: 'TOP', 'PRO', 'SET11', etc.
        min_mmr: minimum avg MMR filter
        mmr_ref: {name_lower: mmr} from leaderboard — used to filter out
                 name collisions (different players with same name but different MMR)

    Returns {(player_lower, deck): {card_name: count_games_seen}}."""
    player_cards = defaultdict(lambda: defaultdict(set))  # (player, deck) -> card -> set of game_ids
    MMR_TOLERANCE = 200  # consider same player if match MMR within this range of leaderboard MMR

    for day in days:
        day_path = BASE / day / subfolder
        if not day_path.exists():
            continue
        for root, _, fnames in os.walk(str(day_path)):
            for fname in fnames:
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                except Exception:
                    continue

                gi = data.get("game_info", {})
                p1 = gi.get("player1", {})
                p2 = gi.get("player2", {})
                m1 = p1.get("mmr") or 0
                m2 = p2.get("mmr") or 0
                avg_mmr = (m1 + m2) / 2 if m1 and m2 else max(m1, m2)
                if avg_mmr < min_mmr:
                    continue

                logs = data.get("log_data", {}).get("logs", [])
                game_id = fname.replace(".json", "")

                for pnum, pinfo in [(1, p1), (2, p2)]:
                    name = (pinfo.get("name") or "").strip().lower()
                    deck = get_deck(pinfo, logs, pnum)
                    if not name or not deck:
                        continue

                    # Filter name collisions: if we have leaderboard MMR for this name,
                    # only accept matches where the player's MMR is close to leaderboard MMR
                    if mmr_ref and name in mmr_ref:
                        player_mmr = pinfo.get("mmr") or 0
                        lb_mmrs = mmr_ref[name]
                        if player_mmr and min(abs(player_mmr - m) for m in lb_mmrs) > MMR_TOLERANCE:
                            continue  # different player with same name

                    key = (name, deck)
                    for ev in logs:
                        if ev.get("player") != pnum:
                            continue
                        if ev.get("type") in ("CARD_PLAYED", "INK_CARD"):
                            for ref in ev.get("cardRefs", []):
                                card_name = ref.get("name")
                                if card_name:
                                    player_cards[key][card_name].add(game_id)

    # Convert to {(player, deck): {card: n_games}}
    result = {}
    for key, cards in player_cards.items():
        result[key] = {card: len(games) for card, games in cards.items()}
    return result


def format_tech_choices(matches, days):
    """Analyze top/high-ELO player decklists vs standard and report tech choices."""
    consensus = load_snapshot_consensus()
    if not consensus:
        return "_Snapshot inkdecks non disponibile._\n"

    # Extract cards from TOP and SET11 high-elo matches
    print("Analisi tech choices dai log...")
    cards_top = extract_player_cards(days, "TOP")
    cards_set11 = extract_player_cards(days, "SET11", min_mmr=MIN_MMR_HIGH)

    # Merge
    all_cards = {}
    for key, cards in {**cards_set11, **cards_top}.items():
        if key in all_cards:
            for c, n in cards.items():
                all_cards[key][c] = max(all_cards[key].get(c, 0), n)
        else:
            all_cards[key] = dict(cards)

    # Build player stats from matches
    player_stats = defaultdict(lambda: {"w": 0, "l": 0, "mmr": 0, "display": ""})
    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            deck = m[f"{pkey}_deck"]
            if not name or not deck:
                continue
            key = (name, deck)
            s = player_stats[key]
            s["display"] = m[f"{pkey}_name"]
            s["mmr"] = max(s["mmr"], m[f"{pkey}_mmr"])
            if m["winner"] == pnum:
                s["w"] += 1
            else:
                s["l"] += 1

    # Filter: players with ≥5 games AND ≥60% WR OR MMR ≥1700
    interesting = []
    for (pname, deck), s in player_stats.items():
        total = s["w"] + s["l"]
        if total < 5:
            continue
        wr = s["w"] / total * 100
        if wr < 60 and s["mmr"] < 1700:
            continue
        if (pname, deck) not in all_cards:
            continue
        interesting.append((pname, deck, s["display"], s["w"], s["l"], wr, s["mmr"]))

    if not interesting:
        return "_Nessun player con dati sufficienti per analisi tech._\n"

    interesting.sort(key=lambda x: (-x[5], -x[6]))

    lines = []
    for pname, deck, display, w, l, wr, mmr in interesting[:15]:
        if deck not in consensus:
            continue

        std = consensus[deck]
        cards = all_cards[(pname, deck)]
        total_games = w + l

        # Tech IN: cards the player uses that are NOT in the standard consensus
        tech_in = []
        for card, n_games in sorted(cards.items(), key=lambda x: -x[1]):
            if card not in std and n_games >= max(2, total_games * 0.3):
                pct = n_games / total_games * 100
                tech_in.append(f"{card} ({n_games}/{total_games}g, {pct:.0f}%)")

        # Tech OUT: standard cards the player NEVER or rarely uses
        tech_out = []
        for card, avg_qty in sorted(std.items(), key=lambda x: -x[1]):
            if avg_qty >= 2.0 and cards.get(card, 0) <= max(1, total_games * 0.2):
                used = cards.get(card, 0)
                tech_out.append(f"{card} (std {avg_qty:.0f}x, visto {used}/{total_games}g)")

        if not tech_in and not tech_out:
            continue

        lines.append(f"**{display}** ({deck}, {w}-{l}, {wr:.0f}%, MMR {mmr}):")
        if tech_in:
            lines.append(f"  - Tech IN: {', '.join(tech_in[:5])}")
        if tech_out:
            lines.append(f"  - Tech OUT: {', '.join(tech_out[:5])}")
        lines.append("")

    if not lines:
        return "_Nessuna variazione significativa dalle liste standard._\n"

    return "\n".join(lines)


def format_emerging_decks(matches, stats_all, wins, total, days):
    """Identify emerging decks: low meta share but strong results from high-ELO players.
    Includes matchup WR table, estimated build from champion card usage, and LLM placeholder."""
    # Total games across all decks
    total_games_all = sum(s["games"] for s in stats_all.values())
    if total_games_all == 0:
        return "_Dati insufficienti._\n"

    # Find low-share archetypes (< 6% meta share)
    low_share_decks = set()
    for deck, s in stats_all.items():
        share = s["games"] / total_games_all * 100
        if share < 6.0:
            low_share_decks.add(deck)

    if not low_share_decks:
        return "_Nessun deck emergente rilevato._\n"

    # Build per-player stats for these decks
    player_stats = defaultdict(lambda: defaultdict(lambda: {"w": 0, "l": 0, "mmr": 0, "display": ""}))
    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            deck = m[f"{pkey}_deck"]
            if not deck or deck not in low_share_decks:
                continue
            name = m[f"{pkey}_name"].lower()
            if not name:
                continue
            s = player_stats[deck][name]
            s["display"] = m[f"{pkey}_name"]
            s["mmr"] = max(s["mmr"], m[f"{pkey}_mmr"])
            if m["winner"] == pnum:
                s["w"] += 1
            else:
                s["l"] += 1

    # Extract cards played by champions
    champion_cards = extract_player_cards(days, "TOP")
    cards_set11 = extract_player_cards(days, "SET11", min_mmr=MIN_MMR_HIGH)
    for key, cards in cards_set11.items():
        if key in champion_cards:
            for c, n in cards.items():
                champion_cards[key][c] = max(champion_cards[key].get(c, 0), n)
        else:
            champion_cards[key] = dict(cards)

    # Load consensus for comparison
    consensus = load_snapshot_consensus()

    # Top decks for matchup columns
    deck_vol = defaultdict(int)
    for d1 in total:
        for d2 in total[d1]:
            deck_vol[d1] += total[d1][d2]
    top_decks = sorted(deck_vol.keys(), key=lambda d: -deck_vol[d])[:8]

    # Per deck: find "champion" players (≥4 games, ≥58% WR, MMR ≥1400)
    emerging = []
    for deck in sorted(low_share_decks):
        ds = stats_all.get(deck)
        if not ds or ds["games"] < 10:
            continue
        share = ds["games"] / total_games_all * 100

        champions = []
        for name, s in player_stats[deck].items():
            t = s["w"] + s["l"]
            if t < 4:
                continue
            wr = s["w"] / t * 100
            if wr >= 58 and s["mmr"] >= 1400:
                champions.append({
                    "name": s["display"], "name_lower": name,
                    "w": s["w"], "l": s["l"],
                    "wr": wr, "mmr": s["mmr"],
                })

        if not champions:
            continue

        champions.sort(key=lambda x: (-x["wr"], -x["mmr"]))
        emerging.append({
            "deck": deck, "share": share,
            "games": ds["games"], "wr": ds["wr"],
            "champions": champions[:5],
        })

    if not emerging:
        return "_Nessun deck emergente con champion ad alto ELO._\n"

    # Sort by number of champions, then avg champion WR
    emerging.sort(key=lambda x: (-len(x["champions"]), -sum(c["wr"] for c in x["champions"]) / len(x["champions"])))

    lines = []
    for e in emerging:
        deck = e["deck"]
        deck_wr_tag = f"**{e['wr']:.0f}%**" if e["wr"] >= 52 else f"{e['wr']:.1f}%"
        lines.append(f"### {deck} — {e['share']:.1f}% share, {e['games']}g, WR {deck_wr_tag}\n")

        # --- Champion table ---
        lines.append("**Champion:**\n")
        lines.append("| Player | W-L | WR | MMR |")
        lines.append("|---|---|---|---|")
        for c in e["champions"]:
            is_pro = is_notable(c["name_lower"])
            tag = " **PRO**" if is_pro else ""
            lines.append(f"| {c['name']}{tag} | {c['w']}-{c['l']} | {c['wr']:.0f}% | {c['mmr']} |")
        lines.append("")

        # --- Matchup WR table ---
        if deck in total:
            mu_decks = [d for d in top_decks if d != deck and total[deck].get(d, 0) >= 3]
            if mu_decks:
                lines.append("**Matchup WR:**\n")
                header = "| vs | WR | W/T |"
                lines.append(header)
                lines.append("|---|---|---|")
                mu_rows = []
                for opp in mu_decks:
                    t = total[deck][opp]
                    w = wins[deck][opp]
                    wr = w / t * 100
                    mu_rows.append((opp, wr, w, t))
                mu_rows.sort(key=lambda x: -x[1])
                for opp, wr, w, t in mu_rows:
                    wr_str = f"**{wr:.0f}%**" if wr >= 60 else f"_{wr:.0f}%_" if wr <= 40 else f"{wr:.0f}%"
                    lines.append(f"| {opp} | {wr_str} | {w}/{t} |")
                lines.append("")

        # --- Estimated build from champion card usage ---
        champ_names = [c["name_lower"] for c in e["champions"]]
        all_cards_deck = defaultdict(lambda: {"games": 0, "players": 0})
        total_champ_games = 0
        for cname in champ_names:
            key = (cname, deck)
            if key not in champion_cards:
                continue
            ps = player_stats[deck][cname]
            pg = ps["w"] + ps["l"]
            total_champ_games = max(total_champ_games, pg)
            for card, n in champion_cards[key].items():
                all_cards_deck[card]["games"] += n
                all_cards_deck[card]["players"] += 1

        if all_cards_deck:
            # Cards seen by ≥2 champions OR in ≥50% of games of a single champion with ≥5 games
            core_cards = []
            for card, info in all_cards_deck.items():
                if info["players"] >= 2 or info["games"] >= 3:
                    core_cards.append((card, info["games"], info["players"]))
            core_cards.sort(key=lambda x: (-x[2], -x[1]))

            if core_cards:
                lines.append("**Build stimata (carte comuni tra i champion):**\n")
                lines.append("| Carta | Visto in | Champion |")
                lines.append("|---|---|---|")
                # Mark which are standard vs tech
                std_set = consensus.get(deck, {})
                for card, games, players in core_cards[:20]:
                    tag = "" if card in std_set else " ⚡"
                    lines.append(f"| {card}{tag} | {games}g | {players}/{len(champ_names)} |")
                lines.append("")
                lines.append("_⚡ = carta non presente nelle liste standard torneo_\n")

        # --- Placeholder for LLM commentary ---
        lines.append(f"<!-- EMERGING_{deck}_COMMENT -->\n")

    return "\n".join(lines)


DASHBOARD_JSON = DAILY_DIR / "output" / "dashboard_data.json"


def _build_otp_otd_data(matches):
    """Build OTP/OTD stats dict: {d1: {d2: {otp_w, otp_t, otd_w, otd_t}}}."""
    stats = defaultdict(lambda: defaultdict(lambda: {"otp_w": 0, "otp_t": 0, "otd_w": 0, "otd_t": 0}))
    for m in matches:
        d1, d2 = m["p1_deck"], m["p2_deck"]
        otp = m.get("otp")
        if not d1 or not d2 or not otp:
            continue
        w = m["winner"]
        if otp == 1:
            stats[d1][d2]["otp_t"] += 1
            stats[d2][d1]["otd_t"] += 1
            if w == 1:
                stats[d1][d2]["otp_w"] += 1
            else:
                stats[d2][d1]["otd_w"] += 1
        else:
            stats[d1][d2]["otd_t"] += 1
            stats[d2][d1]["otp_t"] += 1
            if w == 1:
                stats[d1][d2]["otd_w"] += 1
            else:
                stats[d2][d1]["otp_w"] += 1
    # Convert defaultdicts to regular dicts for JSON
    return {d1: {d2: dict(v) for d2, v in d2s.items()} for d1, d2s in stats.items()}


def _build_top_players_data(matches, min_games=4, per_deck_limit=8, mmr_ref=None, skip_mmr_filter=False):
    """Build top players list PER DECK with matchup breakdown.

    Ranking score: Wilson lower-bound WR (adjusts for sample size)
      + BO3 bonus (10% of score for players with BO3 games)
      + upset bonus (wins vs unfavorable matchups count more)

    Args:
        mmr_ref: {name_lower: [mmr1, mmr2, ...]} from leaderboard — filters name collisions
        skip_mmr_filter: if True, skip MMR collision filter (for pre-verified TOP/PRO matches)
    """
    import math
    MMR_TOL = 200
    # Build stats per (player, deck) — not just per player
    stats = defaultdict(lambda: {
        "display": "", "wins": 0, "losses": 0, "mmr": 0,
        "bo3_games": 0,
        "vs": defaultdict(lambda: {"w": 0, "l": 0})
    })
    for m in matches:
        is_bo3 = "BO3" in m.get("queue", "").upper()
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            deck = m[f"{pkey}_deck"]
            mmr = m[f"{pkey}_mmr"]
            if not name or not deck:
                continue
            # Filter name collisions via leaderboard MMR.
            # Skip filter for matches already in TOP/PRO folders (pre-verified by monitor).
            # BO1 and BO3 have separate ratings (can differ by 600+).
            if mmr_ref and name in mmr_ref and mmr and not skip_mmr_filter:
                best_diff = min(abs(mmr - m) for m in mmr_ref[name])
                if best_diff > MMR_TOL:
                    continue
            opp_key = "p2" if pkey == "p1" else "p1"
            opp_deck = m[f"{opp_key}_deck"]
            key = (name, deck)
            s = stats[key]
            s["display"] = m[f"{pkey}_name"]
            s["mmr"] = max(s["mmr"], mmr)
            if is_bo3:
                s["bo3_games"] += 1
            if m["winner"] == pnum:
                s["wins"] += 1
                if opp_deck:
                    s["vs"][opp_deck]["w"] += 1
            else:
                s["losses"] += 1
                if opp_deck:
                    s["vs"][opp_deck]["l"] += 1

    # Pre-compute meta matchup WR for upset bonus: deck vs opp → wr%
    # Uses aggregate from all matches in this batch
    meta_mu = defaultdict(lambda: {"w": 0, "l": 0})
    for m in matches:
        d1, d2 = m.get("p1_deck"), m.get("p2_deck")
        if d1 and d2:
            if m["winner"] == 1:
                meta_mu[(d1, d2)]["w"] += 1
                meta_mu[(d2, d1)]["l"] += 1
            else:
                meta_mu[(d1, d2)]["l"] += 1
                meta_mu[(d2, d1)]["w"] += 1
    meta_wr = {}
    for (d, o), r in meta_mu.items():
        t = r["w"] + r["l"]
        if t >= 10:
            meta_wr[(d, o)] = r["w"] / t * 100

    def wilson_lower(w, n, z=1.5):
        """Wilson score lower bound — conservative WR estimate."""
        if n == 0:
            return 0
        p = w / n
        return (p + z*z/(2*n) - z * math.sqrt((p*(1-p) + z*z/(4*n)) / n)) / (1 + z*z/n) * 100

    def upset_bonus(vs_dict, deck):
        """Bonus for winning unfavorable matchups (meta WR < 45%)."""
        bonus_wins = 0
        total_wins = 0
        for opp, r in vs_dict.items():
            total_wins += r["w"]
            mu = meta_wr.get((deck, opp))
            if mu is not None and mu < 45 and r["w"] > 0:
                # More credit the harder the matchup
                difficulty = (45 - mu) / 45  # 0..1, higher = harder
                bonus_wins += r["w"] * difficulty
        if total_wins == 0:
            return 0
        return bonus_wins / total_wins  # fraction 0..~0.5

    # Group by deck, rank within each deck
    deck_players = defaultdict(list)
    for (name, deck), s in stats.items():
        total = s["wins"] + s["losses"]
        if total < min_games:
            continue
        wr = s["wins"] / total * 100
        w_score = wilson_lower(s["wins"], total)
        bo3_ratio = s["bo3_games"] / total if total else 0
        bo3_bonus = w_score * 0.10 * bo3_ratio  # up to 10% boost
        u_bonus = w_score * 0.08 * upset_bonus(s["vs"], deck)  # up to ~8% boost
        score = w_score + bo3_bonus + u_bonus
        is_pro = is_notable(name)
        matchups = {}
        for opp, r in sorted(s["vs"].items(), key=lambda x: -(x[1]["w"] + x[1]["l"])):
            matchups[opp] = {"w": r["w"], "l": r["l"]}
        deck_players[deck].append({
            "name": s["display"], "w": s["wins"], "l": s["losses"],
            "wr": round(wr, 1), "mmr": s["mmr"], "deck": deck,
            "is_pro": is_pro, "matchups": matchups,
            "score": round(score, 1), "bo3": s["bo3_games"],
        })

    # Sort by score; show at least 5 per deck (relax min_games if needed)
    result = []
    for deck, players in deck_players.items():
        players.sort(key=lambda x: (-x["score"], -x["mmr"]))
        selected = players[:per_deck_limit]
        # If fewer than 5, try adding players with fewer games (min 1)
        if len(selected) < 5:
            extras = []
            seen = {p["name"].lower() for p in selected}
            for (pname, pdeck), s in stats.items():
                if pdeck != deck or pname in seen:
                    continue
                total = s["wins"] + s["losses"]
                if total < 1 or total >= min_games:
                    continue
                wr = s["wins"] / total * 100
                w_score = wilson_lower(s["wins"], total)
                is_pro = is_notable(pname)
                mu = {}
                for opp, r in sorted(s["vs"].items(), key=lambda x: -(x[1]["w"] + x[1]["l"])):
                    mu[opp] = {"w": r["w"], "l": r["l"]}
                extras.append({
                    "name": s["display"], "w": s["wins"], "l": s["losses"],
                    "wr": round(wr, 1), "mmr": s["mmr"], "deck": deck,
                    "is_pro": is_pro, "matchups": mu,
                    "score": round(w_score, 1), "bo3": s.get("bo3_games", 0),
                })
            extras.sort(key=lambda x: (-x["score"], -x["mmr"]))
            selected.extend(extras[:5 - len(selected)])
        result.extend(selected)
    return result


def _build_tech_choices_data(matches, days):
    """Build tech choices data as list of dicts."""
    consensus = load_snapshot_consensus()
    if not consensus:
        return []
    cards_top = extract_player_cards(days, "TOP")
    cards_set11 = extract_player_cards(days, "SET11", min_mmr=MIN_MMR_HIGH)
    all_cards = {}
    for key, cards in {**cards_set11, **cards_top}.items():
        if key in all_cards:
            for c, n in cards.items():
                all_cards[key][c] = max(all_cards[key].get(c, 0), n)
        else:
            all_cards[key] = dict(cards)

    player_stats = defaultdict(lambda: {"w": 0, "l": 0, "mmr": 0, "display": ""})
    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            deck = m[f"{pkey}_deck"]
            if not name or not deck:
                continue
            key = (name, deck)
            s = player_stats[key]
            s["display"] = m[f"{pkey}_name"]
            s["mmr"] = max(s["mmr"], m[f"{pkey}_mmr"])
            if m["winner"] == pnum:
                s["w"] += 1
            else:
                s["l"] += 1

    interesting = []
    for (pname, deck), s in player_stats.items():
        total = s["w"] + s["l"]
        if total < 5:
            continue
        wr = s["w"] / total * 100
        if wr < 60 and s["mmr"] < 1700:
            continue
        if (pname, deck) not in all_cards:
            continue
        std = consensus.get(deck, {})
        if not std:
            continue
        cards = all_cards[(pname, deck)]
        tech_in = []
        for card, n_games in sorted(cards.items(), key=lambda x: -x[1]):
            if card not in std and n_games >= max(2, total * 0.3):
                tech_in.append({"card": card, "seen": n_games, "total": total})
        tech_out = []
        for card, avg_qty in sorted(std.items(), key=lambda x: -x[1]):
            if avg_qty >= 2.0 and cards.get(card, 0) <= max(1, total * 0.2):
                tech_out.append({"card": card, "std_qty": round(avg_qty, 1), "seen": cards.get(card, 0), "total": total})
        if tech_in or tech_out:
            interesting.append({
                "name": s["display"], "deck": deck,
                "w": s["w"], "l": s["l"], "wr": round(wr, 1), "mmr": s["mmr"],
                "tech_in": tech_in[:5], "tech_out": tech_out[:5],
            })
    interesting.sort(key=lambda x: (-x["wr"], -x["mmr"]))
    return interesting[:15]


def _build_trend_data(matches, days):
    """Build daily WR trend: {day_label: {deck: {w, l}}}."""
    day_stats = defaultdict(lambda: defaultdict(lambda: {"w": 0, "l": 0}))
    for m in matches:
        day = m["day"]
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            deck = m[f"{pkey}_deck"]
            if not deck:
                continue
            if m["winner"] == pnum:
                day_stats[day][deck]["w"] += 1
            else:
                day_stats[day][deck]["l"] += 1
    result = {}
    for day in reversed(days):
        label = f"{day[:2]}/{day[2:4]}"
        result[label] = {d: dict(v) for d, v in day_stats[day].items()}
    return result


def _build_meta_share_data(matches, days):
    """Build meta share: {deck: {share, games, daily: {day: share%}}}."""
    overall = defaultdict(int)
    day_counts = defaultdict(lambda: defaultdict(int))
    day_totals = defaultdict(int)
    for m in matches:
        day = m["day"]
        for pkey in ["p1", "p2"]:
            deck = m[f"{pkey}_deck"]
            if deck:
                overall[deck] += 1
                day_counts[day][deck] += 1
                day_totals[day] += 1
    total_all = sum(overall.values())
    result = {}
    for deck in sorted(overall.keys(), key=lambda d: -overall[d]):
        daily = {}
        for day in days:
            label = f"{day[:2]}/{day[2:4]}"
            if day_totals[day] > 0:
                daily[label] = round(day_counts[day][deck] / day_totals[day] * 100, 1)
            else:
                daily[label] = 0
        result[deck] = {
            "share": round(overall[deck] / total_all * 100, 1) if total_all else 0,
            "games": overall[deck],
            "daily": daily,
        }
    return result


def _build_pro_detail_data(all_matches, mmr_ref=None):
    """Build PRO player detail data."""
    MMR_TOL = 200
    pro_matches = defaultdict(list)
    for m in all_matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            if is_notable(name):
                # Filter name collisions via leaderboard MMR
                mmr = m[f"{pkey}_mmr"]
                if mmr_ref and name in mmr_ref and mmr:
                    if min(abs(mmr - m) for m in mmr_ref[name]) > MMR_TOL:
                        continue
                pro_matches[name].append((m, pnum, pkey))
    result = []
    for pro_name in sorted(pro_matches.keys()):
        ml = pro_matches[pro_name]
        display = ml[0][0][f"{ml[0][2]}_name"]
        wins = sum(1 for m, pnum, _ in ml if m["winner"] == pnum)
        losses = len(ml) - wins
        wr = wins / len(ml) * 100
        deck_r = defaultdict(lambda: {"w": 0, "l": 0})
        mu_r = defaultdict(lambda: {"w": 0, "l": 0})
        for m, pnum, pkey in ml:
            deck = m[f"{pkey}_deck"] or "?"
            opp_key = "p2" if pkey == "p1" else "p1"
            opp_deck = m[f"{opp_key}_deck"] or "?"
            if m["winner"] == pnum:
                deck_r[deck]["w"] += 1
                mu_r[opp_deck]["w"] += 1
            else:
                deck_r[deck]["l"] += 1
                mu_r[opp_deck]["l"] += 1
        result.append({
            "name": display, "w": wins, "l": losses, "wr": round(wr, 1),
            "decks": {d: dict(v) for d, v in deck_r.items()},
            "matchups": {d: dict(v) for d, v in mu_r.items()},
        })
    return result


def _matrix_to_dict(wins, total):
    """Convert matrix defaultdicts to serializable dict."""
    result = {}
    for d1 in total:
        result[d1] = {}
        for d2 in total[d1]:
            result[d1][d2] = {"w": wins[d1][d2], "t": total[d1][d2]}
    return result


def _duelsink_to_dict(data):
    """Extract relevant duels.ink data."""
    if not data:
        return None
    activity = data.get("activity", {})
    color_pairs = data.get("colorPairs", [])
    matchups_raw = data.get("matchups", [])
    play_draw = activity.get("playDrawStats") or {}
    # Values from duels.ink are already percentages (e.g. 56.8, not 0.568)
    wr = {}
    for cp in color_pairs:
        if len(cp.get("colors", [])) < 2:
            continue
        short = _ink_short(cp.get("colors", []))
        if "/" in short:
            continue
        wr[short] = {
            "games": cp.get("games", 0),
            "wr": round(cp.get("winRate", 0), 1),
            "play_rate": round(cp.get("playRate", 0), 1),
            "otp_wr": round(cp.get("firstPlayerWinRate", 0), 1),
        }
    matrix = {}
    for mu in matchups_raw:
        a = _ink_short(mu.get("colorsA", []))
        b = _ink_short(mu.get("colorsB", []))
        if "/" in a or "/" in b:
            continue
        if a not in matrix:
            matrix[a] = {}
        matrix[a][b] = {
            "wr": round(mu.get("winRate", 0), 1),
            "games": mu.get("games", 0),
        }
    return {
        "total_games": activity.get("totalGames", 0),
        "players": activity.get("uniquePlayers", 0),
        "otp_wr": round(play_draw.get("first", play_draw.get("firstPlayerWinRate", 0)) or 0, 1),
        "period": data.get("meta", {}).get("period", ""),
        "wr": wr,
        "matrix": matrix,
    }


def _build_elo_distribution(matches):
    """Build MMR histogram per deck. Bins: 1300-1400, 1400-1500, ..., 1800+."""
    bins = [1300, 1400, 1500, 1600, 1700, 1800, 2000]
    bin_labels = ["1300-1399", "1400-1499", "1500-1599", "1600-1699", "1700-1799", "1800+"]
    deck_mmrs = defaultdict(list)
    for m in matches:
        for pkey in ["p1", "p2"]:
            deck = m[f"{pkey}_deck"]
            mmr = m[f"{pkey}_mmr"]
            if deck and mmr:
                deck_mmrs[deck].append(mmr)
    result = {}
    for deck, mmrs in deck_mmrs.items():
        hist = [0] * len(bin_labels)
        for mmr in mmrs:
            for i in range(len(bins) - 1):
                if bins[i] <= mmr < bins[i + 1]:
                    hist[i] += 1
                    break
            else:
                if mmr >= bins[-1]:
                    hist[-1] += 1
        result[deck] = {"bins": bin_labels, "counts": hist, "avg": round(sum(mmrs) / len(mmrs)) if mmrs else 0}
    return result


def _build_matchup_trend():
    """Build per-day matchup WR over last 5 days for SET11, TOP and PRO."""
    days_5 = get_last_n_days(5)
    result = {}

    for perim, subfolder, min_mmr in [("set11", "SET11", MIN_MMR_HIGH), ("top", "TOP", 0), ("pro", "PRO", 0), ("infinity", "INF", 0)]:
        daily_matrix = {}  # day_label -> {deck -> {opp -> {w, t}}}

        for day in days_5:
            label = f"{day[:2]}/{day[2:4]}"
            matches = load_matches([day], subfolder, min_mmr=min_mmr)

            if not matches:
                continue

            mu = defaultdict(lambda: defaultdict(lambda: {"w": 0, "t": 0}))
            for m in matches:
                d1, d2 = m["p1_deck"], m["p2_deck"]
                if not d1 or not d2:
                    continue
                mu[d1][d2]["t"] += 1
                mu[d2][d1]["t"] += 1
                if m["winner"] == 1:
                    mu[d1][d2]["w"] += 1
                else:
                    mu[d2][d1]["w"] += 1

            daily_matrix[label] = {
                d1: {d2: dict(v) for d2, v in d2s.items()}
                for d1, d2s in mu.items()
            }

        if not daily_matrix:
            continue

        # Build trend: for each deck, for each opponent, WR per day + delta
        day_labels = [f"{d[:2]}/{d[2:4]}" for d in reversed(days_5)]  # chronological
        all_decks = set()
        for dm in daily_matrix.values():
            all_decks.update(dm.keys())

        perim_data = {}
        for deck in all_decks:
            opps = set()
            for dm in daily_matrix.values():
                if deck in dm:
                    opps.update(dm[deck].keys())

            deck_trend = {}
            for opp in opps:
                daily_wr = []
                recent_w, recent_t = 0, 0  # last 2 days
                older_w, older_t = 0, 0    # days 3-5
                for i, dl in enumerate(day_labels):
                    s = daily_matrix.get(dl, {}).get(deck, {}).get(opp, {"w": 0, "t": 0})
                    wr = round(s["w"] / s["t"] * 100, 1) if s["t"] >= 3 else None
                    daily_wr.append({"day": dl, "wr": wr, "w": s["w"], "t": s["t"]})
                    if i >= len(day_labels) - 2:  # last 2
                        recent_w += s["w"]
                        recent_t += s["t"]
                    else:
                        older_w += s["w"]
                        older_t += s["t"]

                recent_wr = round(recent_w / recent_t * 100, 1) if recent_t >= 3 else None
                older_wr = round(older_w / older_t * 100, 1) if older_t >= 3 else None
                delta = round(recent_wr - older_wr, 1) if recent_wr is not None and older_wr is not None else None

                if recent_t >= 3:
                    deck_trend[opp] = {
                        "current_wr": recent_wr,
                        "prev_wr": older_wr,
                        "delta": delta,
                        "recent_games": recent_t,
                        "daily": daily_wr,
                    }

            if deck_trend:
                perim_data[deck] = deck_trend

        result[perim] = perim_data

    return result


def _build_tech_tornado_data(matches, days, consensus, perim_label):
    """Build tech tornado data per deck for a specific perimeter.
    Returns {deck: {total_players, items: [{card, adoption, avg_wr, players, type}]}}"""
    if not consensus:
        return {}

    # Player stats from this perimeter's matches
    player_stats = defaultdict(lambda: {"w": 0, "l": 0, "mmr": 0})
    for m in matches:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            name = m[f"{pkey}_name"].lower()
            deck = m[f"{pkey}_deck"]
            if not name or not deck:
                continue
            s = player_stats[(name, deck)]
            s["mmr"] = max(s["mmr"], m[f"{pkey}_mmr"])
            if m["winner"] == pnum:
                s["w"] += 1
            else:
                s["l"] += 1

    # Card usage from appropriate subfolders
    if perim_label == "SET11":
        all_cards = extract_player_cards(days, "SET11", min_mmr=MIN_MMR_HIGH)
    elif perim_label == "TOP":
        all_cards = extract_player_cards(days, "TOP")
    elif perim_label == "PRO":
        all_cards = extract_player_cards(days, "PRO")
    else:
        cards_pro = extract_player_cards(days, "PRO")
        cards_top = extract_player_cards(days, "TOP")
        all_cards = {}
        for key, cards in {**cards_pro, **cards_top}.items():
            if key in all_cards:
                for c, n in cards.items():
                    all_cards[key][c] = max(all_cards[key].get(c, 0), n)
            else:
                all_cards[key] = dict(cards)

    result = {}
    min_games = 5 if perim_label == "SET11" else (3 if perim_label == "PRO" else 4)
    for deck, std in consensus.items():
        qualifying = []
        for (pname, pdeck), s in player_stats.items():
            if pdeck != deck:
                continue
            total = s["w"] + s["l"]
            if total < min_games:
                continue
            wr = s["w"] / total * 100
            qualifying.append((pname, pdeck, wr, total))
        if len(qualifying) < 3:
            continue

        n_q = len(qualifying)
        items = []

        # IN: non-standard cards used by qualifying players
        card_in = defaultdict(lambda: {"players": 0, "wr_sum": 0})
        for pname, pdeck, wr, total in qualifying:
            pcards = all_cards.get((pname, pdeck), {})
            for card, n_seen in pcards.items():
                if card not in std and n_seen >= max(2, total * 0.3):
                    card_in[card]["players"] += 1
                    card_in[card]["wr_sum"] += wr

        for card, cd in card_in.items():
            if cd["players"] >= 2:
                items.append({
                    "card": card, "players": cd["players"],
                    "adoption": round(cd["players"] / n_q * 100, 1),
                    "avg_wr": round(cd["wr_sum"] / cd["players"], 1),
                    "type": "in",
                })

        # OUT: standard cards dropped by qualifying players
        for card, avg_qty in std.items():
            if avg_qty < 2.0:
                continue
            droppers = 0
            wr_sum = 0
            for pname, pdeck, wr, total in qualifying:
                pcards = all_cards.get((pname, pdeck), {})
                if pcards.get(card, 0) <= max(1, total * 0.2):
                    droppers += 1
                    wr_sum += wr
            if droppers >= 2:
                items.append({
                    "card": card, "players": droppers,
                    "adoption": round(droppers / n_q * 100, 1),
                    "avg_wr": round(wr_sum / droppers, 1),
                    "type": "out",
                })

        # Sort: IN by adoption desc, OUT by adoption desc
        items.sort(key=lambda x: (-1 if x["type"] == "in" else 1, -x["adoption"]))
        if items:
            result[deck] = {"total_players": n_q, "items": items[:15]}

    return result


def _build_reference_decklists():
    """Load best tournament decklist per archetype from inkdecks snapshots."""
    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    if not snapshots:
        return {}
    with open(snapshots[-1]) as f:
        data = json.load(f)
    result = {}
    for arch, decks in data.get("archetypes", {}).items():
        if not decks:
            continue
        # Pick the best deck: highest relevance, then best record
        best = decks[0]
        result[arch] = {
            "player": best.get("player", "?"),
            "rank": best.get("rank", "?"),
            "event": best.get("event", "?"),
            "date": best.get("date", "?"),
            "record": best.get("record", "?"),
            "cards": [{"qty": c["qty"], "name": c["name"]} for c in best.get("cards", [])],
        }
    # Translate legacy deck names
    _LEGACY_NAMES = {"AS": "AmSa", "ES": "EmSa"}
    for old, new in _LEGACY_NAMES.items():
        if old in result and new not in result:
            result[new] = result.pop(old)
    return result


def _build_player_cards_data(days, mmr_ref=None):
    """Build per-player card usage for all dashboard players (core + infinity)."""
    cards_top = extract_player_cards(days, "TOP", mmr_ref=mmr_ref)
    cards_pro = extract_player_cards(days, "PRO", mmr_ref=mmr_ref)
    cards_set11 = extract_player_cards(days, "SET11", min_mmr=MIN_MMR_HIGH, mmr_ref=mmr_ref)
    cards_inf = extract_player_cards(days, "INF", mmr_ref=mmr_ref)
    cards_friends = extract_player_cards(days, "FRIENDS", mmr_ref=mmr_ref)
    merged = {}
    for source in [cards_set11, cards_top, cards_pro, cards_inf, cards_friends]:
        for key, cards in source.items():
            if key in merged:
                for c, n in cards.items():
                    merged[key][c] = max(merged[key].get(c, 0), n)
            else:
                merged[key] = dict(cards)
    # Convert to serializable: {player_lower: {deck: {card: n_games_seen}}}
    # Keep players with >=2 observed games (we don't capture all games, only live-observed)
    result = defaultdict(dict)
    for (pname, deck), cards in merged.items():
        n_games = max(cards.values()) if cards else 0
        if n_games >= 2:
            result[pname][deck] = dict(cards)
    return dict(result)


# ─── Matchup Analyzer Data Loader ─────────────────────────────────────────────

import re as _re

def _parse_report_overview(md_text):
    """Extract overview data from report section 1 (Panoramica)."""
    data = {}
    # WR table: | **AmAm WR** | **40%** (42W-63L) |
    m = _re.search(r'\*\*\w+ WR\*\*\s*\|\s*\*\*(\d+)%\*\*\s*\((\d+)W-(\d+)L\)', md_text)
    if m:
        data['wr'] = int(m.group(1))
        data['wins'] = int(m.group(2))
        data['losses'] = int(m.group(3))
    # OTP WR
    m = _re.search(r'WR OTP\s*\|\s*(\d+)%\s*\((\d+)W-(\d+)L,\s*(\d+)g\)', md_text)
    if m:
        data['otp_wr'] = int(m.group(1))
        data['otp_games'] = int(m.group(4))
    # OTD WR
    m = _re.search(r'WR OTD\s*\|\s*(\d+)%\s*\((\d+)W-(\d+)L,\s*(\d+)g\)', md_text)
    if m:
        data['otd_wr'] = int(m.group(1))
        data['otd_games'] = int(m.group(4))
    # Gap
    m = _re.search(r'Gap OTP/OTD\s*\|\s*(\d+)pp', md_text)
    if m:
        data['gap'] = int(m.group(1))
    # Lore progression table
    lore = []
    for m in _re.finditer(r'\|\s*T(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|', md_text):
        turn = int(m.group(1))
        our = float(m.group(2))
        opp = float(m.group(3))
        lore.append({"t": turn, "our": our, "opp": opp})
    if lore:
        data['lore_progression'] = lore
    return data


def _parse_report_winning_hands(md_text):
    """Extract winning hands data from report section 3."""
    data = {}
    # Find section 3
    sec3 = _re.search(r'## 3\. Mani Vincenti.*?(?=\n## [0-9]|\n---\n## |\Z)', md_text, _re.DOTALL)
    if not sec3:
        return data
    sec = sec3.group(0)
    # Frequenza Carte
    cards = []
    freq_section = _re.search(r'### Frequenza Carte.*?\n((?:\|.*\n)+)', sec)
    if freq_section:
        for row in _re.finditer(r'\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)%\s*\|', freq_section.group(1)):
            name = row.group(1).strip()
            if name and name != 'Carta':
                cards.append({"name": name, "freq": int(row.group(2)), "pct": int(row.group(3))})
    data['cards'] = cards[:15]
    # Sweet spot
    sweet = {}
    sweet_section = _re.search(r'### Sweet Spot.*?\n((?:\|.*\n)+)', sec)
    if sweet_section:
        for row in _re.finditer(r'\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)%', sweet_section.group(1)):
            sweet[f"mull_{row.group(1)}"] = int(row.group(3))
    data['sweet_spot'] = sweet
    # Coppie vincenti
    pairs = []
    pairs_section = _re.search(r'### Coppie Vincenti.*?\n((?:\|.*\n)+)', sec)
    if pairs_section:
        for row in _re.finditer(r'\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)%\s*\|', pairs_section.group(1)):
            name = row.group(1).strip()
            if name and name != 'Coppia':
                pairs.append({"pair": name, "freq": int(row.group(2)), "pct": int(row.group(3))})
    data['winning_pairs'] = pairs[:10]
    return data


def _parse_report_decklist(md_text):
    """Extract decklist data from report section 6."""
    data = {}
    sec6 = _re.search(r'## 6\. Decklist Ottimizzata.*?(?=\n## [0-9]|\Z)', md_text, _re.DOTALL)
    if not sec6:
        return data
    sec = sec6.group(0)
    # Base
    m = _re.search(r'### Base:\s*(.+)', sec)
    if m:
        data['base_source'] = m.group(1).strip()
    # Cuts
    cuts = []
    for m in _re.finditer(r'-(\d+)x\s*\*\*([^*]+)\*\*\s*\(c(\d+)\)\s*.*?score MU:\s*([-+]?\d+\.?\d*)', sec):
        cuts.append({"qty": int(m.group(1)), "card": m.group(2).strip(),
                      "cost": int(m.group(3)), "score": float(m.group(4))})
    data['cuts'] = cuts
    # Adds
    adds = []
    for m in _re.finditer(r'\+(\d+)x\s*\*\*([^*]+)\*\*\s*\(c(\d+)\)\s*.*?score MU:\s*([-+]?\d+\.?\d*)', sec):
        adds.append({"qty": int(m.group(1)), "card": m.group(2).strip(),
                      "cost": int(m.group(3)), "score": float(m.group(4))})
    data['adds'] = adds
    # Full decklist table
    full_list = []
    # Match table rows with 4+ columns: | Qty (change) | Carta | Costo | Score | (optional notes) |
    # Qty formats: "4", "4 ↓-2", "2 (da -2)", "4 (+4)"
    # Score formats: "+0.37", "-0.09", "—", "--"
    # Skip mana curve rows (contain █ or only 2-3 columns)
    for m in _re.finditer(r'\|\s*(\d+)\s*(?:[↓↑]?[-+]?\d+|\([^)]*\))?\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([-+]?\d+\.?\d*|—|--)\s*\|', sec):
        card_name = m.group(2).strip()
        if '█' in card_name or not card_name or card_name in ('Carta', 'Card'):
            continue
        score_str = m.group(4)
        score = 0.0 if score_str in ('—', '--') else float(score_str)
        full_list.append({"qty": int(m.group(1)), "card": card_name,
                          "cost": int(m.group(3)), "score": score})
    # If table parse is incomplete, rebuild from import text
    table_total = sum(c['qty'] for c in full_list)
    if table_total < 60:
        imp = _re.search(r'### Import.*?```\n(.*?)```', sec, _re.DOTALL)
        if imp:
            imp_list = []
            for line in imp.group(1).strip().split('\n'):
                line = line.strip()
                im = _re.match(r'(\d+)\s+(.+?)(?:\s*\(\d+-\d+\))?$', line)
                if im:
                    imp_list.append({"qty": int(im.group(1)), "card": im.group(2).strip(),
                                     "cost": 0, "score": 0.0})
            imp_total = sum(c['qty'] for c in imp_list)
            if imp_total >= table_total:
                full_list = imp_list
    data['full_list'] = full_list
    # Mana curve
    mana = {}
    for m in _re.finditer(r'\|\s*(\d+)\s*\|\s*█+\s*(\d+)\s*\|', sec):
        mana[m.group(1)] = int(m.group(2))
    data['mana_curve'] = mana
    # Import text
    imp = _re.search(r'### Import.*?```\n(.*?)```', sec, _re.DOTALL)
    if imp:
        data['import_text'] = imp.group(1).strip()
    return data


def _parse_playbook(md_text):
    """Extract Playbook Avversario T1-T7 from report."""
    turns = []
    # Find playbook section (either "## Playbook Avversario" or inline T1-T7 headers)
    playbook_start = _re.search(r'## Playbook Avversario.*?\n', md_text)
    if not playbook_start:
        return turns
    section = md_text[playbook_start.end():]
    # Cut at next major section
    next_sec = _re.search(r'\n## (?:Ability|3\.|4\.|5\.|6\.)', section)
    if next_sec:
        section = section[:next_sec.start()]

    # Parse each turn block: ### T1 -- Setup (attivo in 65% delle partite)
    for turn_match in _re.finditer(r'### (T\d+)\s*--\s*(.+?)(?:\(attivo in (\d+)%.*?\))?\s*\n(.*?)(?=\n### T\d+|\n---|\Z)', section, _re.DOTALL):
        turn_num = turn_match.group(1)
        turn_label = turn_match.group(2).strip()
        activity_pct = int(turn_match.group(3)) if turn_match.group(3) else None
        block = turn_match.group(4)

        # Parse plays table
        plays = []
        for row in _re.finditer(r'\|\s*([^|]+?)\s*\[cost:(\d+).*?\]\s*\|\s*(\d+)\s*\((\d+)%\)\s*\|\s*(.+?)\s*\|', block):
            plays.append({
                "card": row.group(1).strip(), "cost": int(row.group(2)),
                "freq": int(row.group(3)), "pct": int(row.group(4)),
                "effect": row.group(5).strip()
            })
        # Also catch non-character plays (songs, items without stats)
        for row in _re.finditer(r'\|\s*([^|]+?)\s*\[cost:(\d+)\]\s*\|\s*(\d+)\s*\((\d+)%\)\s*\|\s*(.+?)\s*\|', block):
            card_name = row.group(1).strip()
            if not any(p['card'] == card_name for p in plays):
                plays.append({
                    "card": card_name, "cost": int(row.group(2)),
                    "freq": int(row.group(3)), "pct": int(row.group(4)),
                    "effect": row.group(5).strip()
                })

        # Parse combos
        combos = []
        for combo in _re.finditer(r'\*\*(.+?)\*\*\s*\((\d+)x\)\s*--\s*(.+)', block):
            combos.append({"cards": combo.group(1), "freq": int(combo.group(2)), "effect": combo.group(3).strip()})

        # Parse impact
        impact = {}
        killed_m = _re.search(r'pezzi uccisi:\s*([\d.]+)/partita\s*--\s*top:\s*(.+)', block)
        if killed_m:
            impact['killed_per_game'] = float(killed_m.group(1))
            impact['killed_top'] = killed_m.group(2).strip()
        bounced_m = _re.search(r'pezzi bounced:\s*([\d.]+)/partita', block)
        if bounced_m:
            impact['bounced_per_game'] = float(bounced_m.group(1))
        lore_m = _re.search(r'Lore media questata:\s*([\d.]+)', block)
        if lore_m:
            impact['lore_quested'] = float(lore_m.group(1))

        turns.append({
            "turn": turn_num, "label": turn_label, "activity_pct": activity_pct,
            "plays": plays[:6], "combos": combos[:5], "impact": impact
        })
    return turns


def _parse_board_state(md_text):
    """Extract board state metrics at T6 and T7."""
    result = {}
    for turn in ['T6', 'T7']:
        sec = _re.search(rf'### A {turn}\s*\n(.*?)(?=\n### |\n---|\Z)', md_text, _re.DOTALL)
        if not sec:
            continue
        block = sec.group(1)
        data = {}
        # Parse metrics table
        for row in _re.finditer(r'\|\s*(.+?)\s*\|\s*([-\d.]+)\s*\|\s*([-\d.]+)\s*\|\s*([-+]?[\d.]+)?\s*\|', block):
            metric = row.group(1).strip()
            try:
                v_win, v_loss = float(row.group(2)), float(row.group(3))
            except (ValueError, TypeError):
                continue
            if 'Nostra lore' in metric: data['our_lore'] = {'win': v_win, 'loss': v_loss}
            elif 'Lore avversaria' in metric: data['opp_lore'] = {'win': v_win, 'loss': v_loss}
            elif 'Gap lore' in metric: data['lore_gap'] = {'win': v_win, 'loss': v_loss}
            elif 'pezzi morti' in metric and 'Nostri' in metric: data['our_dead'] = {'win': v_win, 'loss': v_loss}
            elif 'pezzi bounced' in metric and 'Nostri' in metric: data['our_bounced'] = {'win': v_win, 'loss': v_loss}
        # Parse gap distribution
        gaps = []
        for g in _re.finditer(r'Gap ≥([+-]?\d+):\s*W\s*(\d+)%\s*\|\s*L\s*(\d+)%', block):
            gaps.append({"threshold": int(g.group(1)), "win_pct": int(g.group(2)), "loss_pct": int(g.group(3))})
        data['gap_distribution'] = gaps
        result[turn] = data
    return result


def _parse_killer_responses(md_text):
    """Extract Curve Killer e Risposte (section 4b) with OTP/OTD plays."""
    patterns = []
    sec4b = _re.search(r'### 4b\. Curve Killer.*?(?=\n## [0-9]|\Z)', md_text, _re.DOTALL)
    if not sec4b:
        return patterns
    sec = sec4b.group(0)
    # Parse each pattern: #### #1 Lore burst (T7+) — 20 sconfitte (33%)
    for pat_m in _re.finditer(r'####\s*#(\d+)\s*(.+?)\s*—\s*(\d+)\s*sconfitte\s*\((\d+)%\)(.*?)(?=\n####|\Z)', sec, _re.DOTALL):
        pat = {
            "id": int(pat_m.group(1)), "name": pat_m.group(2).strip(),
            "losses": int(pat_m.group(3)), "pct": int(pat_m.group(4)),
        }
        block = pat_m.group(5)
        # Curva tipica
        curva_m = _re.search(r'\*\*Curva tipica.*?:\*\*\s*(.+)', block)
        if curva_m:
            pat['curve'] = curva_m.group(1).strip()
        # WR when opponent plays these
        wr_m = _re.search(r'\((\d+)W/(\d+)L\s*=\s*(\d+)%\s*WR\s*quando', block)
        if wr_m:
            pat['our_wr_vs_curve'] = int(wr_m.group(3))
        # OTP section
        otp_plays = []
        otp_m = _re.search(r'\*\*OTP\*\*.*?\n\|.*?\n\|.*?\n((?:\|.*?\n)*)', block)
        if otp_m:
            for row in _re.finditer(r'\|\s*(T\d+)\s*\|\s*\*\*(.+?)\*\*.*?\|\s*_(.+?)_.*?\|', otp_m.group(1)):
                otp_plays.append({"turn": row.group(1), "play": row.group(2).strip(), "trap": row.group(3).strip()})
        pat['otp'] = otp_plays
        # OTD section
        otd_plays = []
        otd_m = _re.search(r'\*\*OTD\*\*.*?\n\|.*?\n\|.*?\n((?:\|.*?\n)*)', block)
        if otd_m:
            for row in _re.finditer(r'\|\s*(T\d+)\s*\|\s*\*\*(.+?)\*\*.*?\|\s*_(.+?)_.*?\|', otd_m.group(1)):
                otd_plays.append({"turn": row.group(1), "play": row.group(2).strip(), "trap": row.group(3).strip()})
        pat['otd'] = otd_plays
        # Target prioritari
        targets_m = _re.search(r'\*\*Target prioritari:\*\*\s*(.+)', block)
        if targets_m:
            pat['targets'] = targets_m.group(1).strip()
        patterns.append(pat)
    return patterns[:5]


def _parse_ability_cards(md_text):
    """Extract ability cards (opponent's key cards with abilities)."""
    cards = []
    sec = _re.search(r'## Ability carte chiave.*?(?=\n---|\n## [0-9]|\Z)', md_text, _re.DOTALL)
    if not sec:
        return cards
    for m in _re.finditer(r'\*\*(.+?)\*\*\s*\[cost:(\d+).*?\]\s*--\s*in\s*(\d+)%\s*delle loss\s*\n\s*>\s*(.+)', sec.group(0)):
        cards.append({
            "card": m.group(1).strip(), "cost": int(m.group(2)),
            "loss_pct": int(m.group(3)), "ability": m.group(4).strip()[:150]
        })
    return cards[:12]


def _parse_threats_llm(md_text):
    """Parse Minacce Principali LLM section into structured data."""
    result = {"type_summary": "", "threats": [], "riepilogo": []}
    sec = _re.search(r'## Minacce Principali.*?(?=\n# Curve Killer|\n## [0-9]|\Z)', md_text, _re.DOTALL)
    if not sec:
        return result
    block = sec.group(0)
    # Type summary: **Tipo matchup: SVOLTA.** ...
    ts = _re.search(r'\*\*Tipo matchup:\s*(.+?)\.\*\*\s*(.*)', block)
    if ts:
        result['type_summary'] = f"{ts.group(1).strip()}. {ts.group(2).strip()}"
    # Parse each threat: ### Minaccia #1: Name (N/M loss, P%)
    for tm in _re.finditer(r'### Minaccia #(\d+):\s*(.+?)\s*\((\d+)/(\d+)\s*loss,\s*(\d+)%\)(.*?)(?=\n### Minaccia|\n### Riepilogo|\Z)', block, _re.DOTALL):
        threat = {
            "id": int(tm.group(1)),
            "name": tm.group(2).strip(),
            "losses": int(tm.group(3)),
            "total_losses": int(tm.group(4)),
            "pct": int(tm.group(5)),
            "sections": []
        }
        tbody = tm.group(6)
        # Turno critico line
        tc = _re.search(r'\*\*Turno critico:\s*(.+?)\*\*\s*\|\s*(.+)', tbody)
        if tc:
            threat['critical_turn'] = tc.group(1).strip()
            threat['description'] = tc.group(2).strip()
        # Parse sub-sections: **Prevenzione — ...:**, **Risposta — ...:**, **Mitigazione — ...:**
        for sub in _re.finditer(r'\*\*(Prevenzione|Risposta|Mitigazione)\s*—\s*(.+?)(?:\((\d+)\s*partite\))?\s*:\*\*(.*?)(?=\n\*\*(?:Prevenzione|Risposta|Mitigazione|Note)|\n---|\Z)', tbody, _re.DOTALL):
            sub_data = {
                "type": sub.group(1),
                "label": sub.group(2).strip(),
                "games": int(sub.group(3)) if sub.group(3) else None,
            }
            sub_body = sub.group(4)
            # Extract table rows as plans
            plans = []
            # Find table headers to get plan names (Piano A, Piano B, Piano C)
            header_m = _re.search(r'\|.*?Piano\s*A\s*.*?\|', sub_body)
            if header_m:
                # Parse table rows
                for row in _re.finditer(r'\|\s*(T[\d-]+(?:\s*alt)?)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)?\s*\|', sub_body):
                    plans.append({
                        "turn": row.group(1).strip(),
                        "opponent": row.group(2).strip(),
                        "plan_a": row.group(3).strip(),
                        "plan_b": row.group(4).strip(),
                        "plan_c": row.group(5).strip() if row.group(5) else "",
                    })
            sub_data['plans'] = plans
            threat['sections'].append(sub_data)
        # Notes
        notes = _re.search(r'\*\*Note:?\*\*\s*(.+?)(?=\n\*\*|\n---|\Z)', tbody, _re.DOTALL)
        if notes:
            threat['notes'] = notes.group(1).strip()
        # Mitigazione as text
        mit = _re.search(r'\*\*Mitigazione\s*—\s*(.+?):\*\*\s*\n(.+?)(?=\n---|\n\*\*|\Z)', tbody, _re.DOTALL)
        if mit and not any(s['type'] == 'Mitigazione' for s in threat['sections']):
            threat['mitigation'] = f"{mit.group(1).strip()}: {mit.group(2).strip()}"
        result['threats'].append(threat)
    # Riepilogo table
    riepilogo_m = _re.search(r'### Riepilogo\s*\n\|.*?\n\|.*?\n((?:\|.*\n)*)', block)
    if riepilogo_m:
        for row in _re.finditer(r'\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|', riepilogo_m.group(1)):
            result['riepilogo'].append({
                "threat": row.group(1).strip(),
                "turn": row.group(2).strip(),
                "plan_a": row.group(3).strip(),
                "plan_b": row.group(4).strip(),
                "plan_c": row.group(5).strip(),
            })
    return result


def _load_matchup_analyzer_data():
    """Load matchup analyzer data for embedding in dashboard JSON."""
    result = {"available_decks": [], "all_decks": ["AmAm", "AmSa", "EmSa", "AbS", "AbSt", "AbE", "AbR", "AmySt", "AmyE", "AmyR", "SSt", "RS"]}

    # Deck name mapping (short → long folder name) — ALL 12 decks
    deck_folders = {
        "AmAm": "Amber-Amethyst",
        "AmSa": "Amethyst-Sapphire",
        "EmSa": "Emerald-Sapphire",
        "AbS": "Amber-Sapphire",
        "AbSt": "Amber-Steel",
        "AbE": "Amber-Emerald",
        "AbR": "Amber-Ruby",
        "AmySt": "Amethyst-Steel",
        "AmyE": "Amethyst-Emerald",
        "AmyR": "Amethyst-Ruby",
        "SSt": "Sapphire-Steel",
        "RS": "Ruby-Sapphire",
    }
    # Opponent short→long mapping
    opp_map = {
        "AbE": "Amber-Emerald", "AbR": "Amber-Ruby", "AbS": "Amber-Sapphire",
        "AbSt": "Amber-Steel", "AmyE": "Amethyst-Emerald", "AmyR": "Amethyst-Ruby",
        "AmySt": "Amethyst-Steel", "AmSa": "Amethyst-Sapphire", "EmSa": "Emerald-Sapphire",
        "SSt": "Sapphire-Steel", "AmAm": "Amber-Amethyst", "ESt": "Emerald-Steel",
        "ER": "Emerald-Ruby", "RS": "Ruby-Sapphire",
    }
    long_to_short = {v: k for k, v in opp_map.items()}
    # Map new display names → file names (for files on disk that use old conventions)
    _FILE_NAME = {"AmSa": "AS", "EmSa": "ES"}

    for deck_short, deck_long in deck_folders.items():
        report_dir = ANALYZER_REPORTS / deck_long
        if not report_dir.exists():
            continue

        deck_data = {}
        matchups_found = []
        deck_file = _FILE_NAME.get(deck_short, deck_short)

        # Find all report files for this deck
        for report_file in sorted(report_dir.glob("vs_*.md")):
            opp_long = report_file.stem.replace("vs_", "")
            opp_short = long_to_short.get(opp_long, opp_long)
            opp_file = _FILE_NAME.get(opp_short, opp_short)
            mu_key = f"vs_{opp_short}"

            mu_data = {}
            md_text = report_file.read_text()

            # 1. Overview from report
            mu_data['overview'] = _parse_report_overview(md_text)

            # 2. Killer curves from JSON if available
            kc_file = ANALYZER_OUTPUT / f"killer_curves_{deck_file}_vs_{opp_file}.json"
            if kc_file.exists():
                try:
                    raw = kc_file.read_text()
                    # LLM-generated JSON may contain control chars — strip them
                    import re as _re
                    raw = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', raw)
                    kc = json.loads(raw)
                    mu_data['killer_curves'] = kc.get('curves', [])
                except Exception:
                    mu_data['killer_curves'] = []
            else:
                mu_data['killer_curves'] = []

            # 3. Loss analysis from archive aggregates
            archive_file = None
            for prefix in ['archive_slim_', 'archive_']:
                candidate = ANALYZER_OUTPUT / f"{prefix}{deck_file}_vs_{opp_file}.json"
                if candidate.exists():
                    archive_file = candidate
                    break
            if archive_file:
                try:
                    arch = json.loads(archive_file.read_text())
                    agg = arch.get('aggregates', {})
                    mu_data['loss_analysis'] = {
                        'cause_frequency': agg.get('cause_frequency', {}),
                        'critical_turn_distribution': agg.get('critical_turn_distribution', {}),
                        'component_primary': agg.get('component_primary', {}),
                        'avg_trend_components': agg.get('avg_trend_components', {}),
                        'card_at_critical_turn': dict(list(agg.get('card_at_critical_turn', {}).items())[:15]),
                    }
                except Exception:
                    mu_data['loss_analysis'] = {}
            else:
                mu_data['loss_analysis'] = {}

            # 4. Card scores
            score_file = ANALYZER_SCORES / f"{deck_file}_vs_{opp_file}.json"
            if score_file.exists():
                try:
                    sc = json.loads(score_file.read_text())
                    # Extract card_scores dict if it exists, otherwise use top-level
                    card_scores_raw = sc.get('card_scores', sc)
                    # Filter to cards with meaningful data
                    mu_data['card_scores'] = {
                        k: v for k, v in card_scores_raw.items()
                        if isinstance(v, dict) and 'delta' in v
                    }
                except Exception:
                    mu_data['card_scores'] = {}
            else:
                mu_data['card_scores'] = {}

            # 5. Winning hands from report
            mu_data['winning_hands'] = _parse_report_winning_hands(md_text)

            # 6. Decklist from report
            mu_data['decklist'] = _parse_report_decklist(md_text)

            # 7. Playbook T1-T7
            mu_data['playbook'] = _parse_playbook(md_text)

            # 8. Board state T6/T7
            mu_data['board_state'] = _parse_board_state(md_text)

            # 9. Killer responses (OTP/OTD plays)
            mu_data['killer_responses'] = _parse_killer_responses(md_text)

            # 10. Ability cards
            mu_data['ability_cards'] = _parse_ability_cards(md_text)

            # 11. Minacce Principali LLM — parsed into structured data
            mu_data['threats_llm'] = _parse_threats_llm(md_text)

            deck_data[mu_key] = mu_data
            matchups_found.append(opp_short)

        if matchups_found:
            deck_data['available_matchups'] = sorted(matchups_found)
            result[deck_short] = deck_data
            result['available_decks'].append(deck_short)

    # Load PRO mulligan data and attach to matchups
    try:
        all_days = get_last_n_days(7)
        pro_mull = load_pro_mulligan_data(all_days, game_format="core")

        _attach_mulligan_data(result, pro_mull)
    except Exception as e:
        print(f"PRO mulligan data: {e}")

    result['available_decks'] = sorted(result.get('available_decks', []))
    return result


def _load_matchup_analyzer_data_infinity():
    """Build matchup analyzer for Infinity format (mulligan-only, no reports)."""
    result = {"available_decks": [], "all_decks": []}
    try:
        all_days = get_last_n_days(7)
        pro_mull = load_pro_mulligan_data(all_days, game_format="infinity")
        _attach_mulligan_data(result, pro_mull)
    except Exception as e:
        print(f"PRO mulligan data (infinity): {e}")
    result['available_decks'] = sorted(result.get('available_decks', []))
    return result


def _attach_mulligan_data(result, pro_mull):
    """Attach mulligan data to an analyzer result dict (shared logic)."""
    # Attach to existing deck/matchup entries
    for deck_short in result.get('available_decks', []):
        deck_data = result.get(deck_short, {})
        for mu_key in deck_data.get('available_matchups', []):
            vs_key = f'vs_{mu_key}'
            mu_data = deck_data.get(vs_key)
            if not isinstance(mu_data, dict):
                continue
            mulls = pro_mull.get(deck_short, {}).get(mu_key, [])
            if mulls:
                mu_data['pro_mulligans'] = mulls[:30]

    # Create entries for decks that have mulligan data but no report
    for deck_short, opp_dict in pro_mull.items():
        if deck_short not in result or deck_short not in result.get('available_decks', []):
            # New deck — create minimal entry with mulligan-only matchups
            deck_data = {'available_matchups': []}
            for opp_short, mulls in opp_dict.items():
                if mulls:
                    vs_key = f'vs_{opp_short}'
                    deck_data[vs_key] = {'pro_mulligans': mulls[:30], 'overview': {}}
                    deck_data['available_matchups'].append(opp_short)
            if deck_data['available_matchups']:
                deck_data['available_matchups'].sort()
                result[deck_short] = deck_data
                result['available_decks'].append(deck_short)
                if deck_short not in result.get('all_decks', []):
                    result.setdefault('all_decks', []).append(deck_short)
        else:
            # Existing deck — add mulligan-only matchups not yet covered
            deck_data = result[deck_short]
            existing_mus = set(deck_data.get('available_matchups', []))
            for opp_short, mulls in opp_dict.items():
                if opp_short not in existing_mus and mulls:
                    vs_key = f'vs_{opp_short}'
                    deck_data[vs_key] = {'pro_mulligans': mulls[:30], 'overview': {}}
                    deck_data['available_matchups'].append(opp_short)
            deck_data['available_matchups'] = sorted(deck_data['available_matchups'])


def export_dashboard_json(now, day_labels, days, set11, top, pro, all_matches,
                          stats_set11, stats_top, stats_pro,
                          w_set11, t_set11, w_top, t_top, w_pro, t_pro,
                          duelsink_data,
                          friends_core=None, inf=None, inf_top=None, inf_pro=None, inf_friends=None,
                          stats_friends_core=None, stats_inf=None, stats_inf_top=None, stats_inf_pro=None, stats_inf_friends=None,
                          w_friends_core=None, t_friends_core=None, w_inf=None, t_inf=None,
                          w_inf_top=None, t_inf_top=None, w_inf_pro=None, t_inf_pro=None,
                          w_inf_friends=None, t_inf_friends=None,
                          leaderboard_data=None):
    """Export all dashboard data as JSON for the HTML dashboard."""
    if leaderboard_data is None:
        leaderboard_data = {}
    consensus = load_snapshot_consensus()
    mmr_ref = leaderboard_data.get('mmr_ref', {}) if leaderboard_data else {}
    player_cards = _build_player_cards_data(days, mmr_ref=mmr_ref)

    data = {
        "meta": {
            "updated": now,
            "period": " + ".join(day_labels),
            "games": {
                "set11": len(set11),
                "top": len(top),
                "pro": len(pro),
                "friends_core": len(friends_core),
                "infinity": len(inf),
                "infinity_top": len(inf_top),
                "infinity_pro": len(inf_pro),
                "infinity_friends": len(inf_friends),
                "total": len(all_matches),
            }
        },
        "perimeters": {
            "set11": {
                "label": f"SET11 High ELO (≥{MIN_MMR_HIGH})",
                "wr": {d: dict(v) for d, v in stats_set11.items()},
                "matrix": _matrix_to_dict(w_set11, t_set11),
                "otp_otd": _build_otp_otd_data(set11),
                "trend": _build_trend_data(set11, days),
                "meta_share": _build_meta_share_data(set11, days),
                "top_players": _build_top_players_data(set11, min_games=4, per_deck_limit=8, mmr_ref=mmr_ref),
                "elo_dist": _build_elo_distribution(set11),
                "tech_choices": _build_tech_choices_data(all_matches, days),
            },
            "top": {
                "label": "TOP",
                "wr": {d: dict(v) for d, v in stats_top.items()},
                "matrix": _matrix_to_dict(w_top, t_top),
                "otp_otd": _build_otp_otd_data(top),
                "trend": _build_trend_data(top, days),
                "meta_share": _build_meta_share_data(top, days),
                "top_players": _build_top_players_data(top, min_games=3, per_deck_limit=8, mmr_ref=mmr_ref, skip_mmr_filter=True),
                "elo_dist": _build_elo_distribution(top),
                "tech_choices": [],
            },
            "pro": {
                "label": "PRO",
                "wr": {d: dict(v) for d, v in stats_pro.items()},
                "matrix": _matrix_to_dict(w_pro, t_pro),
                "otp_otd": _build_otp_otd_data(pro),
                "trend": _build_trend_data(pro, days),
                "meta_share": _build_meta_share_data(pro, days),
                "top_players": _build_top_players_data(pro, min_games=2, per_deck_limit=8, mmr_ref=mmr_ref, skip_mmr_filter=True),
                "elo_dist": _build_elo_distribution(pro),
                "tech_choices": [],
            },
            "friends_core": {
                "label": "Friends (Core)",
                "wr": {d: dict(v) for d, v in stats_friends_core.items()},
                "matrix": _matrix_to_dict(w_friends_core, t_friends_core),
                "otp_otd": _build_otp_otd_data(friends_core),
                "trend": _build_trend_data(friends_core, days),
                "meta_share": _build_meta_share_data(friends_core, days),
                "top_players": _build_top_players_data(friends_core, min_games=1, per_deck_limit=8, mmr_ref=mmr_ref),
                "elo_dist": _build_elo_distribution(friends_core),
                "tech_choices": [],
            },
            "infinity": {
                "label": "Infinity",
                "wr": {d: dict(v) for d, v in stats_inf.items()},
                "matrix": _matrix_to_dict(w_inf, t_inf),
                "otp_otd": _build_otp_otd_data(inf),
                "trend": _build_trend_data(inf, days),
                "meta_share": _build_meta_share_data(inf, days),
                "top_players": _build_top_players_data(inf, min_games=2, per_deck_limit=8, mmr_ref=mmr_ref),
                "elo_dist": _build_elo_distribution(inf),
                "tech_choices": [],
            },
            "infinity_top": {
                "label": "Infinity TOP",
                "wr": {d: dict(v) for d, v in stats_inf_top.items()},
                "matrix": _matrix_to_dict(w_inf_top, t_inf_top),
                "otp_otd": _build_otp_otd_data(inf_top),
                "trend": _build_trend_data(inf_top, days),
                "meta_share": _build_meta_share_data(inf_top, days),
                "top_players": _build_top_players_data(inf_top, min_games=1, per_deck_limit=8, mmr_ref=mmr_ref),
                "elo_dist": _build_elo_distribution(inf_top),
                "tech_choices": [],
            },
            "infinity_pro": {
                "label": "Infinity PRO",
                "wr": {d: dict(v) for d, v in stats_inf_pro.items()},
                "matrix": _matrix_to_dict(w_inf_pro, t_inf_pro),
                "otp_otd": _build_otp_otd_data(inf_pro),
                "trend": _build_trend_data(inf_pro, days),
                "meta_share": _build_meta_share_data(inf_pro, days),
                "top_players": _build_top_players_data(inf_pro, min_games=1, per_deck_limit=8, mmr_ref=mmr_ref),
                "elo_dist": _build_elo_distribution(inf_pro),
                "tech_choices": [],
            },
            "infinity_friends": {
                "label": "Friends (Infinity)",
                "wr": {d: dict(v) for d, v in stats_inf_friends.items()},
                "matrix": _matrix_to_dict(w_inf_friends, t_inf_friends),
                "otp_otd": _build_otp_otd_data(inf_friends),
                "trend": _build_trend_data(inf_friends, days),
                "meta_share": _build_meta_share_data(inf_friends, days),
                "top_players": _build_top_players_data(inf_friends, min_games=1, per_deck_limit=8, mmr_ref=mmr_ref),
                "elo_dist": _build_elo_distribution(inf_friends),
                "tech_choices": [],
            },
            "community": _duelsink_to_dict(duelsink_data),
        },
        "leaderboards": leaderboard_data.get('raw', {}),
        "pro_players": _build_pro_detail_data(all_matches, mmr_ref=mmr_ref),
        "consensus": {arch: dict(cards) for arch, cards in consensus.items()},
        "reference_decklists": _build_reference_decklists(),
        "player_cards": player_cards,
        "tech_tornado": {
            "set11": _build_tech_tornado_data(set11, days, consensus, "SET11"),
            "top": _build_tech_tornado_data(top, days, consensus, "TOP"),
            "pro": _build_tech_tornado_data(pro, days, consensus, "PRO"),
        },
        "matchup_trend": _build_matchup_trend(),
        "matchup_analyzer": _load_matchup_analyzer_data(),
        "matchup_analyzer_infinity": _load_matchup_analyzer_data_infinity(),
        "analysis": "",  # filled after report generation
    }

    # Try to load LLM analysis from existing report
    if OUTPUT.exists():
        report_text = OUTPUT.read_text()
        marker = "<!-- CLAUDE_ANALYSIS -->"
        if marker not in report_text:
            # Analysis was already inserted — extract it
            analysis_header = "## Analisi del Giorno"
            idx = report_text.find(analysis_header)
            if idx >= 0:
                analysis = report_text[idx + len(analysis_header):].strip()
                data["analysis"] = analysis

    # Card images: map card name → thumbnail URL for dashboard visuals
    _SET_NUM = {'TFC':1,'ROTF':2,'ITI':3,'URR':4,'SHS':5,'AZS':6,'ARI':7,'ROJ':8,'FAB':9,'WITW':10,'WIS':11,'Q1':'Q1','Q2':'Q2'}
    try:
        _cdb_path = Path(__file__).resolve().parent.parent.parent.parent / "cards_db.json"
        _cdb = json.loads(_cdb_path.read_text())
        _card_img = {}
        for cname, cdata in _cdb.items():
            s = cdata.get('set','').split('\n')[0]
            n = cdata.get('number','').split('\n')[0]
            sn = _SET_NUM.get(s)
            if sn and n.isdigit():
                _card_img[cname] = f"{sn}/{n}"
        # Aliases for card names that differ between match logs and cards_db
        _ALIASES = {
            "Malicious, Mean, and Scary": "Malicious, Mean and Scary",
            "Iago - Stompin' Mad": "Iago - Stomping Mad",
        }
        for alias, canonical in _ALIASES.items():
            if canonical in _card_img and alias not in _card_img:
                _card_img[alias] = _card_img[canonical]
        data["card_images"] = _card_img
        # Card types for pentagon radar
        _card_types = {}
        for cname, cdata in _cdb.items():
            raw_type = cdata.get("type", "").strip()
            if "Song" in raw_type:
                ctype = "song"
            elif raw_type == "Character":
                ctype = "character"
            elif raw_type == "Item":
                ctype = "item"
            elif raw_type == "Action":
                ctype = "action"
            elif "Location" in raw_type:
                ctype = "location"
            else:
                ctype = "other"
            _card_types[cname] = ctype
        data["card_types"] = _card_types
        print(f"Card types: {len(_card_types)} entries")
        # Card inks for deck auto-detection
        _card_inks = {}
        for cname, cdata in _cdb.items():
            ink = cdata.get("ink", "").lower()
            if ink and ink != "dual ink":
                _card_inks[cname] = ink
            elif ink == "dual ink":
                _card_inks[cname] = "dual"
        data["card_inks"] = _card_inks
    except Exception as e:
        print(f"Card images: {e}")
        data["card_images"] = {}
        data["card_types"] = {}

    # Team Training — modulo isolato, se fallisce non blocca nulla
    try:
        from team_training import build_team_data
        team_data = build_team_data(all_matches, pro_matches=pro)
        if team_data:
            data["team"] = team_data
            pc = team_data.get("roster_count", 0)
            pa = len(team_data.get("players", []))
            print(f"Team Training: {pa}/{pc} giocatori con dati")
    except Exception as e:
        print(f"Team Training: skip — {e}")

    DASHBOARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_JSON, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Dashboard JSON: {DASHBOARD_JSON} ({DASHBOARD_JSON.stat().st_size // 1024} KB)")

    # Generate self-contained HTML dashboard with embedded data
    template_path = DAILY_DIR / "dashboard.html"
    output_html = DAILY_DIR / "output" / "dashboard.html"
    if template_path.exists():
        html = template_path.read_text()
        json_str = json.dumps(data, ensure_ascii=False)
        # Insert embedded data variable before the marker comment
        html = html.replace(
            "// /*__INLINE_DATA__*/",
            f"const _EMBEDDED_DATA = {json_str};"
        )
        with open(output_html, "w") as f:
            f.write(html)
        print(f"Dashboard HTML: {output_html} ({output_html.stat().st_size // 1024} KB)")

    # Salva storico in SQLite (vedi HISTORY_DB.md per schema e query)
    try:
        from history_db import save_daily
        # Converti data da "22/03/2026 07:01" a "2026-03-22"
        parts = now.split(" ")[0].split("/")
        if len(parts) == 3:
            iso_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
        else:
            from datetime import date as _d
            iso_date = _d.today().isoformat()
        save_daily(data, iso_date)
    except Exception as e:
        print(f"History DB: errore salvataggio → {e}")

    # Salva killer curves nello storico
    try:
        from history_db import save_killer_curves_from_file
        import glob
        kc_dir = Path(__file__).resolve().parent.parent / "output"
        kc_files = sorted(kc_dir.glob("killer_curves_*.json"))
        kc_saved = 0
        for kc_file in kc_files:
            try:
                save_killer_curves_from_file(str(kc_file))
                kc_saved += 1
            except Exception:
                pass
        if kc_saved:
            print(f"Killer curves storico: {kc_saved} matchup salvati")
    except Exception as e:
        print(f"Killer curves storico: errore → {e}")


MY_DECK = "EmSa"   # Deck personalizzato per il report email


def generate_personal_report(my_deck, days, day_labels, set11, top, pro, all_matches,
                              stats_set11, w_set11, t_set11):
    """Genera report personalizzato per un deck specifico (~50 righe, leggibile da telefono)."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    r = []

    my = stats_set11.get(my_deck)
    if not my:
        return f"# {my_deck} — Nessun dato\n"

    # --- SEZ 1: IL MIO DECK OGGI ---
    day_stats = defaultdict(lambda: {"w": 0, "l": 0})
    for m in set11:
        for pnum, pkey in [(1, "p1"), (2, "p2")]:
            if m[f"{pkey}_deck"] == my_deck:
                if m["winner"] == pnum:
                    day_stats[m["day"]]["w"] += 1
                else:
                    day_stats[m["day"]]["l"] += 1

    total_appearances = sum(
        1 for m in set11 for pkey in ["p1", "p2"] if m[f"{pkey}_deck"] == my_deck
    )
    total_all_appearances = sum(
        1 for m in set11 for pkey in ["p1", "p2"] if m[f"{pkey}_deck"]
    )
    share = total_appearances / total_all_appearances * 100 if total_all_appearances else 0

    ranked_by_games = sorted(stats_set11.items(), key=lambda x: -x[1]["games"])
    rank = next((i + 1 for i, (d, _) in enumerate(ranked_by_games) if d == my_deck), "?")

    r.append(f"# {my_deck} Daily — {now}")

    sorted_days = list(reversed(days))  # oldest first
    trend_parts = []
    for d in sorted_days:
        ds = day_stats[d]
        t = ds["w"] + ds["l"]
        if t >= 3:
            wr = ds["w"] / t * 100
            trend_parts.append(f"{wr:.0f}%({t}g)")
    trend_str = " → ".join(trend_parts) if trend_parts else "—"

    if len(sorted_days) >= 2:
        d_old, d_new = sorted_days[0], sorted_days[-1]
        t_old = day_stats[d_old]["w"] + day_stats[d_old]["l"]
        t_new = day_stats[d_new]["w"] + day_stats[d_new]["l"]
        if t_old >= 3 and t_new >= 3:
            wr_old = day_stats[d_old]["w"] / t_old * 100
            wr_new = day_stats[d_new]["w"] / t_new * 100
            arrow = "↑" if wr_new > wr_old + 2 else ("↓" if wr_new < wr_old - 2 else "→")
        else:
            arrow = "—"
    else:
        arrow = "—"

    r.append(f"> **{my['wr']:.1f}% WR** ({my['games']}g) | Share {share:.1f}% (#{rank}) | Trend: {trend_str} {arrow}")
    r.append("")

    # --- SEZ 2: COSA INCONTRO IN LADDER ---
    r.append("## Cosa incontro")
    r.append("")

    meta_ranked = sorted(stats_set11.items(), key=lambda x: -x[1]["games"])

    day_totals = defaultdict(int)
    day_deck_counts = defaultdict(lambda: defaultdict(int))
    for m in set11:
        for pkey in ["p1", "p2"]:
            deck = m[f"{pkey}_deck"]
            if deck:
                day_totals[m["day"]] += 1
                day_deck_counts[m["day"]][deck] += 1

    r.append(f"| Deck | Share | Trend | vs {my_deck} |")
    r.append("|---|---|---|---|")

    for deck, s in meta_ranked:
        if deck == my_deck:
            continue
        if s["games"] < 20:
            continue

        dk_appearances = sum(
            1 for m in set11 for pkey in ["p1", "p2"] if m[f"{pkey}_deck"] == deck
        )
        dk_share = dk_appearances / total_all_appearances * 100 if total_all_appearances else 0

        if len(sorted_days) >= 2:
            d_old, d_new = sorted_days[0], sorted_days[-1]
            s_old = day_deck_counts[d_old][deck] / day_totals[d_old] * 100 if day_totals[d_old] else 0
            s_new = day_deck_counts[d_new][deck] / day_totals[d_new] * 100 if day_totals[d_new] else 0
            delta = s_new - s_old
            if delta >= 1.0:
                trend_s = f"↑+{delta:.0f}pp"
            elif delta <= -1.0:
                trend_s = f"↓{delta:.0f}pp"
            else:
                trend_s = "="
        else:
            trend_s = "—"

        t_vs = t_set11[my_deck][deck]
        if t_vs >= MIN_GAMES_MATRIX:
            w_vs = w_set11[my_deck][deck]
            wr_vs = w_vs / t_vs * 100
            if wr_vs >= 55:
                wr_cell = f"**{wr_vs:.0f}%** ({t_vs}g)"
            elif wr_vs <= 45:
                wr_cell = f"_{wr_vs:.0f}%_ ({t_vs}g) ⚠"
            else:
                wr_cell = f"{wr_vs:.0f}% ({t_vs}g)"
        else:
            wr_cell = "·"

        r.append(f"| {deck} | {dk_share:.1f}% | {trend_s} | {wr_cell} |")

    r.append("")

    # --- SEZ 3: MATCHUP CRITICI OTP/OTD ---
    r.append("## OTP/OTD critici")
    r.append("")

    otp_data = _build_otp_otd_data(set11)
    my_otp = otp_data.get(my_deck, {})
    critical = []
    for opp, d in my_otp.items():
        otp_t = d["otp_t"]
        otd_t = d["otd_t"]
        if otp_t < 5 or otd_t < 5:
            continue
        otp_wr = d["otp_w"] / otp_t * 100
        otd_wr = d["otd_w"] / otd_t * 100
        gap = abs(otp_wr - otd_wr)
        if gap >= 10:
            critical.append((opp, otp_wr, otd_wr, gap, otp_t, otd_t))

    critical.sort(key=lambda x: -x[3])
    if critical:
        for opp, otp_wr, otd_wr, gap, otp_t, otd_t in critical[:6]:
            note = ""
            if otp_wr < 45 and otd_wr < 45:
                note = " — sfavorito sempre"
            elif otd_wr < 40:
                note = " — OTD critico"
            elif otp_wr < 40:
                note = " — OTP critico"
            r.append(f"- **vs {opp}**: OTP {otp_wr:.0f}% ({otp_t}g) / OTD {otd_wr:.0f}% ({otd_t}g) — gap {gap:.0f}pp{note}")
        r.append("")
    else:
        r.append("_Nessun matchup con gap OTP/OTD ≥10pp (sample sufficiente)._")
        r.append("")

    # --- SEZ 4: CHI VINCE CON IL MIO DECK ---
    r.append(f"## Top player {my_deck}")
    r.append("")

    top_players = _build_top_players_data(all_matches, min_games=3, per_deck_limit=10)
    my_players = [p for p in top_players if p["deck"] == my_deck]
    my_players.sort(key=lambda x: (-x["wr"], -x["mmr"]))

    if my_players:
        r.append("| Player | W-L | WR | MMR | Matchup |")
        r.append("|---|---|---|---|---|")
        for p in my_players[:8]:
            tag = " **PRO**" if p.get("is_pro") else ""
            mu_parts = []
            for opp, mu in sorted(p["matchups"].items(), key=lambda x: -(x[1]["w"] + x[1]["l"])):
                mu_parts.append(f"{opp} {mu['w']}-{mu['l']}")
            mu_str = ", ".join(mu_parts[:3])
            r.append(f"| {p['name']}{tag} | {p['w']}-{p['l']} | {p['wr']:.0f}% | {p['mmr']} | {mu_str} |")
        r.append("")
    else:
        r.append(f"_Nessun player con ≥3 partite su {my_deck}._")
        r.append("")

    # --- SEZ 5: TECH DAL CAMPO ---
    r.append(f"## Tech {my_deck}")
    r.append("")
    consensus = load_snapshot_consensus()
    if consensus and my_deck in consensus:
        std = consensus[my_deck]
        cards_top_d = extract_player_cards(days, "TOP")
        cards_set11_d = extract_player_cards(days, "SET11", min_mmr=MIN_MMR_HIGH)
        all_cards = {}
        for key, cards in {**cards_set11_d, **cards_top_d}.items():
            if key in all_cards:
                for c, n in cards.items():
                    all_cards[key][c] = max(all_cards[key].get(c, 0), n)
            else:
                all_cards[key] = dict(cards)

        player_stats_tech = defaultdict(lambda: {"w": 0, "l": 0, "mmr": 0, "display": ""})
        for m in all_matches:
            for pnum, pkey in [(1, "p1"), (2, "p2")]:
                name = m[f"{pkey}_name"].lower()
                deck = m[f"{pkey}_deck"]
                if deck != my_deck or not name:
                    continue
                key = (name, deck)
                s = player_stats_tech[key]
                s["display"] = m[f"{pkey}_name"]
                s["mmr"] = max(s["mmr"], m[f"{pkey}_mmr"])
                if m["winner"] == pnum:
                    s["w"] += 1
                else:
                    s["l"] += 1

        tech_found = False
        sorted_players = sorted(player_stats_tech.items(),
                                key=lambda x: -(x[1]["w"] / max(1, x[1]["w"] + x[1]["l"])))
        for (pname, deck), s in sorted_players:
            total_g = s["w"] + s["l"]
            if total_g < 4:
                continue
            wr = s["w"] / total_g * 100
            if wr < 58 and s["mmr"] < 1600:
                continue
            if (pname, deck) not in all_cards:
                continue

            cards = all_cards[(pname, deck)]
            tech_in = []
            for card, n_games in sorted(cards.items(), key=lambda x: -x[1]):
                if card not in std and n_games >= max(2, total_g * 0.3):
                    tech_in.append(f"{card} ({n_games}/{total_g}g)")

            tech_out = []
            for card, avg_qty in sorted(std.items(), key=lambda x: -x[1]):
                if avg_qty >= 2.0 and cards.get(card, 0) <= max(1, total_g * 0.2):
                    tech_out.append(f"{card} (std {avg_qty:.0f}x)")

            if tech_in or tech_out:
                r.append(f"**{s['display']}** ({s['w']}-{s['l']}, {wr:.0f}%, MMR {s['mmr']}):")
                if tech_in:
                    r.append(f"  - IN: {', '.join(tech_in[:4])}")
                if tech_out:
                    r.append(f"  - OUT: {', '.join(tech_out[:4])}")
                tech_found = True

        if not tech_found:
            r.append("_Nessuna tech rilevante rilevata._")
        r.append("")
    else:
        r.append("_Snapshot inkdecks non disponibile._")
        r.append("")

    # --- SEZ 6: ALLARMI ---
    r.append("## Allarmi")
    r.append("")

    alerts = []
    for deck, s in meta_ranked:
        if deck == my_deck:
            continue
        t_vs = t_set11[my_deck][deck]
        if t_vs < MIN_GAMES_MATRIX:
            continue
        wr_vs = w_set11[my_deck][deck] / t_vs * 100
        dk_appearances = sum(
            1 for m in set11 for pkey in ["p1", "p2"] if m[f"{pkey}_deck"] == deck
        )
        dk_share = dk_appearances / total_all_appearances * 100 if total_all_appearances else 0

        if wr_vs <= 44 and dk_share >= 8:
            alerts.append(f"⚠ **{deck}** ({dk_share:.0f}% share) ti batte — {wr_vs:.0f}% WR ({t_vs}g)")
        elif wr_vs >= 58 and dk_share >= 8:
            alerts.append(f"✓ **{deck}** ({dk_share:.0f}% share) — matchup forte {wr_vs:.0f}% ({t_vs}g)")

    if len(days) >= 2:
        d_old, d_new = sorted_days[0], sorted_days[-1]
        for deck in stats_set11:
            if deck == my_deck:
                continue
            s_old = day_deck_counts[d_old][deck] / day_totals[d_old] * 100 if day_totals[d_old] else 0
            s_new = day_deck_counts[d_new][deck] / day_totals[d_new] * 100 if day_totals[d_new] else 0
            if s_new - s_old >= 1.5:
                t_vs = t_set11[my_deck][deck]
                if t_vs >= MIN_GAMES_MATRIX:
                    wr_vs = w_set11[my_deck][deck] / t_vs * 100
                    if wr_vs <= 48:
                        alerts.append(f"↑ **{deck}** sale (+{s_new - s_old:.0f}pp) e ti batte {wr_vs:.0f}%")

    stats_top_d = deck_stats(top)
    top_my = stats_top_d.get(my_deck)
    if top_my and top_my["games"] >= 10:
        if top_my["wr"] <= 42:
            alerts.append(f"⚠ Al TOP {my_deck} crolla: {top_my['wr']:.0f}% ({top_my['games']}g)")
        elif top_my["wr"] >= 58:
            alerts.append(f"✓ Al TOP {my_deck} spacca: {top_my['wr']:.0f}% ({top_my['games']}g)")

    if alerts:
        for a in alerts:
            r.append(f"- {a}")
    else:
        r.append("_Nessun allarme._")
    r.append("")

    return "\n".join(r)


def main():
    days = get_last_n_days(2)
    day_labels = [f"{d[:2]}/{d[2:4]}" for d in days]
    print(f"Analisi match: {', '.join(day_labels)}")

    # Load data
    print(f"Caricamento SET11 (MMR >= {MIN_MMR_HIGH})...")
    set11 = load_matches(days, "SET11", min_mmr=MIN_MMR_HIGH)
    print(f"  → {len(set11)} match")

    # Fetch duels.ink leaderboards → aggiorna TOP/PRO dinamicamente
    global TOP_PLAYERS, PRO_PLAYERS, TOP_PLAYERS_INF, PRO_PLAYERS_INF
    print("Caricamento leaderboard duels.ink...")
    leaderboard_data = fetch_leaderboards()
    TOP_PLAYERS = leaderboard_data['core_top']
    PRO_PLAYERS = leaderboard_data['core_pro']
    TOP_PLAYERS_INF = leaderboard_data['inf_top']
    PRO_PLAYERS_INF = leaderboard_data['inf_pro']
    # ALL_NOTABLE: union di tutti per backward compat con tag "is_pro" nei report
    # (qualsiasi player in TOP/PRO/FRIENDS di qualsiasi formato)
    global ALL_NOTABLE
    ALL_NOTABLE = TOP_PLAYERS | PRO_PLAYERS | TOP_PLAYERS_INF | PRO_PLAYERS_INF | FRIENDS
    print(f"  Core: TOP={len(TOP_PLAYERS)} PRO={len(PRO_PLAYERS)}")
    print(f"  Infinity: TOP={len(TOP_PLAYERS_INF)} PRO={len(PRO_PLAYERS_INF)}")
    print(f"  Friends: {len(FRIENDS)} | All notable: {len(ALL_NOTABLE)}")

    # Fetch duels.ink community stats
    print("Caricamento duels.ink community stats...")
    duelsink_data = fetch_duelsink_stats()
    if duelsink_data:
        print(f"  → {duelsink_data.get('activity', {}).get('totalGames', 0):,} partite community")

    # Carica match direttamente dalle cartelle del monitor (già classificati)
    print("Caricamento TOP folder...")
    top_folder = load_matches(days, "TOP")
    print(f"  → {len(top_folder)} match")

    print("Caricamento PRO folder...")
    pro_folder = load_matches(days, "PRO")
    print(f"  → {len(pro_folder)} match")

    print("Caricamento FRIENDS folder...")
    friends_folder = load_matches(days, "FRIENDS")
    print(f"  → {len(friends_folder)} match")

    print("Caricamento INF (Infinity)...")
    inf = load_matches(days, "INF")
    print(f"  → {len(inf)} match")

    # Combined core (SET11+TOP+PRO+FRIENDS folders, dedup)
    all_seen = set()
    all_core = []
    for m in set11 + top_folder + pro_folder + friends_folder:
        if m["game_id"] not in all_seen:
            all_seen.add(m["game_id"])
            all_core.append(m)
    all_matches = all_core  # backward compat

    # Helper per filtrare match per player name
    def _filter_by_players(matches, player_set):
        return [m for m in matches
                if m.get("p1_name", "").lower() in player_set
                or m.get("p2_name", "").lower() in player_set]

    def _is_friend(name):
        nl = name.lower()
        return nl in FRIENDS or any(nl.startswith(p) for p in FRIENDS_PREFIXES)

    def _filter_friends(matches):
        return [m for m in matches
                if _is_friend(m.get("p1_name", ""))
                or _is_friend(m.get("p2_name", ""))]

    # Sub-perimetri Core — uso diretto cartelle monitor (già classificate)
    # Dedup: stessa partita può essere in TOP e PRO, teniamo unica
    top_ids = set()
    top = []
    for m in top_folder:
        if m["game_id"] not in top_ids:
            top_ids.add(m["game_id"])
            top.append(m)

    pro_ids = set()
    pro = []
    for m in pro_folder:
        if m["game_id"] not in pro_ids:
            pro_ids.add(m["game_id"])
            pro.append(m)

    friends_ids = set()
    friends_core = []
    for m in friends_folder:
        if m["game_id"] not in friends_ids:
            friends_ids.add(m["game_id"])
            friends_core.append(m)
    # Fallback: se FRIENDS folder vuota, filtra da all_core (backward compat)
    if not friends_core:
        friends_core = _filter_friends(all_core)

    # Sub-perimetri Infinity (filtra da inf per leaderboard — INF non ha sotto-cartelle TOP/PRO)
    inf_top = _filter_by_players(inf, TOP_PLAYERS_INF)
    inf_pro = _filter_by_players(inf, PRO_PLAYERS_INF)
    inf_friends = _filter_friends(inf)

    print(f"  Core: SET11={len(set11)} TOP={len(top)} PRO={len(pro)} Friends={len(friends_core)}")
    print(f"  Infinity: ALL={len(inf)} TOP={len(inf_top)} PRO={len(inf_pro)} Friends={len(inf_friends)}")

    # Stats
    stats_set11 = deck_stats(set11)
    stats_top = deck_stats(top)
    stats_pro = deck_stats(pro)
    stats_friends_core = deck_stats(friends_core)
    stats_inf = deck_stats(inf)
    stats_inf_top = deck_stats(inf_top)
    stats_inf_pro = deck_stats(inf_pro)
    stats_inf_friends = deck_stats(inf_friends)
    w_set11, t_set11 = build_matrix(set11)
    w_top, t_top = build_matrix(top)
    w_pro, t_pro = build_matrix(pro)
    w_friends_core, t_friends_core = build_matrix(friends_core)
    w_inf, t_inf = build_matrix(inf)
    w_inf_top, t_inf_top = build_matrix(inf_top)
    w_inf_pro, t_inf_pro = build_matrix(inf_pro)
    w_inf_friends, t_inf_friends = build_matrix(inf_friends)

    # Notable matchups
    notable_set11 = find_notable_matchups(w_set11, t_set11)
    notable_top = find_notable_matchups(w_top, t_top)

    # === BUILD REPORT ===
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    r = []

    r.append(f"# Daily Routine — {now}")
    r.append(f"_Periodo: {' + '.join(day_labels)} | Core: SET11={len(set11)} TOP={len(top)} PRO={len(pro)} | INF: ALL={len(inf)} TOP={len(inf_top)} PRO={len(inf_pro)} | Friends: {len(friends_core)}+{len(inf_friends)} | Tot: {len(all_matches)}g_\n")

    # --- SEZIONE 1: PANORAMICA META ---
    r.append("## Meta del Giorno\n")
    r.append("### Win Rate — SET11 High ELO\n")
    r.append(format_wr_table(stats_set11))
    r.append("")

    if stats_top:
        r.append("### Win Rate — TOP\n")
        r.append(format_wr_table(stats_top, min_games=3))
        r.append("")

    if stats_pro:
        r.append("### Win Rate — PRO\n")
        r.append(format_wr_table(stats_pro, min_games=2))
        r.append("")

    # --- SEZIONE 1b: META SHARE ---
    r.append("---\n")
    r.append("## Meta Share\n")
    r.append(format_meta_share(set11, days))
    r.append("")

    # --- SEZIONE 2: TREND ---
    r.append("---\n")
    r.append("## Trend Giornaliero\n")
    r.append(format_trend(set11, list(reversed(days))))
    r.append("")

    # --- SEZIONE 3: MATCHUP ESTREMI ---
    r.append("---\n")
    r.append("## Matchup Chiave\n")

    r.append("### Matrice SET11 High ELO\n")
    r.append(format_matrix(w_set11, t_set11))
    r.append("")
    r.append("#### OTP / OTD — SET11 High ELO\n")
    r.append(format_matrix_otp_otd(set11))
    r.append("")
    r.append("#### Vittorie Assolute — SET11 High ELO\n")
    r.append(format_matrix_wins(w_set11, t_set11))
    r.append("")

    if notable_set11:
        r.append("**Matchup estremi (≥70%):**")
        for d1, d2, wr, t, _ in notable_set11[:10]:
            r.append(f"- {d1} batte {d2}: **{wr:.0f}%** ({t}g)")
        r.append("")

    if top and len(top) >= 30:
        r.append("### Matrice TOP\n")
        r.append(format_matrix(w_top, t_top, top_n=7))
        r.append("")
        r.append("#### Vittorie Assolute — TOP\n")
        r.append(format_matrix_wins(w_top, t_top, top_n=7))
        r.append("")

    if pro and len(pro) >= 15:
        r.append("### Matrice PRO\n")
        r.append(format_matrix(w_pro, t_pro, top_n=6))
        r.append("")

    # --- SEZIONE DUELS.INK ---
    if duelsink_data:
        r.append("---\n")
        r.append(format_duelsink_section(duelsink_data))
        r.append("")

    # --- SEZIONE 4: TOP PLAYERS ---
    r.append("---\n")
    r.append("## Top Players\n")
    r.append("### SET11 High ELO\n")
    r.append(format_top_players(set11, min_games=4, limit=15))
    r.append("")

    if top:
        r.append("### TOP\n")
        r.append(format_top_players(top, min_games=3, limit=12))
        r.append("")

    # --- SEZIONE 4b: SCOUTING TOP ---
    if top:
        r.append("### Scouting TOP — Matchup per Player\n")
        r.append(format_scouting_top(top))
        r.append("")

    # --- SEZIONE 5: PRO DETAIL ---
    r.append("---\n")
    r.append("## PRO Players\n")
    r.append(format_pro_detail(all_matches))
    r.append("")

    # --- SEZIONE 5b: DECK EMERGENTI ---
    r.append("---\n")
    r.append("## Deck Emergenti\n")
    r.append("_Deck con <6% meta share ma risultati forti da player ad alto ELO (≥1400 MMR, ≥58% WR, ≥4 match)._\n")
    w_all, t_all = build_matrix(all_matches)
    r.append(format_emerging_decks(all_matches, deck_stats(all_matches), w_all, t_all, days))
    r.append("")

    # --- SEZIONE 6: TECH CHOICES ---
    r.append("---\n")
    r.append("## Tech Choices — Differenze dalle Liste Standard\n")
    r.append("_Confronto con decklist torneo (inkdecks.com). Tech IN = carte non standard usate dal player. Tech OUT = carte standard assenti._\n")
    r.append(format_tech_choices(all_matches, days))
    r.append("")

    # --- SEZIONE 7: PLACEHOLDER PER ANALISI CLAUDE ---
    r.append("---\n")
    r.append("## Analisi del Giorno\n")
    r.append("<!-- CLAUDE_ANALYSIS -->\n")
    r.append("")

    # Write markdown report
    output = "\n".join(r)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        f.write(output)

    print(f"\nReport salvato: {OUTPUT}")
    print(f"Match totali: {len(all_matches)}")

    # === EXPORT JSON FOR DASHBOARD ===
    export_dashboard_json(
        now, day_labels, days,
        set11, top, pro, all_matches,
        stats_set11, stats_top, stats_pro,
        w_set11, t_set11, w_top, t_top, w_pro, t_pro,
        duelsink_data,
        friends_core=friends_core, inf=inf, inf_top=inf_top, inf_pro=inf_pro, inf_friends=inf_friends,
        stats_friends_core=stats_friends_core, stats_inf=stats_inf, stats_inf_top=stats_inf_top,
        stats_inf_pro=stats_inf_pro, stats_inf_friends=stats_inf_friends,
        w_friends_core=w_friends_core, t_friends_core=t_friends_core,
        w_inf=w_inf, t_inf=t_inf, w_inf_top=w_inf_top, t_inf_top=t_inf_top,
        w_inf_pro=w_inf_pro, t_inf_pro=t_inf_pro, w_inf_friends=w_inf_friends, t_inf_friends=t_inf_friends,
        leaderboard_data=leaderboard_data,
    )


def send_daily_email():
    """Invia il daily report via email con allegati MD/PDF + dashboard HTML."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email import encoders
    import subprocess

    EMAIL = 'alexander9.ed@gmail.com'
    APP_PWD = 'xltowwniuwnfyrgv'
    output_dir = DAILY_DIR / "output"
    today = datetime.now().strftime("%d/%m/%Y")

    # Converti report MD → PDF via weasyprint
    attachments = []
    report_md = output_dir / "daily_routine.md"

    if report_md.exists():
        pdf_path = output_dir / "daily_routine.pdf"
        html_path = output_dir / "daily_routine_email.html"
        css = """
@page { size: A4 landscape; margin: 1.2cm; }
body { font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif;
       font-size: 11px; line-height: 1.5; color: #1a1a1a; }
h1 { font-size: 22px; border-bottom: 2px solid #2c3e50; padding-bottom: 6px;
     margin-top: 20px; color: #2c3e50; }
h2 { font-size: 17px; color: #2c3e50; border-bottom: 1px solid #bdc3c7;
     padding-bottom: 4px; margin-top: 16px; }
h3 { font-size: 14px; color: #34495e; margin-top: 12px; }
h4 { font-size: 12px; color: #555; margin-top: 10px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0;
        font-size: 10px; page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
th { background: #ecf0f1; font-weight: bold; color: #2c3e50; }
tr:nth-child(even) { background: #fafafa; }
strong { color: #c0392b; }
em { color: #7f8c8d; }
code { background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: 10px; }
hr { border: none; border-top: 1px solid #ddd; margin: 12px 0; }
ul, ol { margin: 4px 0; padding-left: 20px; }
li { margin: 2px 0; }
"""
        css_path = output_dir / "_email.css"
        css_path.write_text(css)
        try:
            # Step 1: MD → HTML (pandoc)
            r1 = subprocess.run(
                ["pandoc", str(report_md), "-f", "gfm", "-t", "html5",
                 "--standalone", "-o", str(html_path)],
                capture_output=True, text=True, timeout=30
            )
            if r1.returncode != 0:
                raise RuntimeError(f"pandoc failed: {r1.stderr[:200]}")
            # Step 2: HTML → PDF (weasyprint con CSS)
            r2 = subprocess.run(
                ["weasyprint", "-s", str(css_path), str(html_path), str(pdf_path)],
                capture_output=True, text=True, timeout=120
            )
            if r2.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 1000:
                attachments.append((str(pdf_path), "Daily_Routine.pdf"))
                print(f"  PDF generato: {pdf_path.stat().st_size / 1024:.0f} KB")
            else:
                raise RuntimeError(f"weasyprint failed: {r2.stderr[:200]}")
        except Exception as e:
            print(f"  PDF errore ({e}), allego .md")
            attachments.append((str(report_md), "daily_routine.md"))

    if not attachments:
        print("Nessun file da allegare, skip email.")
        return

    # Componi email
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Subject'] = f'Lorcana Daily Report — {today}'

    total_kb = sum(os.path.getsize(f) for f, _ in attachments) / 1024
    body = f"""Lorcana Daily Report — {today}

Report giornaliero con meta, matchup, top players e scouting PRO.

{len(attachments)} allegato/i ({total_kb:.0f} KB)
"""
    msg.attach(MIMEText(body, 'plain'))

    for file_path, file_name in attachments:
        with open(file_path, 'rb') as f:
            if file_name.endswith('.pdf'):
                part = MIMEBase('application', 'pdf')
            elif file_name.endswith('.html'):
                part = MIMEBase('text', 'html')
            else:
                part = MIMEBase('text', 'markdown')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={file_name}')
            msg.attach(part)

    # Invio
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL, APP_PWD)
        server.send_message(msg)
        server.quit()
        print(f'✓ Email inviata a {EMAIL} ({len(attachments)} allegati, {total_kb:.0f} KB)')
    except Exception as e:
        print(f'✗ Errore invio email: {e}')


if __name__ == "__main__":
    main()
    # send_daily_email()  # disabilitato — mail inviata da generate_and_send.py via cron
