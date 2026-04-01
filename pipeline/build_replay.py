#!/usr/bin/env python3
"""
Genera replay.html con dati embeddati per un matchup specifico.

Uso:
    python3 build_replay.py AmAm ES
    python3 build_replay.py AmAm AbE
    python3 build_replay.py AmAm AbSt
"""

import json
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')
CARDS_DB_PATH = '/mnt/HC_Volume_104764377/finanza/Lor/cards_db.json'


def build_slim_cards_db(archive, full_db):
    """Estrae solo le carte che appaiono nel matchup, con campi essenziali."""
    names = set()
    for g in archive.get('games', []):
        for t in g.get('turns', []):
            for p in t.get('our_plays', []) + t.get('opp_plays', []):
                names.add(p.get('name', ''))
            for side in ['our', 'opp']:
                names.update(t.get('board_state', {}).get(side, []))
                names.update(t.get(f'{side}_dead', []))
                names.update(t.get(f'{side}_bounced', []))
            for q in t.get('our_quests', []) + t.get('opp_quests', []):
                names.add(q.get('name', ''))
            for c in t.get('our_challenges', []) + t.get('opp_challenges', []):
                names.add(c.get('attacker', ''))
                names.add(c.get('defender', ''))
            for a in t.get('our_abilities', []) + t.get('opp_abilities', []):
                names.add(a.get('card', ''))
            for d in t.get('our_drawn', []) + t.get('opp_drawn', []):
                names.add(d.get('name', ''))
    names.discard('')

    slim = {}
    for name in names:
        card = full_db.get(name)
        if card:
            slim[name] = {
                'cost': card.get('cost', ''),
                'type': card.get('type', ''),
                'ink': card.get('ink', ''),
                'str': card.get('str', ''),
                'will': card.get('will', ''),
                'lore': card.get('lore', ''),
                'ability': card.get('ability', ''),
                'classifications': card.get('classifications', ''),
                'set': card.get('set', ''),
                'number': card.get('number', ''),
            }
    return slim


def build_replay_html(our, opp, game_format='core'):
    fmt_suffix = '_inf' if game_format == 'infinity' else ''
    archive_path = os.path.join(OUTPUT_DIR, f'archive_{our}_vs_{opp}{fmt_suffix}.json')
    if not os.path.exists(archive_path):
        print(f"Errore: {archive_path} non trovato")
        sys.exit(1)

    print(f"Carico archivio: {archive_path}")
    with open(archive_path) as f:
        archive = json.load(f)

    print(f"Carico cards_db: {CARDS_DB_PATH}")
    with open(CARDS_DB_PATH) as f:
        full_db = json.load(f)

    slim_db = build_slim_cards_db(archive, full_db)
    print(f"Carte nel matchup: {len(slim_db)}")

    # Minimal archive: keep only what the viewer needs
    slim_archive = {
        'metadata': archive.get('metadata', {}),
        'games': []
    }
    for g in archive.get('games', []):
        slim_archive['games'].append({
            'id': g.get('id', 0),
            'result': g.get('result', ''),
            'we_otp': g.get('we_otp', False),
            'our_name': g.get('our_name', ''),
            'opp_name': g.get('opp_name', ''),
            'our_mmr': g.get('our_mmr', 0),
            'opp_mmr': g.get('opp_mmr', 0),
            'length': g.get('length', 0),
            'turns': g.get('turns', []),
        })

    # ensure_ascii=True to avoid any stray unicode newlines; replace </script> to avoid breaking HTML
    archive_json = json.dumps(slim_archive, ensure_ascii=True, separators=(',', ':')).replace('</script>', '<\\/script>')
    db_json = json.dumps(slim_db, ensure_ascii=True, separators=(',', ':')).replace('</script>', '<\\/script>')

    print(f"Archive JSON: {len(archive_json)//1024} KB")
    print(f"Cards DB JSON: {len(db_json)//1024} KB")

    html = HTML_TEMPLATE.replace('/*__ARCHIVE_DATA__*/null', archive_json)
    html = html.replace('/*__CARDS_DB__*/null', db_json)

    out_path = os.path.join(OUTPUT_DIR, f'replay_{our}_vs_{opp}{fmt_suffix}.html')
    with open(out_path, 'w') as f:
        f.write(html)

    print(f"Scritto: {out_path} ({os.path.getsize(out_path)//1024} KB)")
    return out_path


TEMPLATE_PATH = os.path.join(SCRIPT_DIR, 'replay_template.html')
with open(TEMPLATE_PATH) as _f:
    HTML_TEMPLATE = _f.read()

_OLD_TEMPLATE_REMOVED = True  # vecchio template inline rimosso, ora caricato da replay_template.html
# --- fine builder ---


_UNUSED_START = r'''
<title>Lorcana Replay</title>
<style>
  :root {
    --amber: #D4943A; --amethyst: #7B3FA0; --emerald: #2A8F4E;
    --ruby: #C0392B; --sapphire: #2471A3; --steel: #6C7A89;
    --bg: #0D1117; --bg2: #161B22; --bg3: #21262D;
    --border: #30363D; --text: #E6EDF3; --text2: #8B949E;
    --gold: #D4A03A; --green: #3FB950; --red: #F85149; --yellow: #D29922;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'Segoe UI',system-ui,sans-serif; line-height:1.5; min-height:100vh; }

  /* HEADER */
  .header {
    background: linear-gradient(135deg, #1a1040 0%, #0D1117 50%, #0a1628 100%);
    border-bottom: 2px solid var(--amethyst);
    padding: 10px 20px; display:flex; align-items:center; gap:14px; flex-wrap:wrap;
  }
  .header h1 { font-size:1.15rem; color:var(--gold); }
  .header .matchup-label { font-size:0.9rem; color:var(--text2); }
  .game-result { margin-left:auto; font-size:0.95rem; font-weight:700; padding:2px 12px; border-radius:4px; }
  .game-result.win { background:rgba(63,185,80,0.2); color:var(--green); }
  .game-result.loss { background:rgba(248,81,73,0.2); color:var(--red); }

  /* GAME BAR */
  .game-bar { background:var(--bg2); border-bottom:1px solid var(--border); padding:7px 20px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .game-bar select { background:var(--bg3); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:5px 10px; font-size:0.82rem; max-width:400px; }
  .filter-btn { background:var(--bg3); color:var(--text2); border:1px solid var(--border); border-radius:4px; padding:3px 9px; font-size:0.78rem; cursor:pointer; }
  .filter-btn.active { color:var(--gold); border-color:var(--gold); }
  .filter-btn:hover { border-color:var(--text2); }
  .game-count { color:var(--text2); font-size:0.78rem; margin-left:auto; }

  /* STEP NAV — half-turns */
  .step-nav { background:var(--bg2); border-bottom:1px solid var(--border); padding:7px 20px; display:flex; align-items:center; gap:4px; flex-wrap:wrap; }
  .step-btn {
    background:var(--bg3); color:var(--text2); border:1px solid var(--border); border-radius:4px;
    height:26px; padding:0 6px; font-size:0.7rem; cursor:pointer;
    display:flex; align-items:center; justify-content:center; gap:2px; white-space:nowrap;
  }
  .step-btn:hover { border-color:var(--text); color:var(--text); }
  .step-btn.active { background:var(--gold); color:#000; border-color:var(--gold); font-weight:700; }
  .step-btn.active.opp-step { background:var(--red); color:#fff; border-color:var(--red); }
  .step-btn .step-who { font-size:0.6rem; opacity:0.7; }
  .step-arrow {
    background:none; color:var(--text2); border:1px solid var(--border); border-radius:4px;
    width:26px; height:26px; cursor:pointer; font-size:0.85rem;
    display:flex; align-items:center; justify-content:center;
  }
  .step-arrow:hover { color:var(--gold); border-color:var(--gold); }
  .step-sep { width:1px; height:20px; background:var(--border); margin:0 2px; }

  /* COUNTERS BAR */
  .counters-bar {
    background:var(--bg2); border-bottom:1px solid var(--border);
    padding:6px 20px; display:flex; gap:0; justify-content:center;
  }
  .counter-side {
    flex:1; display:flex; gap:12px; align-items:center; padding:4px 12px;
    border-radius:6px;
  }
  .counter-side.our-side { background:rgba(212,160,58,0.08); justify-content:flex-start; }
  .counter-side.opp-side { background:rgba(248,81,73,0.06); justify-content:flex-end; }
  .counter-divider { width:1px; background:var(--border); margin:0 8px; }
  .counter {
    display:flex; flex-direction:column; align-items:center; gap:0;
    min-width:48px;
  }
  .counter .c-val { font-size:1.1rem; font-weight:700; line-height:1.2; }
  .counter .c-lbl { font-size:0.55rem; text-transform:uppercase; letter-spacing:0.5px; color:var(--text2); line-height:1; }
  .our-side .c-val { color:var(--gold); }
  .opp-side .c-val { color:var(--red); }
  .counter .c-val.neutral { color:var(--text); }
  .counter-name { font-size:0.75rem; font-weight:600; margin-right:auto; color:var(--text); }
  .opp-side .counter-name { margin-right:0; margin-left:auto; }

  /* MAIN LAYOUT */
  .main-area { display:grid; grid-template-columns:1fr 300px; height:calc(100vh - 195px); overflow:hidden; }
  @media (max-width:900px) { .main-area { grid-template-columns:1fr; } .event-panel { max-height:280px; } }

  /* BOARD */
  .board { padding:10px 20px; display:flex; flex-direction:column; gap:4px; overflow-y:auto; }
  .board-side { flex:1; display:flex; flex-direction:column; gap:3px; }
  .board-label { font-size:0.7rem; text-transform:uppercase; letter-spacing:1px; color:var(--text2); display:flex; align-items:center; gap:6px; }
  .board-label .active-player { color:var(--gold); font-weight:700; }
  .board-divider { border:none; border-top:1px dashed var(--border); margin:3px 0; }
  .card-row { display:flex; flex-wrap:wrap; gap:5px; min-height:80px; align-content:flex-start; }

  /* MINI CARD */
  .mini-card {
    width:90px; min-height:100px; border-radius:7px; padding:4px 5px;
    background:var(--bg2); border:2px solid var(--border);
    display:flex; flex-direction:column; gap:1px;
    position:relative; cursor:default; transition:all 0.2s; font-size:0.68rem;
  }
  .mini-card:hover { transform:translateY(-3px); box-shadow:0 5px 16px rgba(0,0,0,0.5); z-index:10; }
  .mini-card .card-top { display:flex; justify-content:space-between; align-items:center; }
  .mini-card .card-cost {
    background:var(--bg3); border-radius:50%; width:18px; height:18px;
    display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.72rem;
  }
  .mini-card .card-ink { font-size:0.5rem; text-transform:uppercase; opacity:0.8; }
  .mini-card .card-name { font-weight:600; font-size:0.68rem; line-height:1.12; color:var(--text); flex:1; }
  .mini-card .card-sub { font-size:0.55rem; color:var(--text2); line-height:1.1; overflow:hidden; max-height:2em; }
  .mini-card .card-stats { display:flex; gap:4px; font-size:0.62rem; color:var(--text2); margin-top:auto; }
  .mini-card .card-keywords { display:flex; flex-wrap:wrap; gap:2px; margin-top:1px; }
  .kw { font-size:0.48rem; padding:0 3px; border-radius:3px; background:var(--bg3); color:var(--text2); line-height:1.4; }
  .kw-ward{background:#1a3a5c;color:#5ba3d9} .kw-evasive{background:#3a1a5c;color:#b07ada}
  .kw-rush{background:#5c1a1a;color:#e06060} .kw-resist{background:#3a3a3a;color:#aaa}
  .kw-bodyguard{background:#4a3a1a;color:var(--gold)} .kw-challenger{background:#5c2a1a;color:#e0a060}
  .kw-support{background:#1a3a2a;color:#60c080} .kw-singer{background:#2a1a4a;color:#a070c0}
  .kw-shift{background:#2a1a3a;color:#c090ff}

  .mini-card.new-card { animation:glowIn 0.5s ease; box-shadow:0 0 10px rgba(212,160,58,0.5); }
  @keyframes glowIn { 0%{opacity:0;transform:scale(0.85)} 100%{opacity:1;transform:scale(1)} }
  .mini-card.quested { transform:rotate(8deg); opacity:0.85; }
  .mini-card.quested:hover { transform:rotate(8deg) translateY(-3px); }
  .mini-card.challenged { border-color:var(--red)!important; }
  .mini-card.dead-card { opacity:0.25; border-color:var(--red)!important; }
  .mini-card.dead-card::after { content:'\2716'; position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:1.6rem; color:var(--red); }

  .ink-amber{border-color:var(--amber)} .ink-amethyst{border-color:var(--amethyst)}
  .ink-emerald{border-color:var(--emerald)} .ink-ruby{border-color:var(--ruby)}
  .ink-sapphire{border-color:var(--sapphire)} .ink-steel{border-color:var(--steel)}
  .type-badge { position:absolute; top:2px; right:3px; font-size:0.55rem; opacity:0.4; }

  /* TOOLTIP */
  .tooltip { display:none; position:fixed; background:var(--bg2); border:1px solid var(--border); border-radius:8px; padding:10px 12px; max-width:280px; z-index:1000; font-size:0.76rem; box-shadow:0 8px 24px rgba(0,0,0,0.6); pointer-events:none; }
  .tooltip.show { display:block; }
  .tooltip .tt-name { font-weight:700; color:var(--gold); margin-bottom:3px; }
  .tooltip .tt-class { color:var(--text2); font-size:0.66rem; margin-bottom:3px; }
  .tooltip .tt-ability { color:var(--text); line-height:1.3; font-size:0.73rem; }
  .tooltip .tt-stats { color:var(--text2); margin-top:4px; font-size:0.68rem; }

  /* EVENT PANEL */
  .event-panel { background:var(--bg2); border-left:1px solid var(--border); padding:10px 12px; overflow-y:auto; display:flex; flex-direction:column; gap:2px; }
  .event-panel h3 { font-size:0.78rem; color:var(--text2); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
  .event-section { margin-bottom:5px; }
  .event-section-label { font-size:0.62rem; color:var(--text2); text-transform:uppercase; letter-spacing:0.5px; padding:3px 0 1px; border-bottom:1px solid var(--border); margin-bottom:2px; }
  .event { display:flex; gap:5px; padding:2px 0; font-size:0.73rem; line-height:1.2; align-items:flex-start; }
  .event .ev-icon { flex-shrink:0; width:14px; text-align:center; font-size:0.73rem; }
  .ev-play{color:var(--green)} .ev-quest{color:var(--gold)} .ev-challenge{color:var(--red)}
  .ev-ability{color:var(--amethyst)} .ev-death{color:#888} .ev-draw{color:var(--sapphire)}
  .ev-bounce{color:var(--emerald)} .ev-support{color:var(--amber)}

  /* SPARKLINE */
  .sparkline-bar { background:var(--bg2); border-top:1px solid var(--border); padding:5px 20px; height:58px; }
  .sparkline-bar svg { width:100%; height:100%; }

  /* KB HINT */
  .kb-hint { position:fixed; bottom:6px; right:6px; background:var(--bg3); border:1px solid var(--border); border-radius:5px; padding:3px 7px; font-size:0.58rem; color:var(--text2); opacity:0.5; }
  .kb-hint kbd { background:var(--bg); border:1px solid var(--border); border-radius:3px; padding:0 3px; }
</style>
</head>
<body>

<div id="app">
  <div class="header">
    <h1>Lorcana Replay</h1>
    <span class="matchup-label" id="matchupLabel"></span>
    <span class="game-result" id="gameResult"></span>
  </div>
  <div class="game-bar">
    <select id="gameSelect"></select>
    <button class="filter-btn active" data-filter="all">Tutte</button>
    <button class="filter-btn" data-filter="W">Vittorie</button>
    <button class="filter-btn" data-filter="L">Sconfitte</button>
    <button class="filter-btn" data-filter="otp">OTP</button>
    <button class="filter-btn" data-filter="otd">OTD</button>
    <span class="game-count" id="gameCount"></span>
  </div>
  <div class="step-nav">
    <button class="step-arrow" id="prevStep">&#9664;</button>
    <div id="stepButtons" style="display:flex;gap:2px;flex-wrap:wrap;align-items:center"></div>
    <button class="step-arrow" id="nextStep">&#9654;</button>
  </div>

  <!-- COUNTERS -->
  <div class="counters-bar">
    <div class="counter-side our-side">
      <span class="counter-name" id="ourName">Noi</span>
      <div class="counter"><span class="c-val" id="cOurLore">0</span><span class="c-lbl">Lore</span></div>
      <div class="counter"><span class="c-val" id="cOurInk">0/0</span><span class="c-lbl">Ink</span></div>
      <div class="counter"><span class="c-val neutral" id="cOurHand">7</span><span class="c-lbl">Hand</span></div>
      <div class="counter"><span class="c-val neutral" id="cOurDiscard">0</span><span class="c-lbl">Discard</span></div>
      <div class="counter"><span class="c-val neutral" id="cOurBoard">0</span><span class="c-lbl">Board</span></div>
    </div>
    <div class="counter-divider"></div>
    <div class="counter-side opp-side">
      <div class="counter"><span class="c-val neutral" id="cOppBoard">0</span><span class="c-lbl">Board</span></div>
      <div class="counter"><span class="c-val neutral" id="cOppDiscard">0</span><span class="c-lbl">Discard</span></div>
      <div class="counter"><span class="c-val neutral" id="cOppHand">7</span><span class="c-lbl">Hand</span></div>
      <div class="counter"><span class="c-val" id="cOppInk">0/0</span><span class="c-lbl">Ink</span></div>
      <div class="counter"><span class="c-val" id="cOppLore">0</span><span class="c-lbl">Lore</span></div>
      <span class="counter-name" id="oppName">Opp</span>
    </div>
  </div>

  <div class="main-area">
    <div class="board">
      <div class="board-side">
        <div class="board-label"><span id="oppLabel">Avversario</span></div>
        <div class="card-row" id="oppBoard"></div>
      </div>
      <hr class="board-divider">
      <div class="board-side">
        <div class="board-label"><span id="ourLabel">Noi</span></div>
        <div class="card-row" id="ourBoard"></div>
      </div>
      <div class="sparkline-bar" id="sparkline"></div>
    </div>
    <div class="event-panel">
      <h3 id="eventTitle">Eventi</h3>
      <div id="eventLog"></div>
    </div>
  </div>
</div>

<div class="tooltip" id="tooltip">
  <div class="tt-name"></div><div class="tt-class"></div><div class="tt-ability"></div><div class="tt-stats"></div>
</div>
<div class="kb-hint"><kbd>&larr;</kbd><kbd>&rarr;</kbd> step &nbsp;<kbd>n</kbd><kbd>p</kbd> partita</div>

<script>
const ARCHIVE = /*__ARCHIVE_DATA__*/null;
const CARDS_DB = /*__CARDS_DB__*/null;
if(!ARCHIVE||!CARDS_DB){document.getElementById('app').innerHTML='<div style="padding:40px;color:var(--red)">Dati non embeddati. Usa build_replay.py.</div>';}

let games=ARCHIVE?ARCHIVE.games:[], filteredGames=[...games];
let currentGameIdx=0, currentStep=0;
let steps=[]; // array of half-turn objects
let handSize={our:0,opp:0}, discardSize={our:0,opp:0};

const INK_COLORS={'Amber':'amber','Amethyst':'amethyst','Emerald':'emerald','Ruby':'ruby','Sapphire':'sapphire','Steel':'steel'};
const INK_LABELS={'amber':'Amb','amethyst':'Amy','emerald':'Eme','ruby':'Rub','sapphire':'Sap','steel':'Ste'};
const KW_RE=[['Ward',/\bWard\b/],['Evasive',/\bEvasive\b/],['Rush',/\bRush\b/],['Resist',/\bResist\s*\+?\d*/],['Bodyguard',/\bBodyguard\b/],['Challenger',/\bChallenger\s*\+?\d*/],['Support',/\bSupport\b/],['Singer',/\bSinger\s+\d+/],['Shift',/\bShift\s+\d+/],['Reckless',/\bReckless\b/],['Vanish',/\bVanish\b/]];

function parseKW(ab){if(!ab)return[];return KW_RE.map(([_,re])=>{const m=ab.match(re);return m?m[0]:null}).filter(Boolean)}
function cardInk(c){return c?INK_COLORS[(c.ink||'').trim()]||'':''}
function shortN(n){if(n.includes(' - ')){const[b,s]=n.split(' - ',2);return{base:b,sub:s.length>16?s.slice(0,16)+'...':s}}return{base:n.length>22?n.slice(0,22)+'...':n,sub:''}}
function typeIc(c){if(!c)return'';const t=(c.type||'').toLowerCase();if(t.includes('song'))return'\u266B';if(t.includes('item'))return'\u2699';if(t.includes('location'))return'\u25CB';if(t.includes('action'))return'\u26A1';return''}

// ── BUILD HALF-TURN STEPS ──
// Each game turn splits into: OPP half, then OUR half
// We track hand size and discard cumulatively
function buildSteps(game) {
  steps = [];
  const weOtp = game.we_otp;
  // Starting hand: 7 each
  let hOur=7, hOpp=7, dOur=0, dOpp=0;

  for (let i=0; i<game.turns.length; i++) {
    const t = game.turns[i];
    const prev = i>0 ? game.turns[i-1] : null;
    const tNum = t.t;

    // --- Normal draw phase (before plays) ---
    // T1: OTP player does NOT draw. OTD draws.
    // T2+: both draw 1.
    let ourDraw=0, oppDraw=0;
    if (tNum === 1) {
      if (weOtp) { oppDraw=1; } else { ourDraw=1; }
    } else {
      ourDraw=1; oppDraw=1;
    }

    // We build intermediate board states:
    // After opp half: opp has played, challenged, quested etc. but our side only has prev board
    // After our half: full turn state

    // --- OPP HALF ---
    hOpp += oppDraw; // normal draw
    // Opp plays: -1 hand per play (shift also from hand). Sung songs: card from hand.
    const oppPlays = t.opp_plays||[];
    hOpp -= oppPlays.length;
    // Opp drawn from abilities
    hOpp += (t.opp_drawn||[]).length;
    // Opp bounced back to opp hand (these are opp's cards returning)
    // Actually opp_bounced = cards bounced FROM opp's board — they go back to opp's hand
    // our_bounced = cards bounced FROM our board — go back to our hand
    hOpp += (t.opp_bounced||[]).length;
    // Discard: opp dead chars + opp played non-persistent cards (actions, songs)
    const oppDeadCount = (t.opp_dead||[]).length;
    const oppActionsPlayed = oppPlays.filter(p => {
      const c = CARDS_DB[p.name];
      if (!c) return false;
      const tp = (c.type||'').toLowerCase();
      return tp.includes('action') || tp.includes('song');
    }).length;
    dOpp += oppDeadCount + oppActionsPlayed;
    // Our dead from opp challenges
    const ourDeadCount = (t.our_dead||[]).length;
    dOur += ourDeadCount;
    // Our cards bounced back to our hand
    hOur += (t.our_bounced||[]).length;

    // Opp discard also from our challenges killing opp? No, opp_dead covers that.

    // Build opp-half board state: opp board = final turn board (approx), our board = prev or same
    // For simplicity: opp board after their plays but before our plays
    // We don't have intermediate board state, so we approximate:
    // opp board = final board + opp_dead (they were there during opp half)
    // our board = prev board (we haven't acted yet)
    const oppBoardAfterOpp = t.board_state?.opp || [];
    const ourBoardDuringOpp = prev ? (prev.board_state?.our || []) : [];

    steps.push({
      who: 'opp',
      turnNum: tNum,
      turnIdx: i,
      label: `T${tNum} Opp`,
      board: { our: ourBoardDuringOpp, opp: oppBoardAfterOpp },
      prevBoard: { our: prev?(prev.board_state?.our||[]):[], opp: prev?(prev.board_state?.opp||[]):[] },
      lore: { our: prev?(prev.lore?.our||0):0, opp: t.lore?.opp||0 },
      ink: { our: prev?(prev.inkwell?.our||0):0, opp: t.inkwell?.opp||0 },
      inkSpent: { our: 0, opp: t.ink_spent?.opp||0 },
      hand: { our: hOur, opp: Math.max(0,hOpp) },
      discard: { our: dOur, opp: dOpp },
      boardCount: { our: ourBoardDuringOpp.length, opp: oppBoardAfterOpp.length },
      events: buildOppEvents(t),
      dead: { our: t.our_dead||[], opp: [] },
      quested: { our: new Set(), opp: new Set((t.opp_quests||[]).map(q=>q.name)) },
      challenged: { our: new Set((t.opp_challenges||[]).map(c=>c.defender)), opp: new Set() },
    });

    // --- OUR HALF ---
    hOur += ourDraw;
    const ourPlays = t.our_plays||[];
    hOur -= ourPlays.length;
    hOur += (t.our_drawn||[]).length;
    const ourActionsPlayed = ourPlays.filter(p => {
      const c = CARDS_DB[p.name];
      if (!c) return false;
      const tp = (c.type||'').toLowerCase();
      return tp.includes('action') || tp.includes('song');
    }).length;
    dOur += ourActionsPlayed;
    // Note: our_dead already counted in opp half

    steps.push({
      who: 'our',
      turnNum: tNum,
      turnIdx: i,
      label: `T${tNum} Noi`,
      board: { our: t.board_state?.our||[], opp: t.board_state?.opp||[] },
      prevBoard: { our: ourBoardDuringOpp, opp: oppBoardAfterOpp },
      lore: { our: t.lore?.our||0, opp: t.lore?.opp||0 },
      ink: { our: t.inkwell?.our||0, opp: t.inkwell?.opp||0 },
      inkSpent: { our: t.ink_spent?.our||0, opp: t.ink_spent?.opp||0 },
      hand: { our: Math.max(0,hOur), opp: Math.max(0,hOpp) },
      discard: { our: dOur, opp: dOpp },
      boardCount: { our: (t.board_state?.our||[]).length, opp: (t.board_state?.opp||[]).length },
      events: buildOurEvents(t),
      dead: { our: [], opp: t.opp_dead||[] },
      quested: { our: new Set((t.our_quests||[]).map(q=>q.name)), opp: new Set() },
      challenged: { our: new Set(), opp: new Set((t.our_challenges||[]).map(c=>c.defender)) },
    });

    hOur = Math.max(0, hOur);
    hOpp = Math.max(0, hOpp);
  }
  return steps;
}

function buildOppEvents(t) {
  const S=[];
  function add(l,evs){if(evs.length)S.push({label:l,events:evs})}
  add('Gioca',(t.opp_plays||[]).map(p=>{
    let h=`<b>${shortN(p.name).base}</b> (${p.ink_paid})`;
    if(p.is_shift)h+=' <span style="color:#c090ff">[SHIFT]</span>';
    if(p.is_sung)h+=' <span style="color:#80d0f0">[SONG]</span>';
    return{icon:'\u25B6',cls:'ev-play',html:h};
  }));
  add('Ability',(t.opp_abilities||[]).map(a=>({icon:'\u2728',cls:'ev-ability',html:`<b>${shortN(a.card).base}</b>: ${a.effect||a.ability||''}`})));
  add('Challenge',(t.opp_challenges||[]).map(c=>{let h=`<b>${shortN(c.attacker).base}</b> \u2192 <b>${shortN(c.defender).base}</b>`;if(c.def_killed)h+=' \u2620';if(c.atk_killed)h+=' (muore)';return{icon:'\u2694',cls:'ev-challenge',html:h}}));
  add('Quest',(t.opp_quests||[]).map(q=>({icon:'\u2B50',cls:'ev-quest',html:`<b>${shortN(q.name).base}</b> +${q.lore} lore`})));
  const dr=[];
  (t.opp_drawn||[]).forEach(d=>dr.push({icon:'\uD83C\uDCCF',cls:'ev-draw',html:`Pesca: <b>${shortN(d.name).base}</b> (${d.cost})`}));
  add('Pesca',dr);
  const de=[];
  (t.our_dead||[]).forEach(n=>de.push({icon:'\u2620',cls:'ev-death',html:`Muore (ns): <b>${shortN(n).base}</b>`}));
  (t.opp_dead||[]).filter(n=>{
    // deaths caused by opp's own actions this half
    return (t.opp_challenges||[]).some(c=>c.atk_killed && c.attacker===n);
  }).forEach(n=>de.push({icon:'\u2620',cls:'ev-death',html:`Muore (avv): <b>${shortN(n).base}</b>`}));
  add('Morti',de);
  const bo=[];
  (t.our_bounced||[]).forEach(n=>bo.push({icon:'\u21A9',cls:'ev-bounce',html:`Rimbalza (ns): <b>${shortN(n).base}</b>`}));
  add('Bounce',bo);
  return S;
}

function buildOurEvents(t) {
  const S=[];
  function add(l,evs){if(evs.length)S.push({label:l,events:evs})}
  add('Gioca',(t.our_plays||[]).map(p=>{
    let h=`<b>${shortN(p.name).base}</b> (${p.ink_paid})`;
    if(p.is_shift)h+=' <span style="color:#c090ff">[SHIFT]</span>';
    if(p.is_sung)h+=' <span style="color:#80d0f0">[SONG]</span>';
    return{icon:'\u25B6',cls:'ev-play',html:h};
  }));
  add('Ability',(t.our_abilities||[]).map(a=>({icon:'\u2728',cls:'ev-ability',html:`<b>${shortN(a.card).base}</b>: ${a.effect||''}`})));
  add('Challenge',(t.our_challenges||[]).map(c=>{let h=`<b>${shortN(c.attacker).base}</b> \u2192 <b>${shortN(c.defender).base}</b>`;if(c.def_killed)h+=' \u2620';if(c.atk_killed)h+=' (muore)';return{icon:'\u2694',cls:'ev-challenge',html:h}}));
  add('Quest',(t.our_quests||[]).map(q=>({icon:'\u2B50',cls:'ev-quest',html:`<b>${shortN(q.name).base}</b> +${q.lore} lore`})));
  const dr=[];
  (t.our_drawn||[]).forEach(d=>dr.push({icon:'\uD83C\uDCCF',cls:'ev-draw',html:`Pesca: <b>${shortN(d.name).base}</b> (${d.cost})`}));
  add('Pesca',dr);
  const de=[];
  (t.opp_dead||[]).forEach(n=>de.push({icon:'\u2620',cls:'ev-death',html:`Muore (avv): <b>${shortN(n).base}</b>`}));
  add('Morti',de);
  const bo=[];
  (t.opp_bounced||[]).forEach(n=>bo.push({icon:'\u21A9',cls:'ev-bounce',html:`Rimbalza (avv): <b>${shortN(n).base}</b>`}));
  add('Bounce',bo);
  return S;
}

// ── INIT ──
function init() {
  const meta = ARCHIVE.metadata||{};
  document.getElementById('matchupLabel').textContent = `${meta.our_deck||'?'} vs ${meta.opp_deck||'?'} \u2014 ${games.length} partite`;
  document.querySelectorAll('.filter-btn').forEach(btn=>{
    btn.addEventListener('click',()=>{
      document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      applyFilter(btn.dataset.filter);
    });
  });
  populateSelect();
  if(games.length) selectGame(0);
}

function applyFilter(f) {
  if(f==='all')filteredGames=[...games];
  else if(f==='W')filteredGames=games.filter(g=>g.result==='W');
  else if(f==='L')filteredGames=games.filter(g=>g.result==='L');
  else if(f==='otp')filteredGames=games.filter(g=>g.we_otp);
  else if(f==='otd')filteredGames=games.filter(g=>!g.we_otp);
  populateSelect();
  if(filteredGames.length) selectGame(0);
  else clearAll();
}

function populateSelect() {
  const sel=document.getElementById('gameSelect');
  sel.innerHTML='';
  filteredGames.forEach((g,i)=>{
    const o=document.createElement('option'); o.value=i;
    const r=g.result==='W'?'\u2705':'\u274C';
    const pl=g.we_otp?'OTP':'OTD';
    const mmr=g.opp_mmr?` MMR:${g.opp_mmr}`:'';
    o.textContent=`#${games.indexOf(g)+1} ${r} ${pl} T${g.length} vs ${g.opp_name||'?'}${mmr}`;
    sel.appendChild(o);
  });
  sel.onchange=()=>selectGame(+sel.value);
  document.getElementById('gameCount').textContent=`${filteredGames.length} partite`;
}

function selectGame(idx) {
  currentGameIdx=idx; currentStep=0;
  const g=filteredGames[idx]; if(!g)return;
  document.getElementById('ourLabel').textContent=g.our_name||'Noi';
  document.getElementById('oppLabel').textContent=g.opp_name||'Avversario';
  document.getElementById('ourName').textContent=g.our_name||'Noi';
  document.getElementById('oppName').textContent=g.opp_name||'Opp';
  const rb=document.getElementById('gameResult');
  rb.textContent=g.result==='W'?'VITTORIA':'SCONFITTA';
  rb.className='game-result '+(g.result==='W'?'win':'loss');

  buildSteps(g);

  // Step buttons
  const c=document.getElementById('stepButtons'); c.innerHTML='';
  let lastTurn=-1;
  steps.forEach((s,i)=>{
    if(s.turnNum!==lastTurn && lastTurn!==-1){
      const sep=document.createElement('span'); sep.className='step-sep'; c.appendChild(sep);
    }
    lastTurn=s.turnNum;
    const b=document.createElement('button');
    b.className='step-btn'+(s.who==='opp'?' opp-step':'');
    b.innerHTML=`T${s.turnNum} <span class="step-who">${s.who==='opp'?'\u25B2':'\u25BC'}</span>`;
    b.onclick=()=>goToStep(i);
    c.appendChild(b);
  });

  goToStep(0);
  renderSparkline(g);
}

function goToStep(idx) {
  if(idx<0||idx>=steps.length)return;
  currentStep=idx;
  const s=steps[idx];
  document.querySelectorAll('.step-btn').forEach((b,i)=>b.classList.toggle('active',i===idx));

  // Title
  const whoLabel = s.who==='opp' ? (filteredGames[currentGameIdx].opp_name||'Avversario') : (filteredGames[currentGameIdx].our_name||'Noi');
  document.getElementById('eventTitle').textContent = `T${s.turnNum} \u2014 ${whoLabel}`;

  // Counters
  document.getElementById('cOurLore').textContent=s.lore.our;
  document.getElementById('cOppLore').textContent=s.lore.opp;
  document.getElementById('cOurInk').textContent=`${s.inkSpent.our}/${s.ink.our}`;
  document.getElementById('cOppInk').textContent=`${s.inkSpent.opp}/${s.ink.opp}`;
  document.getElementById('cOurHand').textContent=s.hand.our;
  document.getElementById('cOppHand').textContent=s.hand.opp;
  document.getElementById('cOurDiscard').textContent=s.discard.our;
  document.getElementById('cOppDiscard').textContent=s.discard.opp;
  document.getElementById('cOurBoard').textContent=s.boardCount.our;
  document.getElementById('cOppBoard').textContent=s.boardCount.opp;

  // Board
  const prevOurSet=countMap(s.prevBoard.our);
  const prevOppSet=countMap(s.prevBoard.opp);
  renderBoard('ourBoard', s.board.our, prevOurSet, s.quested.our, s.challenged.our);
  renderBoard('oppBoard', s.board.opp, prevOppSet, s.quested.opp, s.challenged.opp);
  appendDead('ourBoard', s.dead.our, s.board.our);
  appendDead('oppBoard', s.dead.opp, s.board.opp);

  // Events
  renderEvents(s.events);
  updateMarker(s.turnIdx);
}

function countMap(arr){const m={};arr.forEach(n=>m[n]=(m[n]||0)+1);return m}

function renderBoard(id,cards,prevCounts,questSet,chalSet){
  const el=document.getElementById(id); el.innerHTML='';
  const seen={};
  cards.forEach(name=>{
    seen[name]=(seen[name]||0)+1;
    const card=CARDS_DB[name]||{};
    const mc=mkCard(name,card);
    if(seen[name]>(prevCounts[name]||0))mc.classList.add('new-card');
    if(questSet.has(name))mc.classList.add('quested');
    if(chalSet.has(name))mc.classList.add('challenged');
    el.appendChild(mc);
  });
}

function appendDead(id,deadNames,boardNames){
  const el=document.getElementById(id);
  const bs=new Set(boardNames);
  deadNames.forEach(n=>{if(!bs.has(n)){const mc=mkCard(n,CARDS_DB[n]||{});mc.classList.add('dead-card');el.appendChild(mc)}});
}

function mkCard(name,card){
  const el=document.createElement('div'); el.className='mini-card';
  const ink=cardInk(card); if(ink)el.classList.add('ink-'+ink);
  const{base,sub}=shortN(name);
  const kws=parseKW(card.ability||'');
  const isChar=(card.type||'').toLowerCase().includes('character');
  const ti=typeIc(card);
  el.innerHTML=`<div class="card-top"><span class="card-cost">${card.cost||'?'}</span><span class="card-ink">${ink?INK_LABELS[ink]||'':''}</span></div>${ti?`<span class="type-badge">${ti}</span>`:''}<div class="card-name">${base}</div>${sub?`<div class="card-sub">${sub}</div>`:''}${isChar?`<div class="card-stats">${card.str?`<span>\u2694${card.str}</span>`:''}${card.will?`<span>\uD83D\uDEE1${card.will}</span>`:''}${card.lore?`<span>\u2B50${card.lore}</span>`:''}</div>`:''}${kws.length?'<div class="card-keywords">'+kws.map(k=>`<span class="kw kw-${k.split(/\s/)[0].toLowerCase()}">${k}</span>`).join('')+'</div>':''}`;
  el.onmouseenter=e=>showTT(e,name,card);
  el.onmouseleave=hideTT;
  el.onmousemove=moveTT;
  return el;
}

function showTT(e,name,card){const tt=document.getElementById('tooltip');tt.querySelector('.tt-name').textContent=name;tt.querySelector('.tt-class').textContent=card.classifications||card.type||'';tt.querySelector('.tt-ability').textContent=card.ability||'';const p=[];if(card.cost)p.push('Cost: '+card.cost);if(card.str)p.push(card.str+'/'+card.will);if(card.lore)p.push('Lore: '+card.lore);if(card.ink)p.push(card.ink);tt.querySelector('.tt-stats').textContent=p.join(' \u2022 ');tt.classList.add('show');moveTT(e)}
function moveTT(e){const tt=document.getElementById('tooltip');let x=e.clientX+12,y=e.clientY+12;if(x+280>window.innerWidth)x=e.clientX-290;if(y+200>window.innerHeight)y=e.clientY-200;tt.style.left=x+'px';tt.style.top=y+'px'}
function hideTT(){document.getElementById('tooltip').classList.remove('show')}

function renderEvents(sections){
  const log=document.getElementById('eventLog'); log.innerHTML='';
  for(const sec of sections){
    const d=document.createElement('div');d.className='event-section';
    d.innerHTML=`<div class="event-section-label">${sec.label}</div>`;
    sec.events.forEach(ev=>{const r=document.createElement('div');r.className='event';r.innerHTML=`<span class="ev-icon ${ev.cls}">${ev.icon}</span><span>${ev.html}</span>`;d.appendChild(r)});
    log.appendChild(d);
  }
  if(!sections.length)log.innerHTML='<div style="color:var(--text2);font-size:0.78rem;padding:8px">Nessun evento</div>';
}

function renderSparkline(game){
  const el=document.getElementById('sparkline');const turns=game.turns;if(!turns.length)return;
  const maxL=Math.max(20,...turns.map(t=>Math.max(t.lore?.our||0,t.lore?.opp||0)));
  const w=100,h=40,sx=w/Math.max(turns.length-1,1);
  let op='',rp='';
  turns.forEach((t,i)=>{const x=i*sx;op+=(i?'L':'M')+`${x.toFixed(1)},${(h-h*(t.lore?.our||0)/maxL).toFixed(1)} `;rp+=(i?'L':'M')+`${x.toFixed(1)},${(h-h*(t.lore?.opp||0)/maxL).toFixed(1)} `});
  el.innerHTML=`<svg viewBox="-1 -1 ${w+2} ${h+8}" preserveAspectRatio="none">
    <line x1="0" y1="${h}" x2="${w}" y2="${h}" stroke="var(--border)" stroke-width="0.3"/>
    <line x1="0" y1="${h-h*20/maxL}" x2="${w}" y2="${h-h*20/maxL}" stroke="var(--gold)" stroke-width="0.3" stroke-dasharray="1.5" opacity="0.3"/>
    <path d="${op}" fill="none" stroke="var(--gold)" stroke-width="1.2"/>
    <path d="${rp}" fill="none" stroke="var(--red)" stroke-width="1.2" stroke-dasharray="2"/>
    ${turns.map((t,i)=>`<circle cx="${(i*sx).toFixed(1)}" cy="${(h-h*(t.lore?.our||0)/maxL).toFixed(1)}" r="0.9" fill="var(--gold)" opacity="0.6"/>`).join('')}
    <line id="sparkM" x1="0" y1="0" x2="0" y2="${h}" stroke="var(--text)" stroke-width="0.5" opacity="0.4"/>
    <text x="1" y="${h+5}" fill="var(--text2)" font-size="2.5">T1</text>
    <text x="${w-3}" y="${h+5}" fill="var(--text2)" font-size="2.5">T${turns.length}</text>
    <text x="1" y="3" fill="var(--gold)" font-size="2.5">Noi</text>
    <text x="10" y="3" fill="var(--red)" font-size="2.5">Opp</text>
  </svg>`;
  el.dataset.sx=sx;
}
function updateMarker(turnIdx){const m=document.getElementById('sparkM');if(!m)return;const sx=parseFloat(document.getElementById('sparkline').dataset.sx||0);const x=(turnIdx*sx).toFixed(1);m.setAttribute('x1',x);m.setAttribute('x2',x);m.setAttribute('opacity','0.6')}

function clearAll(){
  ['ourBoard','oppBoard','eventLog','stepButtons'].forEach(id=>{document.getElementById(id).innerHTML=''});
}

// Keyboard
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowRight'||e.key==='l'){e.preventDefault();goToStep(currentStep+1)}
  else if(e.key==='ArrowLeft'||e.key==='h'){e.preventDefault();goToStep(currentStep-1)}
  else if(e.key==='n'){if(currentGameIdx<filteredGames.length-1){document.getElementById('gameSelect').value=currentGameIdx+1;selectGame(currentGameIdx+1)}}
  else if(e.key==='p'){if(currentGameIdx>0){document.getElementById('gameSelect').value=currentGameIdx-1;selectGame(currentGameIdx-1)}}
});
document.getElementById('prevStep').onclick=()=>goToStep(currentStep-1);
document.getElementById('nextStep').onclick=()=>goToStep(currentStep+1);

if(ARCHIVE&&CARDS_DB) init();
</script>
</body>
</html>
'''


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python3 build_replay.py <DECK> <OPP> [--format core|infinity]")
        print("Es:  python3 build_replay.py AmAm ES")
        print("     python3 build_replay.py AmAm ES --format infinity")
        sys.exit(1)

    game_format = 'core'
    if '--format' in sys.argv:
        idx = sys.argv.index('--format')
        if idx + 1 < len(sys.argv):
            game_format = sys.argv[idx + 1].lower()

    build_replay_html(sys.argv[1], sys.argv[2], game_format=game_format)
