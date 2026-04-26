// === PROFILE TAB ===
let pfDrawerOpen = false;
// Default deck: always EmSa on load
let pfActiveDeck = 'EmSa';
let pfInkPickerOpen = false;
let pfInkSel = [];
let pfImproveDeckFocus = null;
let pfImproveDeckStoryCache = {};
let pfImproveDeckStoryInflight = {};
let pfStateBootstrapped = false;
const DEMO_PLAYER = { nick: 'CLOUD', country: 'IT', decks: ['ESt','AmySt','AbSt'] };

function pfEnsureState() {
  if (pfStateBootstrapped) return;
  pfStateBootstrapped = true;
  if (typeof DECK_INKS !== 'undefined' && DECK_INKS[pfActiveDeck]) {
    pfInkSel = [...DECK_INKS[pfActiveDeck]];
  }
  if (typeof selectedDeck !== 'undefined') selectedDeck = pfActiveDeck;
  if (typeof coachDeck !== 'undefined') coachDeck = pfActiveDeck;
  if (typeof selectedInks !== 'undefined' && typeof DECK_INKS !== 'undefined' && DECK_INKS[pfActiveDeck]) {
    selectedInks = [...DECK_INKS[pfActiveDeck]];
  }
}

function pfCardMeta(name) {
  const card = (rvCardsDB || {})[name] || {};
  const costNum = Number(card.cost);
  return {
    card,
    shortName: String(name || '').split(' - ')[0],
    imgUrl: rvCardsDB ? rvCardImgByName(name) : '',
    cost: Number.isFinite(costNum) ? costNum : null,
    type: String(card.type || '').toLowerCase(),
  };
}

function pfPlayerBridgeStats(saved, scope) {
  const nick = saved && saved.duelsNick ? saved.duelsNick.trim() : '';
  if (!nick || !scope) return null;
  const fmtKey = scope.format || currentFormat || 'core';
  const lookup = ((DATA.player_lookup || {})[fmtKey] || {})[nick.toLowerCase()] || {};
  const decks = Object.entries(lookup);
  if (!decks.length) return {
    nick,
    fmtKey,
    games: 0,
    wins: 0,
    losses: 0,
    wr: null,
    deckCount: 0,
    bestDeck: null,
  };

  let wins = 0;
  let losses = 0;
  let bestDeck = null;
  decks.forEach(([deck, value]) => {
    const w = Number(value.w || 0);
    const l = Number(value.l || 0);
    const games = w + l;
    wins += w;
    losses += l;
    if (games && (!bestDeck || games > bestDeck.games)) {
      bestDeck = { deck, games, wr: w / games * 100 };
    }
  });
  const games = wins + losses;
  return {
    nick,
    fmtKey,
    games,
    wins,
    losses,
    wr: games ? wins / games * 100 : null,
    deckCount: decks.length,
    bestDeck,
  };
}

function pfBridgeStatsCard(saved, scope, variant) {
  const stats = pfPlayerBridgeStats(saved, scope);
  if (!stats) return '';
  const isDemo = localStorage.getItem('pf_demo') === '1';
  const title = isDemo ? 'Demo bridge active' : 'Nickname bridge active';
  const deckLine = stats.bestDeck
    ? `${deckImg(stats.bestDeck.deck, 16)} <span>${stats.bestDeck.deck} main deck (${stats.bestDeck.games}g, ${stats.bestDeck.wr.toFixed(1)}% WR)</span>`
    : '<span>No deck sample yet</span>';
  const body = stats.games
    ? `<strong>${stats.games.toLocaleString()}</strong> matches associated, <strong style="color:${wrColor(stats.wr)}">${stats.wr.toFixed(1)}% WR</strong> personal over ${stats.deckCount} deck${stats.deckCount === 1 ? '' : 's'}.`
    : `Nickname linked as <strong>${_bpEsc(stats.nick)}</strong>, but no ${stats.fmtKey.toUpperCase()} matches are associated yet.`;
  const cta = stats.games
    ? `<button onclick="${variant === 'home' ? "switchToTab('improve')" : "var b=document.getElementById('pf-my-stats-body-improve');if(b)b.scrollIntoView({behavior:'smooth',block:'center'});"}" style="background:transparent;border:1px solid rgba(255,215,0,0.34);color:var(--gold);padding:5px 10px;border-radius:5px;font-size:0.74em;font-weight:700;cursor:pointer">${variant === 'home' ? 'Open Improve' : 'Review decks'}</button>`
    : `<button onclick="pfOpenDrawer()" style="background:transparent;border:1px solid rgba(255,215,0,0.34);color:var(--gold);padding:5px 10px;border-radius:5px;font-size:0.74em;font-weight:700;cursor:pointer">Check nickname</button>`;

  return `<div class="pf-bridge-card" style="display:flex;align-items:center;gap:12px;justify-content:space-between;flex-wrap:wrap;padding:11px 13px;margin:${variant === 'home' ? '10px 0 12px' : '0 0 14px'};border:1px solid rgba(255,215,0,0.18);border-radius:8px;background:rgba(255,215,0,0.035)">
    <div style="min-width:220px;flex:1">
      <div style="font-size:0.7rem;color:var(--gold);letter-spacing:0.12em;text-transform:uppercase;font-weight:700;margin-bottom:4px">${title}</div>
      <div style="font-size:0.84em;color:var(--text2);line-height:1.35">${body}</div>
      <div style="display:flex;align-items:center;gap:6px;font-size:0.74em;color:var(--text2);margin-top:5px">${deckLine}</div>
    </div>
    ${cta}
  </div>`;
}

function pfBuildCurveTimeline(cards) {
  if (!cards || typeof cards !== 'object') return '';
  const turns = [
    { key: 1, label: 'T1' },
    { key: 2, label: 'T2' },
    { key: 3, label: 'T3' },
    { key: 4, label: 'T4' },
    { key: 5, label: 'T5' },
    { key: 6, label: 'T6' },
    { key: 7, label: 'T7+' },
  ];
  const grouped = {};
  turns.forEach(t => { grouped[t.key] = []; });

  Object.entries(cards).forEach(([name, qty]) => {
    const meta = pfCardMeta(name);
    if (meta.cost == null) return;
    const bucket = meta.cost >= 7 ? 7 : Math.max(1, meta.cost);
    grouped[bucket].push({ name, qty, ...meta });
  });

  const steps = turns.map(turn => {
    const items = (grouped[turn.key] || []).sort((a, b) =>
      (b.qty - a.qty) ||
      ((b.type.includes('character') ? 1 : 0) - (a.type.includes('character') ? 1 : 0)) ||
      a.shortName.localeCompare(b.shortName)
    );
    const totalCopies = items.reduce((sum, item) => sum + item.qty, 0);
    const topCards = items.slice(0, 3);
    const cardsHtml = topCards.length
      ? `<div class="pf-mycurve-cards">${topCards.map(item => {
          const safeName = _bpEsc(item.name);
          const safeShort = _bpEsc(item.shortName);
          const art = item.imgUrl
            ? `<img src="${item.imgUrl}" alt="${safeName}" loading="lazy">`
            : `<div class="pf-mycurve-card-ph">${safeShort}</div>`;
          const zoom = item.imgUrl ? ` data-zoom="${item.imgUrl}"` : '';
          return `<div class="pf-mycurve-card"${zoom} onclick="if(this.dataset.zoom)pfZoomCard(this)" title="${safeName}">
            ${art}
            <span class="pf-mycurve-cardqty">${item.qty}x</span>
          </div>`;
        }).join('')}</div>`
      : `<div class="pf-mycurve-empty">No line</div>`;
    return `<div class="pf-mycurve-step">
      <div class="pf-mycurve-turn"><b>${turn.label}</b><span>${totalCopies ? totalCopies + 'c' : ''}</span></div>
      ${cardsHtml}
    </div>`;
  }).join('');

  return `<div class="pf-mycurve">
    <div class="pf-mycurve-head">
      <span class="pf-mycurve-title">Deck Curve</span>
      <span class="pf-mycurve-sub">visual by turn</span>
    </div>
    <div class="pf-mycurve-timeline">${steps}</div>
  </div>`;
}

/**
 * Best Plays card — estratto da renderProfileTab (V3-5 22/04).
 * Ora renderizzato primariamente in Play (coach_v2.js).
 * Mostra top 3 highlight reale del deck (killer curves da avversari).
 *
 * @param {string} deckCode - codice deck (es. 'ES', 'AmAm')
 * @returns {string} HTML o '' se nessun dato
 */
function buildBestPlaysCard(deckCode) {
  if (!deckCode) return '';
  if (typeof getScopeContext !== 'function') return '';
  const scope = getScopeContext();
  const BP_CAT_COLORS = { wipe: '#e85d75', lore: '#3FB950', combo: '#7B3FA0', early: '#D4A03A', tempo: '#2471A3' };
  const bpSource = scope.isInfinity ? (DATA.best_plays_infinity || DATA.best_plays || {}) : (DATA.best_plays || {});
  const bp = bpSource[deckCode] || [];
  if (!bp.length) return '';

  const perfPeriod = DATA.meta && DATA.meta.period ? DATA.meta.period : '';
  let html = `<div class="pf-kpi-card" style="margin-top:16px">
    <div class="pf-kpi-title" style="margin-bottom:10px">
      <span>Best Plays</span>
      <span style="font-size:0.85em;font-weight:400;color:var(--text2)">${perfPeriod || 'Last 3 days'}</span>
    </div><div class="bp2-list">`;

  bp.forEach((m, idx) => {
    const catColor = BP_CAT_COLORS[m.catKey] || '#D4A03A';
    const tileId = 'bp2_' + idx;

    const cardsHtml = m.cards.slice(0, 3).map(c => {
      const imgUrl = rvCardsDB ? rvCardImgByName(c.card) : '';
      const short = c.card.split(' - ')[0];
      return imgUrl
        ? `<img class="bp2-card-thumb" src="${imgUrl}" alt="${short}" title="${c.card}">`
        : `<span style="font-size:0.65em;color:var(--text2);max-width:36px;text-align:center;line-height:1.2">${short}</span>`;
    }).join('');

    let effects = '';
    if (m.kills.length) effects += `<span class="bp2-effect kills">&#9760; ${m.kills.length} kill${m.kills.length > 1 ? 's' : ''}</span>`;
    if (m.bounced.length) effects += `<span class="bp2-effect bounce">&#8617; ${m.bounced.length}</span>`;
    if (m.abilities.length) effects += `<span class="bp2-effect combo">&#9733; ${m.abilities.length}</span>`;

    const ctxCards = (m.context || []).map(c => `<strong>${c.split(' - ')[0]}</strong>`).join(', ');
    const ctxHtml = ctxCards ? `<div class="bp2-context"><span style="opacity:0.6">&#9650;</span><span class="bp2-context-text">Board: ${ctxCards}</span></div>` : '';

    const playsHtml = m.cards.map((c, i) => {
      const imgUrl = rvCardsDB ? rvCardImgByName(c.card) : '';
      const short = c.card.split(' - ')[0];
      const imgTag = imgUrl
        ? `<img class="bp2-play-img" src="${imgUrl}" alt="${short}">`
        : `<div style="width:52px;height:73px;border-radius:4px;background:var(--bg3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:0.6em;color:var(--text2);padding:4px">${short}</div>`;
      const plus = i < m.cards.length - 1 ? '<span style="color:var(--text2);font-size:0.85em;font-weight:700;align-self:center;margin-top:-20px;opacity:0.5">+</span>' : '';
      return `<div class="bp2-play-card" title="${c.card}">${imgTag}<span class="bp2-play-cost">${c.cost}</span><span class="bp2-play-name">${short}</span></div>${plus}`;
    }).join('');

    let chipsHtml = '';
    if (m.kills.length) {
      const killNames = m.kills.map(k => `<span class="bp2-killed-name">&#9760; ${k.name}</span>`).join('');
      chipsHtml += `<div class="bp2-effect-chip kill"><span>&#9760;</span><div>${m.kills.length} kill${m.kills.length > 1 ? 's' : ''}${killNames}</div></div>`;
    }
    if (m.lore >= 3) chipsHtml += `<div class="bp2-effect-chip lore"><span>&#11089;</span> +${m.lore} lore</div>`;
    m.abilities.forEach(ab => { chipsHtml += `<div class="bp2-effect-chip ability"><span>&#9733;</span> ${ab}</div>`; });
    m.bounced.forEach(b => { chipsHtml += `<div class="bp2-effect-chip bounce"><span>&#8617;</span> Bounced: ${b}</div>`; });

    const vsTag = m.vs ? `<span style="font-size:0.68em;color:var(--text2);margin-left:4px">vs ${m.vs}</span>` : '';

    html += `<div class="bp2-tile" id="${tileId}" style="--cat-color:${catColor}" onclick="(function(id){var t=document.getElementById(id);var w=t.classList.contains('open');document.querySelectorAll('.bp2-tile.open').forEach(function(e){e.classList.remove('open')});if(!w)t.classList.add('open')})('${tileId}')">
      <div class="bp2-compact">
        <div class="bp2-cat">${m.category.replace(' ', '<br>')}</div>
        <div class="bp2-turn-chip"><div class="bp2-turn-num">T${m.turn}</div><div class="bp2-ink-label">${m.ink}&#128167;</div></div>
        <div class="bp2-cards">${cardsHtml}</div>
        <div class="bp2-summary">
          <div class="bp2-headline">${m.headline}${vsTag}</div>
          <div class="bp2-tagline">${effects}</div>
        </div>
        <svg class="bp2-chevron" width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 5l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
      <div class="bp2-expanded"><div class="bp2-exp-inner">
        ${ctxHtml}
        <div class="bp2-play-label">Cards played</div>
        <div class="bp2-plays-row">${playsHtml}</div>
        <div style="margin-bottom:8px"><div class="bp2-play-label">Effects</div><div class="bp2-effects-list">${chipsHtml}</div></div>
      </div></div>
    </div>`;
  });
  html += '</div></div>';
  return html;
}

function renderProfileTab(main) {
  pfEnsureState();
  const scope = getScopeContext();
  // Preload cards DB for tech card images
  if (!rvCardsDB) {
    fetch('/api/replay/cards_db').then(r => r.json()).then(db => { rvCardsDB = db; if (currentTab === 'home') render(); }).catch(() => {});
  }
  const saved = {
    email: localStorage.getItem('pf_email') || '',
    duelsNick: localStorage.getItem('pf_duels_nick') || '',
    lorcaNick: localStorage.getItem('pf_lorca_nick') || '',
    country: localStorage.getItem('pf_country') || '',
  };
  // Migrate pf_deck → pf_deck_pins
  let pins = JSON.parse(localStorage.getItem('pf_deck_pins') || 'null');
  if (!pins) {
    const old = localStorage.getItem('pf_deck');
    pins = old ? [old] : [];
    localStorage.setItem('pf_deck_pins', JSON.stringify(pins));
  }
  const planLabel = PRO_UNLOCKED ? 'Pro' : 'Free';
  const planCls = PRO_UNLOCKED ? 'plan-pro' : 'plan-free';
  const nick = saved.duelsNick || saved.email || 'Guest';
  const initials = nick[0].toUpperCase();

  // Determine perim for profile data
  const pfPerim = scope.primaryPerimeter;
  const pd = DATA.perimeters[pfPerim] || {};

  // ── HEADER ──
  const gearSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>';
  const isDemo = localStorage.getItem('pf_demo') === '1';
  const hasNudge = !saved.duelsNick || isDemo;
  const headerHtml = `<div class="pf-header">
    <div class="pf-avatar">${initials}</div>
    <div class="pf-identity">
      <div class="pf-nick">${nick}</div>
      <div class="pf-subtitle"><span class="plan-badge ${planCls}">${planLabel}</span>
        ${saved.country ? '<span>' + saved.country + '</span>' : ''}
      </div>
    </div>
    ${hasNudge ? '<button class="pf-info-btn" onclick="var n=document.getElementById(\'pf-nudge-tip\');if(n)n.classList.toggle(\'open\')" title="Setup profile">i</button>' : ''}
    <button class="pf-gear-btn" onclick="pfOpenDrawer()" title="Settings">${gearSvg}</button>
  </div>`;

  // ── ONBOARDING — collapsed into info expandable ──
  let nudgeHtml = '';
  {
    let nudgeInner = '';
    if (!saved.duelsNick) {
      nudgeInner = `<a onclick="pfOpenDrawer()" style="color:var(--gold);cursor:pointer;text-decoration:underline">Link your duels.ink nickname</a> to see lookup stats, or <a onclick="pfLoadDemo()" style="color:var(--gold);cursor:pointer;text-decoration:underline">try demo player</a>.`;
    } else if (isDemo) {
      nudgeInner = `Demo mode — viewing <strong>${saved.duelsNick}</strong>. <a onclick="pfOpenDrawer()" style="color:var(--gold);cursor:pointer;text-decoration:underline">Set your own nickname</a> · <a onclick="pfClearDemo()" style="color:var(--text2);cursor:pointer;text-decoration:underline">reset</a>`;
    }
    if (nudgeInner) {
      nudgeHtml = `<div class="pf-info-tip" id="pf-nudge-tip" style="margin:0 0 8px">${nudgeInner}</div>`;
    }
  }

  const myNick = saved.duelsNick;

  // ── STUDY DECKS (ink picker + pinned shortcuts → syncs to other tabs) ──
  if (!pfActiveDeck && pins.length) pfActiveDeck = pins[0];
  const activeDk = pfActiveDeck;

  // Standard / Custom deck toggle
  const hasDeck = !!myDeckCards;
  const deckModeHtml = `<div class="lab-base-seg" style="margin:0">
    <button class="lab-base-btn${!scope.isCustomDeck || !hasDeck ?' active':''}" style="padding:4px 10px;font-size:0.75em" onclick="myDeckMode='standard';pfInkSel=[];render()">Meta Deck</button>
    <button class="lab-base-btn${scope.isCustomDeck?' active':''}" style="padding:4px 10px;font-size:0.75em"
      onclick="myDeckMode='custom';${hasDeck?'restoreMyDeckInks();render()':'showDeckHistory()'}">My Deck</button>
  </div>`;

  // ── DECK SELECTOR INNER (used inside hero card) ──
  let deckSelectorInner = '';
  if (!scope.isCustomDeck || !hasDeck) {
    // STANDARD MODE: ink picker — step-based layout
    const step = pfInkSel.length;
    const stepLabel = step === 0 ? '<span style="font-size:0.78em;color:var(--gold)">Tap 2 ink colors to select your deck</span>'
                    : step === 1 ? '<span style="font-size:0.78em;color:var(--gold)">Pick one more ink</span>'
                    : '';
    let inkGrid = '<div class="pf-ink-grid">';
    INK_LIST.forEach(ink => {
      const isSel = pfInkSel.includes(ink.id);
      inkGrid += `<div class="pf-ink-btn${isSel ? ' selected' : ''}" onclick="pfToggleInk('${ink.id}')" title="${ink.label}">
        <div style="width:36px;height:36px">${INK_SVGS[ink.id]}</div>
        <span class="pf-ink-label">${ink.label}</span>
      </div>`;
    });
    inkGrid += '</div>';

    let pinAction = '';
    if (step === 2) {
      const key = [...pfInkSel].sort().join('+');
      const resolved = INK_PAIR_TO_DECK[key];
      if (resolved) {
        const isPinned = pins.includes(resolved);
        if (!isPinned && pins.length < 3) {
          pinAction = `<button class="pf-save-btn" style="padding:5px 14px;font-size:0.78em;margin-top:8px" onclick="pfPinAndSelect('${resolved}')">&#9733; Pin this deck</button>`;
        }
      }
    }
    deckSelectorInner = `<div style="margin-bottom:4px">${stepLabel}</div>${inkGrid}${pinAction}`;
  } else {
    // MY DECK MODE
    const deckName = localStorage.getItem('lorcana_deck_name') || 'Unnamed';
    const deckCode = localStorage.getItem('lorcana_deck_code') || selectedDeck || '?';
    const cardCount = myDeckCards ? Object.values(myDeckCards).reduce((s,v)=>s+v,0) : 0;
    const myDeckCurveHtml = myDeckCards ? pfBuildCurveTimeline(myDeckCards) : '';
    deckSelectorInner = `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 12px;border-radius:10px;background:rgba(212,160,58,0.08);border:1px solid rgba(212,160,58,0.25)">
      <div style="display:flex;align-items:center;gap:8px;cursor:pointer;flex:1;min-width:0" onclick="showDeckHistory()">
        ${deckCode !== '?' ? deckImg(deckCode, 28) : ''}
        <div style="min-width:0">
          <div style="font-size:0.88em;font-weight:600;color:var(--gold);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${deckName}</div>
          <div style="font-size:0.68em;color:var(--text2)">${cardCount} cards</div>
        </div>
        <span style="font-size:0.7em;color:var(--text2);margin-left:auto">&#9660;</span>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <span style="cursor:pointer;font-size:0.82em;color:var(--gold)" onclick="showDeckModal()">&#9998; Edit</span>
        <span style="cursor:pointer;color:var(--text2);font-size:0.82em" onclick="clearMyDeckAndRender()">&times;</span>
      </div>
      <div style="width:100%">${myDeckCurveHtml}</div>
    </div>`;
  }

  // Saved Decks section
  let pinsInner = '';
  if (pins.length) {
    let pinCards = '';
    pins.forEach(code => {
      const isActive = activeDk === code;
      const dn = DECK_NAMES[code] || code;
      pinCards += `<div class="pf-saved-deck${isActive ? ' active' : ''}" onclick="pfSelectDeck('${code}')">
        ${deckImg(code, 28)}
        <div style="min-width:0;flex:1">
          <div style="font-size:0.82em;font-weight:600;color:${isActive ? 'var(--gold)' : 'var(--text)'};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${dn}</div>
          <div style="font-size:0.65em;color:var(--text2)">${code}</div>
        </div>
        <span class="pf-saved-deck-x" onclick="event.stopPropagation();pfRemoveDeck('${code}')" title="Remove">&times;</span>
      </div>`;
    });
    pinsInner = `<div class="pf-saved-decks-section">
      <div class="pf-saved-decks-label">Saved Decks</div>
      ${pinCards}
    </div>`;
  }

  // ── DECK OVERVIEW (KPI for selected deck in meta) — embedded into hero card ──
  let heroKpiHtml = '';   // KPI strip + mu strip
  let heroIdentityHtml = ''; // deck name / identity header
  if (activeDk) {
    const perfPeriod = DATA.meta && DATA.meta.period ? DATA.meta.period : '';
    const wr = (pd.wr || {})[activeDk];
    const ms = (pd.meta_share || {})[activeDk];
    const matrix = (pd.matrix || {})[activeDk];
    const searchPerims = scope.isInfinity
      ? ['infinity','infinity_top','infinity_pro']
      : ['set11','top','pro','friends_core'];
    const playerSet = new Set();
    searchPerims.forEach(perim => {
      const tp = (DATA.perimeters[perim] || {}).top_players || [];
      tp.filter(p => p.deck === activeDk).forEach(p => playerSet.add(p.name.toLowerCase()));
    });
    const playerCount = playerSet.size;
    const fullName = DECK_NAMES[activeDk] || activeDk;

    heroIdentityHtml = `<div class="pf-hero-deck-identity">
      ${deckImg(activeDk, 32)}
      <div style="min-width:0">
        <div class="pf-hero-deck-name">${fullName}</div>
        <div class="pf-hero-deck-code">${activeDk}${perfPeriod ? ' &middot; ' + perfPeriod : ''}</div>
      </div>
    </div>`;

    if (wr) {
      const wrVal = parseFloat(wr.wr.toFixed(1));
      const shareVal = ms ? parseFloat(ms.share.toFixed(1)) : 0;
      heroKpiHtml = `<div class="pf-hero-kpi-strip">
        <div class="pf-hero-kpi">
          <div class="pf-hero-kpi-val" style="color:${wrColor(wrVal)}">${wrVal}%</div>
          <div class="pf-hero-kpi-lbl">Win Rate</div>
        </div>
        <div class="pf-hero-kpi">
          <div class="pf-hero-kpi-val">${shareVal}%</div>
          <div class="pf-hero-kpi-lbl">Meta Share</div>
        </div>
        <div class="pf-hero-kpi">
          <div class="pf-hero-kpi-val">${wr.games.toLocaleString()}</div>
          <div class="pf-hero-kpi-lbl">Games</div>
        </div>
        <div class="pf-hero-kpi">
          <div class="pf-hero-kpi-val">${playerCount}</div>
          <div class="pf-hero-kpi-lbl">Players</div>
        </div>
      </div>`;
      if (matrix) {
        const mus = Object.entries(matrix)
          .filter(([_,v]) => v.t >= 5)
          .map(([opp, v]) => ({ opp, wr: v.w/v.t*100, t: v.t }))
          .sort((a,b) => b.wr - a.wr);
        if (mus.length >= 2) {
          const best2 = mus.slice(0, 2);
          const worst2 = mus.slice(-2).reverse();
          heroKpiHtml += `<div class="pf-radar-mu-section">
            <div class="pf-radar-mu-group">
              <div class="pf-radar-mu-label" style="color:var(--green)">Best matchups</div>
              <div class="pf-radar-mu-items">${best2.map(m =>
                `<span class="pf-radar-mu-chip">${deckImg(m.opp,16)} <b style="color:var(--green)">${m.wr.toFixed(0)}%</b></span>`
              ).join('')}</div>
            </div>
            <div class="pf-radar-mu-group">
              <div class="pf-radar-mu-label" style="color:var(--red)">Worst matchups</div>
              <div class="pf-radar-mu-items">${worst2.map(m =>
                `<span class="pf-radar-mu-chip">${deckImg(m.opp,16)} <b style="color:var(--red)">${m.wr.toFixed(0)}%</b></span>`
              ).join('')}</div>
            </div>
          </div>`;
        }
      }
    }
  } else {
    heroIdentityHtml = `<div class="pf-hero-deck-identity" style="border-bottom:none;margin-bottom:0;padding-bottom:0">
      <div style="color:var(--text2);font-size:0.82em">Select 2 inks to analyze a deck</div>
    </div>`;
  }

  // V3-5 22/04: Tech Cards / Non-Standard Picks moved to Deck (pfBuildDeckWorkspace).

  // V3-5 22/04: Meta Radar deep + Consensus List moved to Meta / Deck.
  // Home keeps only the Matchup snapshot card (built below from heroKpiHtml).

  // ── BEST PLAYS v2 (real game highlights) ──
  // V3-5 22/04: il rendering effettivo e' ora in Play (renderCoachV2Tab via buildBestPlaysCard).
  // Qui lasciamo tipsHtml vuoto per Home (Home resta cockpit + snapshot, non "highlight reel").
  const BP_CAT_COLORS = { wipe: '#e85d75', lore: '#3FB950', combo: '#7B3FA0', early: '#D4A03A', tempo: '#2471A3' };
  let tipsHtml = '';
  if (false && activeDk) { // disabilitato in Home (V3-5) — riabilitare flippando false -> true se serve
    const bpSource = scope.isInfinity ? (DATA.best_plays_infinity || DATA.best_plays || {}) : (DATA.best_plays || {});
    const bp = bpSource[activeDk] || [];
    if (bp.length) {
      const perfPeriod = DATA.meta && DATA.meta.period ? DATA.meta.period : '';
      tipsHtml = `<div class="pf-kpi-card">
        <div class="pf-kpi-title" style="margin-bottom:10px">
          <span>Best Plays</span>
          <span style="font-size:0.85em;font-weight:400;color:var(--text2)">${perfPeriod || 'Last 3 days'}</span>
        </div><div class="bp2-list">`;

      bp.forEach((m, idx) => {
        const catColor = BP_CAT_COLORS[m.catKey] || '#D4A03A';
        const tileId = 'bp2_' + idx;

        // Card thumbnails
        const cardsHtml = m.cards.slice(0, 3).map(c => {
          const imgUrl = rvCardsDB ? rvCardImgByName(c.card) : '';
          const short = c.card.split(' - ')[0];
          return imgUrl
            ? `<img class="bp2-card-thumb" src="${imgUrl}" alt="${short}" title="${c.card}">`
            : `<span style="font-size:0.65em;color:var(--text2);max-width:36px;text-align:center;line-height:1.2">${short}</span>`;
        }).join('');

        // Compact effect chips
        let effects = '';
        if (m.kills.length) effects += `<span class="bp2-effect kills">&#9760; ${m.kills.length} kill${m.kills.length > 1 ? 's' : ''}</span>`;
        if (m.bounced.length) effects += `<span class="bp2-effect bounce">&#8617; ${m.bounced.length}</span>`;
        if (m.abilities.length) effects += `<span class="bp2-effect combo">&#9733; ${m.abilities.length}</span>`;

        // Expanded: context
        const ctxCards = (m.context || []).map(c => `<strong>${c.split(' - ')[0]}</strong>`).join(', ');
        const ctxHtml = ctxCards ? `<div class="bp2-context"><span style="opacity:0.6">&#9650;</span><span class="bp2-context-text">Board: ${ctxCards}</span></div>` : '';

        // Expanded: cards played (larger)
        const playsHtml = m.cards.map((c, i) => {
          const imgUrl = rvCardsDB ? rvCardImgByName(c.card) : '';
          const short = c.card.split(' - ')[0];
          const imgTag = imgUrl
            ? `<img class="bp2-play-img" src="${imgUrl}" alt="${short}">`
            : `<div style="width:52px;height:73px;border-radius:4px;background:var(--bg3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:0.6em;color:var(--text2);padding:4px">${short}</div>`;
          const plus = i < m.cards.length - 1 ? '<span style="color:var(--text2);font-size:0.85em;font-weight:700;align-self:center;margin-top:-20px;opacity:0.5">+</span>' : '';
          return `<div class="bp2-play-card" title="${c.card}">${imgTag}<span class="bp2-play-cost">${c.cost}</span><span class="bp2-play-name">${short}</span></div>${plus}`;
        }).join('');

        // Expanded: effect chips
        let chipsHtml = '';
        if (m.kills.length) {
          const killNames = m.kills.map(k => `<span class="bp2-killed-name">&#9760; ${k.name}</span>`).join('');
          chipsHtml += `<div class="bp2-effect-chip kill"><span>&#9760;</span><div>${m.kills.length} kill${m.kills.length > 1 ? 's' : ''}${killNames}</div></div>`;
        }
        if (m.lore >= 3) chipsHtml += `<div class="bp2-effect-chip lore"><span>&#11089;</span> +${m.lore} lore</div>`;
        m.abilities.forEach(ab => { chipsHtml += `<div class="bp2-effect-chip ability"><span>&#9733;</span> ${ab}</div>`; });
        m.bounced.forEach(b => { chipsHtml += `<div class="bp2-effect-chip bounce"><span>&#8617;</span> Bounced: ${b}</div>`; });

        const vsTag = m.vs ? `<span style="font-size:0.68em;color:var(--text2);margin-left:4px">vs ${m.vs}</span>` : '';

        tipsHtml += `<div class="bp2-tile" id="${tileId}" style="--cat-color:${catColor}" onclick="(function(id){var t=document.getElementById(id);var w=t.classList.contains('open');document.querySelectorAll('.bp2-tile.open').forEach(function(e){e.classList.remove('open')});if(!w)t.classList.add('open')})('${tileId}')">
          <div class="bp2-compact">
            <div class="bp2-cat">${m.category.replace(' ', '<br>')}</div>
            <div class="bp2-turn-chip"><div class="bp2-turn-num">T${m.turn}</div><div class="bp2-ink-label">${m.ink}&#128167;</div></div>
            <div class="bp2-cards">${cardsHtml}</div>
            <div class="bp2-summary">
              <div class="bp2-headline">${m.headline}${vsTag}</div>
              <div class="bp2-tagline">${effects}</div>
            </div>
            <svg class="bp2-chevron" width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 5l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
          <div class="bp2-expanded"><div class="bp2-exp-inner">
            ${ctxHtml}
            <div class="bp2-play-label">Cards played</div>
            <div class="bp2-plays-row">${playsHtml}</div>
            <div style="margin-bottom:8px"><div class="bp2-play-label">Effects</div><div class="bp2-effects-list">${chipsHtml}</div></div>
          </div></div>
        </div>`;
      });
      tipsHtml += '</div></div>';
    }
  }

  // ── COACH CORNER (visible only when there's actual coach content) ──
  // V3-5 22/04: empty Coach Corner = visual noise on Home — hidden unless populated.
  let coachHtml = '';
  const teamData = DATA.team;
  let myTeamPlayer = null;
  if (myNick && teamData && teamData.players) {
    myTeamPlayer = teamData.players.find(p => p.name.toLowerCase() === myNick.toLowerCase());
  }
  const diaryKey = myNick ? 'coach_diary_' + myNick : null;
  const diary = diaryKey ? JSON.parse(localStorage.getItem(diaryKey) || '[]') : [];
  const coachNotes = myNick ? (localStorage.getItem('tt_notes_' + myNick) || '') : '';
  const playerAlerts = myTeamPlayer ? (myTeamPlayer.alerts || []) : [];

  if (playerAlerts.length || diary.length || coachNotes) {
    coachHtml = '<div class="pf-kpi-card"><div class="pf-kpi-title"><span>Coach Corner</span></div>';
    if (playerAlerts.length) {
      playerAlerts.forEach(a => {
        const sev = a.type === 'danger' ? 'var(--red)' : 'var(--yellow)';
        coachHtml += `<div style="display:flex;align-items:start;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);font-size:0.84em">
          <span style="width:6px;height:6px;border-radius:50%;background:${sev};margin-top:6px;flex-shrink:0"></span>
          <span>${a.msg}</span></div>`;
      });
    }
    if (diary.length) {
      diary.slice(-5).reverse().forEach(e => {
        const tagColor = e.tag === 'alert' ? 'var(--red)' : e.tag === 'tip' ? 'var(--green)' : 'var(--gold)';
        coachHtml += `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
            <span style="font-size:0.72em;padding:2px 8px;border-radius:10px;background:${tagColor}22;color:${tagColor};text-transform:uppercase;font-weight:600">${e.tag || 'note'}</span>
            <span style="font-size:0.72em;color:var(--text2)">${e.date || ''}</span>
          </div>
          <div style="font-size:0.84em;line-height:1.5">${e.text || ''}</div>
        </div>`;
      });
    }
    if (coachNotes) {
      coachHtml += `<div style="margin-top:10px;padding:10px;background:var(--bg3);border-radius:8px;font-size:0.84em;line-height:1.5;white-space:pre-wrap;color:var(--text2)">${coachNotes}</div>`;
    }
    coachHtml += '</div>';
  }

  // ── SETTINGS DRAWER ──
  const countries = [['IT','Italy'],['DE','Germany'],['FR','France'],['ES','Spain'],['UK','United Kingdom'],['US','United States'],['NL','Netherlands'],['BE','Belgium'],['AT','Austria'],['CH','Switzerland'],['JP','Japan']];
  let countryOpts = '<option value="">Select...</option>';
  countries.forEach(([code, name]) => {
    countryOpts += `<option value="${code}"${saved.country === code ? ' selected' : ''}>${name}</option>`;
  });
  // Deck pins picker
  const allDecks = Object.keys(DECK_INKS || {});
  let pinPickerHtml = '<div style="display:flex;gap:6px;flex-wrap:wrap">';
  allDecks.forEach(d => {
    const isPinned = pins.includes(d);
    const sel = isPinned ? 'border-color:var(--gold);background:rgba(212,160,58,0.15)' : '';
    pinPickerHtml += `<button class="pf-ghost-btn" style="padding:4px 8px;display:flex;align-items:center;gap:4px;${sel}" onclick="pfTogglePin('${d}')">${deckImg(d,22)}</button>`;
  });
  pinPickerHtml += '</div>';

  const drawerHtml = `
  <div class="pf-drawer-overlay${pfDrawerOpen ? ' open' : ''}" onclick="pfCloseDrawer()"></div>
  <div class="pf-drawer${pfDrawerOpen ? ' open' : ''}" id="pf-settings-drawer">
    <div class="pf-drawer-head">
      <h3>Settings</h3>
      <button class="pf-drawer-close" onclick="pfCloseDrawer()">&times;</button>
    </div>
    <div class="pf-drawer-section">
      <h4>Account</h4>
      <div class="pf-form-group">
        <label>Email</label>
        <input type="email" class="ev-input" id="pf-email" value="${saved.email}" placeholder="your@email.com">
      </div>
      <button class="pf-save-btn" onclick="localStorage.setItem('pf_email',document.getElementById('pf-email').value);pfCloseDrawer();render()">Save</button>
    </div>
    <div class="pf-drawer-section">
      <h4>Gaming</h4>
      <div class="pf-form-group">
        <label>duels.ink Nickname</label>
        <input type="text" class="ev-input" id="pf-duels-nick" value="${saved.duelsNick}" placeholder="YourNickname">
      </div>
      <div class="pf-form-group">
        <label>Lorcanito Nickname</label>
        <input type="text" class="ev-input" id="pf-lorca-nick" value="${saved.lorcaNick}" placeholder="YourNickname">
      </div>
      <button class="pf-save-btn" onclick="localStorage.setItem('pf_duels_nick',document.getElementById('pf-duels-nick').value);localStorage.setItem('pf_lorca_nick',document.getElementById('pf-lorca-nick').value);localStorage.removeItem('pf_demo');pfCloseDrawer();render()">Save Nicknames</button>
      <div class="pf-form-group" style="margin-top:14px">
        <label>Country</label>
        <select class="deck-select" id="pf-country" onchange="localStorage.setItem('pf_country',this.value)" style="width:100%">${countryOpts}</select>
      </div>
    </div>
    <div class="pf-drawer-section">
      <h4>Pinned Decks (up to 3)</h4>
      <div style="font-size:0.78em;color:var(--text2);margin-bottom:8px">Click to pin/unpin decks for your home dashboard.</div>
      ${pinPickerHtml}
    </div>
    <div class="pf-drawer-section">
      <h4>Plan</h4>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span class="plan-badge ${planCls}">${planLabel}</span>
        <span style="font-size:0.82em;color:var(--text2)">${PRO_UNLOCKED ? 'Full access' : 'Free plan'}</span>
      </div>
      ${PRO_UNLOCKED ? '' : '<button class="pf-save-btn" style="background:var(--gold);color:var(--bg)" onclick="PRO_UNLOCKED=true;pfCloseDrawer();render()">Upgrade &mdash; 12\u20AC/mo</button>'}
    </div>
  </div>`;

  // ── ASSEMBLE (redesigned layout) ──
  // Row 1: User header
  // Row 2: Hero — Deck Selector card (left) + Meta Radar card (right)
  // Row 3: List Panel — Standard List (left) + Tech Cards (right)
  // Row 3b: Meta Deck
  // Row 4: Best Plays
  // Row 5: Coach Corner

  // Build the mode toggle strip (Meta Deck / My Deck)
  const deckModeToggle = `<div class="lab-base-seg" style="margin:0">
    <button class="lab-base-btn${!scope.isCustomDeck || !hasDeck ?' active':''}" style="padding:3px 9px;font-size:0.7em" onclick="myDeckMode='standard';pfInkSel=[];render()">Meta Deck</button>
    <button class="lab-base-btn${scope.isCustomDeck?' active':''}" style="padding:3px 9px;font-size:0.7em"
      onclick="myDeckMode='custom';${hasDeck?'restoreMyDeckInks();render()':'showDeckHistory()'}">My Deck</button>
  </div>`;
  const bridgeStatsHtml = pfBridgeStatsCard(saved, scope, 'home');

  // ── MY STATS (collapsible, from player_lookup) ──
  let myStatsHtml = '';
  if (myNick) {
    const nickLow = myNick.toLowerCase();
    const fmtKey = scope.format;
    const lookup = ((DATA.player_lookup || {})[fmtKey] || {})[nickLow] || {};
    const allDecks = Object.entries(lookup).sort((a, b) => (b[1].w + b[1].l) - (a[1].w + a[1].l));
    const totalW = allDecks.reduce((s, [_, v]) => s + v.w, 0);
    const totalL = allDecks.reduce((s, [_, v]) => s + v.l, 0);
    const totalGames = totalW + totalL;
    const bestMmr = allDecks.reduce((s, [_, v]) => Math.max(s, v.mmr || 0), 0);

    if (totalGames > 0) {
      const totalWr = (totalW / totalGames * 100).toFixed(1);
      // Build deck rows with WR bar + worst matchup
      let deckRows = '';
      allDecks.forEach(([dk, v]) => {
        const g = v.w + v.l;
        const wr = (v.w / g * 100).toFixed(1);
        const wrPct = parseFloat(wr);
        const isActive = dk === activeDk;
        // Find worst matchup for this deck from community matrix
        const matrix = (pd.matrix || {})[dk] || {};
        let worstOpp = '', worstWr = 100;
        Object.entries(matrix).forEach(([opp, s]) => {
          if (s.t >= 3) {
            const oppWr = s.w / s.t * 100;
            if (oppWr < worstWr) { worstWr = oppWr; worstOpp = opp; }
          }
        });
        const worstHtml = worstOpp
          ? `<span style="display:inline-flex;align-items:center;gap:2px;font-size:0.7em;color:var(--red)">${deckImg(worstOpp,12)} ${worstWr.toFixed(0)}%</span>`
          : '';
        deckRows += `<div class="pf-my-deck-row${isActive ? ' active' : ''}" onclick="pfSelectDeck('${dk}')">
          <div style="display:flex;align-items:center;gap:6px;min-width:0;flex:1">
            ${deckImg(dk, 22)}
            <span style="font-size:0.82em;font-weight:${isActive ? '700' : '500'};color:${isActive ? 'var(--gold)' : 'var(--text)'};white-space:nowrap">${dk}</span>
            <span style="font-size:0.68em;color:var(--text2)">${g}g</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            ${worstHtml}
            <div style="width:50px;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden">
              <div style="height:100%;width:${wrPct}%;background:${wrColor(wrPct)};border-radius:3px"></div>
            </div>
            <span style="font-size:0.82em;font-weight:700;color:${wrColor(wrPct)};min-width:38px;text-align:right">${wr}%</span>
          </div>
        </div>`;
      });

      myStatsHtml = `<div class="pf-my-stats-section">
        <div class="pf-my-stats-toggle" onclick="var b=document.getElementById('pf-my-stats-body');b.style.display=b.style.display==='none'?'block':'none';this.querySelector('.pf-my-stats-chev').classList.toggle('open')">
          <span class="pf-my-stats-label">Player lookup</span>
          <span style="font-size:0.72em;color:var(--text2)">${totalGames}g · ${totalWr}% · MMR ${bestMmr}</span>
          <svg class="pf-my-stats-chev" width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <div id="pf-my-stats-body" style="display:none">
          <div style="display:flex;flex-direction:column;gap:2px;margin-top:6px">
            ${deckRows}
          </div>
        </div>
      </div>`;
    } else {
      myStatsHtml = `<div class="pf-my-stats-section">
        <div class="pf-my-stats-label" style="padding:0">Player lookup</div>
        <div style="font-size:0.75em;color:var(--text2);padding:4px 0">No games found for <strong>${myNick}</strong> in the last 3 days</div>
      </div>`;
    }
  } else {
    myStatsHtml = `<div class="pf-my-stats-section">
      <div class="pf-my-stats-label" style="padding:0">Player lookup</div>
      <div style="font-size:0.75em;color:var(--text2);padding:4px 0"><a onclick="pfOpenDrawer()" style="color:var(--gold);cursor:pointer;text-decoration:underline">Link your duels.ink nickname</a> to see lookup stats</div>
    </div>`;
  }

  // Hero deck card (left panel of hero row)
  const heroDeckCard = `<div class="pf-hero-deck">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <span class="pf-kpi-title" style="margin:0;color:rgba(212,160,58,0.9)">Select Your Deck</span>
      ${deckModeToggle}
    </div>
    ${heroIdentityHtml}
    ${deckSelectorInner}
    ${pinsInner}
    ${(window.V3 && window.V3.SavedDecks) ? window.V3.SavedDecks.buildHomeSection() : ''}
    ${bridgeStatsHtml}
    ${myStatsHtml}
  </div>`;

  // Meta Radar full spostato in Meta tab (V3-5 22/04) — in Home mostriamo solo KPI essenziali + CTA
  const heroRadarCard = activeDk ? `<div class="pf-hero-radar">
    <div class="pf-hero-radar-head">
      <span class="pf-hero-radar-title">Matchup snapshot</span>
      <button onclick="switchToTab('meta')" style="background:transparent;border:1px solid rgba(255,215,0,0.4);color:var(--gold);padding:4px 10px;border-radius:4px;font-size:0.72em;cursor:pointer;font-weight:600">Full Meta →</button>
    </div>
    <div class="pf-radar-deck-banner">
      ${deckImg(activeDk, 36)}
      <div class="pf-radar-deck-info">
        <div class="pf-radar-deck-name">${DECK_NAMES[activeDk] || activeDk}</div>
        <div class="pf-radar-deck-code">${activeDk}</div>
      </div>
    </div>
    ${heroKpiHtml}
  </div>` : `<div class="pf-hero-radar" style="align-items:center;justify-content:center;min-height:120px">
    <div style="color:var(--text2);font-size:0.82em;text-align:center">Select a deck to<br>see KPI snapshot</div>
  </div>`;

  // Empty-state onboarding: shown only when no deck is picked yet.
  const showOnboarding = !activeDk;
  const onboardHtml = showOnboarding ? `<div class="pf-onboard-hero">
    <div class="pf-onboard-head">
      <div class="pf-onboard-eyebrow">START HERE</div>
      <div class="pf-onboard-title">Three steps to unlock your dashboard</div>
    </div>
    <div class="pf-onboard-steps">
      <div class="pf-onboard-step">
        <div class="pf-onboard-num">1</div>
        <div class="pf-onboard-step-title">Pick your deck</div>
        <div class="pf-onboard-step-body">Tap 2 ink colors in the card below, or upload a custom decklist.</div>
      </div>
      <div class="pf-onboard-step">
        <div class="pf-onboard-num">2</div>
        <div class="pf-onboard-step-title">Check the meta</div>
        <div class="pf-onboard-step-body">Open <strong>Meta</strong> to see how your deck matches the field.</div>
      </div>
      <div class="pf-onboard-step">
        <div class="pf-onboard-num">3</div>
        <div class="pf-onboard-step-title">Prepare the match</div>
        <div class="pf-onboard-step-body">Go to <strong>Play</strong> for killer curves, threats and cheatsheet.</div>
      </div>
    </div>
    ${!myNick ? `<div class="pf-onboard-footer">Have a duels.ink nickname? <a onclick="pfOpenDrawer()" style="color:var(--gold);cursor:pointer;text-decoration:underline">Link it</a> to unlock lookup stats.</div>` : ''}
  </div>` : '';

  // A.3 Home insight teaser — single-line hook into Play tab (worst matchup CTA).
  let teaserHtml = '';
  try {
    const activeForTeaser = activeDk;
    if (activeForTeaser && typeof getAnalyzerData === 'function') {
      const _az = getAnalyzerData();
      const _deckData = _az && _az[activeForTeaser];
      const _matchups = _deckData && _deckData.matchups;
      if (_matchups) {
        let _worst = null;
        for (const [opp, m] of Object.entries(_matchups)) {
          const g = (m.wins || 0) + (m.losses || 0);
          if (g < 20) continue;
          if (_worst === null || m.wr < _worst.wr) _worst = { opp, wr: m.wr, games: g };
        }
        if (_worst) {
          const _oppName = DECK_NAMES[_worst.opp] || _worst.opp;
          teaserHtml = `<div class="home-insight-teaser" style="margin:10px 0 14px;padding:10px 14px;background:linear-gradient(135deg,rgba(212,160,58,0.08),rgba(212,160,58,0.02));border-left:3px solid var(--gold);border-radius:6px;cursor:pointer;font-size:0.92em" onclick="coachDeck='${activeForTeaser}';coachOpp='${_worst.opp}';switchToTab('play')">
            <span style="color:var(--text2);font-size:0.82em">Your worst matchup:</span>
            <strong style="color:var(--text)">${_oppName}</strong>
            <span style="color:var(--red);font-weight:700;margin-left:4px">${_worst.wr}% WR</span>
            <span style="color:var(--gold);margin-left:8px">&rarr; Open Play</span>
          </div>`;
        }
      }
    }
  } catch (_) { teaserHtml = ''; }

  // Visual parity with Deck tab — gold-rail block intros (`.deck-intro--above`).
  // Strong headline = block title, prose = short description (1-2 lines).
  const heroIntro = '<div class="deck-intro deck-intro--above">' +
    '<strong>Your home cockpit.</strong> Pick a deck on the left to anchor the dashboard, ' +
    'then read the snapshot on the right to see how that deck is performing in the active scope. ' +
    'Selection syncs to Play, Meta and Deck automatically.' +
    '</div>';
  const coachIntro = coachHtml ? '<div class="deck-intro deck-intro--above">' +
    '<strong>Coach Corner.</strong> Notes, alerts and diary entries tied to your linked nickname. ' +
    'Hidden when there is nothing to show.' +
    '</div>' : '';

  main.innerHTML = `<div class="pf-dash">
    ${headerHtml}
    ${onboardHtml}
    ${nudgeHtml}
    ${teaserHtml}
    ${heroIntro}
    <div class="pf-hero-row">
      ${heroDeckCard}
      ${heroRadarCard}
    </div>
    ${tipsHtml}
    ${coachIntro}
    ${coachHtml}
  </div>
  ${drawerHtml}`;
}

function pfBuildDeckWorkspace(deckCode) {
  const scope = getScopeContext();
  const activeDk = deckCode || coachDeck || selectedDeck || pfActiveDeck;
  if (!activeDk) {
    return `<div class="pf-list-panel" style="margin-bottom:16px">
      <div class="pf-std-card">
        <div class="pf-std-title"><span>Deck Workspace</span></div>
        <div style="color:var(--text2);font-size:0.82em;padding:12px 0">Select a deck first to see consensus, curve and non-standard picks.</div>
      </div>
      <div></div>
    </div>`;
  }

  let techHtml = '';
  const techLevels = scope.isInfinity
    ? [{ key: 'infinity_pro', label: 'PRO', rank: 0 }, { key: 'infinity_top', label: 'TOP', rank: 1 }, { key: 'infinity', label: 'Community', rank: 2 }]
    : [{ key: 'pro', label: 'PRO', rank: 0 }, { key: 'top', label: 'TOP', rank: 1 }, { key: 'set11', label: 'Community', rank: 2 }];
  const merged = {};
  for (const lvl of techLevels) {
    const t = ((DATA.tech_tornado || {})[lvl.key] || {})[activeDk];
    if (!t || !t.items) continue;
    t.items.filter(i => i.type === 'in').forEach(item => {
      if (!merged[item.card]) merged[item.card] = { ...item, label: lvl.label, rank: lvl.rank };
    });
  }
  const techCards = Object.values(merged)
    .sort((a, b) => a.rank - b.rank || b.adoption - a.adoption)
    .slice(0, 5);
  const labelColors = { PRO: 'var(--gold)', TOP: 'var(--sapphire)', Community: 'var(--text2)' };
  if (techCards.length) {
    techHtml = `<div class="pf-tech-flow">`;
    techCards.forEach(item => {
      const imgUrl = rvCardsDB ? rvCardImgByName(item.card) : '';
      const zoomAttr = imgUrl ? ` data-zoom="${imgUrl}"` : '';
      const imgInner = imgUrl
        ? `<img src="${imgUrl}" alt="${item.card}" loading="lazy">`
        : `<div class="pf-tech-img-placeholder">${item.card}</div>`;
      const adoptionPill = `<span class="pf-tech-adoption">${item.adoption}%</span>`;
      const wrPill = `<span class="pf-tech-wr" style="color:${wrColor(item.avg_wr)}">${item.avg_wr}% WR</span>`;
      const conf = item.confidence || 1;
      const dots = '<span class="pf-tech-conf" title="Confidence: ' + ['','Low','Medium','High'][conf] + '">'
        + '●'.repeat(conf) + '<span style="opacity:0.2">' + '●'.repeat(3-conf) + '</span></span>';
      const lblColor = labelColors[item.label] || 'var(--text2)';
      const srcLabel = `<span class="pf-tech-source-label" style="color:${lblColor}">${item.label}</span>`;
      techHtml += `<div class="pf-tech-card tech-in" onclick="pfZoomCard(this)"${zoomAttr}>
        <div class="pf-tech-img-wrap">${imgInner}${adoptionPill}</div>
        <div class="pf-tech-name">${item.card}</div>
        ${wrPill}
        ${srcLabel}
        ${dots}
      </div>`;
    });
    techHtml += `</div>`;
  } else {
    techHtml = `<div style="color:var(--text2);font-size:0.84em;padding:8px 0">No non-standard picks detected for this deck.</div>`;
  }

  const consensusData = DATA.consensus || {};
  const std = consensusData[activeDk];
  let stdListHtml = '';
  let curveHtml = '';
  if (std) {
    const rows = [];
    let totalCards = 0;
    Object.entries(std).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0])).forEach(([name, qty]) => {
      const q = Math.round(qty);
      totalCards += q;
      const meta = pfCardMeta(name);
      const safeName = _bpEsc(name);
      const safeShort = _bpEsc(meta.shortName);
      const art = meta.imgUrl
        ? `<img src="${meta.imgUrl}" alt="${safeName}" loading="lazy">`
        : `<div class="pf-std-vph">${safeShort}</div>`;
      const zoom = meta.imgUrl ? ` data-zoom="${meta.imgUrl}"` : '';
      rows.push(`<div class="pf-std-vcard">
        <div class="pf-std-vart"${zoom} onclick="if(this.dataset.zoom)pfZoomCard(this)" title="${safeName}">
          ${art}
          <span class="pf-std-vqty">${q}x</span>
        </div>
        <div class="pf-std-vname">${safeShort}</div>
      </div>`);
    });
    stdListHtml = `<div class="pf-std-card">
      <div class="pf-std-title">
        <span>Consensus List</span>
        <span class="pf-std-source">consensus avg</span>
      </div>
      <div class="pf-std-list"><div class="pf-std-gallery">${rows.join('')}</div></div>
      <div class="pf-std-total">${totalCards} cards</div>
    </div>`;
    // Deck Curve wrapped in monAccordion — closed by default, images appear on expand
    curveHtml = `<div class="pf-std-card" style="padding:0">
      ${monAccordion('acc-deck-curve', 'Deck Curve', activeDk, pfBuildCurveTimeline(std), {
        desktopOpen: false,
        info: { title: 'About Deck Curve', body: '<p>Per-turn top cards grouped by ink cost (T1-T7+). Tap a card to preview its art.</p>' }
      })}
    </div>`;
  } else {
    stdListHtml = `<div class="pf-std-card">
      <div class="pf-std-title"><span>Consensus List</span></div>
      <div style="color:var(--text2);font-size:0.82em;padding:12px 0">No consensus data available for ${activeDk}.</div>
    </div>`;
  }

  const techCardPanel = `<div class="pf-std-card">
    <div class="pf-std-title" style="margin-bottom:0">
      <span>Non-Standard Picks</span>
      <button class="pf-info-btn" onclick="event.stopPropagation();var t=this.nextElementSibling;if(t)t.classList.toggle('open')" title="What is this?">i</button>
    </div>
    <div class="pf-info-tip" style="margin-top:6px;margin-bottom:8px">Non-standard cards used by winning players (WR ≥ 52%, 15+ games). <strong>Adoption %</strong> = how many winners run it. Source: <span style="color:var(--gold)">PRO</span> &gt; <span style="color:var(--sapphire)">TOP</span> &gt; Community.</div>
    ${techHtml}
  </div>`;

  return `<div class="pf-list-panel" style="margin-bottom:16px">
    <div>
      ${stdListHtml}
      ${curveHtml}
    </div>
    ${techCardPanel}
  </div>`;
}

function pfDeckStoryKey(deckCode) {
  const scope = getScopeContext();
  return [scope.format, scope.primaryPerimeter, deckCode].join('|');
}

function pfDeckTrendSvg(daily) {
  const pts = (Array.isArray(daily) ? daily : []).filter(d => d && d.wr != null);
  if (!pts.length) {
    return '<div style="color:var(--text2);font-size:0.82em;padding:10px 0">No trend data in the last 5 days.</div>';
  }

  const width = 320;
  const height = 120;
  const padX = 16;
  const padY = 14;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;
  const values = pts.map(p => Number(p.wr) || 0);
  const min = Math.min.apply(null, values);
  const max = Math.max.apply(null, values);
  const range = Math.max(1, max - min);
  const stepX = pts.length > 1 ? innerW / (pts.length - 1) : 0;
  const coords = pts.map((p, i) => {
    const x = padX + (stepX * i);
    const y = padY + innerH - (((Number(p.wr) || 0) - min) / range) * innerH;
    return { x, y, wr: Number(p.wr) || 0, date: p.date };
  });
  const line = coords.map(c => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
  const first = coords[0];
  const last = coords[coords.length - 1];
  const delta = last.wr - first.wr;
  const deltaCls = delta > 0 ? 'var(--green)' : delta < 0 ? 'var(--red)' : 'var(--text2)';

  return `
    <div style="width:100%">
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%;height:120px;display:block">
        <rect x="0" y="0" width="${width}" height="${height}" rx="10" fill="rgba(255,255,255,0.02)"></rect>
        <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="rgba(255,255,255,0.08)" stroke-width="1"></line>
        <polyline fill="none" stroke="var(--gold)" stroke-width="2.5" points="${line}"></polyline>
        ${coords.map(c => `
          <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="3.5" fill="var(--gold)"></circle>
        `).join('')}
      </svg>
      <div style="display:flex;justify-content:space-between;gap:8px;margin-top:6px;font-size:0.72em;color:var(--text2)">
        ${coords.map(c => `
          <span style="min-width:0;text-align:center;flex:1">${String(c.date || '').slice(5)}<br><strong style="color:var(--text)">${c.wr.toFixed(1)}%</strong></span>
        `).join('')}
      </div>
      <div style="margin-top:8px;font-size:0.76em;color:${deltaCls};font-weight:700">Trend ${delta >= 0 ? '+' : ''}${delta.toFixed(1)}pp over ${coords.length} observed day${coords.length === 1 ? '' : 's'}</div>
    </div>`;
}

function pfDeckWorstOpps(deckCode) {
  const scope = getScopeContext();
  const perimKey = scope.primaryPerimeter;
  const trend = ((DATA.matchup_trend || {})[perimKey] || {})[deckCode] || {};
  const opps = Object.entries(trend)
    .map(([opp, stats]) => ({
      opp,
      current_wr: stats.current_wr != null ? Number(stats.current_wr) : null,
      prev_wr: stats.prev_wr != null ? Number(stats.prev_wr) : null,
      delta: stats.delta != null ? Number(stats.delta) : null,
      recent_games: stats.recent_games != null ? Number(stats.recent_games) : 0,
    }))
    .filter(row => row.current_wr != null && row.recent_games >= 3)
    .sort((a, b) => a.current_wr - b.current_wr || (b.delta || -999) - (a.delta || -999))
    .slice(0, 3);
  return opps;
}

function pfDeckSampleBreakdown(deckCode) {
  const scope = getScopeContext();
  const perims = scope.isInfinity
    ? [
        { key: 'infinity', label: 'Standard' },
        { key: 'infinity_top', label: 'Top' },
        { key: 'infinity_pro', label: 'Pro' },
      ]
    : [
        { key: 'set11', label: 'Standard' },
        { key: 'top', label: 'Top' },
        { key: 'pro', label: 'Pro' },
      ];
  const source = (DATA && DATA.perimeters) || {};
  return perims.map(p => {
    const pd = source[p.key];
    const row = pd && pd.wr && pd.wr[deckCode];
    if (!row) return null;
    const games = Number(row.games || 0);
    const wr = row.wr != null ? Number(row.wr) : null;
    if (!games || wr == null) return null;
    return { label: p.label, key: p.key, games, wr };
  }).filter(Boolean);
}

function pfGetMatchupReport(deckCode, oppCode) {
  if (!deckCode || !oppCode) return null;
  const analyzer = (DATA && DATA.matchup_analyzer) || {};
  const block = analyzer[deckCode];
  if (!block) return null;
  return block[`vs_${oppCode}`] || null;
}

function pfDeckCrisisCards(deckCode, oppCodes) {
  const oppList = Array.isArray(oppCodes) ? oppCodes.filter(Boolean) : [oppCodes].filter(Boolean);
  const rows = [];

  oppList.forEach(oppCode => {
    const report = pfGetMatchupReport(deckCode, oppCode);
    const scores = (report && report.card_scores) || {};
    Object.entries(scores).forEach(([name, entry]) => {
      const apps = entry && entry.apps != null ? Number(entry.apps) : Number(entry.games || 0);
      const winApps = entry && entry.win_apps != null ? Number(entry.win_apps) : 0;
      const lossApps = entry && entry.loss_apps != null ? Number(entry.loss_apps) : 0;
      const delta = entry && typeof entry.delta === 'number' ? Number(entry.delta) : null;
      const lossHeavy = Math.max(0, lossApps - winApps);
      if (delta == null || apps < 15 || (delta >= 0 && lossHeavy <= 0)) return;
      rows.push({ name, opp: oppCode, apps, delta, winApps, lossApps, lossHeavy });
    });
  });

  rows.sort((a, b) => (b.lossHeavy - a.lossHeavy) || (a.delta - b.delta) || (b.apps - a.apps));
  return rows.slice(0, 5);
}

function pfLoadDeckStory(deckCode) {
  if (!deckCode) return;
  const scope = getScopeContext();
  const key = pfDeckStoryKey(deckCode);
  if (pfImproveDeckStoryCache[key] || pfImproveDeckStoryInflight[key]) return;
  pfImproveDeckStoryInflight[key] = true;
  fetch(`/api/v1/coach/deck-history/${encodeURIComponent(deckCode)}?game_format=${encodeURIComponent(scope.format)}&perimeter=${encodeURIComponent(scope.primaryPerimeter)}&days=5`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      pfImproveDeckStoryCache[key] = data || {};
    })
    .catch(err => {
      pfImproveDeckStoryCache[key] = { error: String(err && err.message ? err.message : err), daily: [] };
    })
    .finally(() => {
      delete pfImproveDeckStoryInflight[key];
      if (pfImproveDeckFocus === deckCode && currentTab === 'improve') {
        render();
      }
    });
}

function pfBuildDeckStory(deckCode) {
  const key = pfDeckStoryKey(deckCode);
  const story = pfImproveDeckStoryCache[key];
  if (!story && !pfImproveDeckStoryInflight[key]) {
    pfLoadDeckStory(deckCode);
  }

  if (story && story.error) {
    return `<div class="pf-std-card" style="margin-bottom:12px">
      <div class="pf-std-title"><span>Deck story</span></div>
      <div style="color:var(--text2);font-size:0.82em;padding:10px 0">Trend data unavailable for the last 5 days.</div>
    </div>`;
  }

  if (!story) {
    return `<div class="pf-std-card" style="margin-bottom:12px">
      <div class="pf-std-title"><span>Deck story</span></div>
      <div style="color:var(--text2);font-size:0.82em;padding:10px 0">Loading last 5 days...</div>
    </div>`;
  }

  const daily = Array.isArray(story.daily) ? story.daily : [];
  const points = daily.filter(d => d && d.wr != null);
  const first = points[0] || null;
  const last = points[points.length - 1] || null;
  const delta = first && last ? (Number(last.wr) - Number(first.wr)) : 0;
  const direction = delta > 0 ? 'climbing' : delta < 0 ? 'slipping' : 'flat';
  const worstOpps = pfDeckWorstOpps(deckCode);
  const focusOpp = worstOpps[0] && worstOpps[0].opp ? worstOpps[0].opp : null;
  const crisisCards = pfDeckCrisisCards(deckCode, worstOpps.slice(0, 3).map(o => o.opp));
  const sampleMix = pfDeckSampleBreakdown(deckCode);
  const topOpps = worstOpps.map(o => {
    const deltaTxt = o.delta != null ? `${o.delta > 0 ? '+' : ''}${o.delta.toFixed(1)}pp` : '—';
    return `<button type="button" onclick="coachDeck='${deckCode}';coachOpp='${o.opp}';switchToTab('play')" style="display:flex;justify-content:space-between;gap:8px;width:100%;padding:8px 10px;border:1px solid rgba(255,255,255,0.08);border-radius:8px;background:rgba(255,255,255,0.02);color:inherit;cursor:pointer;text-align:left;margin-bottom:8px">
      <span style="min-width:0;flex:1">
        <strong style="display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${o.opp}</strong>
        <span style="font-size:0.75em;color:var(--text2)">${o.recent_games} recent games</span>
      </span>
      <span style="text-align:right;min-width:72px">
        <strong style="display:block;color:${wrColor(o.current_wr)}">${o.current_wr.toFixed(1)}%</strong>
        <span style="font-size:0.75em;color:${o.delta != null && o.delta < 0 ? 'var(--red)' : 'var(--text2)'}">${deltaTxt}</span>
      </span>
    </button>`;
  }).join('') || `<div style="color:var(--text2);font-size:0.82em;padding:8px 0">Not enough matchup history yet.</div>`;

  const crisisHtml = crisisCards.length
    ? crisisCards.map(c => {
        const deltaPp = Number(c.delta || 0) * 100;
        const conf = c.apps >= 100 ? 'High' : c.apps >= 30 ? 'Medium' : 'Low';
        const lossLine = c.lossApps || c.winApps
          ? `${c.lossApps} losses · ${c.winApps} wins`
          : `${c.apps} observed games`;
        return `<div style="display:flex;justify-content:space-between;gap:8px;padding:8px 10px;border:1px solid rgba(255,255,255,0.06);border-radius:8px;background:rgba(255,255,255,0.02);margin-bottom:8px">
          <span style="min-width:0;flex:1">
            <strong style="display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${c.name}</strong>
            <span style="font-size:0.75em;color:var(--text2)">${lossLine} · vs ${c.opp} · ${conf} confidence</span>
          </span>
          <span style="text-align:right;min-width:72px;color:${deltaPp <= -2 ? 'var(--red)' : 'var(--gold)'};font-weight:700">${deltaPp > 0 ? '+' : ''}${deltaPp.toFixed(1)}pp</span>
        </div>`;
      }).join('')
    : `<div style="color:var(--text2);font-size:0.82em;padding:8px 0">No strong crisis cards surfaced yet.</div>`;

  const sampleHtml = sampleMix.length
    ? `<div style="margin-top:12px">
        <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.12em;text-transform:uppercase;font-weight:700;margin-bottom:8px">Sample mix</div>
        <div style="display:grid;grid-template-columns:repeat(${sampleMix.length},minmax(0,1fr));gap:8px">
          ${sampleMix.map(s => `<div style="padding:10px 11px;border:1px solid rgba(255,255,255,0.06);border-radius:8px;background:rgba(255,255,255,0.02)">
            <div style="font-size:0.7em;color:var(--text2);text-transform:uppercase;letter-spacing:0.08em">${s.label}</div>
            <div style="margin-top:4px;font-weight:700;color:${wrColor(s.wr)}">${s.wr.toFixed(1)}%</div>
            <div style="font-size:0.72em;color:var(--text2)">${s.games.toLocaleString()} games</div>
          </div>`).join('')}
        </div>
      </div>`
    : '';

  const storyLine = points.length >= 2
    ? `Over the last 5 days, ${deckCode} went from ${first.wr.toFixed(1)}% to ${last.wr.toFixed(1)}% WR (${delta > 0 ? '+' : ''}${delta.toFixed(1)}pp). The pressure is concentrated in ${worstOpps.slice(0, 2).map(o => o.opp).join(' and ') || 'the current field'}.`
    : `Not enough observed games to tell a clean 5-day story yet.`;

  return `<div class="pf-std-card" style="margin-bottom:12px">
    <div class="pf-std-title" style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:10px">
      <div>
        <span>Deck story</span>
        <div style="font-size:0.76em;color:var(--text2);margin-top:2px">${storyLine}</div>
      </div>
      <div style="text-align:right;font-size:0.74em;color:var(--text2)">${direction === 'flat' ? 'Flat' : direction === 'climbing' ? 'Momentum up' : 'Momentum down'}</div>
    </div>
    <div style="display:grid;grid-template-columns:minmax(0,1.5fr) minmax(220px,1fr);gap:14px;align-items:start">
      <div>
        ${pfDeckTrendSvg(daily)}
        ${sampleHtml}
      </div>
      <div>
        <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.12em;text-transform:uppercase;font-weight:700;margin-bottom:8px">Worst opponents</div>
        ${topOpps}
      </div>
    </div>
    <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;margin-top:14px">
      <div>
        <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.12em;text-transform:uppercase;font-weight:700;margin-bottom:8px">Cards in crisis</div>
        ${crisisHtml}
      </div>
      <div>
        <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.12em;text-transform:uppercase;font-weight:700;margin-bottom:8px">Coach narration</div>
        <div style="padding:12px 14px;border:1px solid rgba(255,255,255,0.06);border-radius:8px;background:rgba(255,255,255,0.02);font-size:0.88em;line-height:1.45;color:var(--text2)">
          ${storyLine}
          ${focusOpp && crisisCards.length ? `<br><br>The first fix is usually not a full rebuild: it is tightening the cards that slide hardest in ${focusOpp}.` : ''}
        </div>
      </div>
    </div>
  </div>`;
}

// Improve onboarding hero — aggressive nickname capture (B.5).
// Shows a prominent CTA when no duels.ink nickname is linked.
// Hidden once linked; shrinks to a thin demo strip when in demo mode.
function pfImproveNickHero(saved, isDemo, scope) {
  if (saved.duelsNick && !isDemo) return '';
  if (isDemo) {
    return `<div class="card" style="display:flex;align-items:center;gap:10px;padding:10px 14px;margin-bottom:14px;border:1px solid rgba(255,215,0,0.18);background:linear-gradient(135deg,rgba(255,215,0,0.05),rgba(124,63,160,0.05))">
      <span style="font-size:0.82em;color:var(--text2);flex:1">Demo mode &mdash; viewing <strong style="color:var(--gold)">${saved.duelsNick}</strong>. Stats below are not yours.</span>
      <button onclick="pfOpenDrawer()" style="background:var(--gold);color:#1a1408;border:0;padding:6px 12px;border-radius:5px;font-size:0.78em;font-weight:700;cursor:pointer">Use my nickname</button>
    </div>`;
  }
  // Cold state — no nickname, no demo. Headline + 3 unlocks + dual CTA.
  const fmtKey = scope.format;
  const playerCount = Object.keys((DATA.player_lookup || {})[fmtKey] || {}).length;
  const playersLine = playerCount > 50
    ? `Tracking <strong>${playerCount.toLocaleString()}</strong> players in ${fmtKey.toUpperCase()} right now.`
    : '';
  return `<div class="card" style="padding:18px 20px;margin-bottom:18px;border:1px solid rgba(255,215,0,0.32);background:linear-gradient(135deg,rgba(255,215,0,0.06),rgba(124,63,160,0.05))">
    <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.14em;text-transform:uppercase;font-weight:700;margin-bottom:6px">Step 1 &mdash; unlock your data</div>
    <div style="font-size:1.05rem;font-weight:700;margin-bottom:6px">Link your duels.ink nickname</div>
    <div style="font-size:0.85em;color:var(--text2);margin-bottom:12px">${playersLine ? playersLine + ' ' : ''}Improve runs on the public match logs for the linked nickname &mdash; without one every panel below is empty.</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-bottom:14px;font-size:0.82em">
      <div style="display:flex;gap:8px;align-items:flex-start"><span style="color:var(--gold);font-weight:700">&#10003;</span><span><strong>WR per deck</strong> &middot; what wins on that nickname's logs</span></div>
      <div style="display:flex;gap:8px;align-items:flex-start"><span style="color:var(--gold);font-weight:700">&#10003;</span><span><strong>Worst matchup</strong> &middot; where to focus practice</span></div>
      <div style="display:flex;gap:8px;align-items:flex-start"><span style="color:var(--gold);font-weight:700">&#10003;</span><span><strong>MMR &amp; history</strong> &middot; trend across last sessions</span></div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
      <button onclick="pfOpenDrawer()" style="background:var(--gold);color:#1a1408;border:0;padding:9px 18px;border-radius:6px;font-size:0.88em;font-weight:700;cursor:pointer">Link nickname &rarr;</button>
      <button onclick="pfLoadDemo()" style="background:transparent;border:1px solid rgba(255,255,255,0.18);color:var(--text);padding:8px 14px;border-radius:6px;font-size:0.85em;font-weight:600;cursor:pointer">Try demo player</button>
      <span style="font-size:0.74em;color:var(--text2)">No account needed &middot; stored locally only</span>
    </div>
  </div>`;
}

// Improvement path — prioritized steps from the user's own match data (B.1).
// Returns '' when no nickname or insufficient data; otherwise a step list
// keyed off worst matchup / best matchup / underperforming deck.
function pfImprovementPath(saved, scope) {
  const nick = saved.duelsNick;
  if (!nick) return '';
  const fmtKey = scope.format;
  const lookup = ((DATA.player_lookup || {})[fmtKey] || {})[nick.toLowerCase()] || {};
  const pd = DATA.perimeters[scope.primaryPerimeter] || {};
  const matrix = pd.matrix || {};

  const userDecks = Object.entries(lookup);
  if (!userDecks.length) return '';
  const totalGames = userDecks.reduce((s, [_, v]) => s + v.w + v.l, 0);
  if (totalGames < 20) {
    return `<div class="card" style="padding:14px 18px;margin-bottom:18px;border:1px solid rgba(255,215,0,0.18);background:linear-gradient(135deg,rgba(255,215,0,0.04),rgba(124,63,160,0.04))">
      <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.14em;text-transform:uppercase;font-weight:700;margin-bottom:6px">Improvement path</div>
      <div style="font-size:0.86em;color:var(--text2)">Only ${totalGames} match${totalGames === 1 ? '' : 'es'} tracked so far for <strong>${nick}</strong> in ${fmtKey.toUpperCase()}. Keep playing &mdash; personalized steps unlock at 20 matches.</div>
    </div>`;
  }

  // Step 1 — worst matchup (study). Min 3 games for the matchup pair.
  let worst = null;
  userDecks.forEach(([dk, _v]) => {
    const m = matrix[dk] || {};
    Object.entries(m).forEach(([opp, s]) => {
      const g = (s.t != null ? s.t : (s.w || 0) + (s.l || 0));
      if (g < 3) return;
      const wr = s.w / g * 100;
      if (!worst || wr < worst.wr) worst = { deck: dk, opp, wr, games: g };
    });
  });

  // Step 2 — best matchup (lean into). Min 5 games.
  let best = null;
  userDecks.forEach(([dk, _v]) => {
    const m = matrix[dk] || {};
    Object.entries(m).forEach(([opp, s]) => {
      const g = (s.t != null ? s.t : (s.w || 0) + (s.l || 0));
      if (g < 5) return;
      const wr = s.w / g * 100;
      if (!best || wr > best.wr) best = { deck: dk, opp, wr, games: g };
    });
  });

  // Step 3 — underperforming deck. Min 10 games, WR < 50%.
  let underperformer = null;
  userDecks.forEach(([dk, v]) => {
    const g = v.w + v.l;
    if (g < 10) return;
    const wr = v.w / g * 100;
    if (wr < 50 && (!underperformer || wr < underperformer.wr)) {
      underperformer = { deck: dk, wr, games: g };
    }
  });

  const steps = [];
  if (worst) {
    steps.push({
      verb: 'Study',
      title: `Worst matchup &mdash; ${worst.deck} vs ${worst.opp}`,
      desc: `${worst.wr.toFixed(0)}% WR over ${worst.games} games. Open the killer curves and "How to Respond".`,
      onclick: `coachDeck='${worst.deck}';coachOpp='${worst.opp}';switchToTab('play')`,
      cta: 'Open in Play',
    });
  }
  if (best && (!worst || (best.deck !== worst.deck || best.opp !== worst.opp))) {
    steps.push({
      verb: 'Lean into',
      title: `Best matchup &mdash; ${best.deck} vs ${best.opp}`,
      desc: `${best.wr.toFixed(0)}% WR over ${best.games} games. Tighten the lines you already win.`,
      onclick: `coachDeck='${best.deck}';coachOpp='${best.opp}';switchToTab('play')`,
      cta: 'Review in Play',
    });
  }
  if (underperformer) {
    steps.push({
      verb: 'Rotate',
      title: `Underperforming &mdash; ${underperformer.deck}`,
      desc: `${underperformer.wr.toFixed(0)}% WR over ${underperformer.games} games. Compare with meta builds or try an alternative.`,
      onclick: `pfOpenImproveDeckWorkspace('${underperformer.deck}')`,
      cta: 'Inspect in Improve',
    });
  }

  if (!steps.length) {
    return `<div class="card" style="padding:14px 18px;margin-bottom:18px;border:1px solid rgba(255,215,0,0.18);background:linear-gradient(135deg,rgba(255,215,0,0.04),rgba(124,63,160,0.04))">
      <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.14em;text-transform:uppercase;font-weight:700;margin-bottom:6px">Improvement path</div>
      <div style="font-size:0.86em;color:var(--text2)">${totalGames} matches tracked for <strong>${nick}</strong>. Nothing flagged yet &mdash; you're playing balanced. Keep going.</div>
    </div>`;
  }

  const stepRows = steps.map((s, i) => `
    <div class="pf-impr-step" style="display:flex;gap:12px;align-items:flex-start;padding:12px 14px;border-radius:8px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);cursor:pointer;transition:background 0.15s" onclick="${s.onclick}" onmouseover="this.style.background='rgba(255,215,0,0.04)'" onmouseout="this.style.background='rgba(255,255,255,0.02)'">
      <div style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:rgba(255,215,0,0.12);color:var(--gold);font-weight:700;font-size:0.85em;flex-shrink:0">${i + 1}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:0.72em;color:var(--gold);letter-spacing:0.1em;text-transform:uppercase;font-weight:700;margin-bottom:2px">${s.verb}</div>
        <div style="font-size:0.92em;font-weight:600;margin-bottom:3px">${s.title}</div>
        <div style="font-size:0.8em;color:var(--text2);line-height:1.35">${s.desc}</div>
      </div>
      <div style="font-size:0.78em;color:var(--gold);font-weight:600;flex-shrink:0;margin-top:2px">${s.cta} &rarr;</div>
    </div>
  `).join('');

  return `<div class="card" style="padding:16px 18px;margin-bottom:18px;border:1px solid rgba(255,215,0,0.22);background:linear-gradient(135deg,rgba(255,215,0,0.04),rgba(124,63,160,0.03))">
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;flex-wrap:wrap;gap:6px">
      <div>
        <div style="font-size:0.72rem;color:var(--gold);letter-spacing:0.14em;text-transform:uppercase;font-weight:700">Improvement path</div>
        <div style="font-size:0.78em;color:var(--text2);margin-top:2px">Ranked by gap-to-close from your <strong>${totalGames}</strong> matches in ${fmtKey.toUpperCase()}.</div>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px">${stepRows}</div>
  </div>`;
}

function pfOpenImproveDeckWorkspace(deck) {
  pfImproveDeckFocus = deck;
  pfLoadDeckStory(deck);
  render();
}

function pfCloseImproveDeckWorkspace() {
  pfImproveDeckFocus = null;
  render();
}

function pfToggleImproveDeckWorkspace() {
  if (pfImproveDeckFocus) {
    pfImproveDeckFocus = null;
  } else {
    pfImproveDeckFocus = pfActiveDeck || selectedDeck || coachDeck || null;
    if (pfImproveDeckFocus) pfLoadDeckStory(pfImproveDeckFocus);
  }
  render();
}

function renderImproveTab(main) {
  pfEnsureState();
  const scope = getScopeContext();
  const saved = {
    email: localStorage.getItem('pf_email') || '',
    duelsNick: localStorage.getItem('pf_duels_nick') || '',
    lorcaNick: localStorage.getItem('pf_lorca_nick') || '',
    country: localStorage.getItem('pf_country') || '',
  };
  const nick = saved.duelsNick || saved.email || 'Guest';
  const initials = nick[0].toUpperCase();
  const planLabel = PRO_UNLOCKED ? 'Pro' : 'Free';
  const planCls = PRO_UNLOCKED ? 'plan-pro' : 'plan-free';
  const isDemo = localStorage.getItem('pf_demo') === '1';
  const hasNudge = !saved.duelsNick || isDemo;
  let nudgeHtml = '';
  if (!saved.duelsNick) {
    nudgeHtml = `<div class="pf-info-tip" style="margin:0 0 8px"><a onclick="pfOpenDrawer()" style="color:var(--gold);cursor:pointer;text-decoration:underline">Link your duels.ink nickname</a> to unlock improve signals.</div>`;
  } else if (isDemo) {
    nudgeHtml = `<div class="pf-info-tip" style="margin:0 0 8px">Demo mode &mdash; viewing <strong>${saved.duelsNick}</strong>. Stats below are not yours.</div>`;
  }
  const headerHtml = `<div class="pf-header">
    <div class="pf-avatar">${initials}</div>
    <div class="pf-identity">
      <div class="pf-nick">${nick}</div>
      <div class="pf-subtitle"><span class="plan-badge ${planCls}">${planLabel}</span>
        ${saved.country ? '<span>' + saved.country + '</span>' : ''}
      </div>
    </div>
    ${hasNudge ? `<button class="pf-info-btn" onclick="var n=document.getElementById('pf-improve-tip');if(n)n.classList.toggle('open')" title="Improve setup">i</button>` : ''}
    <button class="pf-gear-btn" onclick="pfOpenDrawer()" title="Settings">&#9881;</button>
  </div>`;

  const myNick = saved.duelsNick;
  const activeDk = pfActiveDeck || selectedDeck || coachDeck;
  const pd = DATA.perimeters[scope.primaryPerimeter] || {};
  let myStatsHtml = '';
  if (myNick) {
    const nickLow = myNick.toLowerCase();
    const fmtKey = scope.format;
    const lookup = ((DATA.player_lookup || {})[fmtKey] || {})[nickLow] || {};
    const allDecks = Object.entries(lookup).sort((a, b) => (b[1].w + b[1].l) - (a[1].w + a[1].l));
    const totalW = allDecks.reduce((s, [_, v]) => s + v.w, 0);
    const totalL = allDecks.reduce((s, [_, v]) => s + v.l, 0);
    const totalGames = totalW + totalL;
    const bestMmr = allDecks.reduce((s, [_, v]) => Math.max(s, v.mmr || 0), 0);
    if (totalGames > 0) {
      const totalWr = (totalW / totalGames * 100).toFixed(1);
      let deckRows = '';
      allDecks.forEach(([dk, v]) => {
        const g = v.w + v.l;
        const wr = (v.w / g * 100).toFixed(1);
        const wrPct = parseFloat(wr);
        const isActive = dk === activeDk;
        const matrix = (pd.matrix || {})[dk] || {};
        let worstOpp = '', worstWr = 100;
        Object.entries(matrix).forEach(([opp, s]) => {
          if (s.t >= 3) {
            const oppWr = s.w / s.t * 100;
            if (oppWr < worstWr) { worstWr = oppWr; worstOpp = opp; }
          }
        });
        const worstHtml = worstOpp
          ? `<span style="display:inline-flex;align-items:center;gap:2px;font-size:0.7em;color:var(--red)">${deckImg(worstOpp,12)} ${worstWr.toFixed(0)}%</span>`
          : '';
        deckRows += `<div class="pf-my-deck-row${isActive ? ' active' : ''}" onclick="pfSelectDeck('${dk}')">
          <div style="display:flex;align-items:center;gap:6px;min-width:0;flex:1">
            ${deckImg(dk, 22)}
            <span style="font-size:0.82em;font-weight:${isActive ? '700' : '500'};color:${isActive ? 'var(--gold)' : 'var(--text)'};white-space:nowrap">${dk}</span>
            <span style="font-size:0.68em;color:var(--text2)">${g}g</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            ${worstHtml}
            <div style="width:50px;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden">
              <div style="height:100%;width:${wrPct}%;background:${wrColor(wrPct)};border-radius:3px"></div>
            </div>
            <span style="font-size:0.82em;font-weight:700;color:${wrColor(wrPct)};min-width:38px;text-align:right">${wr}%</span>
          </div>
        </div>`;
      });
      myStatsHtml = `<div class="pf-my-stats-section">
        <div class="pf-my-stats-toggle" onclick="var b=document.getElementById('pf-my-stats-body-improve');b.style.display=b.style.display==='none'?'block':'none';this.querySelector('.pf-my-stats-chev').classList.toggle('open')">
          <span class="pf-my-stats-label">Player lookup</span>
          <span style="font-size:0.72em;color:var(--text2)">${totalGames}g · ${totalWr}% · MMR ${bestMmr}</span>
          <svg class="pf-my-stats-chev" width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <div id="pf-my-stats-body-improve" style="display:block">
          <div style="display:flex;flex-direction:column;gap:2px;margin-top:8px">
            ${deckRows}
          </div>
        </div>
      </div>`;
    } else {
      myStatsHtml = `<div class="pf-my-stats-section">
        <div class="pf-my-stats-label" style="padding:0">Player lookup</div>
        <div style="font-size:0.75em;color:var(--text2);padding:4px 0">No games found for <strong>${myNick}</strong> in the last 3 days</div>
      </div>`;
    }
  } else {
    myStatsHtml = `<div class="pf-my-stats-section">
      <div class="pf-my-stats-label" style="padding:0">Player lookup</div>
      <div style="font-size:0.75em;color:var(--text2);padding:4px 0"><a onclick="pfOpenDrawer()" style="color:var(--gold);cursor:pointer;text-decoration:underline">Link your duels.ink nickname</a> to see lookup stats</div>
    </div>`;
  }

  const nickHeroHtml = pfImproveNickHero(saved, isDemo, scope);
  const bridgeStatsHtml = pfBridgeStatsCard(saved, scope, 'improve');
  const improvementPathHtml = pfImprovementPath(saved, scope);
  const improveDeckWorkspaceHtml = `
    <div class="pf-my-stats-section" style="margin-top:14px">
      <div class="pf-my-stats-toggle" onclick="pfToggleImproveDeckWorkspace()" style="cursor:pointer">
        <span class="pf-my-stats-label">Deck focus</span>
        <span style="font-size:0.72em;color:var(--text2)">${pfImproveDeckFocus || 'expand the deck workspace'}</span>
        <svg class="pf-my-stats-chev${pfImproveDeckFocus ? ' open' : ''}" width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
      <div id="pf-improve-deck-focus-body" style="display:${pfImproveDeckFocus ? 'block' : 'none'};padding-top:10px">
        ${pfImproveDeckFocus ? pfBuildDeckStory(pfImproveDeckFocus) : ''}
        ${pfImproveDeckFocus ? pfBuildDeckWorkspace(pfImproveDeckFocus) : ''}
      </div>
    </div>`;
  main.innerHTML = `<div class="pf-dash">

    <div class="tab-section-hdr">
      <span class="tab-section-hdr__eyebrow">Profile</span>
      <span class="tab-section-hdr__title">Setup &middot; pinned deck &middot; player lookup</span>
    </div>
    <div class="deck-intro deck-intro--above">
      <strong>Profile.</strong> Link your duels.ink nickname so the dashboard can pull
      your real matches and turn them into improvement signals. The bridge card and
      the path below are computed from this link.
    </div>

    ${nickHeroHtml}
    ${headerHtml}
    ${hasNudge && !nickHeroHtml ? `<div class="pf-info-tip" id="pf-improve-tip" style="margin:0 0 8px">${nudgeHtml || 'Improve collects your personal and study signals.'}</div>` : ''}

    ${bridgeStatsHtml}
    ${improvementPathHtml}
    ${improveDeckWorkspaceHtml}

    <div class="tab-section-hdr" style="margin-top:var(--sp-4)">
      <span class="tab-section-hdr__eyebrow">Player lookup</span>
      <span class="tab-section-hdr__title">Win rates &middot; matchup gaps &middot; deck history</span>
    </div>
    <div class="deck-intro deck-intro--above">
      <strong>Player lookup.</strong> Public match-log signals for the linked nickname:
      WR per deck, worst matchup per deck, best MMR. These are the numbers the
      improvement path uses to suggest the next move.
    </div>

    <div class="pf-kpi-card">
      <div style="font-size:0.82em;color:var(--text2);margin-bottom:12px">Performance signals based on the linked nickname's public match logs.</div>
      ${myStatsHtml}
    </div>

    <div class="tab-section-hdr" style="margin-top:var(--sp-4)">
      <span class="tab-section-hdr__eyebrow">Study</span>
      <span class="tab-section-hdr__title">Blind playbook &middot; card analysis</span>
    </div>
    <div class="deck-intro deck-intro--above">
      <strong>Study.</strong> The Blind Playbook is the pre-meta-knowledge guide for
      your deck — what to keep on mulligan, which curves to look for, what to fear.
      Card Analysis breaks down which cards in your list pull weight and which drag.
    </div>

    <div id="pf-blind-playbook-host-improve"></div>
    ${(window.V3 && window.V3.CardAnalysis) ? window.V3.CardAnalysis.buildSections() : ''}

    <div class="tab-section-hdr" style="margin-top:var(--sp-5)">
      <span class="tab-section-hdr__eyebrow">Practice</span>
      <span class="tab-section-hdr__title">Mulligan Trainer &middot; Replay Viewer</span>
    </div>
    <div class="deck-intro deck-intro--above">
      <strong>Practice.</strong> Drill the openings against real PRO opening hands and
      replay your own match logs at your own pace. Repetition here is what closes the
      gap between knowing the matchup and playing it cleanly.
    </div>
    ${(window.V3 && window.V3.ImprovePlayTools) ? window.V3.ImprovePlayTools.buildSections() : ''}
  </div>`;

  if (activeDk) loadBlindPlaybook(activeDk, currentFormat || 'core', 'pf-blind-playbook-host-improve');
  if (window.V3 && window.V3.ImprovePlayTools) window.V3.ImprovePlayTools.init();
}

// ── Blind Deck Playbook (Sprint-1 Liberation Day) — design from analisidef ──
// Lazy-load: fetch on render, cache by (deck, format) per la sessione, fail closed.
const _blindPlaybookCache = {};
const _blindPlaybookInflight = {};
function _bpEsc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}
function _bpAsText(v) {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  return v.text || v.action || v.card || JSON.stringify(v);
}
function _bpItemList(items) {
  if (!Array.isArray(items) || !items.length) return '';
  return items.map(x => _bpAsText(x)).filter(Boolean);
}
// Pills (carte chip): mulligan + threat answers
function _bpPills(items) {
  const arr = _bpItemList(items);
  if (!arr.length) return '';
  return `<div class="bp-mull-pills">${arr.map(s => `<span class="bp-pill" title="${_bpEsc(s)}">${_bpEsc(s.split(' - ')[0])}</span>`).join('')}</div>`;
}
function _bpMulligan(mul) {
  if (!mul || typeof mul !== 'object') return '';
  // Schema fluido: 'if_otp/if_otd' o 'keep_if_otp/keep_if_otd'
  const fields = [
    ['always_keep', 'Always Keep', 'keep'],
    [['keep_if_otp','if_otp'], 'If OTP', 'otp'],
    [['keep_if_otd','if_otd'], 'If OTD', 'otd'],
    ['never_keep', 'Never Keep', 'never'],
  ];
  const cols = [];
  for (const [keyOrKeys, label, cls] of fields) {
    const keys = Array.isArray(keyOrKeys) ? keyOrKeys : [keyOrKeys];
    let v = null;
    for (const k of keys) { if (Array.isArray(mul[k]) && mul[k].length) { v = mul[k]; break; } }
    if (!v) continue;
    cols.push(`<div class="bp-mull-col">
      <div class="bp-mull-label ${cls}">${_bpEsc(label)}</div>
      ${_bpPills(v)}
    </div>`);
  }
  return cols.length ? `<div class="bp-mull-grid">${cols.join('')}</div>` : '';
}
function _bpCurves(curves) {
  if (!curves || typeof curves !== 'object') return '';
  const turns = ['T1','T2','T3','T4','T5'];
  const rows = turns.map(t => [t, curves[t] != null ? curves[t] : curves[t.toLowerCase()]])
    .filter(([t, v]) => v != null && v !== '')
    .map(([t, v]) => `<div class="bp-curve-row">
      <span class="bp-turn-badge">${t}</span>
      <span class="bp-curve-text">${_bpEsc(_bpAsText(v))}</span>
    </div>`);
  return rows.length ? `<div class="bp-curve-list">${rows.join('')}</div>` : '';
}
function _bpCombos(combos) {
  if (!Array.isArray(combos) || !combos.length) return '';
  const cards = combos.map(c => {
    const cardsStr = Array.isArray(c.cards) ? c.cards.map(s => s.split(' - ')[0]).join(' + ') : (c.cards || '');
    const why = c.why || c.note || '';
    const timing = c.timing || c.turn || '';
    const wr = c.wr || c.win_rate || '';
    return `<div class="bp-combo-card">
      <div class="bp-combo-cards">${_bpEsc(cardsStr)}</div>
      ${(timing || wr) ? `<div class="bp-combo-meta">
        ${timing ? `<span class="bp-combo-timing">${_bpEsc(timing)}</span>` : ''}
        ${wr ? `<span class="bp-combo-wr">${_bpEsc(wr)}</span>` : ''}
      </div>` : ''}
      ${why ? `<div class="bp-combo-why">${_bpEsc(why)}</div>` : ''}
    </div>`;
  }).join('');
  return `<div class="bp-combo-scroll">${cards}</div>`;
}
function _bpChecklist(items) {
  const arr = _bpItemList(items);
  if (!arr.length) return '';
  return `<div class="bp-checklist">${arr.map(s => `<div class="bp-check-item">
    <span class="bp-check-icon">&check;</span>
    <span>${_bpEsc(s)}</span>
  </div>`).join('')}</div>`;
}
function _bpTrapPlays(items) {
  if (!Array.isArray(items) || !items.length) return '';
  return `<div class="bp-trap-list">${items.map(t => {
    const what = (typeof t === 'string') ? t : (t.what || t.text || _bpAsText(t));
    const why = (typeof t === 'object') ? (t.why || t.note || '') : '';
    return `<div class="bp-trap-item">
      <div class="bp-trap-what">&#9888; ${_bpEsc(what)}</div>
      ${why ? `<div class="bp-trap-why">${_bpEsc(why)}</div>` : ''}
    </div>`;
  }).join('')}</div>`;
}
function _bpStrategicHeader(sf) {
  if (!sf || sf.error) return '';
  const tierClass = ({top:'top', competitive:'competitive', mid:'mid', fringe:'fringe'})[sf.tier] || 'mid';
  const skillClass = ({low:'low', medium:'medium', high:'high'})[sf.skill_dependency] || 'medium';
  const arch = sf.archetype ? `<span class="bp-sf-chip arch" title="Archetype">${_bpEsc(sf.archetype)}</span>` : '';
  const tier = sf.tier ? `<span class="bp-sf-chip tier ${tierClass}" title="Meta tier">${_bpEsc(sf.tier)}</span>` : '';
  const skill = sf.skill_dependency ? `<span class="bp-sf-chip skill ${skillClass}" title="Pilot skill dependency">skill: ${_bpEsc(sf.skill_dependency)}</span>` : '';
  const oneLiner = sf.one_liner ? `<div class="bp-sf-oneliner">&ldquo;${_bpEsc(sf.one_liner)}&rdquo;</div>` : '';
  const principles = Array.isArray(sf.key_principles) && sf.key_principles.length
    ? `<ul class="bp-sf-principles">${sf.key_principles.map(p => `<li>${_bpEsc(p)}</li>`).join('')}</ul>`
    : '';
  if (!arch && !tier && !skill && !oneLiner && !principles) return '';
  return `<div class="bp-sf">
    <div class="bp-sf-chips">${arch}${tier}${skill}</div>
    ${oneLiner}
    ${principles}
  </div>`;
}
function _bpWeeklyTechBadge(wt) {
  if (!wt || typeof wt !== 'object') {
    return `<span class="bp-tech-badge no-change">No changes this week</span>`;
  }
  const newTech = wt.new_tech || [];
  const droppedTech = wt.dropped_tech || [];
  const hasChange = newTech.length > 0 || droppedTech.length > 0;
  if (!hasChange) {
    return `<span class="bp-tech-badge no-change" title="No tech changes this week">No changes this week</span>`;
  }
  const adds = newTech.slice(0, 2).map(c => (c.card || c).split(' - ')[0]).join(', ');
  const drops = droppedTech.slice(0, 1).map(c => (c.card || c).split(' - ')[0]).join(', ');
  const parts = [];
  if (adds) parts.push('+' + adds);
  if (drops) parts.push('\u2212' + drops);
  const txt = 'Weekly: ' + parts.join(' \u00b7 ');
  return `<span class="bp-tech-badge has-change" title="${_bpEsc(txt)}">${_bpEsc(txt)}</span>`;
}
function _bpProRefs(refs) {
  if (!Array.isArray(refs) || !refs.length) return '';
  const cards = refs.slice(0, 3).map(r => {
    const name = r.player || r.name || '';
    const wr = (typeof r.wr_pct === 'number') ? `${r.wr_pct.toFixed(1)}% WR (${r.games || '?'} games)` : '';
    const hint = r.hint || r.note || '';
    return `<div class="bp-pro-card">
      <div class="bp-pro-name">${_bpEsc(name)}</div>
      ${wr ? `<div class="bp-pro-wr">${_bpEsc(wr)}</div>` : ''}
      ${hint ? `<div class="bp-pro-hint">${_bpEsc(hint)}</div>` : ''}
    </div>`;
  }).join('');
  return `<div class="bp-pro-row">
    <div class="bp-pro-label">Look how they pilot it</div>
    <div class="bp-pro-cards">${cards}</div>
  </div>`;
}
function _bpAccItem(icon, title, body, openByDefault) {
  if (!body) return '';
  const chev = '<svg class="bp-acc-chevron" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  return `<div class="bp-acc-item${openByDefault ? ' open' : ''}">
    <button class="bp-acc-btn" type="button" onclick="bpAccToggle(this)">
      <span class="bp-acc-icon">${icon}</span>
      <span>${_bpEsc(title)}</span>
      ${chev}
    </button>
    <div class="bp-acc-body"><div class="bp-acc-inner">${body}</div></div>
  </div>`;
}
function bpAccToggle(btn) {
  const item = btn.closest('.bp-acc-item');
  if (item) item.classList.toggle('open');
}
function loadBlindPlaybook(deck, fmt, hostId) {
  const host = document.getElementById(hostId);
  if (!host) return;
  host.innerHTML = '';
  const cacheKey = `${deck}|${fmt}`;
  if (_blindPlaybookCache[cacheKey] === null) return;
  if (_blindPlaybookCache[cacheKey]) {
    _renderBlindPlaybook(_blindPlaybookCache[cacheKey], host);
    return;
  }
  if (_blindPlaybookInflight[cacheKey]) return;
  _blindPlaybookInflight[cacheKey] = true;
  fetch(`/api/v1/profile/blind-playbook/${encodeURIComponent(deck)}?game_format=${encodeURIComponent(fmt)}`)
    .then(r => {
      if (r.status === 404) { _blindPlaybookCache[cacheKey] = null; return null; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(data => {
      delete _blindPlaybookInflight[cacheKey];
      if (!data) return;
      _blindPlaybookCache[cacheKey] = data;
      const stillThere = document.getElementById(hostId);
      if (stillThere && pfActiveDeck === deck) _renderBlindPlaybook(data, stillThere);
    })
    .catch(err => {
      delete _blindPlaybookInflight[cacheKey];
      console.warn('blind playbook load failed', err);
    });
}
function _renderBlindPlaybook(data, host) {
  const pb = data.playbook || {};
  const sf = data.strategic_frame || null;
  const wt = data.weekly_tech || null;
  const proRefs = data.pro_references || pb.pro_references || [];

  // Narrative-first (allineato analisidef): se presente prosa, mostra prosa.
  // Se la prosa manca, mostra solo strategic_frame + placeholder.
  const narrativeRaw = (pb.narrative || '').trim();
  const narrativeHtml = narrativeRaw
    ? `<div class="bp-narrative">${narrativeRaw.split(/\n\s*\n/).filter(Boolean).map(p => `<p>${_bpEsc(p.trim())}</p>`).join('')}</div>`
    : '';

  // Fail closed totale: nessun dato utile -> nasconde tutto
  if (!sf && !narrativeHtml && !proRefs.length) return;

  // Placeholder esplicativo quando narrative manca ma c'e' lo strategic frame
  const noNarrativeNote = (!narrativeHtml && sf)
    ? `<div class="bp-narrative"><p style="opacity:0.65;font-style:italic">Narrative coming in the next weekly batch.</p></div>`
    : '';

  host.innerHTML = `<div class="pf-kpi-card bp-row">
    <div class="bp-header">
      <div>
        <div class="bp-title">How to Pilot &mdash; Blind Guide</div>
        <div class="bp-subtitle">How to play without info on your opponent</div>
      </div>
      ${_bpWeeklyTechBadge(wt)}
    </div>
    ${_bpStrategicHeader(sf)}
    ${narrativeHtml || noNarrativeNote}
    ${_bpProRefs(proRefs)}
  </div>`;
}

// ── Card zoom: tap on mobile → full-screen overlay; hover on desktop → floating tooltip ──
function pfCopyMetaDeck(btn) {
  const ta = btn.parentElement.querySelector('.pf-md-import-data');
  if (!ta) return;
  navigator.clipboard.writeText(ta.value).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy Deck', 1500);
  });
}

function pfGetOrCreateOverlay() {
  let ov = document.getElementById('pf-card-zoom-overlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'pf-card-zoom-overlay';
    ov.className = 'pf-zoom-overlay';
    ov.innerHTML = '<img alt="Card zoom">';
    ov.addEventListener('click', () => { ov.classList.remove('open'); });
    document.body.appendChild(ov);
  }
  return ov;
}
function pfGetOrCreateTooltip() {
  let tip = document.getElementById('pf-card-hover-zoom');
  if (!tip) {
    tip = document.createElement('div');
    tip.id = 'pf-card-hover-zoom';
    tip.className = 'pf-hover-zoom';
    tip.innerHTML = '<img alt="Card zoom">';
    document.body.appendChild(tip);
  }
  return tip;
}

// Card zoom — tap (mobile) or click (desktop) opens overlay
function pfZoomCard(el) {
  const url = el.dataset.zoom;
  if (!url) return;
  const ov = pfGetOrCreateOverlay();
  ov.querySelector('img').src = url;
  ov.classList.add('open');
}

// Desktop hover: tooltip next to card
let _pfHoverCard = null;
document.addEventListener('mouseover', e => {
  const card = e.target.closest('.pf-tech-card[data-zoom], [data-zoom]');
  if (card === _pfHoverCard) return;
  if (!card) {
    if (_pfHoverCard) { _pfHoverCard = null; const t = document.getElementById('pf-card-hover-zoom'); if (t) t.classList.remove('visible'); }
    return;
  }
  _pfHoverCard = card;
  if (window.innerWidth < 768) return;
  const tip = pfGetOrCreateTooltip();
  tip.querySelector('img').src = card.dataset.zoom;
  tip.classList.add('visible');
  const rect = card.getBoundingClientRect();
  const TIP_W = 232;
  const left = rect.right + 14 + TIP_W > window.innerWidth ? rect.left - TIP_W - 10 : rect.right + 14;
  const top = Math.min(Math.max(rect.top - 20, 8), window.innerHeight - 340);
  tip.style.left = left + 'px';
  tip.style.top = top + 'px';
});

function pfOpenDrawer() {
  pfDrawerOpen = true;
  const overlay = document.querySelector('.pf-drawer-overlay');
  const drawer = document.getElementById('pf-settings-drawer');
  if (overlay) overlay.classList.add('open');
  if (drawer) drawer.classList.add('open');
}
function pfCloseDrawer() {
  pfDrawerOpen = false;
  const overlay = document.querySelector('.pf-drawer-overlay');
  const drawer = document.getElementById('pf-settings-drawer');
  if (overlay) overlay.classList.remove('open');
  if (drawer) drawer.classList.remove('open');
}
function pfTogglePin(deck) {
  let pins = JSON.parse(localStorage.getItem('pf_deck_pins') || '[]');
  const idx = pins.indexOf(deck);
  if (idx >= 0) { pins.splice(idx, 1); }
  else if (pins.length < 3) { pins.push(deck); }
  localStorage.setItem('pf_deck_pins', JSON.stringify(pins));
  // Also keep legacy key in sync
  localStorage.setItem('pf_deck', pins[0] || '');
  render();
}
function pfToggleStudied(deck) {
  const studied = JSON.parse(localStorage.getItem('pf_studied_mus') || '[]');
  const idx = studied.indexOf(deck);
  if (idx >= 0) studied.splice(idx, 1); else studied.push(deck);
  localStorage.setItem('pf_studied_mus', JSON.stringify(studied));
  render();
}
function pfSelectDeck(deck) {
  pfActiveDeck = deck;
  pfInkPickerOpen = false;
  pfInkSel = [];
  // Cross-tab sync: set as active comparison in Coach and Lab
  if (deck && deck !== 'STANDARD') {
    selectedDeck = deck;
    coachDeck = deck;
    // Also sync ink picker
    const inks = DECK_INKS[deck];
    if (inks) selectedInks = [...inks];
  }
  render();
}
function pfRemoveDeck(deck) {
  let pins = JSON.parse(localStorage.getItem('pf_deck_pins') || '[]');
  pins = pins.filter(d => d !== deck);
  localStorage.setItem('pf_deck_pins', JSON.stringify(pins));
  localStorage.setItem('pf_deck', pins[0] || '');
  if (pfActiveDeck === deck) pfActiveDeck = pins[0] || 'STANDARD';
  render();
}
function pfToggleInkPicker() {
  pfInkPickerOpen = !pfInkPickerOpen;
  pfInkSel = [];
  render();
}
function pfToggleInk(inkId) {
  const idx = pfInkSel.indexOf(inkId);
  if (idx >= 0) { pfInkSel.splice(idx, 1); }
  else if (pfInkSel.length >= 2) { pfInkSel = [inkId]; }
  else { pfInkSel.push(inkId); }
  // Auto-select deck if 2 inks resolved
  if (pfInkSel.length === 2) {
    const key = [...pfInkSel].sort().join('+');
    const resolved = INK_PAIR_TO_DECK[key];
    if (resolved) {
      pfActiveDeck = resolved;
      selectedDeck = resolved;
      coachDeck = resolved;
      selectedInks = [...pfInkSel];
    }
  }
  render();
}
function pfPinAndSelect(deckCode) {
  let pins = JSON.parse(localStorage.getItem('pf_deck_pins') || '[]');
  if (!pins.includes(deckCode) && pins.length < 3) {
    pins.push(deckCode);
    localStorage.setItem('pf_deck_pins', JSON.stringify(pins));
    localStorage.setItem('pf_deck', pins[0] || '');
  }
  pfSelectDeck(deckCode);
}
function pfAddDeckFromInks() {
  if (pfInkSel.length !== 2) return;
  const key = [...pfInkSel].sort().join('+');
  const deckCode = INK_PAIR_TO_DECK[key];
  if (!deckCode) return;
  let pins = JSON.parse(localStorage.getItem('pf_deck_pins') || '[]');
  if (pins.includes(deckCode) || pins.length >= 3) return;
  pins.push(deckCode);
  localStorage.setItem('pf_deck_pins', JSON.stringify(pins));
  localStorage.setItem('pf_deck', pins[0] || '');
  pfActiveDeck = deckCode;
  pfInkPickerOpen = false;
  pfInkSel = [];
  // Cross-tab sync
  selectedDeck = deckCode;
  coachDeck = deckCode;
  const inks = DECK_INKS[deckCode];
  if (inks) selectedInks = [...inks];
  render();
}
function pfLoadDemo() {
  localStorage.setItem('pf_duels_nick', DEMO_PLAYER.nick);
  localStorage.setItem('pf_country', DEMO_PLAYER.country);
  localStorage.setItem('pf_deck_pins', JSON.stringify(DEMO_PLAYER.decks));
  localStorage.setItem('pf_demo', '1');
  // Set first deck as active benchmark
  const firstDeck = DEMO_PLAYER.decks[0];
  pfActiveDeck = firstDeck;
  selectedDeck = firstDeck;
  coachDeck = firstDeck;
  pfInkSel = DECK_INKS[firstDeck] ? [...DECK_INKS[firstDeck]] : [];
  selectedInks = [...pfInkSel];
  render();
}
function pfClearDemo() {
  localStorage.removeItem('pf_duels_nick');
  localStorage.removeItem('pf_country');
  localStorage.setItem('pf_deck_pins', '[]');
  localStorage.removeItem('pf_demo');
  render();
}
