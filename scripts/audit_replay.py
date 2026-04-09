"""
Audit a .replay.gz: verify every snapshot transition produces a visible change in the viewer.

Usage: python scripts/audit_replay.py <file.replay.gz>

Reports:
  - Each snapshot with what changed (board, hand, ink, lore, items, inkwell)
  - Flags snapshots where NOTHING visibly changed (silent frames)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.replay_service import parse_replay_gz


def diff_cards(prev_list, curr_list):
    """Diff two card lists by iid. Returns added, removed, changed."""
    prev_by_iid = {c['iid']: c for c in prev_list if c.get('iid')}
    curr_by_iid = {c['iid']: c for c in curr_list if c.get('iid')}

    added = [c for iid, c in curr_by_iid.items() if iid not in prev_by_iid]
    removed = [c for iid, c in prev_by_iid.items() if iid not in curr_by_iid]

    changed = []
    for iid in set(prev_by_iid) & set(curr_by_iid):
        p, c = prev_by_iid[iid], curr_by_iid[iid]
        diffs = []
        if p.get('damage', 0) != c.get('damage', 0):
            diffs.append(f"dmg {p.get('damage',0)}->{c.get('damage',0)}")
        if p.get('exerted', False) != c.get('exerted', False):
            diffs.append('exerted' if c['exerted'] else 'readied')
        if p.get('strength', 0) != c.get('strength', 0):
            diffs.append(f"str {p.get('strength',0)}->{c.get('strength',0)}")
        if p.get('willpower', 0) != c.get('willpower', 0):
            diffs.append(f"will {p.get('willpower',0)}->{c.get('willpower',0)}")
        if p.get('lore', 0) != c.get('lore', 0):
            diffs.append(f"lore {p.get('lore',0)}->{c.get('lore',0)}")
        if diffs:
            changed.append((c['name'], diffs))

    return added, removed, changed


def diff_hand(prev_hand, curr_hand):
    """Diff hand (list of names). Returns drawn, lost."""
    prev = list(prev_hand or [])
    curr = list(curr_hand or [])
    prev_copy = prev[:]
    drawn = []
    for name in curr:
        if name in prev_copy:
            prev_copy.remove(name)
        else:
            drawn.append(name)
    lost = prev_copy  # cards in prev but not matched in curr
    return drawn, lost


def diff_inkwell(prev_iw, curr_iw):
    """Diff inkwell cards. Returns added, exert_changes."""
    prev = prev_iw or []
    curr = curr_iw or []

    added = max(0, len(curr) - len(prev))
    exert_changes = 0
    for i in range(min(len(prev), len(curr))):
        if prev[i].get('exerted') != curr[i].get('exerted'):
            exert_changes += 1

    return added, exert_changes


def audit(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()

    result = parse_replay_gz(data)
    snaps = result['snapshots']
    print(f"Game: {result['game_id']}")
    print(f"Players: {result.get('player_names', {})}")
    print(f"Snapshots: {len(snaps)}")
    print(f"Turns: {result.get('turn_count', '?')}")
    print(f"Winner: player {result.get('winner', '?')}")
    print("=" * 80)

    silent = []
    total = len(snaps)

    for i in range(1, total):
        prev = snaps[i - 1]
        curr = snaps[i]
        changes = []

        # Board diff (our + opp)
        for side in ['our', 'opp']:
            pb = (prev.get('board') or {}).get(side, [])
            cb = (curr.get('board') or {}).get(side, [])
            added, removed, changed = diff_cards(pb, cb)
            for c in added:
                changes.append(f"  +board.{side}: {c['name']}")
            for c in removed:
                changes.append(f"  -board.{side}: {c['name']} (destroyed)")
            for name, diffs in changed:
                changes.append(f"  ~board.{side}: {name} [{', '.join(diffs)}]")

        # Items diff
        for side in ['our', 'opp']:
            pi = (prev.get('items') or {}).get(side, [])
            ci = (curr.get('items') or {}).get(side, [])
            added, removed, changed = diff_cards(pi, ci)
            for c in added:
                changes.append(f"  +items.{side}: {c['name']}")
            for c in removed:
                changes.append(f"  -items.{side}: {c['name']}")
            for name, diffs in changed:
                changes.append(f"  ~items.{side}: {name} [{', '.join(diffs)}]")

        # Hand diff
        drawn, lost = diff_hand(prev.get('hand', []), curr.get('hand', []))
        for name in drawn:
            changes.append(f"  +hand: {name}")
        for name in lost:
            changes.append(f"  -hand: {name}")

        # Opp hand count
        prev_hc = prev.get('hand_count_opp', 0)
        curr_hc = curr.get('hand_count_opp', 0)
        if prev_hc != curr_hc:
            changes.append(f"  opp_hand: {prev_hc}->{curr_hc}")

        # Lore
        for side in ['our', 'opp']:
            pl = (prev.get('lore') or {}).get(side, 0)
            cl = (curr.get('lore') or {}).get(side, 0)
            if pl != cl:
                changes.append(f"  lore.{side}: {pl}->{cl} ({'+' if cl > pl else ''}{cl - pl})")

        # Ink count
        for side in ['our', 'opp']:
            pi = (prev.get('ink') or {}).get(side, 0)
            ci = (curr.get('ink') or {}).get(side, 0)
            if pi != ci:
                changes.append(f"  ink.{side}: {pi}->{ci}")

        # Inkwell cards
        for side in ['our', 'opp']:
            piw = (prev.get('inkwell') or {}).get(side, [])
            ciw = (curr.get('inkwell') or {}).get(side, [])
            iw_added, iw_exert = diff_inkwell(piw, ciw)
            if iw_added:
                # Try to identify the new ink card
                if side == 'our' and len(ciw) > len(piw):
                    new_card = ciw[-1].get('name') or '?'
                    changes.append(f"  +inkwell.{side}: {new_card}")
                else:
                    changes.append(f"  +inkwell.{side}: +{iw_added} card(s)")
            if iw_exert:
                changes.append(f"  ~inkwell.{side}: {iw_exert} exert change(s)")

        # Report
        action = curr.get('action_type', '?')
        turn = curr.get('turn', 0)
        label = curr.get('label', '')

        if changes:
            print(f"[{i:3d}] T{turn} {action:25s} {label}")
            for ch in changes:
                print(ch)
        else:
            silent.append((i, turn, action, label))
            print(f"[{i:3d}] T{turn} {action:25s} {label}  *** SILENT ***")

    # === VISUAL COVERAGE: check which effects get arrows/animations ===
    no_arrow = []  # damage/death events with no visual indicator

    for i in range(1, total):
        prev = snaps[i - 1]
        curr = snaps[i]
        action = curr.get('action_type', '')

        # Collect damage and death events
        dmg_events = []
        for side in ['our', 'opp']:
            pb = {c['iid']: c for c in (prev.get('board') or {}).get(side, []) if c.get('iid')}
            cb = {c['iid']: c for c in (curr.get('board') or {}).get(side, []) if c.get('iid')}
            for iid in set(pb) & set(cb):
                if cb[iid].get('damage', 0) > pb[iid].get('damage', 0):
                    dmg_events.append((side, cb[iid]['name'], 'damage', cb[iid]['damage'] - pb[iid]['damage']))
            for iid in set(pb) - set(cb):
                dmg_events.append((side, pb[iid]['name'], 'death', 0))

        if not dmg_events:
            continue

        # Check if the viewer would show an arrow/animation for this frame
        has_arrow = False

        # ATTACK: arrow from newly exerted card, OR from card that died/took damage while exerted (mutual kill)
        if action == 'ATTACK':
            for side_pair in [('our', 'opp'), ('opp', 'our')]:
                atk_side, def_side = side_pair
                pb_atk = {c['iid']: c for c in (prev.get('board') or {}).get(atk_side, []) if c.get('iid')}
                cb_atk = {c['iid']: c for c in (curr.get('board') or {}).get(atk_side, []) if c.get('iid')}
                # Newly exerted
                for iid in set(pb_atk) & set(cb_atk):
                    if cb_atk[iid].get('exerted') and not pb_atk[iid].get('exerted'):
                        has_arrow = True
                        break
                # Died while exerted (mutual kill)
                if not has_arrow:
                    for iid in set(pb_atk) - set(cb_atk):
                        if pb_atk[iid].get('exerted'):
                            has_arrow = True
                            break
                # Took damage while already exerted
                if not has_arrow:
                    for iid in set(pb_atk) & set(cb_atk):
                        if pb_atk[iid].get('exerted') and cb_atk[iid].get('damage', 0) > pb_atk[iid].get('damage', 0):
                            has_arrow = True
                            break
                if has_arrow:
                    break

        # PLAY_CARD spell: card left hand, didn't appear on board
        elif action == 'PLAY_CARD':
            prev_hand = set(prev.get('hand') or [])
            curr_hand = set(curr.get('hand') or [])
            lost = prev_hand - curr_hand
            pb_all = {c['iid'] for side in ['our','opp'] for c in (curr.get('board') or {}).get(side, []) if c.get('iid')}
            pp_all = {c['iid'] for side in ['our','opp'] for c in (prev.get('board') or {}).get(side, []) if c.get('iid')}
            new_on_board = pb_all - pp_all
            if lost and not new_on_board:
                has_arrow = True  # spell overlay

        # Damage transfer: card heals AND another takes damage/dies
        heal_found = False
        for side in ['our', 'opp']:
            pb = {c['iid']: c for c in (prev.get('board') or {}).get(side, []) if c.get('iid')}
            cb = {c['iid']: c for c in (curr.get('board') or {}).get(side, []) if c.get('iid')}
            for iid in set(pb) & set(cb):
                if cb[iid].get('damage', 0) < pb[iid].get('damage', 0):
                    heal_found = True
                    has_arrow = True
                    break
            if heal_found:
                break

        # RESPOND_TO_PROMPT / ACTIVATE_ABILITY: ability highlight
        if action in ('RESPOND_TO_PROMPT', 'ACTIVATE_ABILITY'):
            has_arrow = True  # tc-ability-hit highlight

        if not has_arrow:
            for side, name, etype, amount in dmg_events:
                detail = f"-{amount}" if etype == 'damage' else 'killed'
                no_arrow.append((i, curr.get('turn', 0), action, side, name, detail))

    # Summary
    print("=" * 80)
    print(f"Total snapshots: {total}")
    print(f"Transitions:     {total - 1}")
    print(f"With changes:    {total - 1 - len(silent)}")
    print(f"Silent:          {len(silent)}")

    if silent:
        print(f"\n--- SILENT FRAMES ({len(silent)}) ---")
        for idx, turn, action, label in silent:
            print(f"  [{idx:3d}] T{turn} {action} — {label}")

    print(f"\n--- VISUAL COVERAGE ---")
    if no_arrow:
        print(f"Damage/death events with NO arrow/animation: {len(no_arrow)}")
        for idx, turn, action, side, name, detail in no_arrow:
            print(f"  [{idx:3d}] T{turn} {action:25s} {side} {name} ({detail})")
    else:
        print(f"All damage/death events have arrows or animations.")

    coverage = (total - 1 - len(silent)) / max(total - 1, 1) * 100
    print(f"\nData coverage: {coverage:.1f}%")

    return len(silent) + len(no_arrow)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <file.replay.gz>")
        sys.exit(1)
    n_silent = audit(sys.argv[1])
    sys.exit(0 if n_silent == 0 else 1)
