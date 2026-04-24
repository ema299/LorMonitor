const _monAccRegistry = {};
// Info sheet registry (keyed by accordion id → {title, body})
const _monAccInfoRegistry = {};
function monAccShowInfo(id) {
  const info = _monAccInfoRegistry[id];
  if (info) showInfoSheet(info.title, info.body);
}

// Called from onOpen callbacks that contain Chart.js canvases.
// Triggers a resize event after the accordion animation completes so Chart.js
// can recompute canvas dimensions (otherwise charts inside a closed accordion
// were rendered at 0x0 width).
function monAccOnExpandResize() {
  setTimeout(() => {
    try { window.dispatchEvent(new Event('resize')); } catch(e) {}
  }, 340);
}

function monAccordion(id, labelHtml, summaryHtml, contentHtml, opts = {}) {
  const { openOnMobile = false, sub = false, desktopOpen = true, info = null } = opts;
  if (opts.onOpen) _monAccRegistry[id] = opts;
  if (info) _monAccInfoRegistry[id] = info;
  const isOpenClass = openOnMobile ? ' is-open' : '';
  const desktopOpenClass = desktopOpen ? ' mon-acc--desktop-open' : '';
  const subClass = sub ? ' mon-acc--sub' : '';
  const chevron = '<svg class="mon-acc__chevron" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const infoBtn = info
    ? `<button class="mon-acc__info-btn" type="button" onclick="event.stopPropagation();monAccShowInfo('${id}')" aria-label="About this section">?</button>`
    : '';
  return `<div class="mon-acc${subClass}${desktopOpenClass}${isOpenClass}" id="${id}">
    <div class="mon-acc__hdr" role="button" tabindex="0" onclick="monAccToggle('${id}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();monAccToggle('${id}')}">
      <span class="mon-acc__title">
        <span class="mon-acc__title-row">
          <span class="mon-acc__label-text">${labelHtml}</span>
          ${infoBtn}
        </span>
        ${summaryHtml ? `<span class="mon-acc__summary">${summaryHtml}</span>` : ''}
      </span>${chevron}
    </div>
    <div class="mon-acc__body"><div class="mon-acc__inner">${contentHtml}</div></div>
  </div>`;
}
function monAccToggle(id) {
  const el = document.getElementById(id);
  if (!el) return;
  // If accordion is marked desktop-open, the click does nothing on desktop
  // (CSS forces open state, toggle only relevant on mobile).
  const hasDesktopOpen = el.classList.contains('mon-acc--desktop-open');
  if (hasDesktopOpen && window.innerWidth >= 769) return;
  const isOpen = el.classList.contains('is-open');
  if (isOpen) { el.classList.remove('is-open'); }
  else {
    el.classList.add('is-open');
    const reg = _monAccRegistry[id];
    if (reg && reg.onOpen) {
      requestAnimationFrame(() => requestAnimationFrame(() => { reg.onOpen(id); delete _monAccRegistry[id]; }));
    }
  }
}
function monAccordionInit() {
  Object.keys(_monAccRegistry).forEach(id => {
    const el = document.getElementById(id);
    if (!el) { delete _monAccRegistry[id]; return; }
    if (el.classList.contains('is-open') && _monAccRegistry[id].onOpen) {
      requestAnimationFrame(() => requestAnimationFrame(() => { _monAccRegistry[id].onOpen(id); delete _monAccRegistry[id]; }));
    }
  });
}

// ── Meta Ticker ──
let _editorialItems = null;
let _editorialTs = 0;
const _EDITORIAL_TTL = 300000; // 5 min

async function fetchEditorialItems() {
  const now = Date.now();
  if (_editorialItems && (now - _editorialTs) < _EDITORIAL_TTL) return _editorialItems;
  try {
    const r = await fetch('/api/v1/news/ticker');
    if (!r.ok) return _editorialItems || [];
    _editorialItems = await r.json();
    _editorialTs = now;
  } catch(e) { _editorialItems = _editorialItems || []; }
  return _editorialItems;
}

function buildMetaTickerItems() {
  if (!DATA || !DATA.perimeters) return [];
  const scope = getScopeContext();
  const items = [];
  const perimKey = scope.perimeter || scope.primaryPerimeter;
  const pd = DATA.perimeters[perimKey];
  if (!pd) return [];

  // 1. Fitness top 3
  if (pd.fitness && pd.fitness.length) {
    const top3 = pd.fitness.slice(0, 3);
    top3.forEach((f, i) => {
      if (f.fitness != null)
        items.push({ label: 'META', text: `#${i+1} Fitness: ${f.deck} (${f.fitness.toFixed(1)})` });
    });
  }

  // 2. Meta share leaders
  if (pd.meta_share) {
    const shares = Object.entries(pd.meta_share)
      .filter(([,v]) => v.share > 10)
      .sort((a,b) => b[1].share - a[1].share)
      .slice(0, 2);
    shares.forEach(([dk, v]) => {
      items.push({ label: 'META', text: `${dk}: ${v.share.toFixed(1)}% meta share` });
    });
  }

  // 3. WR swings (biggest deltas)
  if (DATA.matchup_trend && DATA.matchup_trend[perimKey]) {
    const mt = DATA.matchup_trend[perimKey];
    const swings = [];
    for (const dk in mt) {
      for (const opp in mt[dk]) {
        const d = mt[dk][opp];
        if (d.delta != null && Math.abs(d.delta) >= 8 && d.recent_games >= 5)
          swings.push({ dk, opp, delta: d.delta });
      }
    }
    swings.sort((a,b) => Math.abs(b.delta) - Math.abs(a.delta));
    swings.slice(0, 2).forEach(s => {
      const sign = s.delta > 0 ? '+' : '';
      items.push({ label: 'META', text: `${s.dk} vs ${s.opp}: ${sign}${s.delta.toFixed(0)}pp WR shift` });
    });
  }

  return items.slice(0, 6); // cap META items
}

function renderMetaTicker(mount) {
  if (!mount) return;
  const metaItems = buildMetaTickerItems();
  const _channelAbbr = {
    'Lorcana Academy': 'LAc', 'Lorcana Goons': 'LGo', 'The Forbidden Mountain': 'TFM',
    'The Illumiteers': 'Ill', 'DMArmada': 'DMA', 'Team Covenant': 'TCo',
    'Ready Set Draw TCG': 'RSD', 'The Inkwell': 'Ink', 'phonetiic': 'Pho',
    'Mushu Report': 'Msh', 'Inkborn Heroes': 'IbH',
    'Tales of Lorcana': 'ToL', 'Inked Broom': 'IkB',
    'Lorecast': 'LCt',
  };
  const editorial = (_editorialItems || []).map(e => {
    const lang = (e.meta && e.meta.lang) || 'en';
    const abbr = _channelAbbr[e.channel] || (e.channel || '').slice(0, 3);
    return { label: e.label, text: `(${lang}) ${abbr}: ${e.title}`, url: e.url };
  });
  const all = [...metaItems, ...editorial].slice(0, 12);
  if (all.length < 2) { mount.innerHTML = ''; return; }

  const sep = '<span class="meta-ticker__sep">\u00b7</span>';
  function itemHtml(it) {
    const cls = 'meta-ticker__label--' + it.label.toLowerCase();
    if (it.url) {
      return `<a class="meta-ticker__item" href="${it.url}" target="_blank" rel="noopener">` +
        `<span class="meta-ticker__label ${cls}">${it.label}</span>` +
        `<span class="meta-ticker__text">${it.text}</span></a>`;
    }
    return `<span class="meta-ticker__item">` +
      `<span class="meta-ticker__label ${cls}">${it.label}</span>` +
      `<span class="meta-ticker__text">${it.text}</span></span>`;
  }

  const inner = all.map(itemHtml).join(sep);
  const dur = Math.max(25, all.length * 4); // seconds
  mount.innerHTML = `<div class="meta-ticker" style="--ticker-dur:${dur}s">` +
    `<div class="meta-ticker__track">${inner}${sep}${inner}${sep}</div></div>`;
}

function renderLadder(main) {
  const pd = getPerimData();
  const decks = Object.keys(pd.wr).sort((a,b) => pd.wr[b].games - pd.wr[a].games);
  const topDecks = decks.slice(0, 10);

  // If no deck selected, default to EmSa (or top deck if EmSa has no data)
  if (!selectedDeck) {
    selectedDeck = (pd.wr['EmSa']) ? 'EmSa' : topDecks[0];
    const inks = DECK_INKS[selectedDeck];
    if (inks) selectedInks = [...inks];
  }

  main.innerHTML = `
    <!-- META TICKER -->
    <div id="meta-ticker-mount"></div>

    <!-- DECK FITNESS STRIP -->
    <div class="section fit-section">
      <div class="fit-header">
        <div class="fit-title">
          Deck Fitness
          <button class="fit-info-btn" onclick="fitShowInfo()" aria-label="How is Fitness calculated?">?</button>
        </div>
        <span class="fit-subtitle">meta-weighted · 50 = break-even</span>
      </div>
      <div class="fit-strip-wrap">
        <button class="fit-arrow prev" id="fit-arrow-prev" onclick="fitScrollStrip(-1)" aria-label="Scroll left">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M10 4l-4 4 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="fit-arrow next" id="fit-arrow-next" onclick="fitScrollStrip(1)" aria-label="Scroll right">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <div class="fit-strip" id="fit-strip" role="list"></div>
      </div>
      <!-- EMERGING & ROGUE (inside fitness block) -->
      <div id="emerging-section" style="display:none"></div>
    </div>

    <!-- SECTION HEADER: Deep Analysis -->
    <div class="tab-section-hdr">
      <span class="tab-section-hdr__eyebrow">Deep Analysis</span>
      <span class="tab-section-hdr__title">Matchup · Deck Dive · Players · Picks</span>
    </div>

    <!-- MATCHUP MATRIX (collapsible, closed by default on all devices) -->
    <div class="section">
      ${monAccordion('acc-mm', 'Matchup Matrix', '', '<div class="mm-wrap" id="mm-wrap"></div>', {
        desktopOpen: false,
        onOpen: () => renderMatchupMatrix(getPerimData()),
        info: { title: 'About Matchup Matrix', body: '<p>Winrate for every deck pair in the current scope.</p><p>• <strong>Desktop</strong>: full heatmap. Click any cell to open that matchup in the Coach tab.</p><p>• <strong>Mobile</strong>: pick your deck from the dropdown and see the opponent list with WR and game count.</p><p>• Colors: <span style="color:#F85149">red &lt;45%</span>, <span style="color:#D29922">yellow ~50%</span>, <span style="color:#3FB950">green &gt;55%</span>.</p><p style="font-size:0.78em;color:var(--text2)">Matchups with fewer than 15 games are shown dimmed.</p>' }
      })}
    </div>

    <!-- DECK DEEP DIVE -->
    <div class="section">
      ${monAccordion('acc-deck', 'Deck Analysis', '', `
        <div id="deck-body">
          <div id="deck-identity"></div>
          <div id="deck-analysis" class="card" style="margin-bottom:16px;display:none"></div>
          <div id="deck-trend" style="margin-bottom:16px"></div>
          <div class="grid-2" id="deck-charts">
            <div class="chart-box"><h3>Matchup Win Rate</h3><div id="chart-matchup"></div></div>
            <div class="chart-box"><h3>OTP vs OTD Gap</h3><div id="chart-otpotd"></div></div>
          </div>
        </div>
      `, {
        desktopOpen: true,
        onOpen: monAccOnExpandResize,
        info: { title: 'About Deck Analysis', body: '<p>In-depth view of the selected deck in the current meta:</p><p>• <strong>Deck identity</strong> — colors, overall WR, meta share, games</p><p>• <strong>Matchup Win Rate</strong> — WR chart against every opponent</p><p>• <strong>OTP vs OTD Gap</strong> — difference between on-the-play and on-the-draw (positive = the deck wins more when going first)</p>' }
      })}
    </div>

    <!-- TOP PLAYERS -->
    <div class="section">
      ${monAccordion('acc-players', 'Best Format Players <span id="players-deck-label" style="font-weight:400;color:var(--text2);font-size:0.85em"></span>', '', `
        <div id="players-body">
          <div id="deck-compare-strip"></div>
          <div id="players-list"></div>
        </div>
      `, {
        desktopOpen: false,
        onOpen: monAccOnExpandResize,
        info: { title: 'About Best Format Players', body: '<p>Top players in the selected scope, pulled from the <code>duels.ink</code> leaderboard.</p><p>Only players ranked in the <strong>top 100</strong> (TOP) or <strong>top 50</strong> (PRO) for the format are shown.</p><p>Tap a name to open their details: decklist, WR, matchups, diff vs consensus.</p>' }
      })}
    </div>

    <!-- TECH TORNADO CHART -->
    <div class="section">
      ${monAccordion('acc-tech', 'Non-Standard Picks', '', `
        <div id="tech-body">
          <div class="chart-box" id="tech-tornado-box">
            <h3 id="tech-tornado-title">Adoption %: cards cut (←) vs added (→)</h3>
            <canvas id="chart-tech-tornado"></canvas>
          </div>
          <div style="font-size:0.75em;color:var(--text2);margin-top:6px;padding:0 4px">
            Bar = % of qualified players | Color = avg WR (green &ge;55%, red &le;48%) | Hover for details
          </div>
        </div>
      `, {
        desktopOpen: false,
        onOpen: monAccOnExpandResize,
        info: { title: 'About Non-Standard Picks', body: '<p>Cards that diverge from the deck consensus list, used by winning players (WR &ge; 52%, min 15 games).</p><p>• Green: card added (+) with high WR</p><p>• Red: card removed (−) from the consensus</p><p>Merged from PRO + TOP + Community. Max 4 in + 4 out.</p>' }
      })}
    </div>
  `;

  // Render charts (share/WR charts removed — replaced by compact table)
  renderMetaTicker(document.getElementById('meta-ticker-mount'));
  renderFitnessStrip(pd);
  renderEmergingDecks();
  renderMatchupMatrix(pd);
  renderDeckDive(pd);
  renderTechTornado();
}

// ── Emerging & Rogue ──
function renderEmergingDecks() {
  const el = document.getElementById('emerging-section');
  if (!el) return;

  const emg = DATA.emerging_decks || {};
  const fmt = getScopeContext().format;
  const tiles = emg[fmt] || [];

  if (!tiles.length) {
    el.style.display = 'none';
    return;
  }

  const badgeCfg = {
    off_meta:   { icon: '\u2694\uFE0F', label: 'Off-Meta',   border: '#F85149' },
    brew:       { icon: '\uD83E\uDDEA',  label: 'Brew',       border: '#3FB950' },
    new_colors: { icon: '\uD83D\uDD25',  label: 'New Colors', border: 'var(--gold)' },
  };

  let html = `<hr class="emg-divider"><div class="emg-header">
    <span class="emg-title">Emerging & Rogue</span>
    <span class="emg-subtitle">${tiles.length} signal${tiles.length > 1 ? 's' : ''} this week</span>
  </div><div class="emg-strip">`;

  tiles.forEach(t => {
    const cfg = badgeCfg[t.type] || { icon: '', label: t.type, border: 'var(--border)' };
    const wr = t.wr != null ? Math.round(t.wr * 100) : '?';
    const wrClass = wr >= 55 ? 'tier-high' : wr >= 48 ? 'tier-mid' : 'tier-low';
    const inks = DECK_INKS[t.deck] || [];
    const dots = inks.map(i => `<span class="ink-dot" style="background:var(--${i})"></span>`).join('');
    const cards = (t.cards || []).slice(0, 3).map(c => c.split(' - ')[0]).join(', ');
    const player = t.label || '';
    const playerShort = player.length > 16 ? player.slice(0, 15) + '\u2026' : player;

    const cardsJson = JSON.stringify(t.cards || []).replace(/'/g, '&#39;').replace(/"/g, '&quot;');
    html += `<div class="emg-tile" style="border-color:${cfg.border};cursor:pointer" onclick="showRogueDeckSheet('${player.replace(/'/g, "\\'")}','${t.deck}',JSON.parse(this.dataset.cards))" data-cards="${cardsJson}">
      <span class="emg-badge ${t.type}">${cfg.icon} ${cfg.label}</span>
      <div class="emg-deck">${dots} ${t.deck}</div>
      <div class="emg-label" title="${player}">${playerShort}</div>
      <div class="emg-wr ${wrClass}">${wr}%</div>
      <div class="emg-detail">${t.games}g${t.mmr ? ' · ' + t.mmr + ' MMR' : ''}</div>
      ${cards ? `<div class="emg-cards">${cards}</div>` : ''}
    </div>`;
  });

  html += '</div>';
  el.innerHTML = html;
  el.style.display = '';
}

function showRogueDeckSheet(playerName, deckCode, signatureCards) {
  const pc = getScopedPlayerCards();
  const pCards = (pc[playerName.toLowerCase()] || {})[deckCode];
  const cons = (DATA.consensus || {})[deckCode];
  const imgMap = DATA.card_images || {};

  // estQty — same hypergeometric MLE thresholds as buildDeckCompare
  function estQty(pSeen, total, stdQty) {
    const rate = total > 0 ? pSeen / total : 0;
    if (stdQty) return stdQty;
    if (total >= 8) {
      if (rate >= 0.67) return 4;
      if (rate >= 0.54) return 3;
      if (rate >= 0.37) return 2;
      return 1;
    } else {
      if (rate >= 0.54) return 3;
      if (rate >= 0.37) return 2;
      return 1;
    }
  }

  if (!pCards || Object.keys(pCards).length === 0) {
    // No play data — show just signature cards
    const lines = (signatureCards || []).map(c =>
      `<div style="padding:4px 0;border-bottom:1px solid var(--border)">${c}</div>`
    ).join('');
    showInfoSheet(`${deckCode} — ${playerName}`,
      `<p style="color:var(--text2);font-size:0.85em">No play data available for a full estimate. Signature cards:</p>${lines}`);
    return;
  }

  const observedGames = Math.max(...Object.values(pCards));
  const std = cons || {};

  // Build estimated list (same logic as buildDeckCompare)
  const estList = [];
  for (const [card, qty] of Object.entries(std)) {
    const pSeen = pCards[card] || 0;
    estList.push({ card, qty: estQty(pSeen, observedGames, Math.round(qty)), source: pSeen > 0 ? 'kept' : 'assumed', pSeen });
  }
  for (const [card, pSeen] of Object.entries(pCards)) {
    if (!(card in std) && pSeen >= 1) {
      estList.push({ card, qty: estQty(pSeen, observedGames, 0), source: 'added', pSeen });
    }
  }

  let total = estList.reduce((s, c) => s + c.qty, 0);
  // Trim if over 60
  while (total > 60) {
    estList.sort((a, b) => a.pSeen - b.pSeen || a.qty - b.qty);
    const t = estList.find(c => c.qty > 0);
    if (!t) break;
    t.qty--; total--;
    if (t.qty === 0) estList.splice(estList.indexOf(t), 1);
  }

  estList.sort((a, b) => b.qty - a.qty || a.card.localeCompare(b.card));
  total = estList.reduce((s, c) => s + c.qty, 0);
  const observed = estList.filter(c => c.pSeen > 0).reduce((s, c) => s + c.qty, 0);
  const conf = Math.round(observed / 60 * 100);
  const confColor = conf >= 70 ? 'var(--green)' : conf >= 40 ? 'var(--yellow)' : 'var(--red)';
  const confLabel = conf >= 70 ? 'High' : conf >= 40 ? 'Medium' : 'Low';

  const isSig = new Set((signatureCards || []).map(c => c.toLowerCase()));

  const rows = estList.map(c => {
    const sig = isSig.has(c.card.toLowerCase()) ? ' *' : '';
    const clr = c.source === 'added' ? 'color:var(--green)' : c.source === 'assumed' ? 'color:var(--text2)' : '';
    const marker = c.source === 'added' ? ' <span style="color:var(--green);font-size:0.75em">TECH</span>' : c.source === 'assumed' ? ' <span style="color:var(--text2);font-size:0.75em">?</span>' : '';
    return `<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--surface2);${clr}">
      <span>${c.qty}x ${c.card}${sig}${marker}</span>
      <span style="color:var(--text2);font-size:0.8em">${c.pSeen > 0 ? c.pSeen + '/' + observedGames + 'g' : ''}</span>
    </div>`;
  }).join('');

  const copyId = 'rogue-copy-' + Math.random().toString(36).slice(2, 7);
  const copyText = estList.map(c => `${c.qty} ${c.card}`).join('\n');

  showInfoSheet(`${deckCode} — ${playerName}`,
    `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-size:0.85em;color:var(--text2)">${total} cards · ${observedGames} games observed · <span style="color:${confColor}">Confidence ${confLabel} (${conf}%)</span></span>
      <button class="copy-btn" style="font-size:0.75em;padding:2px 8px;cursor:pointer" onclick="navigator.clipboard.writeText(document.getElementById('${copyId}').textContent).then(()=>{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',1500)})">Copy</button>
    </div>
    <div style="max-height:55vh;overflow-y:auto;font-size:0.88em">${rows}</div>
    <pre id="${copyId}" style="display:none">${copyText}</pre>
    <div style="font-size:0.72em;color:var(--text2);margin-top:8px"><span style="color:var(--green)">TECH</span> = non-consensus card · <span style="color:var(--text2)">?</span> = assumed from consensus · * = signature</div>`);
}

// ── Matchup Matrix (desktop heatmap + mobile list) ──
let _mmSelectedDeck = null;
// Sticky session state — persists across perimeter changes
let _mmView = { side: 'otp', bo: 'all' };
// Lazy cache for Bo3/Bo1 slices: key = `${format}|${perim}|${bo}` → { matrix, otp_otd }
let _mmSliceCache = {};
let _mmLoading = false;

function mmCellColor(wr) {
  // Smooth 3-stop gradient: red 40 → yellow 50 → green 60
  if (wr >= 60) return 'rgba(63,185,80,0.85)';
  if (wr >= 55) return 'rgba(63,185,80,0.65)';
  if (wr >= 50) return 'rgba(210,153,34,0.7)';
  if (wr >= 45) return 'rgba(248,81,73,0.55)';
  return 'rgba(248,81,73,0.85)';
}

function mmCacheKey(fmt, perim, bo) { return `${fmt}|${perim}|${bo}`; }

function mmBaseMatrix(pd) {
  // Return the "OTP perspective" matrix (deck_a wins against deck_b)
  // for the currently active slice (all or bo3).
  if (_mmView.bo === 'all') return pd.matrix || {};
  const ctx = getScopeContext();
  const key = mmCacheKey(ctx.format || 'core', ctx.perimeter, _mmView.bo);
  const slice = _mmSliceCache[key];
  return slice ? slice.matrix : null;
}

function mmInvertMatrix(base) {
  // From OTP view to OTD view: cell[row][col] (row OTD vs col OTP) =
  // invert of base[col][row] which is col OTP vs row OTD.
  const inv = {};
  for (const a of Object.keys(base || {})) {
    for (const b of Object.keys(base[a] || {})) {
      const src = base[a][b];
      if (!src) continue;
      if (!inv[b]) inv[b] = {};
      inv[b][a] = { w: src.t - src.w, t: src.t };
    }
  }
  return inv;
}

async function mmLoadSlice(fmt, perim, bo) {
  const key = mmCacheKey(fmt, perim, bo);
  if (_mmSliceCache[key]) return;
  _mmLoading = true;
  renderMatchupMatrix(getPerimData());
  try {
    const url = `/api/v1/dashboard-data/queue-slice?perimeter=${encodeURIComponent(perim)}&queue_filter=${bo}&days=7`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _mmSliceCache[key] = await res.json();
  } catch(e) {
    console.error('[matchup-matrix]', bo, 'slice fetch failed:', e);
    _mmView.bo = 'all';
  } finally {
    _mmLoading = false;
    renderMatchupMatrix(getPerimData());
  }
}

function mmSetSide(side) {
  if (_mmLoading || _mmView.side === side) return;
  _mmView.side = side;
  renderMatchupMatrix(getPerimData());
}

function mmSetBo(bo) {
  if (_mmLoading || _mmView.bo === bo) return;
  _mmView.bo = bo;
  if (bo === 'all') {
    renderMatchupMatrix(getPerimData());
    return;
  }
  const ctx = getScopeContext();
  const fmt = ctx.format || 'core';
  const perim = ctx.perimeter;
  if (_mmSliceCache[mmCacheKey(fmt, perim, bo)]) {
    renderMatchupMatrix(getPerimData());
  } else {
    mmLoadSlice(fmt, perim, bo);
  }
}

function renderMatchupMatrix(pd) {
  const wrap = document.getElementById('mm-wrap');
  if (!wrap) return;
  const wr = pd.wr || {};
  // Decks sorted by popularity (total games)
  const decks = Object.keys(wr)
    .filter(d => wr[d].games >= 15)
    .sort((a, b) => wr[b].games - wr[a].games);

  if (!decks.length) {
    wrap.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text2)">No matchup data available.</div>';
    return;
  }

  // Resolve active matrix based on sticky view state (side + bo).
  const base = mmBaseMatrix(pd);
  const matrix = base ? (_mmView.side === 'otd' ? mmInvertMatrix(base) : base) : null;

  // Default selected deck = user's selected or EmSa or top
  if (!_mmSelectedDeck || !decks.includes(_mmSelectedDeck)) {
    _mmSelectedDeck = (typeof selectedDeck !== 'undefined' && selectedDeck && decks.includes(selectedDeck))
      ? selectedDeck
      : (decks.includes('EmSa') ? 'EmSa' : decks[0]);
  }

  const isMobile = window.innerWidth < 769;

  const legendHtml = `
    <span class="mm-legend">
      <span class="mm-legend-swatch" style="background:rgba(248,81,73,0.85)"></span>&lt;45%
      <span class="mm-legend-swatch" style="background:rgba(210,153,34,0.7)"></span>50%
      <span class="mm-legend-swatch" style="background:rgba(63,185,80,0.85)"></span>&gt;55%
    </span>
  `;
  const sideToggle = `
    <div class="mm-toggle-group" role="group" aria-label="Play side">
      <button class="mm-toggle ${_mmView.side==='otp'?'active':''}" onclick="mmSetSide('otp')" title="On-the-Play: row deck plays first">OTP</button>
      <button class="mm-toggle ${_mmView.side==='otd'?'active':''}" onclick="mmSetSide('otd')" title="On-the-Draw: row deck plays second">OTD</button>
    </div>`;
  const boToggle = `
    <div class="mm-toggle-group" role="group" aria-label="Queue format">
      <button class="mm-toggle ${_mmView.bo==='all'?'active':''}" onclick="mmSetBo('all')" title="All queues">All</button>
      <button class="mm-toggle ${_mmView.bo==='bo3'?'active':''}" ${_mmLoading?'disabled':''} onclick="mmSetBo('bo3')" title="Only Bo3 matches">Bo3</button>
    </div>`;

  let toolbarHtml;
  if (isMobile) {
    const deckOptions = decks.map(d => `<option value="${d}" ${d === _mmSelectedDeck ? 'selected' : ''}>${d} · ${DECK_NAMES[d] || d}</option>`).join('');
    toolbarHtml = `
      <div class="mm-toolbar">
        <label for="mm-deck">Deck:</label>
        <select class="mm-deck-select" id="mm-deck" onchange="mmOnDeckChange(this.value)">${deckOptions}</select>
        ${sideToggle}
        ${boToggle}
        ${legendHtml}
      </div>
    `;
  } else {
    toolbarHtml = `
      <div class="mm-toolbar">
        <span class="mm-toolbar-meta" style="margin-left:0">Click any cell to open matchup in Coach</span>
        ${sideToggle}
        ${boToggle}
        ${legendHtml}
      </div>
    `;
  }

  if (_mmLoading) {
    wrap.innerHTML = `${toolbarHtml}<div style="padding:40px;text-align:center;color:var(--text2);font-size:0.88em">Loading ${_mmView.bo.toUpperCase()} slice…</div>`;
    return;
  }
  if (!matrix) {
    wrap.innerHTML = `${toolbarHtml}<div style="padding:40px;text-align:center;color:var(--text2);font-size:0.88em">No data for this slice.</div>`;
    return;
  }

  if (isMobile) {
    // Mobile: list of opponents for selected deck
    const row = matrix[_mmSelectedDeck] || {};
    const opps = decks.filter(d => d !== _mmSelectedDeck);
    const rowsHtml = opps.map(opp => {
      const cell = row[opp];
      const t = cell ? cell.t : 0;
      const w = cell ? cell.w : 0;
      const wrVal = t > 0 ? (w / t * 100) : null;
      if (!cell || t === 0) {
        return `<div class="mm-list-row empty" aria-label="${opp}: no data">
          ${deckImg(opp, 24)}
          <span class="mm-opp-name">${opp} · ${DECK_NAMES[opp] || opp}</span>
          <span style="color:var(--text2);font-size:0.78em">no data</span>
          <span></span>
        </div>`;
      }
      const lowSample = t < 15;
      const color = mmCellColor(wrVal);
      return `<div class="mm-list-row ${lowSample ? 'low-sample' : ''}"
           onclick="mmOpenMatchup('${_mmSelectedDeck}', '${opp}')"
           onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();mmOpenMatchup('${_mmSelectedDeck}','${opp}')}"
           role="button" tabindex="0"
           aria-label="${_mmSelectedDeck} vs ${opp}: ${wrVal.toFixed(1)} percent winrate, ${t} games">
        ${deckImg(opp, 24)}
        <div style="min-width:0">
          <div class="mm-opp-name">${opp}</div>
          <div class="mm-opp-bar-wrap"><div class="mm-opp-bar" style="width:${Math.max(2, Math.min(100, wrVal))}%;background:${color}"></div></div>
        </div>
        <span class="mm-opp-wr" style="color:${color}">${wrVal.toFixed(1)}%</span>
        <span class="mm-opp-games">${t}g</span>
      </div>`;
    }).join('');
    wrap.innerHTML = `${toolbarHtml}
      <div class="mm-list-header">
        <span style="flex:1">Vs · ${_mmSelectedDeck}</span>
        <span>WR</span><span>Games</span>
      </div>
      <div class="mm-list">${rowsHtml}</div>`;
    return;
  }

  // Desktop: full heatmap
  let thead = '<tr><th class="mm-row-header"></th>';
  decks.forEach(d => {
    thead += `<th class="mm-th" title="${DECK_NAMES[d] || d}"><span class="mm-th-icon">${deckImg(d, 14)}</span>${d}</th>`;
  });
  thead += '</tr>';

  let rowsHtml = '';
  decks.forEach(rowDeck => {
    rowsHtml += `<tr><td class="mm-row-header">${deckImg(rowDeck, 14)} ${rowDeck}</td>`;
    decks.forEach(colDeck => {
      if (rowDeck === colDeck) {
        rowsHtml += `<td class="mm-cell diag">—</td>`;
        return;
      }
      const cell = (matrix[rowDeck] || {})[colDeck];
      const t = cell ? cell.t : 0;
      const w = cell ? cell.w : 0;
      if (!cell || t === 0) {
        rowsHtml += `<td class="mm-cell empty" title="No data">·</td>`;
        return;
      }
      const wrVal = (w / t) * 100;
      const color = mmCellColor(wrVal);
      const lowSample = t < 15;
      rowsHtml += `<td class="mm-cell ${lowSample ? 'low-sample' : ''}"
         style="background:${color}"
         title="${rowDeck} vs ${colDeck}: ${wrVal.toFixed(1)}% (${t}g)"
         onclick="mmOpenMatchup('${rowDeck}','${colDeck}')"
         onkeydown="if(event.key==='Enter'){mmOpenMatchup('${rowDeck}','${colDeck}')}"
         tabindex="0"
         aria-label="${rowDeck} vs ${colDeck}: ${wrVal.toFixed(1)} percent">${wrVal.toFixed(0)}</td>`;
    });
    rowsHtml += '</tr>';
  });

  wrap.innerHTML = `${toolbarHtml}
    <div class="mm-heatmap-wrap">
      <table class="mm-table" role="grid" aria-label="Matchup winrate matrix">
        <thead>${thead}</thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>`;
}

function mmOnDeckChange(deck) {
  _mmSelectedDeck = deck;
  const pd = getPerimData();
  renderMatchupMatrix(pd);
}

function mmOpenMatchup(our, opp) {
  // Cross-tab: switch to Coach V2 with this matchup pre-selected.
  // switchToTab(id, opts) updates selectedDeck/coachDeck/coachOpp/labOpp.
  // We also sync the ink pickers (our + opp) and localStorage so the Coach tab
  // renders the correct ink icons without a reset round.
  const ourInks = DECK_INKS[our];
  if (ourInks) selectedInks = [...ourInks];
  if (typeof syncOppInksFromDeck === 'function') syncOppInksFromDeck(opp);
  try { localStorage.setItem('lorcana_deck_code', our); } catch(e) {}
  switchToTab('play', { deck: our, opp: opp });
}

// ── Deck Fitness Strip ──
function renderFitnessStrip(pd) {
  const wrap = document.getElementById('fit-strip');
  if (!wrap) return;
  const items = (pd && pd.fitness) ? pd.fitness : [];
  if (!items.length) {
    // skeleton fallback (3 cards) if no data yet
    wrap.innerHTML = Array(4).fill(0).map(() => `
      <div class="fit-card skeleton" aria-hidden="true">
        <div class="fit-card-top"><span class="fit-card-name">&nbsp;</span></div>
        <div class="fit-score">&nbsp;</div>
        <div class="fit-bar-bg"><div class="fit-bar-fill" style="width:60%"></div></div>
        <div class="fit-meta">&nbsp;</div>
      </div>`).join('');
    return;
  }
  // After innerHTML rendering, wire scroll handlers and update arrow state
  requestAnimationFrame(() => { fitWireStripScroll(); fitUpdateArrows(); });
  wrap.innerHTML = items.map((r, idx) => {
    const deck = r.deck;
    const hasFit = r.fitness !== null && r.fitness !== undefined;
    let tier = 'none';
    let scoreText = '—';
    if (hasFit) {
      scoreText = r.fitness.toFixed(0);
      if (r.fitness >= 55) tier = 'high';
      else if (r.fitness >= 45) tier = 'mid';
      else tier = 'low';
    }
    const barWidth = hasFit ? Math.max(4, Math.min(100, r.fitness)) : 0;
    const rankClass = (idx === 0 && hasFit) ? 'rank1' : '';
    const rankBadgeClass = (idx === 0 && hasFit) ? 'fit-rank top' : 'fit-rank';
    const rankBadge = hasFit ? `#${r.rank}` : '';
    const name = DECK_NAMES[deck] || deck;
    const shareTxt = r.meta_share ? `${r.meta_share.toFixed(1)}%` : '–';
    return `
      <div class="fit-card ${rankClass}" role="listitem" tabindex="0"
           onclick="fitSelectDeck('${deck}')"
           onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();fitSelectDeck('${deck}')}"
           aria-label="${deck} fitness ${scoreText}, rank ${rankBadge || 'n/a'}, meta share ${shareTxt}">
        <div class="fit-card-top">
          <div class="fit-card-deck">${deckImg(deck, 18)}<span class="fit-card-name">${deck}</span></div>
          <span class="${rankBadgeClass}">${rankBadge}</span>
        </div>
        <div class="fit-score tier-${tier}">${scoreText}</div>
        <div class="fit-bar-bg"><div class="fit-bar-fill tier-${tier}" style="width:${barWidth}%"></div></div>
        <div class="fit-meta">Share ${shareTxt} · ${r.games.toLocaleString()}g</div>
      </div>`;
  }).join('');
}

function fitScrollStrip(dir) {
  const strip = document.getElementById('fit-strip');
  if (!strip) return;
  const cardWidth = 142; // 132 width + 10 gap
  strip.scrollBy({ left: dir * cardWidth * 3, behavior: 'smooth' });
}

function fitUpdateArrows() {
  const strip = document.getElementById('fit-strip');
  const prev = document.getElementById('fit-arrow-prev');
  const next = document.getElementById('fit-arrow-next');
  if (!strip || !prev || !next) return;
  const maxScroll = strip.scrollWidth - strip.clientWidth;
  prev.disabled = strip.scrollLeft <= 2;
  next.disabled = strip.scrollLeft >= maxScroll - 2;
}

function fitWireStripScroll() {
  const strip = document.getElementById('fit-strip');
  if (!strip || strip._wired) return;
  strip._wired = true;
  // Wheel → horizontal scroll on desktop
  strip.addEventListener('wheel', (e) => {
    if (window.innerWidth < 769) return;
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
      e.preventDefault();
      strip.scrollLeft += e.deltaY;
    }
  }, { passive: false });
  strip.addEventListener('scroll', fitUpdateArrows, { passive: true });
  window.addEventListener('resize', fitUpdateArrows, { passive: true });
}

function fitSelectDeck(deck) {
  // Sync cross-tab deck selection via existing helper
  if (typeof selectDeck === 'function') { selectDeck(deck); return; }
  if (typeof onDeckSelect === 'function') { onDeckSelect(deck); return; }
  // Fallback: set global + re-render
  selectedDeck = deck;
  const inks = DECK_INKS[deck];
  if (inks) selectedInks = [...inks];
  if (typeof renderInkPicker === 'function') renderInkPicker();
  loadTab();
}

// Generic info sheet (reusable across sections). bodyHtml may contain <p>, <code>, <strong>.
function showInfoSheet(title, bodyHtml) {
  let sheet = document.getElementById('fit-info-sheet');
  if (!sheet) {
    sheet = document.createElement('div');
    sheet.id = 'fit-info-sheet';
    sheet.className = 'fit-info-sheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-labelledby', 'fit-info-title');
    document.body.appendChild(sheet);
    sheet.addEventListener('click', (e) => { if (e.target === sheet) hideInfoSheet(); });
  }
  sheet.innerHTML = `
    <div class="fit-info-sheet__panel">
      <h3 id="fit-info-title">${title}</h3>
      ${bodyHtml}
      <button class="fit-info-sheet__close" onclick="hideInfoSheet()">Got it</button>
    </div>`;
  sheet.classList.add('open');
}
function hideInfoSheet() {
  const sheet = document.getElementById('fit-info-sheet');
  if (sheet) sheet.classList.remove('open');
}
// Backward-compat: fitShowInfo() triggers the Fitness explanation
function fitShowInfo() {
  showInfoSheet('How Deck Fitness works', `
    <p>A single 0–100 score for each deck in the current meta.</p>
    <p><code>fitness = Σ (WR vs X · meta_share[X]) / Σ meta_share[X]</code></p>
    <p><strong>50 = meta break-even.</strong> Higher = deck performs well weighted by how often you meet each opponent.</p>
    <p style="font-size:0.78em;color:var(--text2)">Matchups with &lt;15 games are excluded.</p>
  `);
}
function fitHideInfo() { hideInfoSheet(); }

function renderShareChart(pd, decks) {
  const top8 = decks.slice(0, 8);
  const others = decks.slice(8);
  const data = top8.map(d => pd.wr[d].games);
  const othersTotal = others.reduce((s,d) => s + pd.wr[d].games, 0);
  const labels = [...top8.map(d => DECK_NAMES[d] || d), 'Altri'];
  data.push(othersTotal);
  const colors = [...top8.map(d => deckColor(d)), '#444'];
  const total = data.reduce((a,b)=>a+b,0);

  // Mobile: HTML list FIRST (always rendered, shown/hidden via CSS — must not depend on Chart.js)
  const listEl = document.getElementById('chart-share-list');
  if (listEl) {
    const allDecks = [...top8, 'altri'];
    const allData  = [...data];
    const allColors = [...colors];
    const allLabels = [...labels];
    let html = '<div class="share-list">';
    allData.forEach((games, i) => {
      const pct = total > 0 ? (games / total * 100).toFixed(1) : '0.0';
      const barW = total > 0 ? Math.max(2, (games / total * 100)).toFixed(1) : 0;
      html += `<div class="share-row">
        <span class="share-dot" style="background:${allColors[i]}"></span>
        <div class="share-bar-track">
          <div class="share-bar-fill" style="width:${barW}%;background:${allColors[i]}"></div>
        </div>
        <span class="share-pct">${pct}%</span>
        <span class="share-games">${games.toLocaleString()}</span>
      </div>
      <div style="font-size:0.72em;color:var(--text2);padding:0 0 2px 18px">${allLabels[i]}</div>`;
    });
    html += '</div>';
    listEl.innerHTML = html;
  }

  // Desktop: Chart.js doughnut (wrapped in try/catch — must not break mobile)
  try {
    const shareCanvas = document.getElementById('chart-share');
    if (shareCanvas && typeof Chart !== 'undefined') {
      const legendPos = window.innerWidth < 900 ? 'bottom' : 'right';
      charts.share = new Chart(shareCanvas, {
        type: 'doughnut',
        data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: { position: legendPos, labels: { color: '#8B949E', font: { size: 11 }, boxWidth: 12, padding: 8 } },
            tooltip: {
              callbacks: {
                label: ctx => {
                  const pct = (ctx.raw / total * 100).toFixed(1);
                  return ` ${ctx.label}: ${ctx.raw.toLocaleString()} (${pct}%)`;
                }
              }
            }
          }
        }
      });
    }
  } catch(e) { console.warn('Share chart init failed:', e); }
}

function renderWRChart(pd, decks) {
  const top8 = decks.slice(0, 8);
  const container = document.getElementById('chart-wr');
  if (!container) return;

  // Track spans 42–58; dot positioned as % from left
  const minWR = 42, maxWR = 58, range = maxWR - minWR;

  function lpColor(wr) {
    if (wr >= 54) return 'green';
    if (wr <= 46) return 'red';
    return 'gray';
  }

  let html = '<div class="lollipop-chart">';
  top8.forEach(d => {
    const wr    = parseFloat(pd.wr[d].wr.toFixed(1));
    const games = pd.wr[d].games;
    const col   = lpColor(wr);
    const clamp = Math.max(minWR, Math.min(maxWR, wr));
    const dotPct  = ((clamp - minWR) / range * 100).toFixed(2);  // % from left
    const midPct  = ((50   - minWR) / range * 100).toFixed(2);   // always 50% of range
    // Stem: from midPct to dotPct
    const stemLeft  = Math.min(parseFloat(dotPct), parseFloat(midPct)).toFixed(2);
    const stemWidth = Math.abs(parseFloat(dotPct) - parseFloat(midPct)).toFixed(2);
    const wrCls = wr >= 55 ? 'wr-good' : wr <= 45 ? 'wr-bad' : 'wr-mid';

    html += `<div class="lp-row">
      <span class="lp-label" title="${DECK_NAMES[d]||d}">${deckImg(d,30)}</span>
      <div class="lp-track">
        <div class="lp-ref"></div>
        <div class="lp-stem lp-stem-${col}" style="left:${stemLeft}%;width:${stemWidth}%"></div>
        <div class="lp-dot lp-${col}" style="left:${dotPct}%"></div>
      </div>
      <span class="lp-value ${wrCls}">${wr}% <span style="color:var(--text2);font-weight:400;font-size:0.85em">(${games})</span></span>
    </div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

// Simple markdown-to-HTML
function renderMarkdown(md) {
  if (!md) return '';
  return md
    .replace(/### (.+)/g, '<h4 style="color:var(--gold);margin:16px 0 8px">$1</h4>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul style="margin:4px 0 12px 16px;color:var(--text)">$1</ul>')
    .replace(/\n\n/g, '<br>')
    .replace(/\n/g, ' ');
}

// (Tech Global section replaced by Bubble Chart)

// === DECK DEEP DIVE ===
function renderDeckDive(pd) {
  const d = selectedDeck;
  if (!pd || !pd.wr[d]) {
    // No data for this deck in current perimeter
    const el = document.getElementById('deck-identity');
    if (el) {
      const fullName = DECK_NAMES[d] || d || '?';
      // Find perimeters that have data for this deck
      const altPerims = [];
      const scope = getScopeContext();
      const fmtPerims = scope.availablePerimeters;
      fmtPerims.forEach(p => {
        const pData = DATA.perimeters[p.id];
        if (pData && pData.wr && pData.wr[d] && p.id !== scope.perimeter) altPerims.push(p);
      });
      const altBtns = altPerims.map(p => `<button class="perim-btn" onclick="document.querySelectorAll('.perim-btn').forEach(b=>b.classList.remove('active'));currentPerim='${p.id}';selectedDeck='${d}';syncPerimButtons();render()">${p.label}</button>`).join(' ');
      el.innerHTML = `<div class="card" style="text-align:center;padding:32px">
        <div style="font-size:1.2em;color:var(--text2);margin-bottom:8px">${fullName}</div>
        <div style="color:var(--yellow);margin-bottom:16px">No data available for the current scope.</div>
        ${altBtns ? '<div style="font-size:0.85em;color:var(--text2);margin-bottom:8px">Prova:</div>' + altBtns : ''}
      </div>`;
    }
    return;
  }
  const wr = pd.wr[d];

  // Identity card
  const inks = DECK_INKS[d] || [];
  const dots = inks.map(i => `<span class="ink-dot" style="background:${INK_COLORS[i]}"></span>`).join('');
  const share = pd.meta_share[d];
  const shareStr = share ? `${share.share}%` : '-';

  const fullName = DECK_NAMES[d] || d;
  const eloDist = pd.elo_dist ? pd.elo_dist[d] : null;
  const eloAvg = eloDist ? eloDist.avg : '';

  document.getElementById('deck-identity').innerHTML = `
    <div class="identity" style="justify-content:space-between">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div>
          <div class="deck-name">${deckImg(d,42)}</div>
          <div class="ink-dots">${dots} <span style="color:var(--text2);font-size:0.85em;margin-left:6px">${fullName}</span></div>
        </div>
        <div class="stat-row">
          <div class="stat"><div class="val ${wrClass(wr.wr)}">${wr.wr.toFixed(1)}%</div><div class="lbl">Win Rate</div></div>
          <div class="stat"><div class="val">${wr.games.toLocaleString()}</div><div class="lbl">Games</div></div>
          <div class="stat"><div class="val">${shareStr}</div><div class="lbl">Meta Share</div></div>
          ${eloAvg ? `<div class="stat"><div class="val">${eloAvg}</div><div class="lbl">MMR Medio</div></div>` : ''}
        </div>
      </div>
      <div style="min-width:180px;max-width:240px" id="elo-hist-box">
        <canvas id="chart-elo-hist" height="60"></canvas>
      </div>
    </div>
  `;

  // Render ELO histogram
  if (eloDist && eloDist.counts.some(c => c > 0)) {
    if (charts.eloHist) charts.eloHist.destroy();
    const inks2 = DECK_INKS[d] || ['steel','steel'];
    charts.eloHist = new Chart(document.getElementById('chart-elo-hist'), {
      type: 'bar',
      data: {
        labels: eloDist.bins,
        datasets: [{
          data: eloDist.counts,
          backgroundColor: `${INK_COLORS[inks2[0]]}88`,
          borderColor: INK_COLORS[inks2[1]],
          borderWidth: 1,
          borderRadius: 3,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { display: false },
          x: { ticks: { color: '#8B949E', font: { size: 9 }, maxRotation: 45 }, grid: { display: false } }
        },
        plugins: {
          legend: { display: false },
          title: { display: true, text: 'ELO', color: '#8B949E', font: { size: 9 }, padding: 2 },
          tooltip: {
            callbacks: { label: ctx => ` ${ctx.raw} player` }
          }
        }
      }
    });
  }

  // Deck-specific analysis
  renderDeckAnalysis(d);
  // Matchup trend (5 days)
  renderMatchupTrend(d);
  // Charts
  renderMatchupChart(pd, d);
  renderOTPOTDChart(pd, d);
  renderPlayers(pd, d);
  renderTechTornado();
  document.getElementById('players-deck-label').innerHTML = `${deckImg(d,30)} <span style="color:var(--text2);font-size:0.8em">${fullName}</span>`;

  // Render deck compare strip (pentagon + delta) when custom mode
  const stripEl = document.getElementById('deck-compare-strip');
  if (stripEl) {
    if (getScopeContext().isCustomDeck && myDeckCards && DATA.consensus && DATA.consensus[d]) {
      const std = DATA.consensus[d];
      const added = [], missing = [];
      for (const [card, qty] of Object.entries(myDeckCards)) {
        if (!std[card]) added.push(card);
      }
      for (const [card, qty] of Object.entries(std)) {
        if (!myDeckCards[card]) missing.push(card);
      }
      const common = Object.keys(myDeckCards).filter(c => c in std).length;

      let deltaHtml = '';
      if (added.length) deltaHtml += '<div style="color:var(--green);font-size:0.8em">+' + added.length + ' not in consensus: ' + added.slice(0,3).join(', ') + (added.length>3?'...':'') + '</div>';
      if (missing.length) deltaHtml += '<div style="color:var(--red);font-size:0.8em">-' + missing.length + ' missing from consensus: ' + missing.slice(0,3).join(', ') + (missing.length>3?'...':'') + '</div>';
      deltaHtml += '<div style="color:var(--text2);font-size:0.75em">' + common + ' cards in common</div>';

      // Pentagon SVG
      var pentSvg = '';
      try { pentSvg = buildDeckPentagon(d, 100); } catch(e) { console.error('Pentagon:', e); }

      stripEl.innerHTML = '<div class="card" style="display:flex;align-items:center;gap:20px;padding:16px 20px;margin-bottom:12px;border-left:3px solid var(--gold);flex-wrap:wrap">'
        + (pentSvg ? '<div style="flex-shrink:0">' + pentSvg + '</div>' : '')
        + '<div>'
        + '<div style="font-size:0.9em;color:var(--gold);font-weight:600;margin-bottom:6px">Your deck vs Consensus</div>'
        + deltaHtml
        + '</div>'
        + '</div>';
    } else {
      stripEl.innerHTML = '';
    }
  }
}

function renderDeckAnalysis(deck) {
  const el = document.getElementById('deck-analysis');
  const pd = getPerimData();
  const wr = pd.wr[deck];
  if (!wr) { el.style.display = 'none'; return; }

  const inks = DECK_INKS[deck] || [];
  const grad = inks.length >= 2 ? `linear-gradient(90deg, ${INK_COLORS[inks[0]]}, ${INK_COLORS[inks[1]]})` : 'var(--gold)';
  el.style.display = 'block';
  el.style.borderLeft = '3px solid';
  el.style.borderImage = grad + ' 1';

  // Build deck-specific analysis from data
  const fullName = DECK_NAMES[deck] || deck;
  const lines = [];

  // WR status
  const wrVal = wr.wr;
  const wrStatus = wrVal >= 54 ? 'strong' : wrVal >= 50 ? 'even' : wrVal >= 47 ? 'struggling' : 'weak';
  lines.push(`<strong>${fullName}</strong> — WR ${wrVal.toFixed(1)}% (${wr.games} matches), deck <strong>${wrStatus}</strong> in this scope.`);

  // Best and worst matchups
  const matrix = pd.matrix[deck];
  if (matrix) {
    const mus = Object.entries(matrix)
      .filter(([_,v]) => v.t >= 5)
      .map(([opp, v]) => ({ opp, wr: v.w/v.t*100, w: v.w, t: v.t }))
      .sort((a,b) => b.wr - a.wr);
    if (mus.length >= 2) {
      const best = mus[0];
      const worst = mus[mus.length - 1];
      lines.push(`Miglior matchup: <strong>vs ${DECK_NAMES[best.opp]||best.opp}</strong> (${best.wr.toFixed(0)}%, ${best.w}/${best.t}). Peggior matchup: <strong>vs ${DECK_NAMES[worst.opp]||worst.opp}</strong> (${worst.wr.toFixed(0)}%, ${worst.w}/${worst.t}).`);
    }
  }

  // OTP/OTD gap
  const otp = pd.otp_otd[deck];
  if (otp) {
    const gaps = Object.entries(otp)
      .filter(([_,v]) => v.otp_t >= 3 && v.otd_t >= 3)
      .map(([opp, v]) => ({
        opp,
        otpWr: v.otp_w/v.otp_t*100,
        otdWr: v.otd_w/v.otd_t*100,
        gap: v.otp_w/v.otp_t*100 - v.otd_w/v.otd_t*100
      }))
      .sort((a,b) => b.gap - a.gap);
    if (gaps.length > 0 && gaps[0].gap > 15) {
      const g = gaps[0];
      lines.push(`Attenzione al dado vs <strong>${DECK_NAMES[g.opp]||g.opp}</strong>: OTP ${g.otpWr.toFixed(0)}% vs OTD ${g.otdWr.toFixed(0)}% (gap ${g.gap.toFixed(0)}pp).`);
    }
  }

  // Trend
  const perimKey = getScopeContext().perimeter;
  const trend = (DATA.matchup_trend || {})[perimKey] || {};
  const deckTrend = trend[deck];
  if (deckTrend) {
    const improving = Object.entries(deckTrend).filter(([_,v]) => v.delta !== null && v.delta >= 5).map(([o,v]) => `${DECK_NAMES[o]||o} (+${v.delta.toFixed(0)}pp)`);
    const declining = Object.entries(deckTrend).filter(([_,v]) => v.delta !== null && v.delta <= -5).map(([o,v]) => `${DECK_NAMES[o]||o} (${v.delta.toFixed(0)}pp)`);
    if (improving.length) lines.push(`In miglioramento vs: ${improving.join(', ')}.`);
    if (declining.length) lines.push(`In calo vs: ${declining.join(', ')}.`);
  }

  // Tech trends
  const tornado = (DATA.tech_tornado || {})[perimKey] || {};
  const deckTech = tornado[deck];
  if (deckTech && deckTech.items.length > 0) {
    const topIn = deckTech.items.filter(i => i.type === 'in').slice(0, 2);
    const topOut = deckTech.items.filter(i => i.type === 'out').slice(0, 2);
    if (topIn.length) lines.push(`Tech emergenti: ${topIn.map(i => `<strong>${i.card}</strong> (${i.adoption}% adoption, ${i.avg_wr}% WR)`).join(', ')}.`);
    if (topOut.length) lines.push(`Cards dropping out: ${topOut.map(i => `<strong>${i.card}</strong> (${i.adoption}% cut it)`).join(', ')}.`);
  }

  el.innerHTML = `
    <div style="font-size:0.8em;color:var(--gold);text-transform:uppercase;margin-bottom:8px">Analisi — ${fullName}</div>
    <div style="font-size:0.88em;line-height:1.7">${lines.map(l => '<p style="margin:4px 0">' + l + '</p>').join('')}</div>
  `;
}

function renderMatchupTrend(deck) {
  const el = document.getElementById('deck-trend');
  const perimKey = getScopeContext().perimeter;
  const trend = (DATA.matchup_trend || {})[perimKey] || {};
  const deckTrend = trend[deck];
  if (!deckTrend || !Object.keys(deckTrend).length) {
    el.innerHTML = '';
    return;
  }

  // Sort by games desc
  const entries = Object.entries(deckTrend)
    .filter(([_, v]) => v.current_wr !== null)
    .sort((a, b) => b[1].recent_games - a[1].recent_games)
    .slice(0, 10);

  const cells = entries.map(([opp, v]) => {
    const wr = v.current_wr;
    const delta = v.delta;
    let arrow = '', deltaClass = '';
    if (delta !== null) {
      if (delta >= 3) { arrow = '▲'; deltaClass = 'wr-good'; }
      else if (delta <= -3) { arrow = '▼'; deltaClass = 'wr-bad'; }
      else { arrow = '='; deltaClass = 'wr-mid'; }
    }
    const wrBg = wr >= 55 ? 'rgba(63,185,80,0.15)' : wr <= 45 ? 'rgba(248,81,73,0.15)' : 'rgba(210,153,34,0.1)';
    const deltaStr = delta !== null ? `${delta > 0 ? '+' : ''}${delta}pp` : '';
    const oppFull = DECK_NAMES[opp] || opp;
    return `<div style="background:${wrBg};border-radius:6px;padding:6px 8px;text-align:center;min-width:90px">
      <div style="font-weight:600;font-size:0.75em;line-height:1.2">${oppFull}</div>
      <div style="font-size:1.1em;font-weight:700;${wr>=55?'color:var(--green)':wr<=45?'color:var(--red)':'color:var(--yellow)'}">${wr}%</div>
      <div class="${deltaClass}" style="font-size:0.8em">${arrow} ${deltaStr}</div>
      <div style="font-size:0.65em;color:var(--text2)">${v.recent_games}g</div>
    </div>`;
  }).join('');

  el.innerHTML = `
    <div class="card" style="padding:12px 16px">
      <div style="font-size:0.8em;color:var(--text2);text-transform:uppercase;margin-bottom:8px">Trend Matchup (ultimi 3gg vs 3gg precedenti)</div>
      <div style="display:flex;gap:6px;overflow-x:auto;padding-bottom:4px">${cells}</div>
    </div>`;
}

function renderMatchupChart(pd, deck) {
  const container = document.getElementById('chart-matchup');
  if (!container) return;
  const matrix = pd.matrix;
  if (!matrix[deck]) { container.innerHTML = ''; return; }

  const opps = Object.keys(matrix[deck]).sort((a,b) => {
    const wrA = matrix[deck][a].t > 0 ? matrix[deck][a].w / matrix[deck][a].t * 100 : 50;
    const wrB = matrix[deck][b].t > 0 ? matrix[deck][b].w / matrix[deck][b].t * 100 : 50;
    return wrB - wrA;
  }).filter(o => matrix[deck][o].t >= 3);

  // Track spans 30–70; wider range for matchups
  const minWR = 30, maxWR = 70, range = maxWR - minWR;

  function lpColor(wr) {
    if (wr >= 54) return 'green';
    if (wr <= 46) return 'red';
    return 'gray';
  }

  let html = '<div class="lollipop-chart">';
  opps.forEach(o => {
    const s   = matrix[deck][o];
    const wr  = parseFloat((s.w / s.t * 100).toFixed(1));
    const col = lpColor(wr);
    const clamp   = Math.max(minWR, Math.min(maxWR, wr));
    const dotPct  = ((clamp - minWR) / range * 100).toFixed(2);
    const midPct  = ((50   - minWR) / range * 100).toFixed(2);
    const stemLeft  = Math.min(parseFloat(dotPct), parseFloat(midPct)).toFixed(2);
    const stemWidth = Math.abs(parseFloat(dotPct) - parseFloat(midPct)).toFixed(2);
    const wrCls = wr >= 55 ? 'wr-good' : wr <= 45 ? 'wr-bad' : 'wr-mid';

    html += `<div class="lp-row">
      <span class="lp-label" title="${DECK_NAMES[o]||o}">${deckImg(o,28)}</span>
      <div class="lp-track">
        <div class="lp-ref"></div>
        <div class="lp-stem lp-stem-${col}" style="left:${stemLeft}%;width:${stemWidth}%"></div>
        <div class="lp-dot lp-${col}" style="left:${dotPct}%"></div>
      </div>
      <span class="lp-value ${wrCls}">${wr}% <span style="color:var(--text2);font-weight:400;font-size:0.85em">${s.w}/${s.t}</span></span>
    </div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

function renderOTPOTDChart(pd, deck) {
  const container = document.getElementById('chart-otpotd');
  if (!container) return;
  const otpData = pd.otp_otd;
  if (!otpData[deck]) { container.innerHTML = ''; return; }

  function getOTPGap(s) {
    const otp = s.otp_t >= 3 ? s.otp_w / s.otp_t * 100 : 50;
    const otd = s.otd_t >= 3 ? s.otd_w / s.otd_t * 100 : 50;
    return otp - otd;
  }

  const opps = Object.keys(otpData[deck]).filter(o => {
    const s = otpData[deck][o];
    return s.otp_t >= 3 || s.otd_t >= 3;
  }).sort((a,b) => getOTPGap(otpData[deck][b]) - getOTPGap(otpData[deck][a]));

  // Track spans 20–80
  const minWR = 20, maxWR = 80, range = maxWR - minWR;
  const midPctNum = (50 - minWR) / range * 100;

  function dotPct(wr) {
    const c = Math.max(minWR, Math.min(maxWR, wr));
    return ((c - minWR) / range * 100).toFixed(2);
  }

  // Legend
  let html = `<div style="display:flex;gap:16px;font-size:0.74em;color:var(--text2);margin-bottom:10px;align-items:center">
    <span style="display:flex;align-items:center;gap:5px"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#3FB950"></span> OTP</span>
    <span style="display:flex;align-items:center;gap:5px"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#8892F2"></span> OTD</span>
    <span style="margin-left:auto;font-size:0.9em">50% ref. line</span>
  </div>`;

  html += '<div style="display:flex;flex-direction:column;gap:4px">';
  opps.forEach(o => {
    const s = otpData[deck][o];
    const otpWR = s.otp_t >= 3 ? parseFloat((s.otp_w / s.otp_t * 100).toFixed(1)) : null;
    const otdWR = s.otd_t >= 3 ? parseFloat((s.otd_w / s.otd_t * 100).toFixed(1)) : null;
    const gap   = otpWR !== null && otdWR !== null ? (otpWR - otdWR).toFixed(0) : null;
    const gapColor = gap !== null
      ? (parseFloat(gap) >= 10 ? 'var(--yellow)' : parseFloat(gap) <= -10 ? 'var(--red)' : 'var(--text2)')
      : 'var(--text2)';

    // Connector line between the two dots (left = min of the two, width = difference)
    let lineLeft = '50', lineWidth = '0';
    if (otpWR !== null && otdWR !== null) {
      const p1 = parseFloat(dotPct(otpWR));
      const p2 = parseFloat(dotPct(otdWR));
      lineLeft  = Math.min(p1, p2).toFixed(2);
      lineWidth = Math.abs(p1 - p2).toFixed(2);
    }

    const otpValStr = otpWR !== null ? `OTP ${otpWR}%` : 'OTP —';
    const otdValStr = otdWR !== null ? `OTD ${otdWR}%` : 'OTD —';
    const gapStr    = gap !== null ? `<span style="color:${gapColor};font-size:0.78em">${gap > 0 ? '+' : ''}${gap}pp</span>` : '';

    html += `<div class="db-row">
      <span class="lp-label" title="${DECK_NAMES[o]||o}">${deckImg(o,28)}</span>
      <div class="db-track">
        <div class="db-ref"></div>
        <div class="db-line" style="left:${lineLeft}%;width:${lineWidth}%"></div>
        ${otpWR !== null ? `<div class="db-dot-otp" style="left:${dotPct(otpWR)}%"></div>` : ''}
        ${otdWR !== null ? `<div class="db-dot-otd" style="left:${dotPct(otdWR)}%"></div>` : ''}
      </div>
      <div class="db-vals">
        <span class="db-val db-val-otp">${otpValStr}</span>
        <span class="db-val db-val-otd">${otdValStr} ${gapStr}</span>
      </div>
    </div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

// === PLAYERS ===
function renderPlayers(pd, deck) {
  const container = document.getElementById('players-list');
  const scope = getScopeContext();
  // Filter: min 6 games for SET11, min 4 for TOP, min 2 for PRO
  const minG = scope.perimeter.includes('pro') ? 2 : (scope.perimeter.includes('top') ? 4 : 6);
  const players = (pd.top_players || []).filter(p => p.deck === deck && (p.w + p.l) >= minG);

  if (!players.length) {
    container.innerHTML = '<div class="card" style="color:var(--text2)">No qualified top player with this deck (min ' + minG + ' matches).</div>';
    return;
  }

  const medals = ['🥇','🥈','🥉'];
  container.innerHTML = players.slice(0, 8).map((p, i) => {
    const rank = i < 3 ? medals[i] : `${i+1}.`;
    const proTag = p.is_pro ? '<span class="pro-tag">PRO</span>' : '';
    const wrCl = wrClass(p.wr);
    const totalG = p.w + p.l;
    const deckChip = p.deck
      ? `<span style="display:inline-flex;align-items:center;gap:6px;color:var(--text2);font-size:0.78em;font-weight:500;margin-left:8px">${deckImg(p.deck,20)}<span>${p.deck}</span></span>`
      : '';

    // Matchup grid (colored cells)
    const muEntries = Object.entries(p.matchups || {}).sort((a,b) => (b[1].w+b[1].l) - (a[1].w+a[1].l));
    const muGrid = muEntries.slice(0, 10).map(([opp, r]) => {
      const t = r.w + r.l;
      const wr = t > 0 ? r.w / t * 100 : 50;
      const bg = wr >= 60 ? 'rgba(63,185,80,0.25)' : wr <= 40 ? 'rgba(248,81,73,0.25)' : 'rgba(210,153,34,0.15)';
      const border = wr >= 60 ? 'var(--green)' : wr <= 40 ? 'var(--red)' : 'var(--yellow)';
      return `<div class="mu-cell" style="background:${bg};border:1px solid ${border}">
        <div class="opp-name">${deckImg(opp,24)}</div>
        <div class="wl">${r.w}-${r.l}</div>
      </div>`;
    }).join('');

    // Deck comparison
    const deckCompareHtml = buildDeckCompare(p.name, deck, totalG);

    return `
      <div class="player-card" onclick="this.classList.toggle('open')">
        <div class="player-header">
          <span class="rank">${rank}</span>
          <span class="name">${p.name} ${proTag}${deckChip}</span>
          <div class="stats-mini">
            <span>${p.w}-${p.l}</span>
            <span class="wr-val ${wrCl}">${p.wr}%</span>
            <span style="color:var(--text2)">MMR ${p.mmr}</span>
          </div>
          <span class="arrow">▼</span>
        </div>
        <div class="player-detail">
          <div style="margin-top:10px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:0.8em;color:var(--text2)">
            <span style="display:inline-flex;align-items:center;gap:6px">
              <strong style="color:var(--text)">Main Deck:</strong>
              ${p.deck ? `${deckImg(p.deck,20)} <span>${p.deck}</span>` : '<span>Unknown</span>'}
            </span>
            <span><strong style="color:var(--text)">Observed:</strong> ${totalG} games</span>
          </div>
          <div style="margin-top:12px">
            <h4 style="font-size:0.8em;color:var(--text2);text-transform:uppercase;margin-bottom:6px">Matchup (${totalG} matches)</h4>
            <div class="mu-grid">${muGrid}</div>
          </div>
          ${scope.isCustomDeck && myDeckCards ? buildCustomCompare(p.name, deck, totalG) : deckCompareHtml}
        </div>
      </div>`;
  }).join('');
}

// Helper: build unified diff HTML from two card dicts
function buildUnifiedDiff(stdCards, playerCards, stdLabel, playerLabel, footerInfoHtml, stdCopyText, playerCopyText) {
  // Collect all unique card names
  const allCards = new Set([...Object.keys(stdCards), ...Object.keys(playerCards)]);
  const rows = [];

  allCards.forEach(card => {
    const sq = stdCards[card] || 0;
    const pq = playerCards[card] || 0;
    let type = 'same';
    if (sq === 0 && pq > 0) type = 'added';
    else if (sq > 0 && pq === 0) type = 'cut';
    else if (sq !== pq) type = 'changed';
    rows.push({ card, sq, pq, type });
  });

  // Sort: added first, then cut, then changed, then same — all alphabetical within group
  const order = { added: 0, cut: 1, changed: 2, same: 3 };
  rows.sort((a, b) => (order[a.type] - order[b.type]) || a.card.localeCompare(b.card));

  const nAdded   = rows.filter(r => r.type === 'added').length;
  const nCut     = rows.filter(r => r.type === 'cut').length;
  const nChanged = rows.filter(r => r.type === 'changed').length;
  const nSame    = rows.filter(r => r.type === 'same').length;

  const stdCopyId    = 'ddcopy-std-'    + Math.random().toString(36).slice(2,7);
  const playerCopyId = 'ddcopy-player-' + Math.random().toString(36).slice(2,7);

  // Hidden pre-elements for copy
  let html = `<div class="deck-diff">`;

  // Header bar
  html += `<div class="deck-diff-header">
    <span class="ddh-title">${stdLabel} <span style="color:var(--text2);font-weight:400">vs</span> ${playerLabel}</span>
    <span class="ddh-badge ddh-badge-common">${nSame} in comune</span>`;
  if (nAdded)   html += `<span class="ddh-badge ddh-badge-added">+${nAdded} aggiunte</span>`;
  if (nCut)     html += `<span class="ddh-badge ddh-badge-cut">−${nCut} tagliate</span>`;
  if (nChanged) html += `<span class="ddh-badge ddh-badge-changed">${nChanged} modificate</span>`;
  html += `</div>`;

  // Column headers
  html += `<div class="deck-diff-cols">
    <span>Carta</span>
    <span class="dc-std">Std</span>
    <span class="dc-player">Player</span>
    <span class="dc-delta">Δ</span>
  </div>`;

  // Card rows
  rows.forEach(r => {
    const delta = r.pq - r.sq;
    const deltaStr = delta === 0 ? '' : (delta > 0 ? `+${delta}` : `${delta}`);
    const deltaCls = delta > 0 ? 'pos' : delta < 0 ? 'neg' : '';
    const sqStr    = r.sq > 0 ? `${r.sq}x` : '—';
    const pqStr    = r.pq > 0 ? `${r.pq}x` : '—';
    html += `<div class="deck-diff-row ${r.type}">
      <span class="deck-diff-card">${r.card}</span>
      <span class="deck-diff-qty${r.sq > 0 ? ' present' : ''}">${sqStr}</span>
      <span class="deck-diff-qty${r.pq > 0 ? ' present' : ''}">${pqStr}</span>
      <span class="deck-diff-delta ${deltaCls}">${deltaStr}</span>
    </div>`;
  });

  // Footer
  html += `<div class="deck-diff-footer">
    <span class="ddf-info">${footerInfoHtml}</span>
    <div class="ddf-btns">
      <button class="deck-diff-copy-btn std" onclick="event.stopPropagation();copyTextToClipboard('${stdCopyId}',this,'Copied!')">Copy Consensus</button>
      <button class="deck-diff-copy-btn player" onclick="event.stopPropagation();copyTextToClipboard('${playerCopyId}',this,'Copied!')">Copy Player</button>
    </div>
  </div>`;

  // Hidden copy text
  html += `<textarea id="${stdCopyId}" style="position:absolute;left:-9999px;top:-9999px" readonly>${stdCopyText}</textarea>`;
  html += `<textarea id="${playerCopyId}" style="position:absolute;left:-9999px;top:-9999px" readonly>${playerCopyText}</textarea>`;
  html += `</div>`;
  return html;
}

function copyTextToClipboard(textareaId, btn, successMsg) {
  const ta = document.getElementById(textareaId);
  if (!ta) return;
  navigator.clipboard.writeText(ta.value).then(() => {
    const orig = btn.textContent;
    btn.textContent = successMsg || 'Copied!';
    setTimeout(() => btn.textContent = orig, 1600);
  }).catch(() => {
    ta.select(); document.execCommand('copy');
  });
}

function buildDeckCompare(playerName, deck, totalGames) {
  const consensus = DATA.consensus || {};
  const playerCards = getScopedPlayerCards();
  const refDecklists = DATA.reference_decklists || {};
  const std = consensus[deck];
  const pCards = (playerCards[playerName.toLowerCase()] || {})[deck];
  const refList = refDecklists[deck];
  const refDeck = Array.isArray(refList) ? refList[0] : refList;

  if (!pCards) return '';

  // Consensus decklist text
  let stdText = '';
  let refInfo = '';
  if (refDeck) {
    refInfo = `${refDeck.player} — ${refDeck.rank || '?'} @ ${(refDeck.event || '').substring(0, 45)}`;
    stdText = refDeck.cards.map(c => `${c.qty} ${c.name}`).join('\n');
  } else if (std) {
    stdText = Object.entries(std).sort((a,b) => b[1] - a[1]).map(([name, qty]) => `${Math.round(qty)} ${name}`).join('\n');
  } else {
    stdText = 'Consensus unavailable for this deck in the current snapshot.';
  }

  // Build estimated decklist from player_cards data.
  // player_cards = {card: n_games_seen} — cards played or inked across games.
  // We DON'T see cards drawn but not played. So play rate << deck inclusion rate.
  // observedGames = max card sightings (best proxy for how many games we captured)
  const observedGames = Object.values(pCards).length > 0 ? Math.max(...Object.values(pCards)) : 0;
  // Estimate qty with thresholds adapted to sample size (use observedGames, not totalGames).
  // Estimate card qty in deck from play frequency.
  // In Lorcana, you play/ink ~10-12 cards per game out of 60 in deck.
  // A 4x card has ~45% chance of appearing in any game (played or inked).
  // A 2x card has ~25%. A 1x has ~13%.
  // With few games, any card seen is probably in the deck — we just can't
  // know copies precisely. Default to consensus qty or 3x.
  function estQty(pSeen, total, stdQty) {
    const rate = total > 0 ? pSeen / total : 0;
    // If we have a consensus qty for this card, use it as baseline
    if (stdQty) return stdQty;
    // Hypergeometric MLE thresholds (60-card deck, ~20 cards seen, ~16 played per game)
    // P(≥1 copy played): 1x=27%, 2x=47%, 3x=61%, 4x=72%
    // Boundaries = midpoints: 37%, 54%, 67%
    if (total >= 8) {
      if (rate >= 0.67) return 4;
      if (rate >= 0.54) return 3;
      if (rate >= 0.37) return 2;
      return 1;
    } else {
      // Very few games: same thresholds but cap at 3x (insufficient data for 4x)
      if (rate >= 0.54) return 3;
      if (rate >= 0.37) return 2;
      return 1;
    }
  }

  const added = [], kept = [], cut = [];
  if (std) {
    for (const [card, qty] of Object.entries(std)) {
      const pSeen = pCards[card] || 0;
      if (pSeen === 0) {
        cut.push({ card, stdQty: Math.round(qty) });
      } else {
        const sq = Math.round(qty);
        kept.push({ card, stdQty: sq, pSeen, estQ: estQty(pSeen, observedGames, sq) });
      }
    }
  }
  for (const [card, pSeen] of Object.entries(pCards)) {
    if ((!std || !(card in std)) && pSeen >= 1) {
      added.push({ card, pSeen, estQ: estQty(pSeen, observedGames, 0) });
    }
  }
  kept.sort((a,b) => b.pSeen - a.pSeen);
  added.sort((a,b) => b.pSeen - a.pSeen);
  cut.sort((a,b) => b.stdQty - a.stdQty);

  // === Build 60-card estimated decklist ===
  // Step 1: start with kept (consensus cards seen) + added (non-consensus seen)
  const estDeckList = [];
  kept.forEach(c => estDeckList.push({ card: c.card, qty: c.estQ, source: 'kept', pSeen: c.pSeen }));
  added.forEach(c => estDeckList.push({ card: c.card, qty: c.estQ, source: 'added', pSeen: c.pSeen }));

  let deckTotal = estDeckList.reduce((s, c) => s + c.qty, 0);

  // Step 2: if under 60, fill with cut cards (consensus cards NOT seen — probably still in deck)
  if (deckTotal < 60 && cut.length > 0) {
    for (const c of cut) {
      if (deckTotal >= 60) break;
      const qty = Math.min(c.stdQty, 60 - deckTotal);
      estDeckList.push({ card: c.card, qty, source: 'assumed', pSeen: 0 });
      deckTotal += qty;
    }
  }

  // Step 3: if still under 60, pad remaining from consensus (increase qtys)
  if (deckTotal < 60) {
    const gap = 60 - deckTotal;
    const keptInDeck = estDeckList.filter(c => c.source === 'kept' && c.qty < 4);
    let remaining = gap;
    for (const c of keptInDeck) {
      if (remaining <= 0) break;
      const add = Math.min(4 - c.qty, remaining);
      c.qty += add;
      remaining -= add;
    }
    deckTotal = estDeckList.reduce((s, c) => s + c.qty, 0);
  }

  // Step 4: if over 60, trim lowest-frequency cards
  while (deckTotal > 60) {
    estDeckList.sort((a, b) => a.pSeen - b.pSeen || a.qty - b.qty);
    const target = estDeckList.find(c => c.qty > 0);
    if (!target) break;
    target.qty--;
    deckTotal--;
    if (target.qty === 0) estDeckList.splice(estDeckList.indexOf(target), 1);
  }

  // Sort for display: by source (kept, added, assumed) then name
  estDeckList.sort((a, b) => {
    const order = { kept: 0, added: 1, assumed: 2 };
    return (order[a.source] || 3) - (order[b.source] || 3) || a.card.localeCompare(b.card);
  });

  // Confidence: % of cards actually observed
  const observedCards = estDeckList.filter(c => c.pSeen > 0).reduce((s, c) => s + c.qty, 0);
  const confidence = Math.round(observedCards / 60 * 100);
  const confLabel = confidence >= 70 ? 'Alta' : confidence >= 40 ? 'Media' : 'Bassa';
  const confColor = confidence >= 70 ? 'var(--green)' : confidence >= 40 ? 'var(--yellow)' : 'var(--red)';

  // Build text for copy (clean format: "qty Name" — no markers, import-friendly)
  const estLines = estDeckList.map(c => `${c.qty} ${c.card}`);
  const estText = estLines.join('\n');

  // Build card dicts for unified diff
  const stdCardDict = {};
  if (refDeck) {
    refDeck.cards.forEach(c => { stdCardDict[c.name] = c.qty; });
  } else if (std) {
    Object.entries(std).forEach(([name, qty]) => { stdCardDict[name] = Math.round(qty); });
  }
  const estCardDict = {};
  estDeckList.forEach(c => { estCardDict[c.card] = c.qty; });

  const stdLabel = !std
    ? `<span style="color:var(--text2)">Consensus non disponibile</span>`
    : refInfo
      ? `<span style="color:var(--sapphire)">Consensus</span> <span style="color:var(--text2);font-weight:400;font-size:0.88em">(${refDeck.player || ''})</span>`
      : `<span style="color:var(--sapphire)">Consensus</span>`;
  const playerLabel = `<span style="color:var(--gold)">Stimata ${playerName}</span>`;

  const footerInfo  = `${observedGames}/${totalGames}g osservate · <span style="color:${confColor}">Confidenza ${confLabel} (${confidence}%)</span>  <span style="color:var(--text2);margin-left:6px">* tech · ? assunta</span>`;

  return buildUnifiedDiff(stdCardDict, estCardDict, stdLabel, playerLabel, footerInfo, stdText, estText);
}

function copyDeck(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const text = el.textContent.replace('Copia', '').trim();
  navigator.clipboard.writeText(text).then(() => {
    const btn = el.querySelector('.copy-btn');
    if (btn) { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copia', 1500); }
  });
}

// === MY DECK — Meta vs Personalizzato ===
let myDeckMode = 'standard'; // 'standard' or 'custom' — always starts standard
let myDeckCards = null; // {cardName: qty}

function loadMyDeck() {
  try {
    const raw = localStorage.getItem('lorcana_my_deck');
    if (raw) {
      myDeckCards = JSON.parse(raw);
      // Restore saved deckCode if available (avoids re-detection issues)
      const savedCode = localStorage.getItem('lorcana_deck_code');
      if (savedCode && DECK_INKS[savedCode]) {
        selectedDeck = savedCode;
        coachDeck = savedCode;
        selectedInks = [...DECK_INKS[savedCode]];
      }
    }
  } catch(e) { myDeckCards = null; }
}
loadMyDeck();

function onMyDeckToggle(checked) {
  if (checked) {
    if (!myDeckCards) { showDeckModal(); return; }
    myDeckMode = 'custom';
  } else {
    myDeckMode = 'standard';
  }
  rerenderPlayers();
}

function updateMyDeckUI() {
  // If deck was removed, force standard
  if (!myDeckCards) myDeckMode = 'standard';
  renderInkPickerBar();
}

function parseDecklist(text) {
  const cards = {};
  let total = 0;
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const m = trimmed.match(/^(\d+)\s+(.+?)(?:\s+\(\d+-\d+\))?$/);
    if (m) {
      const qty = parseInt(m[1]);
      const name = m[2].trim();
      cards[name] = (cards[name] || 0) + qty;
      total += qty;
    }
  }
  return { cards, total };
}

function validateDeck(cards) {
  // Returns {warnings[]} — warnings never block loading
  const warnings = [];
  const total = Object.values(cards).reduce((s,v) => s+v, 0);

  // 1. Count check (warning only — some formats allow 60+)
  if (total < 60) warnings.push(`Solo ${total} carte (consigliato 60)`);

  // 2. Max 4 copies (warning only)
  for (const [name, qty] of Object.entries(cards)) {
    if (qty > 4) warnings.push(`${name}: ${qty} copie (max 4)`);
  }

  // 3. Color check — card must appear in consensus or player_cards for selected deck
  if (selectedDeck) {
    const knownCards = new Set();
    const std = (DATA.consensus || {})[selectedDeck] || {};
    Object.keys(std).forEach(c => knownCards.add(c));
    const pc = getScopedPlayerCards();
    for (const pdata of Object.values(pc)) {
      const deckCards = pdata[selectedDeck];
      if (deckCards) Object.keys(deckCards).forEach(c => knownCards.add(c));
    }
    for (const perimKey of ['set11','top','pro']) {
      const tornado = ((DATA.tech_tornado || {})[perimKey] || {})[selectedDeck];
      if (tornado && tornado.items) tornado.items.forEach(i => knownCards.add(i.card));
    }
    const unknown = Object.keys(cards).filter(c => !knownCards.has(c));
    if (unknown.length > 0) {
      warnings.push(`${unknown.length} unrecognized cards for ${DECK_NAMES[selectedDeck] || selectedDeck}: ${unknown.slice(0,5).join(', ')}${unknown.length > 5 ? '...' : ''}`);
    }
  }

  return { warnings };
}

function saveMyDeck(cards, deckName, existingId) {
  myDeckCards = cards;
  myDeckMode = 'custom';
  localStorage.setItem('lorcana_my_deck', JSON.stringify(cards));
  // Auto-detect deck code
  autoDetectDeckInks(cards);
  const code = selectedDeck || '?';
  const user = (localStorage.getItem('pf_duels_nick') || 'guest').toLowerCase();
  const name = deckName || (code + ' ' + new Date().toISOString().slice(5, 10));
  if (existingId) {
    // Update existing deck on server
    fetch('/api/decks', { method: 'PUT', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ user, id: existingId, name, cards, deckCode: code })
    }).catch(() => {});
  } else {
    // Save new deck to server
    fetch('/api/decks', { method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ user, name, cards, deckCode: code })
    }).catch(() => {});
  }
}

function autoDetectDeckInks(cards) {
  const cardInks = DATA.card_inks || {};
  // Count ink occurrences weighted by qty
  const inkCounts = {};
  for (const [name, qty] of Object.entries(cards)) {
    const ink = cardInks[name];
    if (!ink || ink === 'inkless') continue;
    if (ink.includes('/')) {
      // Dual ink: "amethyst/sapphire" — count both colors
      for (const c of ink.split('/')) {
        const col = c.trim();
        if (col) inkCounts[col] = (inkCounts[col] || 0) + qty;
      }
    } else if (ink !== 'dual' && ink !== 'Dual Ink') {
      inkCounts[ink] = (inkCounts[ink] || 0) + qty;
    }
  }
  // Top 2 inks
  const sorted = Object.entries(inkCounts).sort((a, b) => b[1] - a[1]);
  if (sorted.length >= 2) {
    const ink1 = sorted[0][0]; // e.g. "amber"
    const ink2 = sorted[1][0];
    selectedInks = [ink1, ink2];
    // Resolve deck code
    const key = [ink1, ink2].sort().join('+');
    const deckCode = INK_PAIR_TO_DECK[key];
    if (deckCode) {
      selectedDeck = deckCode;
      coachDeck = deckCode;
      localStorage.setItem('lorcana_deck_code', deckCode);
      coachOpp = null;
      labOpp = null;
      oppSelectedInks = [];
    }
  }
}

function restoreMyDeckInks() {
  // Use stored deckCode (reliable) instead of re-detecting from card names
  const saved = localStorage.getItem('lorcana_deck_code');
  if (saved && DECK_INKS[saved]) {
    selectedDeck = saved;
    coachDeck = saved;
    selectedInks = [...DECK_INKS[saved]];
  } else if (myDeckCards) {
    autoDetectDeckInks(myDeckCards);
  }
}

function clearMyDeck() {
  myDeckCards = null;
  myDeckMode = 'standard';
  localStorage.removeItem('lorcana_my_deck');
  localStorage.removeItem('lorcana_deck_name');
  localStorage.removeItem('lorcana_deck_code');
  localStorage.removeItem('lorcana_deck_id');
}

async function showDeckHistory() {
  const existing = document.getElementById('deck-history-overlay');
  if (existing) { existing.remove(); return; }
  const user = (localStorage.getItem('pf_duels_nick') || 'guest').toLowerCase();
  let decks = [];
  try {
    const resp = await fetch('/api/decks?user=' + encodeURIComponent(user));
    const data = await resp.json();
    decks = data.decks || [];
    _serverDecksCache = decks; // Share cache with loadServerDeck
  } catch(e) {
    // Fallback: use cache or localStorage
    decks = _serverDecksCache.length ? _serverDecksCache : JSON.parse(localStorage.getItem('lorcana_deck_history') || '[]');
  }
  const overlay = document.createElement('div');
  overlay.className = 'deck-modal-overlay';
  overlay.id = 'deck-history-overlay';
  let listHtml = '';
  if (decks.length === 0) {
    listHtml = '<div style="color:var(--text2);text-align:center;padding:20px">No saved decks yet. Import one first.</div>';
  } else {
    decks.slice().reverse().forEach(h => {
      const isCurrent = myDeckCards && JSON.stringify(Object.entries(myDeckCards).sort()) === JSON.stringify(Object.entries(h.cards || {}).sort());
      listHtml += `<div class="pf-deck-hist-row${isCurrent ? ' active' : ''}">
        <div style="display:flex;align-items:center;gap:8px;flex:1;min-width:0;cursor:pointer" onclick="loadServerDeck('${h.id}')">
          ${h.deckCode ? deckImg(h.deckCode, 28) : ''}
          <div style="min-width:0">
            <div style="font-size:0.88em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${h.name || 'Unnamed'}</div>
            <div style="font-size:0.72em;color:var(--text2)">${h.updated || h.created || '?'} &middot; ${h.total || '?'} cards</div>
          </div>
        </div>
        ${isCurrent ? '<span style="font-size:0.72em;color:var(--gold);font-weight:600;flex-shrink:0">ACTIVE</span>' : ''}
        <button style="background:none;border:none;color:var(--gold);cursor:pointer;font-size:0.78em;padding:2px 6px;flex-shrink:0" onclick="event.stopPropagation();editServerDeck('${h.id}')" title="Edit">Edit</button>
        <button style="background:none;border:none;color:var(--text2);cursor:pointer;font-size:0.9em;padding:0 4px;flex-shrink:0" onclick="event.stopPropagation();deleteServerDeck('${h.id}')" title="Delete">&times;</button>
      </div>`;
    });
  }
  overlay.innerHTML = `<div class="deck-modal" onclick="event.stopPropagation()" style="max-width:420px">
    <h3>Saved Decks</h3>
    <div style="max-height:350px;overflow-y:auto">${listHtml}</div>
    <div class="btn-row" style="margin-top:12px">
      <button class="btn-load" onclick="document.getElementById('deck-history-overlay').remove();localStorage.removeItem('lorcana_deck_id');myDeckCards=null;showDeckModal()">+ New Deck</button>
      <button class="btn-cancel" onclick="document.getElementById('deck-history-overlay').remove()">Close</button>
    </div>
  </div>`;
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

// Store fetched decks for quick access
let _serverDecksCache = [];
async function _fetchUserDecks() {
  const user = (localStorage.getItem('pf_duels_nick') || 'guest').toLowerCase();
  try {
    const resp = await fetch('/api/decks?user=' + encodeURIComponent(user));
    const data = await resp.json();
    _serverDecksCache = data.decks || [];
  } catch(e) { _serverDecksCache = []; }
  return _serverDecksCache;
}

async function loadServerDeck(id) {
  const decks = _serverDecksCache.length ? _serverDecksCache : await _fetchUserDecks();
  const entry = decks.find(d => d.id === id);
  if (!entry) return;
  myDeckCards = entry.cards;
  myDeckMode = 'custom';
  localStorage.setItem('lorcana_my_deck', JSON.stringify(entry.cards));
  localStorage.setItem('lorcana_deck_name', entry.name || '');
  localStorage.setItem('lorcana_deck_id', entry.id);
  // Use stored deckCode if available (more reliable than re-detecting from card names)
  if (entry.deckCode && DECK_INKS[entry.deckCode]) {
    selectedDeck = entry.deckCode;
    coachDeck = entry.deckCode;
    selectedInks = [...DECK_INKS[entry.deckCode]];
    localStorage.setItem('lorcana_deck_code', entry.deckCode);
  } else {
    autoDetectDeckInks(entry.cards);
  }
  document.getElementById('deck-history-overlay')?.remove();
  render();
}

async function editServerDeck(id) {
  const decks = _serverDecksCache.length ? _serverDecksCache : await _fetchUserDecks();
  const entry = decks.find(d => d.id === id);
  if (!entry) return;
  document.getElementById('deck-history-overlay')?.remove();
  // Load deck into edit modal
  myDeckCards = entry.cards;
  localStorage.setItem('lorcana_my_deck', JSON.stringify(entry.cards));
  localStorage.setItem('lorcana_deck_name', entry.name || '');
  localStorage.setItem('lorcana_deck_id', entry.id);
  showDeckModal();
}

async function deleteServerDeck(id) {
  const user = (localStorage.getItem('pf_duels_nick') || 'guest').toLowerCase();
  await fetch('/api/decks?user=' + encodeURIComponent(user) + '&id=' + encodeURIComponent(id), { method: 'DELETE' });
  _serverDecksCache = _serverDecksCache.filter(d => d.id !== id);
  document.getElementById('deck-history-overlay')?.remove();
  showDeckHistory();
}

function showDeckModal() {
  const existing = document.getElementById('deck-modal-overlay');
  if (existing) existing.remove();

  const saved = myDeckCards ? Object.entries(myDeckCards).sort((a,b)=>a[0].localeCompare(b[0])).map(([c,q])=>`${q} ${c}`).join('\n') : '';
  const deckLabel = DECK_NAMES[selectedDeck] || selectedDeck || '?';

  const overlay = document.createElement('div');
  overlay.className = 'deck-modal-overlay';
  overlay.id = 'deck-modal-overlay';
  overlay.innerHTML = `
    <div class="deck-modal" onclick="event.stopPropagation()">
      <h3>Il Tuo Deck — ${deckLabel}</h3>
      <div class="pf-form-group" style="margin-bottom:8px">
        <label style="font-size:0.78em;color:var(--text2)">Deck name</label>
        <input type="text" class="ev-input" id="deck-name-input" placeholder="e.g. AbR aggro v2" value="${myDeckCards ? (localStorage.getItem('lorcana_deck_name') || '') : ''}" style="font-size:0.88em">
      </div>
      <div class="deck-status" id="deck-parse-status">${myDeckCards ? '<span class="ok">' + Object.values(myDeckCards).reduce((s,v)=>s+v,0) + ' cards loaded</span>' : 'Paste your decklist exported from duels.ink'}</div>
      <div id="deck-validation-msg"></div>
      <textarea id="deck-input" placeholder="2 Basil - Undercover Detective (8-86)&#10;4 Cinderella - Dream Come True (10-155)&#10;4 Clarabelle - Clumsy Guest (5-86)&#10;...">${saved}</textarea>
      <div class="btn-row">
        ${myDeckCards ? '<button class="btn-clear" onclick="clearMyDeck();closeDeckModal();updateMyDeckUI();rerenderPlayers()">Delete</button>' : ''}
        <button class="btn-cancel" onclick="closeDeckModal()">Cancel</button>
        <button class="btn-load" id="deck-load-btn" onclick="doLoadDeck()">${myDeckCards ? 'Update' : 'Load'}</button>
      </div>
    </div>`;

  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDeckModal(); });
  document.body.appendChild(overlay);

  const ta = document.getElementById('deck-input');
  const updateStatus = () => {
    const { cards, total } = parseDecklist(ta.value);
    const status = document.getElementById('deck-parse-status');
    const valMsg = document.getElementById('deck-validation-msg');
    const loadBtn = document.getElementById('deck-load-btn');
    if (total === 0) {
      status.innerHTML = 'Paste your decklist';
      valMsg.innerHTML = '';
      return;
    }
    const v = validateDeck(cards);
    status.innerHTML = '<span class="ok">' + total + ' cards</span>';
    const msgs = v.warnings.map(w => '<div style="color:var(--yellow);font-size:0.8em">&#9888; ' + w + '</div>');
    valMsg.innerHTML = msgs.join('');
  };
  ta.addEventListener('input', updateStatus);
  ta.addEventListener('paste', () => setTimeout(updateStatus, 50));
  updateStatus(); // validate on open
}

function closeDeckModal() {
  const m = document.getElementById('deck-modal-overlay');
  if (m) m.remove();
  updateMyDeckUI();
}

function doLoadDeck() {
  try {
    const ta = document.getElementById('deck-input');
    if (!ta) { closeDeckModal(); return; }
    const val = ta.value;
    const { cards, total } = parseDecklist(val);
    if (total < 1) {
      const valMsg = document.getElementById('deck-validation-msg');
      if (valMsg) valMsg.innerHTML = '<div style="color:var(--red);font-size:0.8em">No cards found</div>';
      return;
    }
    // Max 4x check (hard block)
    for (const [name, qty] of Object.entries(cards)) {
      if (qty > 4) {
        const valMsg = document.getElementById('deck-validation-msg');
        if (valMsg) valMsg.innerHTML = '<div style="color:var(--red);font-size:0.8em">' + name + ': ' + qty + ' copie (max 4)</div>';
        return;
      }
    }
    const deckNameEl = document.getElementById('deck-name-input');
    const deckName = deckNameEl ? deckNameEl.value.trim() : '';
    if (deckName) localStorage.setItem('lorcana_deck_name', deckName);
    const existingId = localStorage.getItem('lorcana_deck_id') || '';
    saveMyDeck(cards, deckName, existingId);
    // Force close modal
    const m = document.getElementById('deck-modal-overlay');
    if (m) m.remove();
    updateMyDeckUI();
    render(); // full re-render to update all tabs
  } catch(e) {
    console.error('doLoadDeck error:', e);
    const m = document.getElementById('deck-modal-overlay');
    if (m) m.remove();
  }
}

function rerenderPlayers() {
  const pd = getPerimData();
  if (pd && selectedDeck) renderPlayers(pd, selectedDeck);
}

function estimatePlayerDeck(playerName, deck, totalGames) {
  const playerCards = getScopedPlayerCards();
  const consensus = DATA.consensus || {};
  const pCards = (playerCards[playerName.toLowerCase()] || {})[deck];
  const std = consensus[deck];
  if (!pCards || !std) return null;

  const estDeck = {};
  for (const [card, qty] of Object.entries(std)) {
    const pSeen = pCards[card] || 0;
    const pPct = totalGames > 0 ? Math.round(pSeen / totalGames * 100) : 0;
    if (pPct >= 20) estDeck[card] = Math.round(qty);
  }
  for (const [card, pSeen] of Object.entries(pCards)) {
    if (!(card in std)) {
      const pPct = totalGames > 0 ? Math.round(pSeen / totalGames * 100) : 0;
      if (pPct >= 30) estDeck[card] = 4;
    }
  }
  return estDeck;
}

function buildCustomCompare(playerName, deck, totalGames) {
  // In custom mode: MY deck vs player's estimated — show unified diff
  if (!getScopeContext().isCustomDeck || !myDeckCards) return '';
  const estDeck = estimatePlayerDeck(playerName, deck, totalGames);
  if (!estDeck) return '';

  // If identical
  const allCards = new Set([...Object.keys(myDeckCards), ...Object.keys(estDeck)]);
  let hasDiff = false;
  for (const card of allCards) {
    if ((myDeckCards[card] || 0) !== (estDeck[card] || 0)) { hasDiff = true; break; }
  }
  if (!hasDiff) {
    return '<div style="margin-top:12px;font-size:0.85em;color:var(--green);text-align:center;padding:10px">Deck identical to yours!</div>';
  }

  const myTotal  = Object.values(myDeckCards).reduce((s,v) => s+v, 0);
  const myText   = Object.entries(myDeckCards).sort((a,b) => a[0].localeCompare(b[0])).map(([c,q]) => `${q} ${c}`).join('\n');
  const estText  = Object.entries(estDeck).sort((a,b) => a[0].localeCompare(b[0])).map(([c,q]) => `${q} ${c}`).join('\n');

  const myLabel     = `<span style="color:var(--sapphire)">Il Tuo Deck</span> <span style="color:var(--text2);font-weight:400;font-size:0.88em">(${myTotal} cards)</span>`;
  const playerLabel = `<span style="color:var(--gold)">Stimata ${playerName}</span>`;
  const footerInfo  = `${totalGames} matches analyzed`;

  return buildUnifiedDiff(myDeckCards, estDeck, myLabel, playerLabel, footerInfo, myText, estText);
}

// === TECH TORNADO CHART ===
function renderTechTornado() {
  if (charts.techTornado) charts.techTornado.destroy();
  const perimKey = getScopeContext().perimeter;
  const tornado = (DATA.tech_tornado || {})[perimKey] || {};
  const deckData = tornado[selectedDeck];
  const canvas = document.getElementById('chart-tech-tornado');
  const box = document.getElementById('tech-tornado-box');
  const title = document.getElementById('tech-tornado-title');

  if (!deckData || !deckData.items.length) {
    if (title) title.textContent = 'No tech data for ' + (DECK_NAMES[selectedDeck] || selectedDeck);
    canvas.style.display = 'none';
    return;
  }
  canvas.style.display = 'block';
  if (title) title.textContent = `${selectedDeck}: cards cut (←) vs added (→) — ${deckData.total_players} players analyzed`;

  // Separate IN and OUT, sort by adoption
  const ins = deckData.items.filter(i => i.type === 'in').sort((a,b) => b.adoption - a.adoption).slice(0, 4);
  const outs = deckData.items.filter(i => i.type === 'out').sort((a,b) => b.adoption - a.adoption).slice(0, 4);

  // Interleave: OUTs on top (negative), then INs below (positive)
  const labels = [...outs.map(o => o.card), ...ins.map(i => i.card)];
  const values = [...outs.map(o => -o.adoption), ...ins.map(i => i.adoption)];
  const wrColors = [...outs, ...ins].map(item => {
    if (item.avg_wr >= 55) return item.type === 'in' ? 'rgba(63,185,80,0.8)' : 'rgba(63,185,80,0.6)';
    if (item.avg_wr <= 48) return item.type === 'in' ? 'rgba(248,81,73,0.6)' : 'rgba(248,81,73,0.8)';
    return item.type === 'in' ? 'rgba(210,153,34,0.7)' : 'rgba(210,153,34,0.5)';
  });
  const borders = [...outs, ...ins].map(item =>
    item.type === 'in' ? '#3FB950' : '#F85149'
  );
  const allItems = [...outs, ...ins];

  charts.techTornado = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: wrColors,
        borderColor: borders,
        borderWidth: 2,
        borderRadius: 4,
        borderSkipped: false,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: {
            color: '#8B949E',
            callback: v => Math.abs(v) + '%'
          },
          title: { display: true, text: '← CUT (%)          ADD (%) →', color: '#8B949E' }
        },
        y: {
          ticks: {
            color: (ctx) => {
              const idx = ctx.index;
              return idx < outs.length ? '#F85149' : '#3FB950';
            },
            font: { size: 12 },
            autoSkip: false,
            maxRotation: 0
          },
          grid: { display: false }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: ctx => {
              const idx = ctx[0].dataIndex;
              const item = allItems[idx];
              return item.type === 'in' ? `+ ADD: ${item.card}` : `- CUT: ${item.card}`;
            },
            label: ctx => {
              const idx = ctx.dataIndex;
              const item = allItems[idx];
              return [
                ` ${item.players} player (${item.adoption}% adoption)`,
                ` WR media: ${item.avg_wr}%`,
                item.type === 'in' ? ' Card not in consensus deck' : ' Consensus card not played'
              ];
            }
          }
        }
      },
      onClick: (evt, elements) => {
        if (!elements.length) return;
        const idx = elements[0].index;
        const item = allItems[idx];
        if (!item || !rvCardsDB) return;
        const url = rvCardImgByName(item.card);
        if (!url) return;
        const ov = pfGetOrCreateOverlay();
        ov.querySelector('img').src = url;
        ov.classList.add('open');
      }
    }
  });
}
