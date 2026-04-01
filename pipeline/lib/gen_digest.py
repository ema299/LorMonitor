"""
Genera un digest compatto dell'archivio per l'LLM.
Legge archive + cards_db, produce una sezione llm_digest con:
- Aggregati chiave (già nell'archivio, riformattati)
- Example games compattate (solo turni opp rilevanti)
- Carte DB pre-lookup-ate per le top_cards
"""

import json, os

CARDS_DB_PATH = '/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json'


def _load_cards():
    """Load cards DB — duels.ink primary, local fallback."""
    try:
        from test_kc.src.cards_api import get_cards_db
        db = get_cards_db()
        if db and len(db) > 100:
            return db
    except Exception:
        pass
    with open(CARDS_DB_PATH) as f:
        return json.load(f)


def generate_digest(archive_path):
    """Aggiunge llm_digest all'archivio esistente.

    Returns:
        path del digest salvato (stesso dir, nome digest_*.json)
    """
    with open(archive_path) as f:
        arch = json.load(f)
    db = _load_cards()

    meta = arch['metadata']
    agg = arch['aggregates']
    lp = agg.get('loss_profiles', {})
    ls = agg.get('lore_speed', {})
    games_by_id = {g['id']: g for g in arch['games']}

    # --- 1. Aggregati chiave (compatti) ---
    summary = {
        'matchup': f"{meta['our_deck']} vs {meta['opp_deck']}",
        'games': meta['total_games'],
        'wins': meta['wins'],
        'losses': meta['losses'],
        'format': meta.get('game_format', 'core'),
        'component_primary': agg['component_primary'],
        'critical_turn_dist': agg['critical_turn_distribution'],
        'avg_trend': {k: [round(v, 1) for v in vals[:7]]
                      for k, vals in agg['avg_trend_components'].items()
                      if k in ('board', 'lore', 'lore_pot', 'removal', 'opp_lore_vel')},
        'alert_losses': agg['alert_summary']['losses_per_type'],
        'lore_speed': {
            'reach_10': ls['reach_10'],
            'reach_15': ls['reach_15'],
            'fast_loss_ids': ls['fast_loss_ids'],
            'top_burst': ls['lore_burst'][:3],
        },
        'card_examples': {name: {'count': d['count'],
                                  'avg_crit_turn': d.get('avg_critical_turn')}
                          for name, d in sorted(agg.get('card_examples', {}).items(),
                                                key=lambda x: -x[1].get('count', 0))[:10]},
        'combos': [{'cards': c['cards'], 'count': c['count'], 'turn': c.get('avg_turn')}
                   for c in agg.get('combos_at_critical_turn', [])[:5]],
    }

    # --- 2. Loss profiles compatti ---
    profiles = {}
    for bucket_name in ['fast', 'typical', 'slow']:
        p = lp.get(bucket_name)
        if not p:
            continue
        profiles[bucket_name] = {
            'count': p['count'],
            'pct': p['pct'],
            'causes': p['causes'],
            'component': p['component_primary'],
            'alerts': p['alert_types'],
            'mechanics': p['mechanics'],
            'wipe_rate': p['wipe_rate'],
            'lore_t4': p['lore_t4'],
            'top_cards': dict(sorted(p['top_cards'].items(),
                                     key=lambda x: -x[1])[:8]),
            'example_ids': p['example_game_ids'],
        }
    summary['profiles'] = profiles

    # --- 3. Example games compattate ---
    all_example_ids = set()
    for p in lp.values():
        # Take first 6 example games per profile (most representative)
        all_example_ids.update(p.get('example_game_ids', [])[:6])
    all_example_ids.update(ls.get('fast_loss_ids', [])[:3])

    compact_games = []
    for gid in sorted(all_example_ids):
        g = games_by_id.get(gid)
        if not g or g['result'] not in ('L', 'loss'):
            continue

        a = g.get('analysis', {})
        lspd = a.get('lore_speed', {})

        # Which profiles include this game?
        in_profiles = []
        for bname, bdata in lp.items():
            if gid in bdata.get('example_game_ids', []):
                in_profiles.append(bname)
        if gid in ls.get('fast_loss_ids', []):
            in_profiles.append('fast_loss')

        # Compact turns: only opp plays + lore + key events
        turns_compact = []
        cum_opp_lore = 0
        for t in g['turns']:
            tn = t['t']
            opp_plays = [(p['name'], p.get('ink_paid', 0))
                         for p in t.get('opp_plays', [])]
            opp_lore = sum(q.get('lore', 0) for q in t.get('opp_quests', []))
            opp_dead = t.get('opp_dead', [])
            our_dead = t.get('our_dead', [])
            our_bounced = t.get('our_bounced', [])
            cum_opp_lore += opp_lore

            # Key abilities: only recursion, discard, return (skip STR buffs, draws)
            key_abs = []
            for ab in t.get('opp_abilities', []):
                eff = ab.get('effect', '')
                if any(kw in eff for kw in
                       ['from discard', 'plays', 'Returned', 'return']):
                    key_abs.append(f"{ab['card']}: {eff[:35]}")

            # Skip empty turns and turns past T8 (critical turns almost always ≤T7)
            if tn > 8:
                continue
            if not opp_plays and not opp_lore and not opp_dead and not our_dead:
                continue

            # Compact format with FULL card names
            parts = []
            if opp_plays:
                plays_str = '+'.join(f"{n}({ink})" for n, ink in opp_plays)
                parts.append(plays_str)
            if opp_lore:
                parts.append(f"→{cum_opp_lore}L(+{opp_lore})")
            if opp_dead:
                parts.append(f"Odead:{','.join(opp_dead[:2])}")
            if our_dead:
                parts.append(f"Udead:{','.join(our_dead[:2])}")
            if our_bounced:
                parts.append(f"Ubounce:{','.join(our_bounced[:2])}")
            if key_abs:
                parts.append(f"ab:{';'.join(key_abs[:2])}")

            turn_str = f"T{tn}: {' | '.join(parts)}"
            turns_compact.append(turn_str)

        # Compact criticals
        crits_str = ','.join(f"T{c['turn']}{c['component'][0]}({c['swing']})"
                             for c in a.get('criticals', []))

        header = (f"G{gid} [{','.join(in_profiles)}] len={g['length']} "
                  f"r15={lspd.get('opp_reach_15','?')} "
                  f"burst={lspd.get('best_lore_burst',0)}@T{lspd.get('best_lore_burst_turn','?')} "
                  f"crits={crits_str}")

        compact_games.append({
            'header': header,
            'turns': turns_compact,
        })

    summary['example_games'] = compact_games

    # --- 4. Cards DB per carte rilevanti ---
    # Only include cards that appear in card_examples (top 10 by frequency)
    # plus top 5 from each profile not already included
    all_cards = set(summary['card_examples'].keys())
    for p in profiles.values():
        top5 = list(p['top_cards'].keys())[:5]
        all_cards.update(top5)

    cards_lookup = {}
    for name in sorted(all_cards):
        if name not in db:
            continue
        c = db[name]
        # Ultra-compact: "c2 1/2 1L Emerald Char | ABILITY TEXT"
        parts = [f"c{c['cost']}"]
        if c.get('str') and c.get('will'):
            parts.append(f"{c['str']}/{c['will']}")
        if c.get('lore'):
            parts.append(f"{c['lore']}L")
        parts.append(c['ink'])
        parts.append(c['type'].split(' · ')[0])  # Character, Action, Item
        base = ' '.join(parts)
        ability = c.get('ability', '')[:80]
        cards_lookup[name] = f"{base} | {ability}" if ability else base

    summary['cards_db'] = cards_lookup

    # --- Salva ---
    out_dir = os.path.dirname(archive_path)
    base = os.path.basename(archive_path).replace('archive_', 'digest_')
    out_path = os.path.join(out_dir, base)
    with open(out_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str, ensure_ascii=False)

    return out_path


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 -m lib.gen_digest <archive_path>")
        sys.exit(1)
    path = generate_digest(sys.argv[1])
    size_kb = os.path.getsize(path) / 1024
    print(f"Digest: {path} ({size_kb:.0f} KB)")
