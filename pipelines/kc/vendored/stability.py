"""Stability evaluator for killer curves vs current digest.

Vendorized from analisidef/test_kc/src/stability.py.
Adapted: reads digest from App_tool/output/digests/, KC from PG.
"""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DIGEST_DIR = _PROJECT_ROOT / "output" / "digests"

MIN_LOSSES = 50
MIN_LOSSES_INF = 20
DECKS = "AmAm AmSa EmSa AbE AbS AbR AbSt AmySt SSt AmyE AmyR RS".split()


def extract_digest_snapshot(digest: dict) -> dict:
    snap = {
        "losses": digest.get("losses", 0),
        "games": digest.get("games", 0),
        "component_primary": digest.get("component_primary", {}),
        "alert_losses": digest.get("alert_losses", {}),
        "profiles": {},
    }
    for pname in ["fast", "typical", "slow"]:
        p = digest.get("profiles", {}).get(pname, {})
        snap["profiles"][pname] = {
            "count": p.get("count", 0),
            "pct": p.get("pct", 0),
            "mechanics": p.get("mechanics", {}),
            "wipe_rate": p.get("wipe_rate", 0),
            "lore_t4": p.get("lore_t4", {}),
            "top_cards": list(p.get("top_cards", {}).keys())[:8],
        }
    return snap


def get_curve_cards(kc: dict) -> set:
    cards = set()
    for c in kc.get("curves", []):
        cards.update(c.get("key_cards", []))
        for _t, plays in c.get("sequence", {}).items():
            if isinstance(plays, dict):
                for p in plays.get("plays", []):
                    if isinstance(p, dict):
                        cards.add(p.get("card", ""))
    cards.discard("")
    return cards


def _digest_path(our: str, opp: str, game_format: str) -> Path:
    sfx = '_inf' if game_format == 'infinity' else ''
    return DIGEST_DIR / f"digest_{our}_vs_{opp}{sfx}.json"


def evaluate_stability(our: str, opp: str, game_format: str = 'core',
                       existing_kc: dict | None = None) -> dict:
    """Evaluate stability. Returns dict with level and details.

    existing_kc: the current KC data from PG (if any). If None, assumes no curves exist.
    """
    dp = _digest_path(our, opp, game_format)
    min_l = MIN_LOSSES_INF if game_format == 'infinity' else MIN_LOSSES

    result = {"matchup": f"{our}_vs_{opp}", "level": "UNSTABLE", "reasons": [], "scores": {}}

    if not dp.exists():
        result["reasons"].append("no_digest")
        return result

    digest = json.load(open(dp))
    if digest.get("losses", 0) < min_l:
        result["level"] = "SKIP"
        result["reasons"].append(f"low_losses ({digest.get('losses', 0)})")
        return result

    if not existing_kc:
        result["reasons"].append("no_curves")
        return result

    meta = existing_kc.get("metadata", {})
    snap = meta.get("digest_snapshot", {})
    new_snap = extract_digest_snapshot(digest)

    old_l = snap.get("losses", meta.get("based_on_losses", 0))
    new_l = new_snap["losses"]
    delta_loss = abs(new_l - old_l) / max(old_l, 1) * 100
    result["scores"]["delta_loss"] = round(delta_loss, 1)

    digest_cards = set()
    for p in new_snap["profiles"].values():
        digest_cards.update(p.get("top_cards", [])[:5])
    curve_cards = get_curve_cards(existing_kc)

    if digest_cards and curve_cards:
        overlap = len(digest_cards & curve_cards) / len(digest_cards) * 100
    else:
        overlap = 0
    result["scores"]["card_overlap"] = round(overlap, 1)
    new_threats = sorted(digest_cards - curve_cards)
    if new_threats:
        result["scores"]["new_threats"] = new_threats

    new_mechs = set()
    lost_mechs = set()
    for pname in ["fast", "typical", "slow"]:
        old_p = snap.get("profiles", {}).get(pname, {})
        new_p = new_snap["profiles"].get(pname, {})
        old_m = set(k for k, v in old_p.get("mechanics", {}).items()
                    if v > old_p.get("count", 1) * 0.15)
        new_m = set(k for k, v in new_p.get("mechanics", {}).items()
                    if v > new_p.get("count", 1) * 0.15)
        new_mechs.update(new_m - old_m)
        lost_mechs.update(old_m - new_m)
    if new_mechs:
        result["scores"]["new_mechanics"] = sorted(new_mechs)
    if lost_mechs:
        result["scores"]["lost_mechanics"] = sorted(lost_mechs)
    mechs_changed = len(new_mechs) + len(lost_mechs)

    old_comp = snap.get("component_primary", {})
    new_comp = new_snap["component_primary"]
    old_top = max(old_comp, key=old_comp.get) if old_comp else None
    new_top = max(new_comp, key=new_comp.get) if new_comp else None
    comp_shifted = old_top != new_top and old_top is not None
    result["scores"]["component"] = f"{old_top}->{new_top}" if comp_shifted else new_top

    lore_shift = 0
    for pname in ["fast", "typical"]:
        old_p5 = snap.get("profiles", {}).get(pname, {}).get("lore_t4", {}).get("p5", 0)
        new_p5 = new_snap["profiles"].get(pname, {}).get("lore_t4", {}).get("p5", 0)
        shift = new_p5 - old_p5
        if shift < lore_shift:
            lore_shift = shift
    result["scores"]["lore_t4_shift"] = lore_shift

    if not snap:
        if overlap >= 80 and delta_loss < 20:
            result["level"] = "GREY"
            result["reasons"].append("no_snapshot_but_cards_match")
        else:
            result["level"] = "UNSTABLE"
            result["reasons"].append("no_snapshot")
        return result

    instab_signals = 0
    if delta_loss > 50:
        instab_signals += 2
        result["reasons"].append(f"delta_loss_high ({delta_loss:.0f}%)")
    elif delta_loss > 30:
        instab_signals += 1
        result["reasons"].append(f"delta_loss_medium ({delta_loss:.0f}%)")

    if overlap < 60:
        instab_signals += 2
        result["reasons"].append(f"low_overlap ({overlap:.0f}%)")
    elif overlap < 80:
        instab_signals += 1
        result["reasons"].append(f"medium_overlap ({overlap:.0f}%)")

    if mechs_changed >= 2:
        instab_signals += 2
        result["reasons"].append(f"mechanics_shift ({sorted(new_mechs)})")
    elif mechs_changed == 1:
        instab_signals += 1
        result["reasons"].append(f"mechanics_minor ({sorted(new_mechs | lost_mechs)})")

    if comp_shifted:
        instab_signals += 1
        result["reasons"].append(f"component_shifted ({old_top}->{new_top})")

    if lore_shift <= -3:
        instab_signals += 1
        result["reasons"].append(f"lore_t4_worse ({lore_shift})")

    if instab_signals >= 3:
        result["level"] = "UNSTABLE"
    elif instab_signals >= 1:
        result["level"] = "GREY"
    else:
        result["level"] = "STABLE"

    return result
