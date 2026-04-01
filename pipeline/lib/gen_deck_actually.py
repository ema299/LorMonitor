"""Sezione DECK ACTUALLY — chi gioca questo deck ora, con che risultati, con che carte.

Fonti:
- matches/ PRO+TOP ultimi 3 giorni → player recenti con WR e MMR
- decks_db/ → decklist da torneo (inkdecks.com)
- pro_momento.json → pro monitorati
- PRO_momento/studio_*.md → studi dettagliati se disponibili
"""

import json, os, glob
from collections import defaultdict, Counter
from .loader import DECK_COLORS, DECK_LONG_NAMES, MATCHES_DIR, DECKS_DB_DIR
from .formatting import short

GUIDES_DIR = "/mnt/HC_Volume_104764377/finanza/Lor/guides"
PRO_MOMENTO_DIR = "/mnt/HC_Volume_104764377/finanza/Lor/PRO_momento"


def _match_colors(ic, target):
    return tuple(sorted(c.lower() for c in ic)) == tuple(sorted(target))


def _get_deck(colors):
    for code, cols in DECK_COLORS.items():
        if _match_colors(colors, cols):
            return code
    return None


def _find_winner(logs):
    winner = None
    for e in logs:
        if e.get('type') in ('GAME_END', 'GAME_CONCEDED'):
            w = (e.get('data') or {}).get('winner') or e.get('winner')
            if w in (1, 2):
                winner = int(w)
    return winner


def _scan_recent_players(deck_code, n_days=3):
    """Scan last n_days of PRO+TOP matches for players using this deck."""
    our_colors = DECK_COLORS.get(deck_code)
    if not our_colors:
        return []

    players = defaultdict(lambda: {'wins': 0, 'losses': 0, 'mmr': 0, 'opps': []})
    match_dirs = sorted(glob.glob(os.path.join(MATCHES_DIR, '*/')))[-n_days:]

    for mdir in match_dirs:
        for subdir in ['PRO', 'TOP']:
            folder = os.path.join(mdir, subdir)
            if not os.path.isdir(folder):
                continue
            for f in os.listdir(folder):
                if not f.endswith('.json'):
                    continue
                try:
                    m = json.load(open(os.path.join(folder, f)))
                except Exception:
                    continue
                gi = m.get('game_info', {})
                p1 = gi.get('player1', {})
                p2 = gi.get('player2', {})
                logs = m.get('log_data', {}).get('logs', [])
                winner = _find_winner(logs)
                if winner is None:
                    continue

                for pnum, pinfo, opp_info in [(1, p1, p2), (2, p2, p1)]:
                    colors = pinfo.get('inkColors', [])
                    if not _match_colors(colors, our_colors):
                        continue
                    name = pinfo.get('name', '?')
                    mmr = int(pinfo.get('mmr', 0) or 0)
                    opp_colors = opp_info.get('inkColors', [])
                    opp_deck = _get_deck(opp_colors) or '?'
                    won = (winner == pnum)

                    players[name]['mmr'] = max(players[name]['mmr'], mmr)
                    if won:
                        players[name]['wins'] += 1
                    else:
                        players[name]['losses'] += 1
                    players[name]['opps'].append((opp_deck, won))

    # Filter: at least 3 games
    result = []
    for name, d in players.items():
        total = d['wins'] + d['losses']
        if total < 3:
            continue
        wr = d['wins'] / total * 100
        result.append({
            'name': name, 'mmr': d['mmr'],
            'wins': d['wins'], 'losses': d['losses'],
            'wr': wr, 'total': total,
            'opps': d['opps'],
        })
    result.sort(key=lambda x: (-x['wr'], -x['mmr']))
    return result


def _load_pro_momento(deck_code):
    """Load pro players playing this deck from pro_momento.json."""
    path = os.path.join(GUIDES_DIR, 'pro_momento.json')
    if not os.path.exists(path):
        return []
    try:
        data = json.load(open(path))
    except Exception:
        return []
    pros = []
    for name, d in data.get('players', {}).items():
        if d.get('deck') == deck_code:
            pros.append({
                'name': name, 'mmr': d.get('mmr', 0),
                'wr': d.get('wr', 0), 'games': d.get('games', 0),
                'detected': d.get('detected', '?'),
            })
    pros.sort(key=lambda x: (-x['wr'], -x['mmr']))
    return pros


def _load_tournament_decks(deck_code, db):
    """Load tournament decklists from decks_db/."""
    from .loader import load_deck_pool
    _, decks = load_deck_pool(deck_code, db)
    return decks


def _find_pro_study(deck_code):
    """Find detailed pro study markdown if available."""
    if not os.path.isdir(PRO_MOMENTO_DIR):
        return []
    studies = []
    for f in os.listdir(PRO_MOMENTO_DIR):
        if f.startswith('studio_') and f.endswith('.md'):
            path = os.path.join(PRO_MOMENTO_DIR, f)
            try:
                content = open(path).read(500)  # first 500 chars to identify deck
                if deck_code in content or DECK_LONG_NAMES.get(deck_code, '') in content:
                    # Read the full file for the decklist and key sections
                    full = open(path).read()
                    player_name = f.replace('studio_', '').replace('.md', '')
                    studies.append({'player': player_name, 'path': path, 'content': full})
            except Exception:
                continue
    return studies


def _load_daily_meta(deck_code):
    """Extract meta context for this deck from daily_routine.md."""
    path = os.path.join(os.path.dirname(GUIDES_DIR), 'Analisi_deck', 'analisidef', 'daily', 'output', 'daily_routine.md')
    if not os.path.exists(path):
        return {}
    try:
        content = open(path).read()
    except Exception:
        return {}

    meta = {}
    # Find WR in High ELO table
    for line in content.split('\n'):
        if f'| {deck_code} ' in line or f'| **{deck_code}**' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                try:
                    wr_str = parts[3].replace('**', '').replace('_', '').replace('%', '')
                    meta['high_elo_wr'] = float(wr_str)
                    meta['high_elo_games'] = int(parts[2].strip())
                except (ValueError, IndexError):
                    pass
            break

    # Find meta share
    for line in content.split('\n'):
        if f'| {deck_code} ' in line and 'Share' not in line and '%' in line:
            parts = [p.strip() for p in line.split('|')]
            for p in parts:
                if 'pp' not in p and '%' in p:
                    try:
                        meta['meta_share'] = float(p.replace('%', ''))
                    except ValueError:
                        pass
                    break
            break

    return meta


def _compare_decklists(decks, db):
    """Compare tournament decklists to find consensus and divergence."""
    if not decks:
        return {}, {}
    card_freq = Counter()
    card_qty = defaultdict(list)
    for d in decks:
        for name, qty in d['cards'].items():
            card_freq[name] += 1
            card_qty[name].append(qty)

    n = len(decks)
    consensus = {}  # cards in all or most decks
    flex = {}  # cards in some decks

    for name, freq in card_freq.items():
        avg_qty = sum(card_qty[name]) / len(card_qty[name])
        if freq >= n * 0.8:
            consensus[name] = {'freq': freq, 'avg_qty': avg_qty, 'n_decks': n}
        elif freq >= 2:
            flex[name] = {'freq': freq, 'avg_qty': avg_qty, 'n_decks': n}

    return consensus, flex


def generate(our, opp, games, db, **ctx):
    """Generate DECK ACTUALLY section."""
    our_long = DECK_LONG_NAMES.get(our, our)

    L = [f"## 8. Deck Actually — Chi Gioca {our} Ora\n"]
    L.append(f"_Dati da PRO/TOP monitoring e tornei recenti._\n")

    # ── META CONTEXT ──
    meta = _load_daily_meta(our)
    if meta:
        parts = []
        if 'high_elo_wr' in meta:
            parts.append(f"WR High ELO: **{meta['high_elo_wr']:.1f}%** ({meta.get('high_elo_games', '?')}g)")
        if 'meta_share' in meta:
            parts.append(f"Meta share: {meta['meta_share']:.1f}%")
        if parts:
            L.append(f"**Meta attuale:** {' | '.join(parts)}\n")

    # ── PRO MONITORATI ──
    pros = _load_pro_momento(our)
    if pros:
        L.append(f"### PRO che giocano {our}\n")
        L.append("| Player | MMR | WR | Partite | Detected |")
        L.append("|--------|-----|-----|---------|----------|")
        for p in pros[:6]:
            L.append(f"| **{p['name']}** | {p['mmr']} | {p['wr']}% | {p['games']}g | {p['detected']} |")
        L.append("")

    # ── PLAYER RECENTI PRO/TOP ──
    recent = _scan_recent_players(our, n_days=3)
    if recent:
        L.append(f"### Player Recenti (ultimi 3 giorni, PRO+TOP)\n")
        L.append("| Player | MMR | Record | WR | Matchup |")
        L.append("|--------|-----|--------|-----|---------|")
        for p in recent[:8]:
            # Summarize matchups
            opp_summary = Counter()
            for opp_deck, won in p['opps']:
                opp_summary[opp_deck] += 1
            top_opps = ', '.join(f"{d}({c})" for d, c in opp_summary.most_common(3))
            L.append(f"| **{p['name']}** | {p['mmr']} | {p['wins']}W-{p['losses']}L | {p['wr']:.0f}% | {top_opps} |")
        L.append("")

    # ── DECKLIST DA TORNEO ──
    decks = _load_tournament_decks(our, db)
    if decks:
        L.append(f"### Decklist da Torneo ({len(decks)} liste)\n")
        for d in decks:
            L.append(f"- **{d['player']}** ({d['rank']})")
        L.append("")

        # Consensus vs flex
        consensus, flex = _compare_decklists(decks, db)
        if consensus:
            L.append("**Core condiviso** (in ≥80% delle liste):\n")
            for name in sorted(consensus, key=lambda x: -consensus[x]['avg_qty']):
                c = consensus[name]
                info = db.get(name, {})
                cost = info.get('cost', '?')
                L.append(f"- {name} (c{cost}) — media {c['avg_qty']:.1f}x in {c['freq']}/{c['n_decks']} liste")
            L.append("")

        if flex:
            L.append("**Flex slot** (scelte divergenti tra le liste):\n")
            for name in sorted(flex, key=lambda x: -flex[x]['freq']):
                c = flex[name]
                info = db.get(name, {})
                cost = info.get('cost', '?')
                L.append(f"- {name} (c{cost}) — {c['avg_qty']:.1f}x in {c['freq']}/{c['n_decks']} liste")
            L.append("")

    if not pros and not recent and not decks:
        L.append(f"_Nessun dato PRO/TOP disponibile per {our}._\n")

    return '\n'.join(L) + '\n', {}
