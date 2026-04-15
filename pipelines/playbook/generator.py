"""
Blind Deck Playbook generator — native App_tool port (Sprint-1 Mossa B).

Ports `analisidef/lib/gen_deck_playbook.py` (1573 LOC) into App_tool. Behaviour
is identical to the source modulo two adaptations:

1. Path constants adapted:
   - BASE points at App_tool root (digests and `output/` still live on the
     shared filesystem — keeping the analisidef output tree as bridge until
     Fase F moves per-matchup digests into PG).
   - DASHBOARD_DATA stays on the shared filesystem (analisidef daily output)
     until migrated in a later phase.
   - CARDS_DB_PATH and SNAPSHOT_DIR are shared filesystem paths (unchanged).

2. Prompt rewritten in ENGLISH. Analisidef forced 'italiano fluido'; App_tool
   is English-only (see CLAUDE.md + memory `feedback_app_language_english.md`).
   All instructions, role hints and JSON field descriptions in
   `build_blind_prompt`, `build_narrative_prompt` and `build_strategic_prompt`
   were translated. The narrative schema itself (keys, types) is unchanged so
   the output payload stays compatible with `playbook_service.upsert_playbook`.

Public entry point:
    generate_playbook(deck, game_format="core", use_llm=True, model="gpt-5.4-mini")
      -> dict payload with keys: meta, aggregated, pro_references, weekly_tech,
         playbook, strategic_frame.

OpenAI key resolution: OPENAI_API_KEY env var, falling back to /tmp/.openai_key.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Resolve App_tool project root so we can import lib/ regardless of CWD.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from lib.cards_dict import (
    _classify_removal,
    _is_draw,
    _is_ramp,
    _parse_shift_cost,
)

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
# App_tool root. Used only for output/ fallback (bridge until per-matchup
# digests are persisted in PG).
BASE = Path("/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/App_tool")

# Source of per-matchup digests. Today still produced by the analisidef batch
# and read off the shared filesystem. Fase F will move these into PG.
ANALISIDEF_BASE = Path("/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef")

# Shared filesystem paths (unchanged from analisidef source).
SNAPSHOT_DIR = Path("/mnt/HC_Volume_104764377/finanza/Lor/decks_db/history")
DASHBOARD_DATA = ANALISIDEF_BASE / "daily/output/dashboard_data.json"
CARDS_DB_PATH = Path("/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json")

DECK_COLORS = {
    "AmAm": "Amber, Amethyst",   "AS": "Amethyst, Sapphire",
    "ES": "Emerald, Sapphire",   "AbE": "Amber, Emerald",
    "AbS": "Amber, Sapphire",    "AbR": "Amber, Ruby",
    "AbSt": "Amber, Steel",      "AmySt": "Amethyst, Steel",
    "SSt": "Sapphire, Steel",    "AmyE": "Amethyst, Emerald",
    "AmyR": "Amethyst, Ruby",    "RS": "Ruby, Sapphire",
}

DECK_ALIAS = {"EmSa": "ES", "AmSa": "AS"}


# ---------------------------------------------------------------------------
# 0. CANONICAL NAME MAP
# ---------------------------------------------------------------------------

_CANONICAL_CACHE = {"db_path": None, "map": None}


def _normalize_card_key(name):
    return "".join(c for c in (name or "").lower() if c.isalnum())


def _score_canonical_entry(name, entry):
    score = 0
    t = str(entry.get("type", ""))
    ink = str(entry.get("ink", ""))
    if t and t[0].isupper():
        score += 10
    if "·" in t or " " in t:
        score += 3
    if ink and ink[0].isupper():
        score += 2
    if entry.get("ability"):
        score += 1
    return score


def build_canonical_name_map(cards_db):
    groups = {}
    for name, entry in cards_db.items():
        if not isinstance(entry, dict):
            continue
        nk = _normalize_card_key(name)
        if not nk:
            continue
        groups.setdefault(nk, []).append(name)
    name_map = {}
    for nk, variants in groups.items():
        if len(variants) == 1:
            name_map[variants[0]] = variants[0]
        else:
            best = max(variants, key=lambda n: _score_canonical_entry(n, cards_db[n]))
            for v in variants:
                name_map[v] = best
    return name_map


def get_canonical_map():
    if _CANONICAL_CACHE["map"] is None:
        with open(CARDS_DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
        _CANONICAL_CACHE["map"] = build_canonical_name_map(db)
    return _CANONICAL_CACHE["map"]


def canon(name):
    if not name or not isinstance(name, str):
        return name
    cmap = get_canonical_map()
    return cmap.get(name, name)


# ---------------------------------------------------------------------------
# 1. AGGREGATION
# ---------------------------------------------------------------------------

def load_deck_digests(deck, game_format):
    """Load all digest_<DECK>_vs_*[_inf].json for a deck from analisidef output/."""
    sfx = "_inf" if game_format == "infinity" else ""
    pattern = str(ANALISIDEF_BASE / f"output/digest_{deck}_vs_*{sfx}.json")
    paths = sorted(glob.glob(pattern))
    paths = [p for p in paths if not any(p.endswith(f"_{lang}.json")
                                         for lang in ("it", "de", "ja", "zh"))]
    if game_format == "core":
        paths = [p for p in paths if "_inf.json" not in p]
    digests = []
    for p in paths:
        try:
            with open(p) as f:
                d = json.load(f)
            d["_source_path"] = p
            digests.append(d)
        except Exception:
            continue
    return digests


def _parse_classifications(raw_value):
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        return [str(x).strip() for x in raw_value if str(x).strip()]
    text = str(raw_value).replace("•", "·")
    return [part.strip() for part in text.split("·") if part.strip()]


def _parse_detailed_keywords(ability):
    if not ability:
        return []
    keywords = []
    if re.search(r"\bBodyguard\b", ability, re.IGNORECASE):
        keywords.append("Bodyguard")
    challenger = re.search(r"\bChallenger\s*\+?(\d+)", ability, re.IGNORECASE)
    if challenger:
        keywords.append(f"Challenger +{challenger.group(1)}")
    if re.search(r"\bEvasive\b", ability, re.IGNORECASE):
        keywords.append("Evasive")
    if re.search(r"\bReckless\b", ability, re.IGNORECASE):
        keywords.append("Reckless")
    resist = re.search(r"\bResist\s*\+?(\d+)", ability, re.IGNORECASE)
    if resist:
        keywords.append(f"Resist {resist.group(1)}")
    if re.search(r"\bRush\b", ability, re.IGNORECASE):
        keywords.append("Rush")
    shift = re.search(r"\bShift\s+(\d+)", ability, re.IGNORECASE)
    if shift:
        keywords.append(f"Shift {shift.group(1)}")
    singer = re.search(r"\bSinger\s+(\d+)", ability, re.IGNORECASE)
    if singer:
        keywords.append(f"Singer {singer.group(1)}")
    if re.search(r"\bSupport\b", ability, re.IGNORECASE):
        keywords.append("Support")
    if re.search(r"\bVanish\b", ability, re.IGNORECASE):
        keywords.append("Vanish")
    if re.search(r"\bWard\b", ability, re.IGNORECASE):
        keywords.append("Ward")
    return keywords


def _infer_role_and_caveat(name, card_type, ability, keywords):
    ability_l = (ability or "").lower()
    role = "body_lore"
    caveat = None

    tutor_match = re.search(r"look at the top (\d+) cards?", ability_l)
    shift_cost = _parse_shift_cost(ability)

    if "banish all opposing damaged" in ability_l:
        role = "conditional_wipe"
        caveat = "requires opponents damaged (needs softener like MMS)"
    elif "put 1 damage counter on each" in ability_l:
        role = "aoe_softener"
    elif "shuffle chosen" in ability_l and "draw" in ability_l:
        role = "removal_permanent"
        draws = re.search(r"draws?\s+(\d+)\s+cards?", ability_l)
        draw_n = draws.group(1) if draws else "cards"
        caveat = f"opponent draws {draw_n} — expensive trade"
    elif "you played a princess" in ability_l:
        role = "ink_engine" if (_is_ramp(ability) or _is_draw(ability)) else "draw_engine"
        caveat = "triggers only if another Princess played same turn"
    elif "each player exerts" in ability_l or "each player with more than" in ability_l:
        role = "disruption"
        caveat = "symmetric effect"
    elif tutor_match:
        role = f"tutor_{tutor_match.group(1)}"
    elif _is_ramp(ability):
        role = "ramp"
    elif "banish chosen item" in ability_l:
        role = "item_banish"
    elif re.search(r"when you play this character, banish", ability_l):
        role = "etb_removal"
    elif re.search(r"pay \d+ .*banish", ability_l) or re.search(r"⬡.*banish chosen", ability_l):
        role = "activated_removal"
    elif shift_cost is not None:
        role = "finisher_shift"

    removal_type = _classify_removal(ability)
    if role == "body_lore" and removal_type in {"banish_etb", "damage_etb", "exert_etb", "banish_spell", "damage_spell"}:
        role = "etb_removal" if "etb" in removal_type else "removal_permanent"
    if role == "body_lore" and _is_draw(ability):
        role = "draw_engine"
    if role == "body_lore" and shift_cost is not None:
        role = "finisher_shift"
    if role == "body_lore" and keywords and any(k.startswith("Singer ") for k in keywords):
        role = "body_lore"

    return role, caveat


def build_card_dossiers(card_names, cards_db):
    dossiers = {}
    for name in sorted(set(card_names)):
        card = cards_db.get(name)
        if not card:
            continue
        ability = card.get("ability", "") or ""
        card_type = card.get("type", "") or ""
        keywords = _parse_detailed_keywords(ability)
        role, caveat = _infer_role_and_caveat(name, card_type, ability, keywords)
        is_character = "Character" in card_type
        dossiers[name] = {
            "cost": int(card.get("cost", 0) or 0),
            "ink": card.get("ink") or None,
            "type": card_type,
            "body": f"{card.get('str')}/{card.get('will')}" if is_character else None,
            "lore": int(card.get("lore", 0) or 0) if is_character else None,
            "classifications": _parse_classifications(card.get("classifications")),
            "keywords": keywords,
            "ability": ability,
            "role": role,
            "caveat": caveat,
        }
    return dossiers


def build_interactions(card_names, dossiers):
    interactions = []
    names = [name for name in sorted(set(card_names)) if name in dossiers]

    for enabler in names:
        ability = (dossiers[enabler].get("ability") or "").lower()
        keywords = dossiers[enabler].get("keywords") or []
        does_damage = (
            "damage" in ability
            or any(k.startswith("Challenger") for k in keywords)
        )
        if not does_damage:
            continue
        for payoff in names:
            if payoff == enabler:
                continue
            payoff_dossier = dossiers[payoff]
            if payoff_dossier.get("role") != "conditional_wipe":
                continue
            if payoff_dossier.get("caveat") != "requires opponents damaged (needs softener like MMS)":
                continue
            interactions.append({
                "type": "damage_setup",
                "enabler": enabler,
                "payoff": payoff,
                "note": f"{enabler} softens the board -> {payoff} banishes damaged",
            })

    base_by_name = defaultdict(list)
    for name in names:
        base = name.split(" - ")[0]
        base_by_name[base].append(name)
    for base, cards in base_by_name.items():
        shift_targets = []
        bases = []
        for name in cards:
            dossier = dossiers[name]
            shift_kw = next((kw for kw in dossier.get("keywords", []) if kw.startswith("Shift ")), None)
            if shift_kw:
                shift_targets.append((name, int(shift_kw.split()[1])))
            else:
                bases.append(name)
        for base_card in bases:
            for shift_name, shift_cost in shift_targets:
                raw_cost = dossiers[shift_name]["cost"]
                interactions.append({
                    "type": "shift_chain",
                    "base": base_card,
                    "into": shift_name,
                    "shift_cost": shift_cost,
                    "raw_cost": raw_cost,
                    "saved": raw_cost - shift_cost,
                })

    for singer in names:
        singer_kw = next((kw for kw in dossiers[singer].get("keywords", []) if kw.startswith("Singer ")), None)
        if not singer_kw:
            continue
        singer_cost = int(singer_kw.split()[1])
        for song in names:
            song_type = dossiers[song].get("type") or ""
            if "Song" not in song_type:
                continue
            song_cost = dossiers[song].get("cost") or 0
            if song_cost <= singer_cost:
                interactions.append({
                    "type": "song_enable",
                    "singer": singer,
                    "song": song,
                    "note": f"{singer} sings {song} for 0 ink",
                })

    for engine in names:
        ability = dossiers[engine].get("ability") or ""
        if "you played a Princess" not in ability:
            continue
        enablers = [
            name for name in names
            if name != engine and "Princess" in (dossiers[name].get("classifications") or [])
        ]
        if enablers:
            interactions.append({
                "type": "conditional_trigger",
                "engine": engine,
                "enabler_type": "Princess",
                "candidate_enablers": enablers,
            })

    deduped = []
    seen = set()
    for interaction in interactions:
        key = json.dumps(interaction, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(interaction)
    return deduped


def aggregate_playbook(digests):
    if not digests:
        return {}

    matchup_breakdown = []
    our_cards_freq = Counter()
    our_cards_turn_sum = {}
    threat_response = defaultdict(lambda: Counter())
    threat_response_turn = defaultdict(lambda: {})

    total_games = 0
    total_wins = 0

    w_songs_weighted = 0.0
    l_songs_weighted = 0.0
    w_removal_weighted = 0.0
    l_removal_weighted = 0.0
    w_first_song_weighted = 0.0
    w_first_song_games = 0
    l_first_song_weighted = 0.0
    l_first_song_games = 0

    dis_rate_weighted = 0.0
    dis_types = Counter()
    stripped_all = Counter()
    songs_stripped_pct_weighted = 0.0

    combo_stats = defaultdict(lambda: {
        "games": 0, "wins": 0, "total_rate_pct_weighted": 0.0,
        "total_weight": 0, "singers": Counter(), "singer_best": Counter(),
        "singer_trap": Counter(),
    })

    neut_stats = defaultdict(lambda: {"count": 0, "turn_weighted": 0.0, "type": set()})

    for d in digests:
        n = d.get("games", 0)
        wins = d.get("wins", 0)
        if n <= 0:
            continue
        total_games += n
        total_wins += wins

        matchup = d.get("matchup", "") or ""
        opp_sigla = matchup.split(" vs ")[1].strip() if " vs " in matchup else "?"

        pb = d.get("our_playbook", {})

        for c in pb.get('our_key_combos', []) or []:
            for card in c.get('cards', []) or []:
                our_cards_freq[canon(card)] += c.get('games', 0)
        for opp_card, ndata in (pb.get('our_neutralizations') or {}).items():
            opp_card_c = canon(opp_card)
            for remover, info in (ndata.get('neutralized_by') or {}).items():
                cnt = info.get('count', 0)
                avg_t = info.get('avg_turn', 0)
                if remover.startswith('challenge:'):
                    remover_card = canon(remover.replace('challenge:', ''))
                    remover_key = f'challenge:{remover_card}'
                    our_cards_freq[remover_card] += cnt
                    threat_response[opp_card_c][remover_key] += cnt
                    if avg_t:
                        threat_response_turn[opp_card_c][remover_key] = avg_t
                else:
                    remover_c = canon(remover)
                    our_cards_freq[remover_c] += cnt
                    threat_response[opp_card_c][remover_c] += cnt
                    if avg_t:
                        threat_response_turn[opp_card_c][remover_c] = avg_t
        stripped = (pb.get('our_disruption') or {}).get('cards_stripped', {}) or {}
        for card, cnt in stripped.items():
            our_cards_freq[canon(card)] += cnt

        wr_pct = round(wins / n * 100, 1) if n else 0
        top_rem = []
        for opp_card, ndata in list((pb.get('our_neutralizations') or {}).items())[:4]:
            rems = ndata.get('neutralized_by') or {}
            best = max(rems.items(), key=lambda kv: kv[1].get('count', 0), default=None)
            if best and best[1].get('count', 0) >= 3:
                top_rem.append({
                    'threat': canon(opp_card),
                    'answer': canon(best[0]) if not best[0].startswith('challenge:')
                              else f"challenge:{canon(best[0].replace('challenge:',''))}",
                    'count': best[1]['count'],
                    'avg_turn': best[1].get('avg_turn'),
                })
        top_combos = []
        for c in (pb.get('our_key_combos') or [])[:2]:
            if c.get('games', 0) >= 3:
                top_combos.append({
                    'cards': [canon(x) for x in (c.get('cards', []) or [])],
                    'games': c['games'],
                    'wr': c.get('wr', 0),
                })
        matchup_breakdown.append({
            'opp': opp_sigla,
            'games': n,
            'wins': wins,
            'wr_pct': wr_pct,
            'top_removers': top_rem,
            'key_combos': top_combos,
        })

        wb = pb.get("our_win_behavior", {})
        w = wb.get("wins", {})
        l = wb.get("losses", {})
        if w:
            w_songs_weighted += w.get("songs_per_game", 0) * wins
            w_removal_weighted += w.get("removal_per_game", 0) * wins
            if w.get("first_song_turn") is not None:
                w_first_song_weighted += w["first_song_turn"] * wins
                w_first_song_games += wins
        if l:
            losses_n = n - wins
            l_songs_weighted += l.get("songs_per_game", 0) * losses_n
            l_removal_weighted += l.get("removal_per_game", 0) * losses_n
            if l.get("first_song_turn") is not None:
                l_first_song_weighted += l["first_song_turn"] * losses_n
                l_first_song_games += losses_n

        dis = pb.get("our_disruption", {})
        rate = dis.get("rate_pct", 0)
        dis_rate_weighted += rate * n
        if dis.get("type"):
            dis_types[dis["type"]] += n
        for card, cnt in (dis.get("cards_stripped") or {}).items():
            stripped_all[canon(card)] += cnt
        songs_stripped_pct_weighted += dis.get("songs_stripped_pct", 0) * n

        for c in pb.get("our_key_combos", []) or []:
            canon_cards = [canon(x) for x in (c.get("cards", []) or [])]
            key = tuple(sorted(canon_cards))
            if not key:
                continue
            st = combo_stats[key]
            g = c.get("games", 0)
            wr = c.get("wr", 0)
            st["games"] += g
            st["wins"] += int(round(g * wr / 100)) if g and wr else 0
            st["total_rate_pct_weighted"] += c.get("rate_pct", 0) * n
            st["total_weight"] += n
            for s in c.get("singers", []) or []:
                sname = canon(s.get("singer", ""))
                verdict = s.get("verdict", "")
                sg = s.get("games", 0)
                if sname:
                    st["singers"][sname] += sg
                    if verdict == "best":
                        st["singer_best"][sname] += sg
                    elif verdict == "trap":
                        st["singer_trap"][sname] += sg

        for opp_card, ndata in (pb.get("our_neutralizations") or {}).items():
            opp_c = canon(opp_card)
            for remover, info in (ndata.get("neutralized_by") or {}).items():
                if remover.startswith("challenge:"):
                    rem_c = f"challenge:{canon(remover.replace('challenge:',''))}"
                else:
                    rem_c = canon(remover)
                k = (opp_c, rem_c)
                cnt = info.get("count", 0)
                neut_stats[k]["count"] += cnt
                avg_t = info.get("avg_turn", 0)
                if avg_t:
                    neut_stats[k]["turn_weighted"] += avg_t * cnt
                if info.get("type"):
                    neut_stats[k]["type"].add(info["type"])

    if total_games == 0:
        return {}

    losses_total = total_games - total_wins

    def _avg(num, denom):
        return round(num / denom, 2) if denom > 0 else None

    out = {
        "total_games": total_games,
        "total_wins": total_wins,
        "overall_wr_pct": round(total_wins / total_games * 100, 1),
        "matchups_count": len(digests),
        "win_behavior": {
            "songs_per_win": _avg(w_songs_weighted, total_wins),
            "songs_per_loss": _avg(l_songs_weighted, losses_total),
            "removal_per_win": _avg(w_removal_weighted, total_wins),
            "removal_per_loss": _avg(l_removal_weighted, losses_total),
            "first_song_win_turn": _avg(w_first_song_weighted, w_first_song_games),
            "first_song_loss_turn": _avg(l_first_song_weighted, l_first_song_games),
        },
        "disruption": {
            "rate_pct_avg": _avg(dis_rate_weighted, total_games),
            "songs_stripped_pct_avg": _avg(songs_stripped_pct_weighted, total_games),
            "dominant_type": dis_types.most_common(1)[0][0] if dis_types else None,
            "top_stripped_cards": [
                {"card": c, "count": n}
                for c, n in stripped_all.most_common(6)
            ],
        },
    }

    combo_list = []
    for key, st in combo_stats.items():
        if st["games"] < 3:
            continue
        wr = round(st["wins"] / st["games"] * 100, 1) if st["games"] else 0
        rate_pct = round(st["total_rate_pct_weighted"] / st["total_weight"], 1) if st["total_weight"] else 0
        best = st["singer_best"].most_common(1)
        trap = st["singer_trap"].most_common(1)
        combo_list.append({
            "cards": list(key),
            "games": st["games"],
            "wr_pct": wr,
            "play_rate_pct": rate_pct,
            "best_singer": best[0][0] if best else None,
            "trap_singer": trap[0][0] if trap else None,
        })
    combo_list.sort(key=lambda c: -c["games"])
    out["key_combos"] = combo_list[:5]

    neut_list = []
    for (opp_card, remover), s in neut_stats.items():
        if s["count"] < 5:
            continue
        neut_list.append({
            "opp_card": opp_card,
            "remover": remover,
            "count": s["count"],
            "avg_turn": round(s["turn_weighted"] / s["count"], 1) if s["count"] else None,
            "types": sorted(s["type"]),
        })
    neut_list.sort(key=lambda x: -x["count"])
    out["top_neutralizations"] = neut_list[:8]

    out["our_top_cards"] = [
        {"card": card, "signal_count": cnt}
        for card, cnt in our_cards_freq.most_common(15)
    ]

    threat_map = []
    for opp_card, responders in threat_response.items():
        total_cnt = sum(responders.values())
        if total_cnt < 5:
            continue
        top = responders.most_common(3)
        threat_map.append({
            "threat": opp_card,
            "total_responses": total_cnt,
            "top_answers": [
                {"card": r, "count": c, "avg_turn": threat_response_turn[opp_card].get(r)}
                for r, c in top
            ],
        })
    threat_map.sort(key=lambda x: -x["total_responses"])
    out["threat_response_map"] = threat_map[:10]

    matchup_breakdown.sort(key=lambda m: -m["games"])
    out["per_matchup"] = matchup_breakdown

    card_names = set()
    for entry in out.get("our_top_cards", []):
        card_names.add(entry["card"])
    for combo in out.get("key_combos", []):
        for card in combo.get("cards", []) or []:
            card_names.add(card)
    for row in out.get("threat_response_map", []):
        threat = row.get("threat")
        if threat and not str(threat).startswith("challenge:"):
            card_names.add(threat)
        for answer in row.get("top_answers", []):
            card = answer.get("card")
            if card and not str(card).startswith("challenge:"):
                card_names.add(card)

    try:
        with open(CARDS_DB_PATH, encoding="utf-8") as f:
            cards_db = json.load(f)
    except Exception:
        cards_db = {}

    dossiers = build_card_dossiers(card_names, cards_db)
    out["card_dossiers"] = dossiers
    out["interactions"] = build_interactions(card_names, dossiers)

    return out


# ---------------------------------------------------------------------------
# 2. PRO PLAYERS
# ---------------------------------------------------------------------------

def _normalize_deck_key(k):
    return DECK_ALIAS.get(k, k)


def load_pro_references(deck, game_format, min_games=20, top_n=3):
    if not DASHBOARD_DATA.exists():
        return []
    try:
        with open(DASHBOARD_DATA) as f:
            data = json.load(f)
    except Exception:
        return []

    pros = data.get("pro_players", []) or []
    refs = []
    for p in pros:
        decks = p.get("decks", {}) or {}
        decks_norm = {_normalize_deck_key(k): v for k, v in decks.items()}
        entry = decks_norm.get(deck)
        if not entry:
            continue
        w = entry.get("w", 0)
        l = entry.get("l", 0)
        g = w + l
        if g < min_games:
            continue
        wr = round(w / g * 100, 1) if g else 0
        refs.append({
            "name": p.get("name", "?"),
            "games": g,
            "wr_pct": wr,
            "wins": w, "losses": l,
        })
    refs.sort(key=lambda r: (-r["wr_pct"], -r["games"]))
    return refs[:top_n]


# ---------------------------------------------------------------------------
# 3. WEEKLY TECH DIFF
# ---------------------------------------------------------------------------

def _closest_snapshot(target_date):
    candidates = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    best = None
    best_delta = timedelta(days=999)
    for p in candidates:
        try:
            ds = p.stem.replace("snapshot_", "")
            d = datetime.strptime(ds, "%Y%m%d").date()
            delta = abs(d - target_date)
            if delta < best_delta:
                best = p
                best_delta = delta
        except Exception:
            continue
    return best


def _top_card_counter(archetype_entries, max_decks=5):
    c = Counter()
    decks_counted = 0
    for entry in (archetype_entries or [])[:max_decks]:
        for card in entry.get("cards", []):
            c[card.get("name", "")] += card.get("qty", 0)
        decks_counted += 1
    if decks_counted == 0:
        return {}
    return {name: round(v / decks_counted, 2) for name, v in c.items() if name}


def weekly_tech_diff(deck, today=None):
    if today is None:
        today = datetime.now().date()
    prev = today - timedelta(days=7)

    today_snap = _closest_snapshot(today)
    prev_snap = _closest_snapshot(prev)

    if not today_snap or not prev_snap or today_snap == prev_snap:
        return {"new_tech": [], "dropped_tech": [], "unchanged_core": [],
                "today_snap": str(today_snap.name) if today_snap else None,
                "prev_snap": str(prev_snap.name) if prev_snap else None}

    try:
        t_data = json.load(open(today_snap))
        p_data = json.load(open(prev_snap))
    except Exception:
        return {"new_tech": [], "dropped_tech": [], "unchanged_core": [],
                "today_snap": None, "prev_snap": None}

    t_decks = t_data.get("archetypes", {}).get(deck) or []
    p_decks = p_data.get("archetypes", {}).get(deck) or []
    t_cards = _top_card_counter(t_decks)
    p_cards = _top_card_counter(p_decks)

    new_tech = []
    dropped_tech = []
    unchanged = []
    all_cards = set(t_cards) | set(p_cards)
    for c in all_cards:
        tq = t_cards.get(c, 0)
        pq = p_cards.get(c, 0)
        delta = round(tq - pq, 2)
        if tq > 0 and pq == 0:
            new_tech.append({"card": c, "avg_qty_now": tq, "delta": delta})
        elif tq == 0 and pq > 0:
            dropped_tech.append({"card": c, "avg_qty_prev": pq, "delta": delta})
        elif abs(delta) >= 1.0 and tq > 0 and pq > 0:
            (new_tech if delta > 0 else dropped_tech).append({
                "card": c, "delta": delta,
                "avg_qty_now": tq, "avg_qty_prev": pq,
            })
        else:
            if tq >= 3.0:
                unchanged.append({"card": c, "avg_qty": tq})

    new_tech.sort(key=lambda x: -abs(x.get("delta", 0)))
    dropped_tech.sort(key=lambda x: -abs(x.get("delta", 0)))
    unchanged.sort(key=lambda x: -x["avg_qty"])

    return {
        "today_snap": today_snap.name,
        "prev_snap": prev_snap.name,
        "today_decks_count": len(t_decks),
        "prev_decks_count": len(p_decks),
        "new_tech": new_tech[:6],
        "dropped_tech": dropped_tech[:6],
        "unchanged_core": unchanged[:10],
    }


# ---------------------------------------------------------------------------
# 4. PROMPT BUILDERS — ENGLISH ONLY
# ---------------------------------------------------------------------------

def build_blind_prompt(deck, game_format, aggregated, pro_refs, tech_diff):
    """Assemble the v1 blind guide prompt. Kept for backward compatibility
    even though generate_playbook() uses the v2 narrative path. English-only.
    """
    colors = DECK_COLORS.get(deck, "?")
    fmt_label = "Infinity" if game_format == "infinity" else "Core-Constructed"

    our_top = aggregated.get("our_top_cards", [])[:12]
    threat_map = aggregated.get("threat_response_map", [])[:8]
    per_matchup = aggregated.get("per_matchup", [])
    combos = aggregated.get("key_combos", [])[:5]

    prompt_parts = [
        f"You are an expert Lorcana tactical coach. Write a BLIND guide (how you pilot G1 without knowing the opponent) for {deck} ({colors}) in {fmt_label}.",
        "",
        "The reader wants to know CONCRETELY how to play the deck: card names, specific turns, real sequences, how pros pilot it.",
        "DO NOT write abstract averages (e.g. 'avg 0.32 songs', 'removal 3.4 vs 3.65'). Write card names and turns.",
        "",
        "REQUIRED STYLE (abstract template — replace with the cards present IN THE DATA below):",
        "  - '<T_setup> <ramp-card> -> <T_setup+1> <draw-card> + <payoff-card-from-top>'",
        "  - '<removal-card> neutralizes <opp-threat> (<count>x at turn <avg_turn>)'",
        "  - 'Close with <finisher-card> challenge on <opp-threat> (<count> times T<X>)'",
        "ANTI-EXAMPLES (do not write like this):",
        "  - 'Songs per game: 0.32 vs 0.22 in losses' (abstract average)",
        "  - 'Stabilize the board and convert advantage' (vague)",
        "",
        "VOCABULARY RULE:",
        "  Use ONLY the cards present in 'OUR MOST PLAYED CARDS', 'KEY COMBOS' and as 'answer' in 'THREAT MAP'.",
        "  The 'threat' entries in 'THREAT MAP' are opponent cards (allowed in threat_answers[*].threat).",
        "  If the data does not contain the right card for a sentence, do NOT invent it: write 'no reliable answer' or omit the point.",
        "",
        "=== OUR MOST PLAYED CARDS (cross-matchup, from combo + stripped + remover) ===",
        json.dumps(our_top, indent=2, ensure_ascii=False),
        "",
        "=== KEY COMBOS (real rate + WR, with preferred singer) ===",
        json.dumps(combos, indent=2, ensure_ascii=False),
        "",
        "=== THREAT MAP -> ANSWERS (what neutralizes what, and with which of our cards) ===",
        json.dumps(threat_map, indent=2, ensure_ascii=False),
        "",
        "=== PER-MATCHUP BREAKDOWN (what varies vs each opponent deck) ===",
        json.dumps(per_matchup, indent=2, ensure_ascii=False),
        "",
        "=== REFERENCE PRO PLAYERS (names + records) ===",
        json.dumps(pro_refs, indent=2, ensure_ascii=False),
        "",
        "=== WEEKLY TECH (decklist diff, last 7 days) ===",
        json.dumps(tech_diff, indent=2, ensure_ascii=False),
        "",
        "=== CARD DOSSIERS (ability text + role + caveat) ===",
        json.dumps(aggregated.get("card_dossiers", {}), indent=2, ensure_ascii=False),
        "",
        "=== INTERACTIONS (why the combos work) ===",
        json.dumps(aggregated.get("interactions", []), indent=2, ensure_ascii=False),
        "",
        "=== OUTPUT INSTRUCTIONS (strict JSON, no markdown, no prose outside) ===",
        "",
        "{",
        f'  "deck": "{deck}",',
        f'  "format": "{game_format}",',
        f'  "colors": "{colors}",',
        '  "summary": "2-3 concrete sentences: archetype + win condition with key card names (ONLY from the data above) + average time to close.",',
        '  "mulligan_blind": {',
        '    "always_keep": ["<3-4 card names from the data above: ramp/draw/setup>"],',
        '    "keep_if_otp": ["<extra cards if on the play, from data>"],',
        '    "keep_if_otd": ["<extra cards if on the draw, from data>"],',
        '    "never_keep": ["<cards you never want in opening hand, from data>"]',
        '  },',
        '  "target_curves": {',
        '    "T1": "<card played from data; if none plausible: \\"pass / ink\\">",',
        '    "T2": "<card from data (with explicit combo if one exists)>",',
        '    "T3": "<...>", "T4": "<...>", "T5": "<...>"',
        '  },',
        '  "win_condition": "How you close: concrete sequence with card names TAKEN FROM THE DATA ABOVE. Typical observed closing turn.",',
        '  "plan_b": "If plan A is disrupted: alternative cards FROM THE DATA ABOVE (do not invent).",',
        '  "key_combos": [',
        '    {"cards": ["<card A>", "<card B>"], "timing": "T<x>-T<y>", "why": "<1 sentence + real numbers from the KEY COMBOS block>", "wr_cited": <number from KEY COMBOS>, "best_singer": "<X if cited, otherwise null>"}',
        '  ],',
        '  "threat_answers": [',
        '    {"threat": "<opponent card from the THREAT MAP block>", "answer": "<our answer card from the block + numbers (count+turn)>", "note": "<1 line>"}',
        '  ],',
        '  "trap_plays": [',
        '    {"what": "<concrete trap with card names FROM DATA>", "why": "<reason>"}',
        '  ],',
        '  "pro_style": "Short paragraph: how the cited pros pilot THIS deck. If you have valid pro_references, name them and hypothesize their style from data. If pro_references is empty -> exact string \\"no reliable pro data\\".",',
        '  "weekly_tech_notes": "Impact of new tech on opening hand / curve. If no change: exact string \\"no significant shift\\".",',
        '  "pro_references": [',
        '    {"player": "<exact name from the provided pro_refs>", "wr_pct": <num>, "games": <num>, "hint": "<1-line observation>"}',
        '  ],',
        '  "blind_checklist_5": [',
        '    "<5 concrete one-liners citing cards FROM THE DATA ABOVE, 1 per line, <= 100 characters>"',
        '  ]',
        '}',
        "",
        "STRICT RULES:",
        f"1. EVERY one of our cards you mention MUST appear in the 'OUR MOST PLAYED CARDS', 'KEY COMBOS' or as 'answer' in 'THREAT MAP'. Zero exceptions. If it's not there, do NOT invent it.",
        f"2. Allowed colors for our cards: {colors}. Citing cards outside these colors in mulligan/target_curves/key_combos/blind_checklist_5/win_condition/plan_b/trap_plays = critical error.",
        "3. In threat_answers: 'threat' = opponent card (from THREAT MAP), 'answer' = our card (from our pool).",
        "4. Quote numbers ONLY if they are present in the provided data (e.g. 'WR 77.4%' if wr in JSON = 77.4; '7x T7.7' if count=7, avg_turn=7.7). Never fabricate numbers.",
        "5. NO generic phrases like 'develop resources' or 'trade efficiently'. Card names and turns, or nothing.",
        "6. pro_style: if pro_references is empty, write EXACTLY \"no reliable pro data\" — no invented paragraph.",
        "7. blind_checklist_5: exactly 5 bullets, concrete, <= 100 characters, each citing at least 1 card from the data.",
        "8. weekly_tech_notes: if new_tech/dropped_tech is empty, write EXACTLY \"no significant shift\".",
        "9. If an opponent card appears frequently (in threat_response_map) it is a THREAT to deal with -> mention it in threat_answers.",
        "10. FORBIDDEN to use as example-guide cards that are NOT in the data blocks of this deck (no cross-deck contamination).",
        "11. For EVERY card cited, reason starting from ability and role in the dossier. Do not invent effects.",
        "12. For EVERY proposed combo, also implicitly cite the interactions entry that explains the mechanic.",
        "13. If a card has a caveat, mention it in trap_plays or plan_b.",
        "14. If a card has role=finisher_shift and interactions has shift_chain: explain the shift_base -> shift_into sequence and the ink saved.",
        "15. Do not write 'wipe the board' if the card's role does not include wipe / banish / etb_removal. Do not call finisher a card with role=ink_engine or tutor_*.",
    ]
    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# 4b. NARRATIVE PROMPT (v2) — prose, whitelist + grounding. English only.
# ---------------------------------------------------------------------------

def _get_card_ink_map():
    if "ink_map" not in _CANONICAL_CACHE or _CANONICAL_CACHE.get("ink_map") is None:
        with open(CARDS_DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
        _CANONICAL_CACHE["ink_map"] = {name: (entry.get("ink") or "").strip() for name, entry in db.items()}
    return _CANONICAL_CACHE["ink_map"]


def _card_matches_deck(card_name, deck_colors_str):
    ink_map = _get_card_ink_map()
    ink = ink_map.get(card_name, "").strip()
    if not ink:
        return False
    if ink.lower() == "dual ink":
        return True
    deck_colors = {c.strip().lower() for c in deck_colors_str.split(",")}
    card_inks = {p.strip().lower() for p in ink.replace("/", ",").split(",") if p.strip()}
    if not card_inks:
        return False
    return card_inks.issubset(deck_colors)


def build_narrative_whitelists(aggregated, deck_colors_str):
    SIGNAL_MIN = 30

    our_candidates = set()
    for c in aggregated.get("our_top_cards", []) or []:
        if c.get("signal_count", 0) >= SIGNAL_MIN and c.get("card"):
            our_candidates.add(c["card"].strip())
    for c in aggregated.get("key_combos", []) or []:
        for card in (c.get("cards") or []):
            if card: our_candidates.add(card.strip())
        for k in ("best_singer", "trap_singer"):
            v = c.get(k)
            if v: our_candidates.add(v.strip())
    for inter in aggregated.get("interactions", []) or []:
        for k in ("enabler", "payoff", "base", "into"):
            v = inter.get(k)
            if v: our_candidates.add(v.strip())
    for t in aggregated.get("threat_response_map", []) or []:
        for a in (t.get("top_answers") or []):
            card = a.get("card", "")
            if card.startswith("challenge:"):
                card = card.split(":", 1)[1]
            if card: our_candidates.add(card.strip())
    for n in aggregated.get("top_neutralizations", []) or []:
        if n.get("remover"): our_candidates.add(n["remover"].strip())

    our = {c for c in our_candidates if _card_matches_deck(c, deck_colors_str)}

    opp = set()
    for t in aggregated.get("threat_response_map", []) or []:
        if t.get("threat"):
            opp.add(t["threat"].strip())
    for n in aggregated.get("top_neutralizations", []) or []:
        if n.get("opp_card"):
            opp.add(n["opp_card"].strip())

    return {"our": our, "opp": opp}


def build_narrative_whitelist(aggregated):
    """DEPRECATED: backward-compat shim."""
    wls = build_narrative_whitelists(aggregated, "")
    return wls["our"] | wls["opp"]


def build_narrative_prompt(deck, game_format, aggregated, pro_refs, prev_error=None):
    """V2 prompt — produces `narrative` (prose) + `cards_mentioned`. English only."""
    colors = DECK_COLORS.get(deck, "?")
    fmt_label = "Infinity" if game_format == "infinity" else "Core-Constructed"

    top_cards = [c["card"] for c in (aggregated.get("our_top_cards") or [])[:12]]
    combos = []
    for c in (aggregated.get("key_combos") or [])[:5]:
        combos.append({
            "cards": c.get("cards"),
            "games": c.get("games"),
            "wr_pct": c.get("wr_pct"),
            "play_rate_pct": c.get("play_rate_pct"),
            "best_singer": c.get("best_singer"),
            "trap_singer": c.get("trap_singer"),
        })
    threats = []
    for t in (aggregated.get("threat_response_map") or [])[:8]:
        threats.append({
            "threat": t.get("threat"),
            "top_answers": [
                {"card": a.get("card"), "count": a.get("count"), "avg_turn": a.get("avg_turn")}
                for a in (t.get("top_answers") or [])[:2]
            ],
        })

    wb_raw = aggregated.get("win_behavior", {}) or {}
    wb_filtered = {}
    stat_pairs = [
        ("songs_per_win", "songs_per_loss", "songs"),
        ("removal_per_win", "removal_per_loss", "removal"),
        ("first_song_win_turn", "first_song_loss_turn", "first_song_turn"),
    ]
    for win_key, loss_key, label in stat_pairs:
        wv, lv = wb_raw.get(win_key), wb_raw.get(loss_key)
        if wv is None or lv is None:
            continue
        if "turn" in label:
            if round(wv) == round(lv):
                continue
            wb_filtered[f"{label}_win_rounded"] = round(wv)
            wb_filtered[f"{label}_loss_rounded"] = round(lv)
        else:
            if math.floor(wv) == math.floor(lv):
                continue
            wb_filtered[f"{label}_win_floor"] = math.floor(wv)
            wb_filtered[f"{label}_loss_floor"] = math.floor(lv)
    if len(wb_filtered) < len([k for k in stat_pairs if wb_raw.get(k[0]) is not None]):
        wb_filtered["_note"] = "some win/loss statistics omitted because not discriminating after rounding"

    interactions_raw = aggregated.get("interactions", []) or []
    interactions = []
    for inter in interactions_raw:
        card_keys = ("enabler", "payoff", "base", "into", "engine")
        cards_involved = [inter.get(k) for k in card_keys if inter.get(k)]
        for ce in (inter.get("candidate_enablers") or []):
            cards_involved.append(ce)
        if cards_involved and all(not _card_matches_deck(c, colors) for c in cards_involved):
            continue
        if "candidate_enablers" in inter:
            inter = dict(inter)
            inter["candidate_enablers"] = [
                ce for ce in inter["candidate_enablers"] if _card_matches_deck(ce, colors)
            ]
            if not inter["candidate_enablers"] and inter.get("type") == "conditional_trigger":
                continue
        interactions.append(inter)
    win_behavior = wb_filtered
    total_games = aggregated.get("total_games", 0)
    overall_wr = aggregated.get("overall_wr_pct", 0)

    wls = build_narrative_whitelists(aggregated, colors)
    our_cards_list = sorted(wls["our"])
    opp_cards_list = sorted(wls["opp"])

    parts = [
        f"You are a Lorcana coach. Write a BLIND guide as PROSE for {deck} ({colors}) in {fmt_label}.",
        "",
        "GOAL: 220-260 words in fluent English, flowing prose (2-3 paragraphs), ZERO bullet points.",
        "ACCEPTABLE MINIMUM: 180 words, MAXIMUM 320. Out of range = rejected.",
        "The reader is a pilot who wants to understand in 60 seconds how the deck plays — without knowing what's on the other side.",
        "",
        "CARDINAL PRINCIPLE — NON-ATTACKABILITY:",
        "Every claim must be anchored to the data below. If there is no anchor, OMIT that point.",
        "But do NOT drop whole coverage areas: the data below covers several levers (2+ combos, shift chain, singer, win/loss pattern) and you MUST touch them.",
        "",
        f"=== AGGREGATE STATS ({total_games} games, WR {overall_wr}%) ===",
        json.dumps(win_behavior, indent=2, ensure_ascii=False),
        "",
        "=== KEY COMBOS (games = sample size, wr_pct = real WR) ===",
        json.dumps(combos, indent=2, ensure_ascii=False),
        "",
        "=== THREAT MAP -> ANSWERS (avg_turn = OBSERVED average turn) ===",
        json.dumps(threats, indent=2, ensure_ascii=False),
        "",
        "=== INTERACTIONS (explain shift/combo mechanics) ===",
        json.dumps(interactions, indent=2, ensure_ascii=False),
        "",
        f"=== OUR CARDS (single pool for 'our' role — {colors}) ===",
        json.dumps(our_cards_list, ensure_ascii=False),
        "",
        "=== OPPONENT CARDS (single pool for 'opp' role — citable ONLY as threats) ===",
        json.dumps(opp_cards_list, ensure_ascii=False),
        "",
        "=== PRO PLAYERS (only if relevant, citable by name) ===",
        json.dumps(pro_refs, indent=2, ensure_ascii=False),
        "",
        "=== OUTPUT FORMAT (strict JSON) ===",
        "{",
        '  "narrative": "2-3 paragraphs of prose, 220-280 words, fluent English",',
        '  "our_cards_cited": ["<OUR cards cited in the narrative (from the OUR CARDS pool)>"],',
        '  "opp_cards_cited": ["<OPPONENT cards cited as threats (from the OPPONENT CARDS pool)>"]',
        "}",
        "",
        "STRICT RULES:",
        "1. OUR: every card you cite as a deck asset (combo, singer, shift, our removal) MUST be in OUR CARDS. Zero exceptions.",
        "1b. OPP: every card cited as a THREAT (e.g. 'against Ariel', 'answer Hades') MUST be in OPPONENT CARDS.",
        "1c. Never invert: never use a name from OPPONENT CARDS as our synergy/enabler/singer. This is the worst error.",
        "2. TURNS: NEVER use decimals (forbidden: 'T5.73', 'T8.9', 'T7.2'). If the datum has decimals, round and write:",
        "   - if integer or close (<=0.2 away): 'T<n>' (e.g. 7.05 -> 'T7', 7.92 -> 'T8')",
        "   - if between two integers: 'between T<n> and T<n+1>' (e.g. 7.5 -> 'between T7 and T8') or 'around T<round>'",
        "   - for a range (multiple turns, different values): 'between T<min> and T<max>' without decimals (e.g. T7.2-T9.0 -> 'between T7 and T9')",
        "   The turn cited MUST derive from a real avg_turn in THREAT MAP or combo data. No invented turns.",
        "3. WIN RATE: if you cite a WR% (e.g. '70.3%'), it MUST be a wr_pct present in KEY COMBOS.",
        "3b. SAMPLE SIZE: do NOT quote absolute game counts (forbidden: 'over 2266 games', '1320 games', 'sample of 730 games'). The WR% is enough. The reader does not want to know how many games: they want to know how to play.",
        "4. NUMBERS — INTEGERS ONLY (except WR% percentages):",
        "   - Turns: NEVER decimals (rule 2 above).",
        "   - Song/removal averages (e.g. 2.09, 1.03, 6.38, 4.6): round DOWN (floor) and write the integer. 2.09 -> 2, 1.03 -> 1, 6.38 -> 6, 4.6 -> 4. Write 'you play on average 2 songs' (not '2.09').",
        "   - Ink saved: already integers (2, 3, etc.), leave as is.",
        "   - ONLY EXCEPTION ALLOWED: WR% can have 1 decimal (70.3%, 62.5%, 80.2%). Here precision matters.",
        "   - IMPORTANT: if rounding down win and loss yields the SAME integer (e.g. win=0.58->0, loss=0.47->0, or win=5.23->5, loss=5.05->5), do NOT cite that comparison. It is a non-discriminating figure and writing it confuses the reader (e.g. '5 removals vs 5' is useless). Omit the statistic or cite only the other lever where there is real difference.",
        "   Writing '1.03 songs' shows a raw figure, not a guide. Always round.",
        "5. NO GENERIC PHRASES: avoid 'stabilize the board', 'convert advantage', 'play ahead of tempo'. Use concrete verbs and cards.",
        "6. ZERO BULLETS: continuous prose, no bullet lists, no numbered lists.",
        "7. our_cards_cited and opp_cards_cited: EXACT list of cited cards, classified correctly according to their role in the narrative.",
        "",
        "MANDATORY COVERAGE (the text must touch ALL these points if the data allows):",
        "  A. At least 2 distinct pairs from KEY COMBOS (not only #1). If you have 3+ combos above 60% WR, cite the second one as a parallel/alternative plan.",
        "  B. Shift chain from INTERACTIONS (base -> into + ink saved), if present.",
        "  C. At least 1 of best_singer and trap_singer, if they appear in the combos.",
        "  D. At least 1 real avg_turn from THREAT MAP to anchor closing timing.",
        "  E. The win vs loss pattern from AGGREGATE STATS (differentiated songs/removal), closing with a synthetic read.",
        "",
        "SUGGESTED STRUCTURE:",
        "  - Par 1: archetype + main engine (combo #1 with WR + sample + real timing) + typical closer",
        "  - Par 2: parallel engine/toolkit (combo #2, shift chain, singer/trap singer)",
        "  - Par 3: win vs loss pattern (song+removal averages) with a final read of the deck",
        "",
        "If a datum is weak (sample <30, small WR delta) it is NOT a valid anchor — do not cite it.",
    ]

    if prev_error:
        parts.extend([
            "",
            "=== RETRY — PREVIOUS ATTEMPT FAILED ===",
            f"Reason: {prev_error}",
            "Redo respecting the constraints.",
        ])

    return "\n".join(parts)


def validate_narrative(parsed, whitelists, min_words=180, max_words=320):
    """Validate v2 narrative output. Messages in English."""
    if not isinstance(parsed, dict):
        return False, "Output is not a dict"
    narrative = parsed.get("narrative")
    our_cited = parsed.get("our_cards_cited")
    opp_cited = parsed.get("opp_cards_cited")
    if not isinstance(narrative, str) or not narrative.strip():
        return False, "'narrative' field missing or empty"
    if not isinstance(our_cited, list):
        return False, "'our_cards_cited' field must be a list"
    if not isinstance(opp_cited, list):
        return False, "'opp_cards_cited' field must be a list"

    our_lower = {w.lower() for w in whitelists.get("our", set())}
    opp_lower = {w.lower() for w in whitelists.get("opp", set())}

    our_offenders = [c.strip() for c in our_cited if isinstance(c, str) and c.strip().lower() not in our_lower]
    if our_offenders:
        misclassified = [c for c in our_offenders if c.lower() in opp_lower]
        if misclassified:
            return False, f"CRITICAL: opponent cards classified as ours in our_cards_cited: {misclassified[:3]} (role error)"
        return False, f"Cards outside OUR CARDS in our_cards_cited: {our_offenders[:5]}"

    opp_offenders = [c.strip() for c in opp_cited if isinstance(c, str) and c.strip().lower() not in opp_lower]
    if opp_offenders:
        return False, f"Cards outside OPPONENT CARDS in opp_cards_cited: {opp_offenders[:5]}"

    text_lower = narrative.lower()
    all_cited = list(our_cited) + list(opp_cited)
    missing = [c for c in all_cited if isinstance(c, str) and c.strip().lower() not in text_lower]
    if missing:
        return False, f"Cards declared but not present in narrative: {missing[:5]}"

    words = len(narrative.split())
    if words < min_words:
        return False, f"Narrative too short ({words} words, minimum {min_words})"
    if words > max_words:
        return False, f"Narrative too long ({words} words, maximum {max_words})"

    return True, None


# ---------------------------------------------------------------------------
# 5. LLM CALL
# ---------------------------------------------------------------------------

def call_openai(prompt, model="gpt-5.4-mini"):
    """Call OpenAI. Reads OPENAI_API_KEY env var, falls back to /tmp/.openai_key."""
    from openai import OpenAI

    if not os.getenv("OPENAI_API_KEY"):
        key_file = Path("/tmp/.openai_key")
        if key_file.exists():
            os.environ["OPENAI_API_KEY"] = key_file.read_text().strip()
        else:
            raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI()
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        max_completion_tokens=8000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system",
             "content": "You output only valid JSON, no markdown, no prose, no code fences. Keep responses concise but complete — all required fields populated, no field left empty."},
            {"role": "user", "content": prompt},
        ],
    )
    elapsed = time.time() - t0
    text = resp.choices[0].message.content
    if text.strip().startswith("```"):
        lines = [l for l in text.strip().split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines)

    usage = resp.usage
    return {
        "text": text,
        "elapsed_sec": round(elapsed, 1),
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }


# ---------------------------------------------------------------------------
# 6. STRATEGIC PASS (pass 2) — English only
# ---------------------------------------------------------------------------

def build_strategic_prompt(deck, game_format, aggregated, playbook, pro_refs):
    """Pass 2 — strategic framing. Returns high-level archetype/tier/skill_dep/
    one_liner/key_principles. English only.
    """
    colors = DECK_COLORS.get(deck, "?")
    fmt_label = "Infinity" if game_format == "infinity" else "Core-Constructed"

    matchup_breakdown = aggregated.get("per_matchup", []) or []
    wrs = [m["wr_pct"] for m in matchup_breakdown if m.get("games", 0) >= 20]
    spread = {
        "best_matchup": max(matchup_breakdown, key=lambda m: m.get("wr_pct", 0), default={}),
        "worst_matchup": min(matchup_breakdown, key=lambda m: m.get("wr_pct", 100), default={}),
        "wr_variance": (max(wrs) - min(wrs)) if wrs else None,
    }
    total_wr = aggregated.get("overall_wr_pct", 0)
    pro_wr_avg = None
    if pro_refs:
        pro_wr_avg = round(sum(p["wr_pct"] for p in pro_refs) / len(pro_refs), 1)
    skill_signal = {
        "total_wr": total_wr,
        "pro_wr_avg": pro_wr_avg,
        "delta_pro_vs_total": (pro_wr_avg - total_wr) if pro_wr_avg is not None else None,
    }

    pb_compact = {
        "narrative": playbook.get("narrative"),
        "cards_mentioned_count": len(playbook.get("cards_mentioned", []) or []),
    }

    parts = [
        f"You are a Lorcana tactical coach. You have the mechanical playbook for {deck} ({colors}) in {fmt_label}, already generated by a first LLM. Your task: add 5 high-level strategic fields, do NOT rewrite the mechanical part.",
        "",
        "=== AGGREGATE STATS ===",
        f"Total games: {aggregated.get('total_games', 0)} | WR: {total_wr}%",
        f"Matchups covered: {aggregated.get('matchups_count', 0)}",
        f"WR spread across matchups (min >=20 games): best {spread['best_matchup'].get('opp','?')} {spread['best_matchup'].get('wr_pct','?')}%, worst {spread['worst_matchup'].get('opp','?')} {spread['worst_matchup'].get('wr_pct','?')}%, variance {spread['wr_variance']}",
        f"Pro references (>=20 games): {len(pro_refs)} player(s){', pro vs total WR delta: ' + str(skill_signal['delta_pro_vs_total']) + '%' if skill_signal['delta_pro_vs_total'] is not None else ''}",
        "",
        "=== MECHANICAL PLAYBOOK (Pass 1 — reference, DO NOT modify) ===",
        json.dumps(pb_compact, indent=2, ensure_ascii=False),
        "",
        "=== EXPECTED OUTPUT (strict JSON, ONLY these 5 fields) ===",
        "{",
        '  "archetype": "aggro | midrange | control | combo | tempo | midrange-control | ramp-combo | ...",',
        '  "tier": "top | competitive | mid | fringe",',
        '  "skill_dependency": "low | medium | high",',
        '  "one_liner": "1 sentence summarising how the deck plays. Concrete (not generic), max 100 characters.",',
        '  "key_principles": [',
        '    "strategic principle 1 — NOT a specific card, but a piloting rule",',
        '    "principle 2",',
        '    "principle 3"',
        "  ]",
        "}",
        "",
        "RULES:",
        "1. archetype: infer from combos and target curves in the mechanical playbook (e.g. finisher-based + tutoring = midrange-control).",
        "2. tier: infer from total WR (>54% top, 50-54% competitive, 46-49% mid, <46% fringe).",
        "3. skill_dependency: if delta_pro_vs_total >= 5% = high; 2-5% = medium; <2% = low. If pro_wr_avg is None: medium by default.",
        "4. one_liner: must capture the overall plan in 1 sentence. No value judgements (no 'strong/weak deck').",
        "5. key_principles: 3 HIGH-LEVEL points (not 'play card X on T4'). Good examples: 'Every turn needs an active tutor', 'Do not commit the finisher without setup', 'Plan B runs on attrition, not on tempo'.",
        "6. FORBIDDEN to cite card names in key_principles (that is the job of the mechanical playbook from Pass 1).",
        "7. Pure JSON output, no markdown, no outside prose, all 5 fields filled. All fields MUST be in fluent English.",
    ]
    return "\n".join(parts)


def run_strategic_pass(deck, game_format, aggregated, playbook, pro_refs, model="gpt-5.4-mini"):
    if not playbook or playbook.get("error"):
        return {"strategic_frame": None, "meta": {"skipped": True, "reason": "pass1_failed"}}
    if not playbook.get("narrative"):
        return {"strategic_frame": None, "meta": {"skipped": True, "reason": "pass1_empty"}}

    prompt = build_strategic_prompt(deck, game_format, aggregated, playbook, pro_refs)
    try:
        resp = call_openai(prompt, model=model)
        parsed = json.loads(resp["text"])
    except Exception as e:
        return {
            "strategic_frame": {"error": "pass2_failed", "detail": str(e)[:200]},
            "meta": {"skipped": False, "error": True},
        }

    cost = (resp["input_tokens"] / 1e6) * 0.75 + (resp["output_tokens"] / 1e6) * 4.50
    return {
        "strategic_frame": parsed,
        "meta": {
            "skipped": False,
            "input_tokens": resp["input_tokens"],
            "output_tokens": resp["output_tokens"],
            "elapsed_sec": resp["elapsed_sec"],
            "estimated_cost_usd": round(cost, 4),
        },
    }


# ---------------------------------------------------------------------------
# 7. ORCHESTRATION — public entry point
# ---------------------------------------------------------------------------

def generate_playbook(deck, game_format="core", use_llm=True, model="gpt-5.4-mini"):
    """Complete pipeline: aggregate -> tech diff -> pro refs -> prompt -> LLM -> JSON.

    Returns a dict payload compatible with playbook_service.upsert_playbook:
      - meta: deck, format, generated_at, digest_count, total_games, model,
              input_tokens, output_tokens, elapsed_sec, estimated_cost_usd
      - aggregated: aggregated stats
      - pro_references: top pros for this deck
      - weekly_tech: new_tech / dropped_tech / unchanged_core
      - playbook: narrative + our_cards_cited + opp_cards_cited (or error)
      - strategic_frame: archetype / tier / skill_dependency / one_liner / key_principles
    """
    digests = load_deck_digests(deck, game_format)
    aggregated = aggregate_playbook(digests)
    pro_refs = load_pro_references(deck, game_format)
    tech_diff = weekly_tech_diff(deck)

    result = {
        "meta": {
            "deck": deck,
            "format": game_format,
            "colors": DECK_COLORS.get(deck, "?"),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "digest_count": len(digests),
            "total_games": aggregated.get("total_games", 0),
            "model": model if use_llm else None,
        },
        "aggregated": aggregated,
        "pro_references": pro_refs,
        "weekly_tech": tech_diff,
        "playbook": None,
    }

    if not use_llm:
        return result

    if len(digests) < 2:
        result["playbook"] = {"error": "data_insufficient", "digests": len(digests)}
        return result

    deck_colors = DECK_COLORS.get(deck, "?")
    whitelists = build_narrative_whitelists(aggregated, deck_colors)
    MAX_ATTEMPTS = 2
    total_in, total_out, total_elapsed = 0, 0, 0.0
    parsed = None
    last_parse_error = None
    validation_error = None
    prev_error = None
    attempt = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = build_narrative_prompt(deck, game_format, aggregated, pro_refs, prev_error=prev_error)
        resp = call_openai(prompt, model=model)
        total_in += resp["input_tokens"]
        total_out += resp["output_tokens"]
        total_elapsed += resp["elapsed_sec"]
        try:
            parsed_try = json.loads(resp["text"])
        except json.JSONDecodeError as e:
            last_parse_error = str(e)
            prev_error = f"Attempt {attempt}: invalid JSON ({last_parse_error})"
            continue
        ok, err = validate_narrative(parsed_try, whitelists)
        if ok:
            parsed = parsed_try
            validation_error = None
            break
        parsed = parsed_try
        validation_error = err
        prev_error = err

    if parsed and parsed.get("narrative"):
        pb = {
            "deck": deck,
            "format": game_format,
            "colors": deck_colors,
            "narrative": parsed.get("narrative"),
            "our_cards_cited": parsed.get("our_cards_cited", []),
            "opp_cards_cited": parsed.get("opp_cards_cited", []),
        }
        if validation_error:
            pb["validation_warning"] = validation_error
        result["playbook"] = pb
    else:
        result["playbook"] = {
            "error": "llm_invalid_json" if last_parse_error else "narrative_empty",
            "parse_error": last_parse_error,
        }

    result["meta"]["elapsed_sec"] = round(total_elapsed, 1)
    result["meta"]["input_tokens"] = total_in
    result["meta"]["output_tokens"] = total_out
    result["meta"]["attempts"] = attempt
    cost_pass1 = (total_in / 1e6) * 0.75 + (total_out / 1e6) * 4.50

    pass2 = run_strategic_pass(deck, game_format, aggregated, result["playbook"], pro_refs, model=model)
    result["strategic_frame"] = pass2["strategic_frame"]
    cost_pass2 = pass2["meta"].get("estimated_cost_usd", 0) or 0
    result["meta"]["pass2"] = pass2["meta"]
    result["meta"]["estimated_cost_usd"] = round(cost_pass1 + cost_pass2, 4)

    return result
