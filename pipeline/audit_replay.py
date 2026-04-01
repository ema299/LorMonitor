#!/usr/bin/env python3
"""
Audit replay: checks archive games against cards_db for data integrity issues.
Runs 8 categories of checks across every turn of every game.
"""

import json
import sys
from collections import defaultdict

ARCHIVE = "/mnt/HC_Volume_104764377/finanza/Lor/Analisi_deck/analisidef/output/archive_AmAm_vs_ES.json"
CARDS_DB = "/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json"

def load_data():
    with open(ARCHIVE) as f:
        archive = json.load(f)
    with open(CARDS_DB) as f:
        db = json.load(f)
    return archive, db

# ── helpers ──────────────────────────────────────────────────────────────────

def card_type(db, name):
    """Return card type or None."""
    if name in db:
        return db[name].get("type", "")
    return None

def is_action_or_song(db, name):
    t = card_type(db, name)
    if t is None:
        return False
    return "Action" in t  # covers "Action" and "Action · Song"

def is_song(db, name):
    t = card_type(db, name)
    if t is None:
        return False
    return "Song" in t

def card_cost(db, name):
    if name in db:
        try:
            return int(db[name]["cost"])
        except (ValueError, KeyError):
            return None
    return None

def base_name(name):
    """'Clarabelle - Light on Her Hooves' -> 'Clarabelle'"""
    return name.split(" - ")[0].strip() if " - " in name else name

# ── CHECK 1: Duplicate challenges ────────────────────────────────────────────

def check_duplicate_challenges(games, db):
    issues = []
    for game in games:
        gid = game["id"]
        for turn in game["turns"]:
            t = turn["t"]
            for side in ["our_challenges", "opp_challenges"]:
                challs = turn.get(side, [])
                if len(challs) < 2:
                    continue
                # Group by (attacker, defender) pair
                pairs = defaultdict(list)
                for i, c in enumerate(challs):
                    key = (c["attacker"], c["defender"])
                    pairs[key].append(i)
                for (atk, dfn), indices in pairs.items():
                    if len(indices) > 1:
                        issues.append({
                            "game": gid, "turn": t, "side": side,
                            "attacker": atk, "defender": dfn,
                            "count": len(indices),
                            "details": [challs[i] for i in indices]
                        })
    return issues

# ── CHECK 2: Non-persistent cards in board_state ─────────────────────────────

def check_non_persistent_in_board(games, db):
    issues = []
    for game in games:
        gid = game["id"]
        for turn in game["turns"]:
            t = turn["t"]
            bs = turn.get("board_state", {})
            for side_key in ["our", "opp"]:
                for card in bs.get(side_key, []):
                    if is_action_or_song(db, card):
                        issues.append({
                            "game": gid, "turn": t, "side": side_key,
                            "card": card, "type": card_type(db, card)
                        })
    return issues

# ── CHECK 3: Ability mismatch ────────────────────────────────────────────────

# Known mismatches we want to flag
ABILITY_MISMATCH_RULES = {
    "Malicious, Mean and Scary": {
        "db_keyword": "each opposing character",
        "log_bad": ["puts 1 damage counter on itself"],
        "description": "Log says 'puts 1 damage on itself' but DB says 'Put 1 damage counter on each opposing character'"
    },
    "Raging Storm": {
        "db_keyword": "Banish all characters",
        "log_bad": ["banishes a card"],
        "description": "Log says 'banishes a card' (singular) but DB says 'Banish all characters' (ALL, both sides)"
    },
    "Elsa - The Fifth Spirit": {
        "db_keyword": "exert chosen opposing character",
        "log_bad": ["exerts a character"],
        "description": "Log says 'exerts a character' (generic) but DB says 'exert chosen opposing character' (must be opposing)"
    },
}

def check_ability_mismatch(games, db):
    issues = []
    # Also do a generic scan: compare log effect text vs DB ability text
    all_mismatches = defaultdict(lambda: {"count": 0, "examples": []})

    for game in games:
        gid = game["id"]
        for turn in game["turns"]:
            t = turn["t"]
            for side in ["our_abilities", "opp_abilities"]:
                for ab in turn.get(side, []):
                    card = ab.get("card", "")
                    effect = ab.get("effect", "")

                    # Check known mismatches
                    if card in ABILITY_MISMATCH_RULES:
                        rule = ABILITY_MISMATCH_RULES[card]
                        for bad in rule["log_bad"]:
                            if bad in effect:
                                key = (card, effect, rule["description"])
                                all_mismatches[key]["count"] += 1
                                if len(all_mismatches[key]["examples"]) < 3:
                                    all_mismatches[key]["examples"].append(
                                        f"Game {gid} T{t} ({side})"
                                    )

                    # Generic: check if card exists in DB and has ability text
                    if card in db:
                        db_ability = db[card].get("ability", "")
                        if db_ability and effect:
                            # Flag if log says "banishes a card" but DB says "banish all"
                            if "banish" in effect.lower() and "all" in db_ability.lower() and "all" not in effect.lower():
                                key = (card, effect, f"DB says: {db_ability[:100]}")
                                all_mismatches[key]["count"] += 1
                                if len(all_mismatches[key]["examples"]) < 3:
                                    all_mismatches[key]["examples"].append(
                                        f"Game {gid} T{t}"
                                    )

    for (card, effect, desc), data in all_mismatches.items():
        issues.append({
            "card": card,
            "log_effect": effect,
            "mismatch": desc,
            "occurrences": data["count"],
            "examples": data["examples"]
        })
    return issues

# ── CHECK 4: Board state after tuck (Under the Sea) ─────────────────────────

def check_board_after_tuck(games, db):
    issues = []
    for game in games:
        gid = game["id"]
        for turn in game["turns"]:
            t = turn["t"]
            for side in ["our_abilities", "opp_abilities"]:
                for ab in turn.get(side, []):
                    effect = ab.get("effect", "")
                    card = ab.get("card", "")
                    if "putting" not in effect or "bottom of deck" not in effect:
                        continue
                    # Parse tucked card names from effect like:
                    # "putting X, Y, Z on bottom of deck"
                    prefix = effect.split("putting")[1].split("on bottom")[0].strip()
                    # Handle "N characters" case
                    if "characters" in prefix:
                        continue  # can't determine names
                    tucked = [c.strip() for c in prefix.split(",") if c.strip()]

                    bs = turn.get("board_state", {})
                    # Determine which board to check: Under the Sea tucks opposing chars
                    # The ability comes from the caster's side, so tucked cards should be
                    # removed from the OPPOSITE board
                    if "our" in side:
                        target_board = bs.get("opp", [])
                        target_side = "opp"
                    else:
                        target_board = bs.get("our", [])
                        target_side = "our"

                    for tucked_card in tucked:
                        if tucked_card in target_board:
                            issues.append({
                                "game": gid, "turn": t, "card": card,
                                "tucked": tucked_card,
                                "still_in_board": target_side,
                                "board": target_board
                            })
    return issues

# ── CHECK 5: Board state after Banish All (Raging Storm) ────────────────────

def check_board_after_banish_all(games, db):
    issues = []
    for game in games:
        gid = game["id"]
        for turn in game["turns"]:
            t = turn["t"]
            for side in ["our_abilities", "opp_abilities"]:
                for ab in turn.get(side, []):
                    card = ab.get("card", "")
                    if card not in db:
                        continue
                    db_ability = db[card].get("ability", "")
                    # Check for "banish all characters" type effects
                    if "banish all characters" not in db_ability.lower():
                        continue

                    bs = turn.get("board_state", {})
                    our_board = bs.get("our", [])
                    opp_board = bs.get("opp", [])

                    # Filter: only characters should be banished, not items/locations
                    remaining_our = [c for c in our_board if card_type(db, c) == "Character"]
                    remaining_opp = [c for c in opp_board if card_type(db, c) == "Character"]

                    if remaining_our or remaining_opp:
                        issues.append({
                            "game": gid, "turn": t, "card": card,
                            "our_chars_remaining": remaining_our,
                            "opp_chars_remaining": remaining_opp,
                            "full_our_board": our_board,
                            "full_opp_board": opp_board
                        })
    return issues

# ── CHECK 6: MMS damage mismatch ────────────────────────────────────────────

def check_mms_damage(games, db):
    """MMS should deal 1 damage to each opposing character.
    Log says 'puts 1 damage counter on itself' which is wrong.
    Check if the opposing board's characters survive when they shouldn't (1 will chars)."""
    issues = []
    for game in games:
        gid = game["id"]
        for turn in game["turns"]:
            t = turn["t"]
            for side in ["our_abilities", "opp_abilities"]:
                for ab in turn.get(side, []):
                    card = ab.get("card", "")
                    effect = ab.get("effect", "")
                    if card != "Malicious, Mean and Scary":
                        continue

                    # MMS deals 1 damage to each OPPOSING character
                    # Check if any 1-will opposing chars survived
                    bs = turn.get("board_state", {})
                    if "our" in side:
                        target_board = bs.get("opp", [])
                        target_side = "opp"
                    else:
                        target_board = bs.get("our", [])
                        target_side = "our"

                    fragile = []
                    for c in target_board:
                        if c in db:
                            will = db[c].get("will", "")
                            try:
                                w = int(will)
                                if w <= 1:
                                    fragile.append(f"{c} (will={w})")
                            except (ValueError, TypeError):
                                pass

                    if fragile:
                        issues.append({
                            "game": gid, "turn": t, "side": side,
                            "fragile_surviving": fragile,
                            "log_effect": effect,
                            "note": "MMS should kill 1-will chars (unless Resist/Ward); log says 'puts 1 damage on itself'"
                        })
    return issues

# ── CHECK 7: Sung validation ────────────────────────────────────────────────

def check_sung_validation(games, db):
    """For every sung play, verify singer exists on board and has enough cost."""
    issues = []
    for game in games:
        gid = game["id"]
        prev_board = {"our": [], "opp": []}

        for turn in game["turns"]:
            t = turn["t"]

            for side_prefix in ["our", "opp"]:
                plays = turn.get(f"{side_prefix}_plays", [])
                # Board at start of this turn (before plays) is tricky.
                # We use prev turn's board_state as the starting board,
                # but characters played THIS turn before the song can also sing.
                # We'll use a running board that adds chars as they're played.

                running_board = list(prev_board.get(side_prefix, []))

                for play in plays:
                    if not play.get("is_sung"):
                        # Add non-song chars to running board for singer availability
                        if not is_action_or_song(db, play["name"]):
                            running_board.append(play["name"])
                        continue

                    song_name = play["name"]
                    singer_name = play.get("singer", "")
                    song_cost = card_cost(db, song_name)

                    if not singer_name:
                        issues.append({
                            "game": gid, "turn": t, "side": side_prefix,
                            "song": song_name, "issue": "NO_SINGER_FIELD",
                            "detail": "is_sung=true but no singer specified"
                        })
                        continue

                    # Check singer on board
                    if singer_name not in running_board:
                        issues.append({
                            "game": gid, "turn": t, "side": side_prefix,
                            "song": song_name, "singer": singer_name,
                            "issue": "SINGER_NOT_ON_BOARD",
                            "board": running_board[:],
                            "detail": f"Singer '{singer_name}' not found on board"
                        })
                        continue

                    # Check singer cost >= song cost (standard singing rule)
                    singer_cost = card_cost(db, singer_name)

                    # Check for Sing Together
                    db_entry = db.get(song_name, {})
                    ability_text = db_entry.get("ability", "")
                    is_sing_together = "Sing Together" in ability_text

                    if is_sing_together:
                        # For Sing Together, sum of character costs must meet threshold
                        # We can't easily check this without knowing which chars contribute
                        # Just flag if single singer cost < song cost and no Singer keyword
                        pass
                    else:
                        # Standard: singer cost >= song cost, OR has Singer keyword
                        if singer_cost is not None and song_cost is not None:
                            singer_db = db.get(singer_name, {})
                            singer_ability = singer_db.get("ability", "")
                            has_singer_keyword = "Singer" in singer_ability

                            if not has_singer_keyword and singer_cost < song_cost:
                                issues.append({
                                    "game": gid, "turn": t, "side": side_prefix,
                                    "song": song_name, "song_cost": song_cost,
                                    "singer": singer_name, "singer_cost": singer_cost,
                                    "issue": "SINGER_COST_TOO_LOW",
                                    "detail": f"Singer cost {singer_cost} < song cost {song_cost} and no Singer keyword"
                                })

            # Update prev_board for next turn
            prev_board = turn.get("board_state", prev_board)

    return issues

# ── CHECK 8: Exert carryover ────────────────────────────────────────────────

def check_exert_carryover(games, db):
    """Characters that quest/challenge at turn N should be exerted during opp's
    half of turn N. They ready at the START of their owner's next turn.

    We check: if our char quests/challenges at turn N, it should NOT be available
    to quest/challenge again at turn N+1 UNLESS it has Rush or was readied somehow.

    Since the archive doesn't track exerted state explicitly, we look for
    chars that quest/challenge on consecutive turns (which would be impossible
    without a ready effect)."""
    issues = []

    for game in games:
        gid = game["id"]
        turns = game["turns"]

        for side_prefix in ["our", "opp"]:
            for i in range(len(turns) - 1):
                curr = turns[i]
                nxt = turns[i + 1]
                curr_t = curr["t"]
                next_t = nxt["t"]

                # Get chars that quested or challenged this turn
                exerted_chars = set()
                for q in curr.get(f"{side_prefix}_quests", []):
                    exerted_chars.add(q["name"])
                for c in curr.get(f"{side_prefix}_challenges", []):
                    exerted_chars.add(c["attacker"])

                if not exerted_chars:
                    continue

                # Check if same chars quest or challenge next turn
                # This is legal because they ready at start of their turn
                # But: if they also SING next turn, they'd be exerting to sing
                # Actually, questing/challenging exerts the character.
                # At the start of their NEXT turn, they ready.
                # So questing T1 then questing T2 is fine (they ready at start of T2).
                #
                # The real check would be: did they do TWO exert-actions in the same turn?
                # Let's check that instead: quest + challenge in same turn, or quest + sing

                same_turn_double = set()
                questers = {q["name"] for q in curr.get(f"{side_prefix}_quests", [])}
                challengers = {c["attacker"] for c in curr.get(f"{side_prefix}_challenges", [])}
                # Singers: chars that sang a song this turn
                singers = set()
                for p in curr.get(f"{side_prefix}_plays", []):
                    if p.get("is_sung") and p.get("singer"):
                        singers.add(p["singer"])

                # Quest + challenge same char same turn
                qc = questers & challengers
                for c in qc:
                    same_turn_double.add((c, "quest+challenge"))
                # Quest + sing same char same turn
                qs = questers & singers
                for c in qs:
                    same_turn_double.add((c, "quest+sing"))
                # Challenge + sing same char same turn
                cs = challengers & singers
                for c in cs:
                    same_turn_double.add((c, "challenge+sing"))
                # Sing twice same char same turn
                singer_list = []
                for p in curr.get(f"{side_prefix}_plays", []):
                    if p.get("is_sung") and p.get("singer"):
                        singer_list.append(p["singer"])
                singer_counts = defaultdict(int)
                for s in singer_list:
                    singer_counts[s] += 1
                for s, cnt in singer_counts.items():
                    if cnt > 1:
                        same_turn_double.add((s, f"sing x{cnt}"))

                for (char, action_type) in same_turn_double:
                    # Check if char has Bodyguard or some ready effect
                    # For now just flag it
                    issues.append({
                        "game": gid, "turn": curr_t, "side": side_prefix,
                        "character": char, "double_exert": action_type,
                        "detail": f"Character exerted twice in same turn: {action_type}"
                    })

    return issues

# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    archive, db = load_data()
    games = archive["games"]
    total_games = len(games)
    total_turns = sum(len(g["turns"]) for g in games)

    print(f"=" * 80)
    print(f"AUDIT REPLAY: {archive['metadata']['our_deck']} vs {archive['metadata']['opp_deck']}")
    print(f"Games: {total_games}  |  Total turns: {total_turns}")
    print(f"=" * 80)

    # Run all checks
    checks = [
        ("1. DUPLICATE CHALLENGES", check_duplicate_challenges(games, db)),
        ("2. NON-PERSISTENT IN BOARD", check_non_persistent_in_board(games, db)),
        ("3. ABILITY MISMATCH", check_ability_mismatch(games, db)),
        ("4. BOARD AFTER TUCK", check_board_after_tuck(games, db)),
        ("5. BOARD AFTER BANISH ALL", check_board_after_banish_all(games, db)),
        ("6. MMS DAMAGE (1-will survivors)", check_mms_damage(games, db)),
        ("7. SUNG VALIDATION", check_sung_validation(games, db)),
        ("8. EXERT CARRYOVER (double exert)", check_exert_carryover(games, db)),
    ]

    print()
    print("SUMMARY")
    print("-" * 60)
    for name, issues in checks:
        print(f"  {name}: {len(issues)} issues")
    print("-" * 60)
    total_issues = sum(len(i) for _, i in checks)
    print(f"  TOTAL: {total_issues} issues")
    print()

    # Detailed output per check
    for name, issues in checks:
        if not issues:
            print(f"\n{'='*60}")
            print(f"{name}: CLEAN (0 issues)")
            continue

        print(f"\n{'='*60}")
        print(f"{name}: {len(issues)} issues")
        print(f"{'='*60}")

        if name == "1. DUPLICATE CHALLENGES":
            # Group by game
            by_game = defaultdict(list)
            for iss in issues:
                by_game[iss["game"]].append(iss)
            games_affected = len(by_game)
            print(f"  Affected games: {games_affected}/{total_games}")
            print()
            for gid in sorted(by_game.keys())[:10]:
                for iss in by_game[gid]:
                    dets = iss["details"]
                    kills = [d.get("def_killed") for d in dets]
                    print(f"  Game {gid} T{iss['turn']} {iss['side']}: "
                          f"{iss['attacker']} -> {iss['defender']}  x{iss['count']}  "
                          f"def_killed={kills}")
            if games_affected > 10:
                print(f"  ... and {games_affected - 10} more games")

        elif name == "2. NON-PERSISTENT IN BOARD":
            for iss in issues[:10]:
                print(f"  Game {iss['game']} T{iss['turn']} {iss['side']}: "
                      f"{iss['card']} (type={iss['type']})")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")

        elif name == "3. ABILITY MISMATCH":
            for iss in issues:
                print(f"\n  Card: {iss['card']}")
                print(f"  Log effect: \"{iss['log_effect']}\"")
                print(f"  Mismatch: {iss['mismatch']}")
                print(f"  Occurrences: {iss['occurrences']}")
                print(f"  Examples: {', '.join(iss['examples'][:5])}")

        elif name == "4. BOARD AFTER TUCK":
            for iss in issues[:10]:
                print(f"  Game {iss['game']} T{iss['turn']}: {iss['card']} tucked "
                      f"'{iss['tucked']}' but still in {iss['still_in_board']} board")
                print(f"    Board: {iss['board']}")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")

        elif name == "5. BOARD AFTER BANISH ALL":
            for iss in issues[:10]:
                print(f"  Game {iss['game']} T{iss['turn']}: {iss['card']} should clear all chars")
                if iss["our_chars_remaining"]:
                    print(f"    Our chars remaining: {iss['our_chars_remaining']}")
                if iss["opp_chars_remaining"]:
                    print(f"    Opp chars remaining: {iss['opp_chars_remaining']}")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")

        elif name == "6. MMS DAMAGE (1-will survivors)":
            for iss in issues[:10]:
                print(f"  Game {iss['game']} T{iss['turn']} ({iss['side']}): "
                      f"fragile chars surviving: {iss['fragile_surviving']}")
                print(f"    Log: \"{iss['log_effect']}\"")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")

        elif name == "7. SUNG VALIDATION":
            by_type = defaultdict(list)
            for iss in issues:
                by_type[iss["issue"]].append(iss)
            for issue_type, sub_issues in by_type.items():
                print(f"\n  [{issue_type}] ({len(sub_issues)} cases)")
                for iss in sub_issues[:5]:
                    print(f"    Game {iss['game']} T{iss['turn']} {iss['side']}: "
                          f"song={iss['song']}, singer={iss.get('singer','N/A')}")
                    if "board" in iss:
                        print(f"      Board: {iss['board']}")
                    print(f"      {iss['detail']}")
                if len(sub_issues) > 5:
                    print(f"    ... and {len(sub_issues) - 5} more")

        elif name == "8. EXERT CARRYOVER (double exert)":
            by_type = defaultdict(list)
            for iss in issues:
                by_type[iss["double_exert"]].append(iss)
            for action_type, sub_issues in by_type.items():
                print(f"\n  [{action_type}] ({len(sub_issues)} cases)")
                for iss in sub_issues[:5]:
                    print(f"    Game {iss['game']} T{iss['turn']} {iss['side']}: "
                          f"{iss['character']}")
                if len(sub_issues) > 5:
                    print(f"    ... and {len(sub_issues) - 5} more")

if __name__ == "__main__":
    main()
