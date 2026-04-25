// === INK COLORS ===
const INK_COLORS = {
  amber: '#D4943A', amethyst: '#7B3FA0', emerald: '#2A8F4E',
  ruby: '#C0392B', sapphire: '#2471A3', steel: '#6C7A89'
};
const DECK_INKS = {
  AmSa: ['amethyst','sapphire'], EmSa: ['emerald','sapphire'], AbS: ['amber','sapphire'],
  AmAm: ['amber','amethyst'], AbSt: ['amber','steel'], AbE: ['amber','emerald'],
  AmySt: ['amethyst','steel'], AmyE: ['amethyst','emerald'], AmyR: ['amethyst','ruby'],
  ER: ['emerald','ruby'], RS: ['ruby','sapphire'], RSt: ['ruby','steel'],
  SSt: ['sapphire','steel'], ESt: ['emerald','steel'], AbR: ['amber','ruby']
};

const DECK_NAMES = {
  AmSa: 'Amethyst / Sapphire', EmSa: 'Emerald / Sapphire', AbS: 'Amber / Sapphire',
  AmAm: 'Amber / Amethyst', AbSt: 'Amber / Steel', AbE: 'Amber / Emerald',
  AmySt: 'Amethyst / Steel', AmyE: 'Amethyst / Emerald', AmyR: 'Amethyst / Ruby',
  ER: 'Emerald / Ruby', RS: 'Ruby / Sapphire', RSt: 'Ruby / Steel',
  SSt: 'Sapphire / Steel', ESt: 'Emerald / Steel', AbR: 'Amber / Ruby'
};

function deckLabel(deck) {
  const inks = DECK_INKS[deck] || [];
  const dots = inks.map(i => `<span class="ink-dot" style="background:${INK_COLORS[i]};display:inline-block;width:10px;height:10px;border-radius:50%;vertical-align:middle"></span>`).join('');
  return `${dots} ${deck}`;
}
// Deck icon mapping (deck code → base filename without extension)
const DECK_PNG = {
  AmAm:'AMBER_AMETHYST', AbE:'AMBER_GREEN', AbR:'AMBER_RUBY',
  AbS:'AMBER_SAPPHIRE', AbSt:'AMBER_STEEL', AmyE:'AMETHYST_EMERALD',
  AmyR:'AMETHYST_RUBY', AmSa:'AMETHYST_SAPPHIRE', AmySt:'AMETHYST_STEEL',
  ER:'EMERALD_RUBY', EmSa:'EMERALD_SAPPHIRE', ESt:'EMERALD_STEEL',
  RS:'RUBY_SAPPHIRE', RSt:'RUBY_STEEL', SSt:'SAPPHIRE_STEEL'
};
// deckBadge — renders deck icon (PNG if available, fallback to SVG ink icons).
// size: 'sm' (inline row) | '' (default) | 'lg' (header)
function deckBadge(deck, size) {
  const inks = DECK_INKS[deck] || [];
  const cls = size === 'lg' ? 'ink-badge-lg' : size === 'sm' ? 'ink-badge-sm' : 'ink-badge';
  const png = DECK_PNG[deck];
  if (png) {
    const sz = size === 'lg' ? 38 : size === 'sm' ? 24 : 30;
    return `<span class="${cls}"><span class="ib-icons">${deckImg(deck,sz)}</span></span>`;
  }
  const icons = inks.map(i => INK_SVGS[i] || '').join('');
  return `<span class="${cls}"><span class="ib-icons">${icons}</span><span class="ib-code">${deck}</span></span>`;
}
function deckLabelText(deck) { return `${deck} (${DECK_NAMES[deck] || deck})`; }
function deckImg(deck, px) {
  const base = DECK_PNG[deck];
  const h = px || 24;
  const w = Math.round(h * 0.87); // aspect ratio 330:380
  if (base) return `<picture><source srcset="deck_icons/${base}.webp" type="image/webp"><img src="deck_icons/${base}.png" alt="${deck}" width="${w}" height="${h}" style="vertical-align:middle;object-fit:contain" title="${DECK_NAMES[deck]||deck}" loading="lazy" data-deck="${deck}" data-sz="${h}" onerror="deckImgErr(this)"></picture>`;
  const inks = DECK_INKS[deck] || [];
  const dotSz = Math.max(8, Math.round(h * 0.45));
  return inks.map(i => `<span style="display:inline-block;width:${dotSz}px;height:${dotSz}px;border-radius:50%;background:${INK_COLORS[i]};vertical-align:middle"></span>`).join('') + ` <span style="font-size:0.8em">${deck}</span>`;
}
function deckImgErr(img) {
  const deck = img.dataset.deck;
  const h = parseInt(img.dataset.sz) || 24;
  const inks = DECK_INKS[deck] || [];
  const dotSz = Math.max(8, Math.round(h * 0.45));
  const dots = inks.map(i => {
    const s = document.createElement('span');
    s.style.cssText = 'display:inline-block;width:'+dotSz+'px;height:'+dotSz+'px;border-radius:50%;background:'+INK_COLORS[i]+';vertical-align:middle';
    return s;
  });
  const pic = img.closest('picture');
  if (pic) { pic.replaceWith(...dots); }
}
function deckGradient(deck) {
  const inks = DECK_INKS[deck] || ['steel','steel'];
  return `linear-gradient(135deg, ${INK_COLORS[inks[0]]}, ${INK_COLORS[inks[1]]})`;
}
function deckColor(deck, idx=0) {
  const inks = DECK_INKS[deck] || ['steel'];
  return INK_COLORS[inks[idx] || inks[0]];
}
function wrClass(wr) {
  if (wr >= 55) return 'wr-good';
  if (wr <= 45) return 'wr-bad';
  return 'wr-mid';
}
function wrColor(wr) {
  if (wr >= 55) return '#3FB950';
  if (wr <= 45) return '#F85149';
  return '#D29922';
}

// === TAB SWITCH HELPER ===
const TAB_ALIASES = {
  profile: 'home',
  home: 'home',
  monitor: 'meta',
  meta: 'meta',
  coach: 'play',
  coach_v2: 'play',
  play: 'play',
  lab: 'deck',
  deck: 'deck',
  improve: 'improve',
  team: 'team',
  pro_tools: 'team',
  community: 'events',
  events: 'events',
};

function normalizeTabId(tabId) {
  return TAB_ALIASES[tabId] || tabId;
}

function switchToTab(tabId, opts) {
  const normalizedTabId = normalizeTabId(tabId);
  currentTab = normalizedTabId;
  if (opts && opts.deck) { selectedDeck = opts.deck; coachDeck = opts.deck; }
  if (opts && opts.opp) { coachOpp = opts.opp; labOpp = opts.opp; }
  document.body.dataset.activeTab = normalizedTabId;
  document.querySelectorAll('.tab').forEach(t => {
    const isActive = t.dataset.tab === normalizedTabId;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
    t.setAttribute('tabindex', isActive ? '0' : '-1');
  });
  document.querySelectorAll('.bnav-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === normalizedTabId));
  window.scrollTo({ top: 0, behavior: 'smooth' });
  render();
}

// === INK DEFINITIONS WITH SVG ICONS ===
// Stylized Lorcana ink symbols as inline SVGs
const INK_SVGS = {
  amber: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2L15.5 8.5L22 12L15.5 15.5L12 22L8.5 15.5L2 12L8.5 8.5Z" fill="#D4943A"/><circle cx="12" cy="12" r="3.5" fill="#F0C060" opacity="0.6"/></svg>`,
  amethyst: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 1L17 7L20 12L17 17L12 23L7 17L4 12L7 7Z" fill="#7B3FA0"/><path d="M12 5L15 9L17 12L15 15L12 19L9 15L7 12L9 9Z" fill="#A060D0" opacity="0.5"/></svg>`,
  emerald: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2C12 2 6 8 6 14C6 17.3 8.7 20 12 20C15.3 20 18 17.3 18 14C18 8 12 2 12 2Z" fill="#2A8F4E"/><path d="M12 7C12 7 9 11 9 14.5C9 16.2 10.3 17.5 12 17.5C13.7 17.5 15 16.2 15 14.5C15 11 12 7 12 7Z" fill="#50C070" opacity="0.5"/></svg>`,
  ruby: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2L14.5 5H19L21 9L12 22L3 9L5 5H9.5Z" fill="#C0392B"/><path d="M12 6L13.5 8H16L17 10L12 18L7 10L8 8H10.5Z" fill="#E05040" opacity="0.5"/></svg>`,
  sapphire: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2C12 2 4 7 4 13C4 17.4 7.6 21 12 21C16.4 21 20 17.4 20 13C20 7 12 2 12 2Z" fill="#2471A3"/><path d="M9 11C9 11 8 13 9.5 15C11 17 13 17 14.5 15C16 13 15 11 15 11" stroke="#60B0E0" stroke-width="1.5" fill="none" opacity="0.6"/><circle cx="11" cy="10" r="1.5" fill="#60B0E0" opacity="0.4"/></svg>`,
  steel: `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" fill="#6C7A89"/><circle cx="12" cy="12" r="5.5" fill="none" stroke="#9AA5B0" stroke-width="1.5" opacity="0.6"/><circle cx="12" cy="12" r="2" fill="#9AA5B0" opacity="0.5"/><path d="M12 3V7M12 17V21M3 12H7M17 12H21" stroke="#9AA5B0" stroke-width="1" opacity="0.3"/></svg>`,
};
const INK_LIST = [
  { id: 'amber', label: 'Amber', color: '#D4943A' },
  { id: 'amethyst', label: 'Amethyst', color: '#7B3FA0' },
  { id: 'emerald', label: 'Emerald', color: '#2A8F4E' },
  { id: 'ruby', label: 'Ruby', color: '#C0392B' },
  { id: 'sapphire', label: 'Sapphire', color: '#2471A3' },
  { id: 'steel', label: 'Steel', color: '#6C7A89' },
];

// Reverse lookup: sorted ink pair → deck code
const INK_PAIR_TO_DECK = {};
for (const [code, inks] of Object.entries(DECK_INKS)) {
  const key = [...inks].sort().join('+');
  INK_PAIR_TO_DECK[key] = code;
}

// === FORMAT → PERIMETER MAPPING ===
const FORMAT_PERIMS = {
  core: [
    { id: 'set11', label: 'SET11 High ELO' },
    { id: 'top', label: 'TOP' },
    { id: 'pro', label: 'PRO' },
    { id: 'friends_core', label: 'Friends' },
    { id: 'community', label: 'Community' },
  ],
  infinity: [
    { id: 'infinity', label: 'Infinity' },
    { id: 'infinity_top', label: 'TOP' },
    { id: 'infinity_pro', label: 'PRO' },
    { id: 'infinity_friends', label: 'Friends' },
  ],
};

// === STATE ===
let DATA = null;
let currentFormat = localStorage.getItem('lorcana_format') || 'core';
let currentPerim = 'set11';
let currentTab = 'home';
// Restore deck from Profile pins on startup
let _savedPins = JSON.parse(localStorage.getItem('pf_deck_pins') || '[]');
let selectedDeck = 'EmSa';
let selectedInks = selectedDeck && DECK_INKS[selectedDeck] ? [...DECK_INKS[selectedDeck]] : [];
let oppSelectedInks = []; // opponent ink selection for coach/lab
let coachDeck = selectedDeck || 'EmSa';
let coachOpp = null;
let labOpp = null;
let PRO_UNLOCKED = true;
let charts = {};
let cv2SecTab = 'killer_cards'; // secondary tab in coach v2
let labBaseMode = 'standard'; // 'standard' or 'personal'

function getScopeContext() {
  const format = currentFormat === 'infinity' ? 'infinity' : 'core';
  const isCustomDeck = myDeckMode === 'custom' && !!myDeckCards;
  const perims = FORMAT_PERIMS[format] || FORMAT_PERIMS.core;
  const primaryPerimeter = format === 'infinity' ? 'infinity' : 'set11';
  const effectivePerimeter = perims.some(p => p.id === currentPerim) ? currentPerim : primaryPerimeter;
  return {
    format,
    perimeter: effectivePerimeter,
    primaryPerimeter,
    availablePerimeters: perims,
    isInfinity: format === 'infinity',
    isCustomDeck,
    deckMode: isCustomDeck ? 'custom' : 'meta',
  };
}

function getScopedPlayerCards() {
  const scope = getScopeContext();
  return scope.isInfinity ? (DATA.player_cards_infinity || {}) : (DATA.player_cards || {});
}

// === LOAD DATA ===
// /*__INLINE_DATA__*/
// === LOAD DATA (from API, no embedded blob) ===
async function loadData() {
  try {
    const resp = await fetch('/api/v1/dashboard-data');
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    DATA = await resp.json();
  } catch(e) {
    console.error('Failed to load dashboard data:', e);
    document.getElementById('main-content').innerHTML =
      '<div class="card" style="text-align:center;padding:40px"><h2>Loading error</h2><p>Could not fetch dashboard data from API. Please try again later.</p></div>';
    return;
  }
  fetchEditorialItems(); // pre-fetch news ticker (async, non-blocking)
  initKPI();
  initFormat();
  render();
}

function initFormat() {
  // Check if infinity data exists, disable button if not
  const hasInfinity = FORMAT_PERIMS.infinity.some(p => hasPerimData(p.id));
  const infBtn = document.querySelector('.format-btn[data-format="infinity"]');
  if (infBtn && !hasInfinity) {
    infBtn.disabled = true;
    infBtn.title = 'Dati in arrivo';
    // Force core if infinity was saved but has no data
    if (currentFormat === 'infinity') currentFormat = 'core';
  }

  // Apply saved format
  setFormat(currentFormat);
}

function initKPI() {
  const scope = getScopeContext();
  const m = DATA.meta;
  const g = m.games || {};
  const rangeLabel = m.period_range || m.period;
  let kpis = `<div class="kpi"><div class="value">${m.period}</div><div class="label">${rangeLabel}</div></div>`;

  if (scope.isInfinity) {
    kpis += `<div class="kpi"><div class="value">${(g.infinity||0).toLocaleString()}</div><div class="label">Infinity</div></div>`;
    kpis += `<div class="kpi"><div class="value">${(g.infinity_top||0).toLocaleString()}</div><div class="label">TOP</div></div>`;
    kpis += `<div class="kpi"><div class="value">${(g.infinity_pro||0).toLocaleString()}</div><div class="label">PRO</div></div>`;
  } else {
    kpis += `<div class="kpi"><div class="value">${(g.set11||0).toLocaleString()}</div><div class="label">SET11</div></div>`;
    kpis += `<div class="kpi"><div class="value">${(g.top||0).toLocaleString()}</div><div class="label">TOP</div></div>`;
    kpis += `<div class="kpi"><div class="value">${(g.pro||0).toLocaleString()}</div><div class="label">PRO</div></div>`;
  }
  kpis += `<div class="kpi"><div class="value">${m.updated}</div><div class="label">Last update</div></div>`;

  // KC Spy health badge — distinguishes canary flake (LLM JSON glitch) from
  // real data rot. Badge reflects what the user actually sees: if the stored
  // killer_curves files are clean, a canary JSON error is a WARN, not a FAIL.
  const spy = DATA.kc_spy;
  if (spy) {
    const rawStatus = spy.status;
    const vAfter = spy.validation_after_fix || spy.validation || {};
    const failCount = vAfter.files_fail || 0;
    const okCount = (vAfter.files_ok || 0) + (vAfter.files_warn || 0);
    const dataHealthy = failCount === 0 && okCount > 0;

    let effective = rawStatus;
    let note = '';
    if (rawStatus === 'FAIL' && dataHealthy) {
      effective = 'WARN';
      note = ' (canary flake, stored data OK)';
    }

    const color = effective === 'OK' ? 'var(--green)' : effective === 'WARN' ? 'var(--yellow)' : 'var(--red)';
    const icon = effective === 'OK' ? '✓' : effective === 'WARN' ? '⚠' : '✗';
    const detail = failCount > 0 ? `${failCount} fail` : `${okCount} files OK`;
    const tooltip = `KC Spy ${spy.date}: canary ${rawStatus}, ${detail}${note}`;
    kpis += `<div class="kpi" title="${tooltip}" style="cursor:help"><div class="value" style="color:${color}">${icon}</div><div class="label">KC Health</div></div>`;
  }

  document.getElementById('kpi-bar').innerHTML = kpis;
  // Hide lock icons when PRO is unlocked
  if (PRO_UNLOCKED) {
    document.querySelectorAll('.lock-icon').forEach(l => l.style.display = 'none');
  }
}

function getPerimData() {
  return DATA.perimeters[getScopeContext().perimeter] || null;
}

// Check if a perimeter has data
function hasPerimData(perimId) {
  const pd = DATA.perimeters[perimId];
  return pd && pd.wr && Object.keys(pd.wr).length > 0;
}

// Sync perimeter buttons to current format
function syncPerimButtons() {
  const bar = document.querySelector('.perimeter-bar');
  const scope = getScopeContext();
  const perims = scope.availablePerimeters;

  // Rebuild perimeter buttons
  let html = '<span class="label">Scope:</span>';
  perims.forEach((p, i) => {
    const active = p.id === currentPerim ? ' active' : '';
    const disabled = !hasPerimData(p.id);
    html += `<button class="perim-btn${active}" data-perim="${p.id}" ${disabled ? 'disabled style="opacity:0.4;cursor:not-allowed"' : ''}>${p.label}</button>`;
  });
  html += '<span class="perim-info" id="perim-info"></span>';
  bar.innerHTML = html;

  // Re-attach events
  bar.querySelectorAll('.perim-btn:not([disabled])').forEach(btn => {
    btn.addEventListener('click', () => {
      bar.querySelectorAll('.perim-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPerim = btn.dataset.perim;
      // Keep deck selection if it has data in new perimeter
      const newPd = getPerimData();
      if (!selectedDeck || !newPd || !newPd.wr[selectedDeck]) {
        selectedDeck = null;
        selectedInks = [];
      }
      render();
    });
  });
}

// Switch format
function setFormat(fmt) {
  currentFormat = fmt;
  localStorage.setItem('lorcana_format', fmt);

  // Update format buttons
  document.querySelectorAll('.format-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.format === fmt);
  });

  // Update format badge
  const badge = document.getElementById('format-badge');
  if (fmt === 'infinity') {
    badge.style.display = '';
    badge.textContent = 'INFINITY';
    badge.style.background = 'rgba(42,143,78,0.2)';
    badge.style.color = 'var(--emerald)';
  } else {
    badge.style.display = 'none';
  }

  // Default perimeter for format
  const perims = FORMAT_PERIMS[fmt];
  const firstAvailable = perims.find(p => hasPerimData(p.id));
  currentPerim = firstAvailable ? firstAvailable.id : perims[0].id;
  // Keep deck selection if valid in new format
  const newPd = getPerimData();
  if (!selectedDeck || !newPd || !newPd.wr[selectedDeck]) {
    selectedDeck = null;
    selectedInks = [];
  }

  syncPerimButtons();
  initKPI();
  render();
}

// Profile format toggle helpers
function pfToggleFormat() {
  pfSetFormat(getScopeContext().isInfinity ? 'core' : 'infinity');
}
function pfSetFormat(fmt) {
  setFormat(fmt);  // reuses existing global format switch + render
}

// Build ink picker HTML (compact, for format bar)
function buildInkPickerBar() {
  const scope = getScopeContext();
  const pd = getPerimData();
  const decks = pd ? Object.keys(pd.wr) : [];
  const frozen = scope.isCustomDeck;

  let html = '<span class="ip-label">Deck:</span>';

  INK_LIST.forEach(ink => {
    const isSelected = selectedInks.includes(ink.id);
    const cls = isSelected ? ' selected' : '';
    const frozenStyle = frozen && !isSelected ? 'opacity:0.25;pointer-events:none;' : frozen && isSelected ? 'pointer-events:none;' : '';
    html += `<div class="ink-icon-wrap${cls}" ${frozen ? '' : 'onclick="toggleInk(\'' + ink.id + '\')"'} title="${ink.label}" style="${frozenStyle}">
      ${INK_SVGS[ink.id]}
    </div>`;
  });

  // Result: show deck name if 2 selected
  if (selectedInks.length === 2) {
    const key = [...selectedInks].sort().join('+');
    const deckCode = INK_PAIR_TO_DECK[key];
    if (deckCode) {
      const inks = DECK_INKS[deckCode];
      const dots = inks.map(i => `<span class="ink-dot-sm" style="background:${INK_COLORS[i]}"></span>`).join('');
      const hasData = decks.includes(deckCode);
      html += `<div class="ink-deck-result">${dots} <span class="idr-name">${deckCode}</span>`;
      if (frozen) html += ` <span style="font-size:0.7em;color:var(--gold)">&#128274;</span>`;
      else if (!hasData) html += ` <span class="idr-warn">&#9888;</span>`;
      html += `</div>`;
    } else {
      html += `<div class="ink-deck-result"><span class="idr-warn">?</span></div>`;
    }
  } else if (selectedInks.length === 1) {
    html += `<div class="ink-deck-result" style="opacity:0.5"><span style="color:var(--text2);font-size:0.8em">+1</span></div>`;
  }

  return html;
}

function renderInkPickerBar() {
  const bar = document.getElementById('ink-picker-bar');
  if (bar) bar.innerHTML = buildInkPickerBar();
}

function buildMyDeckChip() {
  const hasDeck = !!myDeckCards;
  let html = '<div class="mydeck-chip">';

  // Switch always visible
  html += `<div class="lab-base-seg" style="margin:0">
    <button class="lab-base-btn${!getScopeContext().isCustomDeck || !hasDeck ?' active':''}" style="padding:5px 14px;font-size:0.8em" onclick="event.stopPropagation();myDeckMode='standard';render()">Meta Deck</button>
    <button class="lab-base-btn${getScopeContext().isCustomDeck && hasDeck ?' active':''}" style="padding:5px 14px;font-size:0.8em" ${!hasDeck?'disabled':''}
      onclick="event.stopPropagation();myDeckMode='custom';restoreMyDeckInks();render()">Mio Deck</button>
  </div>`;

  if (hasDeck) {
    const total = Object.values(myDeckCards).reduce((s,v) => s+v, 0);
    const isActive = getScopeContext().isCustomDeck;
    const badgeStyle = isActive
      ? 'background:rgba(212,160,58,0.2);border:1px solid var(--gold);color:var(--gold);font-weight:700'
      : 'background:var(--bg3);border:1px solid var(--border);color:var(--text2)';
    html += `<span style="font-size:0.78em;padding:3px 10px;border-radius:10px;${badgeStyle}">${total} cards</span>`;
    html += `<span style="cursor:pointer;font-size:0.85em;color:var(--gold)" onclick="event.stopPropagation();showDeckModal()" title="Edit deck">&#9998;</span>`;
    html += `<span style="cursor:pointer;color:var(--text2);font-size:0.95em" onclick="event.stopPropagation();clearMyDeckAndRender()" title="Remove deck">&times;</span>`;
  } else {
    html += `<button class="mydeck-btn-upload" onclick="event.stopPropagation();showDeckModal()">+ <span>Upload</span></button>`;
  }

  html += '</div>';
  return html;
}

function clearMyDeckAndRender() {
  clearMyDeck();
  render();
}

// === PENTAGON RADAR COMPONENT ===
function countCardTypes(cardDict) {
  const types = DATA.card_types || {};
  const counts = { character: 0, action: 0, song: 0, item: 0, location: 0 };
  for (const [name, qty] of Object.entries(cardDict)) {
    const t = types[name] || 'other';
    if (counts[t] !== undefined) counts[t] += qty;
  }
  return counts;
}

function buildPentagonSVG(countsA, countsB, radius, labelA, labelB) {
  var axes = [
    { key: 'character', label: 'Characters' },
    { key: 'action', label: 'Actions' },
    { key: 'location', label: 'Locations' },
    { key: 'item', label: 'Items' },
    { key: 'song', label: 'Songs' },
  ];
  var n = axes.length;
  var margin = 45;
  var cx = radius + margin;
  var cy = radius + margin - 5;
  var size = (radius + margin) * 2;
  var totalH = size + 30;

  var maxVals = axes.map(function(a) { return Math.max(countsA[a.key] || 0, countsB[a.key] || 0, 1); });

  function getPoints(counts, r) {
    return axes.map(function(a, i) {
      var angle = (-90 + (360 / n) * i) * Math.PI / 180;
      var val = Math.max((counts[a.key] || 0) / maxVals[i], 0.05);
      return (cx + r * val * Math.cos(angle)).toFixed(1) + ',' + (cy + r * val * Math.sin(angle)).toFixed(1);
    }).join(' ');
  }

  var svg = '<svg viewBox="0 0 ' + size + ' ' + totalH + '" width="' + size + '" height="' + totalH + '" xmlns="http://www.w3.org/2000/svg" style="display:block">';

  // Grid
  for (var level = 0.25; level <= 1; level += 0.25) {
    var pts = axes.map(function(_, i) {
      var angle = (-90 + (360 / n) * i) * Math.PI / 180;
      return (cx + radius * level * Math.cos(angle)).toFixed(1) + ',' + (cy + radius * level * Math.sin(angle)).toFixed(1);
    }).join(' ');
    svg += '<polygon points="' + pts + '" fill="none" stroke="#30363D" stroke-width="0.5"/>';
  }
  // Axis lines
  axes.forEach(function(_, i) {
    var angle = (-90 + (360 / n) * i) * Math.PI / 180;
    var x = cx + radius * Math.cos(angle);
    var y = cy + radius * Math.sin(angle);
    svg += '<line x1="' + cx + '" y1="' + cy + '" x2="' + x.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="#30363D" stroke-width="0.5"/>';
  });

  // Data polygons
  svg += '<polygon points="' + getPoints(countsB, radius) + '" fill="rgba(36,113,163,0.2)" stroke="#2471A3" stroke-width="1.5"/>';
  svg += '<polygon points="' + getPoints(countsA, radius) + '" fill="rgba(212,160,58,0.2)" stroke="#D4A03A" stroke-width="1.5"/>';

  // Labels + values
  axes.forEach(function(a, i) {
    var angle = (-90 + (360 / n) * i) * Math.PI / 180;
    var lr = radius + 22;
    var lx = cx + lr * Math.cos(angle);
    var ly = cy + lr * Math.sin(angle);
    var anchor = Math.abs(Math.cos(angle)) < 0.1 ? 'middle' : Math.cos(angle) > 0 ? 'start' : 'end';
    svg += '<text x="' + lx.toFixed(1) + '" y="' + (ly + 3).toFixed(1) + '" fill="#8B949E" font-size="11" font-weight="500" text-anchor="' + anchor + '">' + a.label + '</text>';
    var valA = countsA[a.key] || 0;
    var valB = countsB[a.key] || 0;
    svg += '<text x="' + lx.toFixed(1) + '" y="' + (ly + 16).toFixed(1) + '" fill="#D4A03A" font-size="11" font-weight="700" text-anchor="' + anchor + '">' + valA + '</text>';
    svg += '<text x="' + lx.toFixed(1) + '" y="' + (ly + 27).toFixed(1) + '" fill="#2471A3" font-size="10" text-anchor="' + anchor + '">' + valB + '</text>';
  });

  // Legend
  var legendY = cy + radius + 35;
  svg += '<circle cx="' + (cx - 50) + '" cy="' + legendY + '" r="5" fill="#D4A03A"/>';
  svg += '<text x="' + (cx - 42) + '" y="' + (legendY + 4) + '" fill="#D4A03A" font-size="11" font-weight="600">' + (labelA || 'Mio') + '</text>';
  svg += '<circle cx="' + (cx + 10) + '" cy="' + legendY + '" r="5" fill="#2471A3"/>';
  svg += '<text x="' + (cx + 18) + '" y="' + (legendY + 4) + '" fill="#2471A3" font-size="11" font-weight="600">' + (labelB || 'Consensus') + '</text>';

  svg += '</svg>';
  return svg;
}

// Build compact bar comparison for myDeck vs consensus
function buildDeckCompareChart(deckCode) {
  if (!myDeckCards || !DATA.card_types) return '';
  const consensus = DATA.consensus ? DATA.consensus[deckCode] : null;
  if (!consensus) return '';

  const stdCards = {};
  for (const [name, qty] of Object.entries(consensus)) {
    stdCards[name] = Math.round(qty);
  }

  const myCounts = countCardTypes(myDeckCards);
  const stdCounts = countCardTypes(stdCards);

  const axes = [
    { key: 'character', label: 'Char' },
    { key: 'action', label: 'Action' },
    { key: 'song', label: 'Song' },
    { key: 'item', label: 'Item' },
    { key: 'location', label: 'Loc' },
  ];

  const maxVal = Math.max(...axes.map(a => Math.max(myCounts[a.key]||0, stdCounts[a.key]||0)), 1);

  let html = '<div style="display:flex;flex-direction:column;gap:4px;width:100%">';
  // Legend
  html += '<div style="display:flex;gap:12px;font-size:0.7em;margin-bottom:2px"><span style="color:var(--gold)">&#9632; Mio</span><span style="color:var(--sapphire)">&#9632; Consensus</span></div>';

  axes.forEach(a => {
    const my = myCounts[a.key] || 0;
    const std = stdCounts[a.key] || 0;
    const myPct = (my / maxVal * 100).toFixed(0);
    const stdPct = (std / maxVal * 100).toFixed(0);
    const diff = my - std;
    const diffStr = diff > 0 ? `<span style="color:var(--green)">+${diff}</span>` : diff < 0 ? `<span style="color:var(--red)">${diff}</span>` : '';

    html += `<div style="display:flex;align-items:center;gap:6px;font-size:0.75em">
      <span style="min-width:38px;color:var(--text2);text-align:right">${a.label}</span>
      <div style="flex:1;display:flex;flex-direction:column;gap:1px">
        <div style="height:6px;border-radius:3px;background:var(--gold);width:${myPct}%;min-width:2px"></div>
        <div style="height:6px;border-radius:3px;background:var(--sapphire);width:${stdPct}%;min-width:2px;opacity:0.7"></div>
      </div>
      <span style="min-width:28px;font-size:0.9em;color:var(--gold);font-weight:600">${my}</span>
      <span style="min-width:22px;font-size:0.85em;color:var(--text2)">${std}</span>
      <span style="min-width:20px;font-size:0.85em">${diffStr}</span>
    </div>`;
  });

  html += '</div>';
  return html;
}

// Toggle ink selection
function toggleInk(inkId) {
  const idx = selectedInks.indexOf(inkId);
  if (idx >= 0) {
    selectedInks.splice(idx, 1);
  } else {
    if (selectedInks.length >= 2) {
      selectedInks = [inkId]; // reset to new selection
    } else {
      selectedInks.push(inkId);
    }
  }

  // If 2 inks selected, resolve deck and sync everywhere
  if (selectedInks.length === 2) {
    const key = [...selectedInks].sort().join('+');
    const deckCode = INK_PAIR_TO_DECK[key];
    if (deckCode) {
      selectedDeck = deckCode;
      coachDeck = deckCode;
      coachOpp = null;
      labOpp = null;
      oppSelectedInks = [];
    }
  }

  // Re-render ink picker bar
  renderInkPickerBar();

  // Re-render current tab content when deck changes
  if (selectedInks.length === 2) {
    if (currentTab === 'meta' && currentPerim !== 'community') {
      const pd = getPerimData();
      if (pd) renderDeckDive(pd);
    } else if (currentTab === 'play' || currentTab === 'deck') {
      render();
    }
  }
}

// === RENDER ===
function render() {
  destroyCharts();
  const main = document.getElementById('main-content');
  // Re-trigger fade-in animation on tab switch
  main.style.animation = 'none';
  main.offsetHeight; // force reflow
  main.style.animation = '';
  const perimBar = document.querySelector('.perimeter-bar');

  if (currentTab === 'meta') {
    const scope = getScopeContext();
    perimBar.style.display = '';
    document.getElementById('format-bar').style.display = '';
    renderInkPickerBar();
    const pd = getPerimData();
    const isCommunity = scope.perimeter === 'community';
    if (isCommunity) {
      renderCommunity(main);
    } else if (!pd) {
      const isTopPro = ['top','pro','infinity_top','infinity_pro'].includes(scope.perimeter);
      if (isTopPro) {
        const count = scope.perimeter.includes('pro') ? 50 : 100;
        const label = scope.perimeter.includes('pro') ? 'PRO' : 'TOP';
        main.innerHTML = `<div class="card" style="text-align:center;padding:40px">
          <h2>No matches yet</h2>
          <p>Not enough recent matches from ${label} ${count} leaderboard players.</p>
          <p style="font-size:0.85em;color:var(--text2)">Try a wider scope (SET11) or check back later.</p>
        </div>`;
      } else {
        main.innerHTML = '<div class="card" style="text-align:center;padding:40px"><h2>No data</h2><p>No data available for this scope.</p></div>';
      }
    } else {
      renderLadder(main);
    }
    // Update perim info
    const info = document.getElementById('perim-info');
    if (info) {
      if (isCommunity) {
        const cd = DATA.perimeters.community;
        if (cd) info.textContent = `${cd.total_games.toLocaleString()} matches | ${cd.players.toLocaleString()} players | OTP WR: ${cd.otp_wr}%`;
      } else {
        const games = DATA.meta.games[scope.perimeter] || 0;
        info.textContent = `${games.toLocaleString()} matches · last 3 days`;
      }
    }
  } else if (currentTab === 'play') {
    perimBar.style.display = 'none';
    document.getElementById('format-bar').style.display = '';
    // Sync coachDeck with selectedDeck from ink picker
    if (selectedDeck && selectedDeck !== coachDeck) {
      coachDeck = selectedDeck;
      coachOpp = null;
    }
    renderInkPickerBar();
    renderCoachV2Tab(main);
  } else if (currentTab === 'deck') {
    perimBar.style.display = 'none';
    document.getElementById('format-bar').style.display = '';
    // Sync coachDeck with selectedDeck from ink picker
    if (selectedDeck && selectedDeck !== coachDeck) {
      coachDeck = selectedDeck;
      labOpp = null;
    }
    renderInkPickerBar();
    renderLabTab(main);
  } else if (currentTab === 'improve') {
    perimBar.style.display = 'none';
    document.getElementById('format-bar').style.display = 'none';
    renderImproveTab(main);
  } else if (currentTab === 'team') {
    perimBar.style.display = 'none';
    document.getElementById('format-bar').style.display = 'none';
    renderTeamTab(main);
  } else if (currentTab === 'events') {
    perimBar.style.display = 'none';
    document.getElementById('format-bar').style.display = 'none';
    const eventsDiv = document.createElement('div');
    const communityDiv = document.createElement('div');
    renderEventsTab(eventsDiv);
    renderCommunityTab(communityDiv);
    main.innerHTML = '';
    main.appendChild(eventsDiv);
    main.appendChild(communityDiv);
  } else if (currentTab === 'home') {
    perimBar.style.display = 'none';
    document.getElementById('format-bar').style.display = 'none';
    renderProfileTab(main);
  }
}

function destroyCharts() {
  Object.values(charts).forEach(c => c.destroy());
  charts = {};
}

// === RENDER COMMUNITY ===
function renderCommunity(main) {
  const cd = DATA.perimeters.community;
  if (!cd) {
    main.innerHTML = '<div class="card">Dati community non disponibili.</div>';
    return;
  }

  const decks = Object.keys(cd.wr).sort((a,b) => cd.wr[b].games - cd.wr[a].games);
  const top8 = decks.slice(0, 8);

  main.innerHTML = `
    <div class="section">
      <div class="section-title">Community Stats (duels.ink)</div>
      <div class="grid-2">
        <div class="chart-box">
          <h3>Meta Share (Community)</h3>
          <div class="share-desktop"><canvas id="chart-comm-share" style="max-height:280px"></canvas></div>
          <div class="share-mobile" id="chart-comm-share-list"></div>
        </div>
        <div class="chart-box"><h3>Win Rate (Community)</h3><div id="chart-comm-wr"></div></div>
      </div>
    </div>
  `;

  // Share chart — desktop: doughnut, mobile: HTML list
  const shareData = top8.map(d => cd.wr[d].games);
  const othersGames = decks.slice(8).reduce((s,d) => s + cd.wr[d].games, 0);
  const allShareData  = [...shareData, othersGames];
  const allColors     = [...top8.map(d => deckColor(d)), '#444'];
  const allLabels     = [...top8.map(d => DECK_NAMES[d] || d), 'Altri'];
  const shareTotal    = allShareData.reduce((a,b)=>a+b,0);

  // Mobile list FIRST (must not depend on Chart.js)
  const commListEl = document.getElementById('chart-comm-share-list');
  if (commListEl) {
    let html = '<div class="share-list">';
    allShareData.forEach((games, i) => {
      const pct = shareTotal > 0 ? (games / shareTotal * 100).toFixed(1) : '0.0';
      const barW = shareTotal > 0 ? Math.max(2, (games / shareTotal * 100)).toFixed(1) : 0;
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
    commListEl.innerHTML = html;
  }

  // Desktop doughnut (wrapped in try/catch)
  try {
    const shareCanvas = document.getElementById('chart-comm-share');
    if (shareCanvas && typeof Chart !== 'undefined') {
      const legendPos = window.innerWidth < 900 ? 'bottom' : 'right';
      charts.commShare = new Chart(shareCanvas, {
        type: 'doughnut',
        data: { labels: allLabels, datasets: [{ data: allShareData, backgroundColor: allColors, borderWidth: 0 }] },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: { position: legendPos, labels: { color: '#8B949E', font: { size: 11 }, boxWidth: 12, padding: 8 } },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.raw.toLocaleString()} (${(ctx.raw/shareTotal*100).toFixed(1)}%)`
              }
            }
          }
        }
      });
    }
  } catch(e) { console.warn('Community share chart init failed:', e); }

  // WR chart — lollipop (same component as main monitor)
  const commWrContainer = document.getElementById('chart-comm-wr');
  if (commWrContainer) {
    const minWR = 42, maxWR = 58, range = maxWR - minWR;
    function commLpColor(wr) {
      if (wr >= 54) return 'green';
      if (wr <= 46) return 'red';
      return 'gray';
    }
    let html = '<div class="lollipop-chart">';
    top8.forEach(d => {
      const wr    = parseFloat(cd.wr[d].wr.toFixed(1));
      const games = cd.wr[d].games;
      const col   = commLpColor(wr);
      const clamp = Math.max(minWR, Math.min(maxWR, wr));
      const dotPct    = ((clamp - minWR) / range * 100).toFixed(2);
      const midPct    = ((50    - minWR) / range * 100).toFixed(2);
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
        <span class="lp-value ${wrCls}">${wr}% <span style="color:var(--text2);font-weight:400;font-size:0.85em">(${games.toLocaleString()})</span></span>
      </div>`;
    });
    html += '</div>';
    commWrContainer.innerHTML = html;
  }
}

// === PREMIUM WRAPPER ===
// ═══════════════════════════════════════════════════════════════════
// REPLAY VIEWER (inline in Lab tab)
// ═══════════════════════════════════════════════════════════════════
// Replay viewer extracted to coach_v2.js

// Privacy layer §24.8 — fire-and-forget paywall intent recorder. Reads the
// JWT from the same localStorage keys used by tcGetAuthToken (team_coaching.js).
// If no token is present the call is skipped entirely — the user can still
// click Unlock PRO with the same client-side fake unlock behavior as before.
// Silent on any error (no console noise, no user-visible failure).
function recordPaywallIntent(tier) {
  try {
    const keys = ['lm_access_token', 'access_token', 'auth_access_token'];
    let token = null;
    for (const k of keys) { const v = localStorage.getItem(k); if (v) { token = v; break; } }
    if (!token) return;
    fetch('/api/v1/user/interest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({ tier: tier })
    }).catch(() => {});
  } catch (_) { /* never throw from onclick */ }
}

function wrapPremium(innerHtml, context) {
  if (PRO_UNLOCKED) return innerHtml;
  // Contextual paywall messaging
  let title = 'PRO Content';
  let desc = 'Unlock game plans, killer curves, card ratings, and deck optimizer to level up your game.';
  let price = '9';
  if (context === 'coach' && coachDeck && coachOpp) {
    const az = getAnalyzerData();
    const mu = getMatchupData(coachOpp);
    const nCurves = (mu?.killer_curves || []).length;
    const nGames = ((mu?.overview?.wins||0) + (mu?.overview?.losses||0));
    title = `${coachDeck} vs ${coachOpp} — PRO Analysis`;
    if (nCurves > 0) {
      desc = `Unlock ${nCurves} killer curve${nCurves>1?'s':''} and threat responses, validated on ${nGames} real matches.`;
    } else {
      desc = `Unlock detailed matchup analysis with playbook, card ratings, and deck optimizer for ${nGames} matches.`;
    }
  } else if (context === 'lab') {
    title = 'Lab — PRO Tools';
    desc = 'Unlock Mulligan Trainer (real PRO hands), Card Impact analysis, and optimized decklists.';
  } else if (context === 'team') {
    title = 'Team Training — PRO';
    desc = 'Unlock team analytics: player comparison, weakness heatmap, session agendas, and coaching tools.';
  } else if (context === 'profile_matches') {
    title = 'My Matches — PRO';
    desc = 'Auto-import your duels.ink match history, track your win rate trend, and analyze your performance.';
  } else if (context === 'profile_errors') {
    title = 'Error Detection — PRO';
    desc = 'Automatic misplay detection across your real games, with severity ratings and fix suggestions.';
  } else if (context === 'profile_progress') {
    title = 'Learning Progress — PRO';
    desc = 'Track School clips completed and matchups studied, with improvement trend over time.';
  }
  return `<div class="premium-wall">
    <div class="premium-content">${innerHtml}</div>
    <div class="paywall-overlay">
      <div class="lock-big">🔒</div>
      <h3>${title}</h3>
      <p>${desc}</p>
      <button class="unlock-btn" onclick="recordPaywallIntent('pro');PRO_UNLOCKED=true;document.querySelectorAll('.tab .lock-icon').forEach(l=>l.style.display='none');render()">Unlock PRO — ${price}&euro;/month</button>
    </div>
  </div>`;
}

function getAnalyzerData() {
  if (!DATA) return {};
  const az = (getScopeContext().isInfinity && DATA.matchup_analyzer_infinity)
    ? DATA.matchup_analyzer_infinity
    : (DATA.matchup_analyzer || {});
  // Derive available_matchups from vs_* keys if missing
  const decks = az.available_decks || [];
  for (const dk of decks) {
    if (az[dk] && (!az[dk].available_matchups || az[dk].available_matchups.length === 0)) {
      az[dk].available_matchups = Object.keys(az[dk])
        .filter(k => k.startsWith('vs_'))
        .map(k => k.slice(3))
        .sort();
    }
  }
  return az;
}

// === MATCHUP SELECTOR (shared) ===
function buildMatchupSelector(tabPrefix) {
  const az = getAnalyzerData();
  const availDecks = az.available_decks || [];
  if (!coachDeck || !availDecks.includes(coachDeck)) coachDeck = availDecks[0] || 'AmAm';
  const deckData = az[coachDeck];
  const matchups = deckData ? (deckData.available_matchups || []) : [];
  const currentOpp = tabPrefix === 'coach' ? coachOpp : labOpp;

  // Our deck: ink icons + name
  const inks = DECK_INKS[coachDeck] || [];
  const inkIcons = inks.map(i => `<span class="mu-ink-icon">${INK_SVGS[i] || ''}</span>`).join('');
  const deckName = DECK_NAMES[coachDeck] || coachDeck;
  const isAvail = availDecks.includes(coachDeck);

  // Opponent: ink icon picker
  let oppHtml = '<div class="opp-ink-picker">';
  INK_LIST.forEach(ink => {
    const isSel = oppSelectedInks.includes(ink.id);
    const cls = isSel ? ' selected' : '';
    oppHtml += `<div class="opp-ink-wrap${cls}" onclick="toggleOppInk('${ink.id}','${tabPrefix}')" title="${ink.label}">
      ${INK_SVGS[ink.id]}
    </div>`;
  });
  oppHtml += '</div>';

  // Opponent result
  let oppResult = '';
  if (oppSelectedInks.length === 2) {
    const key = [...oppSelectedInks].sort().join('+');
    const oppCode = INK_PAIR_TO_DECK[key];
    if (oppCode) {
      const oppInks = DECK_INKS[oppCode] || [];
      const dots = oppInks.map(i => `<span class="ink-dot-sm" style="background:${INK_COLORS[i]}"></span>`).join('');
      const hasData = matchups.includes(oppCode);
      oppResult = `<div class="opp-result">${deckImg(oppCode,34)} <span class="opp-name" style="display:none">${oppCode}</span>`;
      if (!hasData && isAvail) oppResult += ` <span class="opp-warn">&#9888;</span>`;
      oppResult += `</div>`;
    } else {
      oppResult = `<div class="opp-result"><span class="opp-warn">?</span></div>`;
    }
  } else if (oppSelectedInks.length === 1) {
    oppResult = `<div class="opp-result" style="opacity:0.5"><span style="color:var(--text2);font-size:0.8em">+1</span></div>`;
  }

  return `<div class="matchup-selector">
    <div class="mu-our-deck">
      ${deckImg(coachDeck,42)}
      <span class="mu-deck-name" style="display:none">${coachDeck}</span>
      <span class="mu-deck-sub">${deckName}</span>
      ${!isAvail ? '<span style="color:var(--yellow);font-size:0.75em">&#9888; no data</span>' : ''}
    </div>
    <span class="arrow">vs</span>
    ${oppHtml}
    ${oppResult}
  </div>`;
}

function syncOppInksFromDeck(deckCode) {
  if (deckCode && DECK_INKS[deckCode]) {
    oppSelectedInks = [...DECK_INKS[deckCode]];
  } else {
    oppSelectedInks = [];
  }
}

function toggleOppInk(inkId, tabPrefix) {
  const idx = oppSelectedInks.indexOf(inkId);
  if (idx >= 0) {
    oppSelectedInks.splice(idx, 1);
  } else {
    if (oppSelectedInks.length >= 2) {
      oppSelectedInks = [inkId];
    } else {
      oppSelectedInks.push(inkId);
    }
  }

  // Resolve opponent deck
  if (oppSelectedInks.length === 2) {
    const key = [...oppSelectedInks].sort().join('+');
    const oppCode = INK_PAIR_TO_DECK[key];
    if (oppCode) {
      if (tabPrefix === 'coach') coachOpp = oppCode;
      else labOpp = oppCode;
    }
  }

  render();
}

function getMatchupData(oppKey) {
  const az = getAnalyzerData();
  const dd = az[coachDeck];
  if (!dd) return null;
  return dd['vs_'+oppKey] || null;
}

// === COACH TAB ===
function cardImgUrl(cardName) {
  if (!cardName) return '';
  const ci = (DATA.card_images || {})[cardName];
  if (!ci) return '';
  const [s, n] = ci.split('/');
  return `https://cards.duels.ink/lorcana/en/thumbnail/${s}-${n.replace(/^0+/,'')}.webp`;
}

function renderCoachTab(main) {
  const az = getAnalyzerData();
  const availDecks = az.available_decks || [];
  const matchups = (az[coachDeck]||{}).available_matchups || [];
  if (!coachOpp || !matchups.includes(coachOpp)) {
    coachOpp = matchups[0] || null;
    syncOppInksFromDeck(coachOpp);
  }

  const selectorHtml = buildMatchupSelector('coach');

  const deckData = az[coachDeck];
  if (!deckData || !coachOpp) {
    main.innerHTML = selectorHtml + `<div class="coming-soon-card"><div class="lock-emoji">🔒</div><h3>Coming Soon</h3><p>Select opponent using the ink icons above.</p></div>`;
    return;
  }

  const mu = getMatchupData(coachOpp);
  if (!mu) {
    main.innerHTML = selectorHtml + `<div class="coming-soon-card"><div class="lock-emoji">📊</div><h3>Data not available</h3><p>No report for this matchup.</p></div>`;
    return;
  }

  const ov = mu.overview || {};
  const pb = mu.playbook || [];
  const bs = mu.board_state || {};
  const kr = mu.killer_responses || [];
  const ac = mu.ability_cards || [];
  const la = mu.loss_analysis || {};

  let content = selectorHtml;

  // 1. Overview KPIs + Lore Chart
  content += `<div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-value ${(ov.wr||0)>=50?'wr-good':'wr-bad'}">${ov.wr||'?'}%</div><div class="kpi-label">Win Rate</div></div>
    <div class="kpi-card"><div class="kpi-value">${ov.otp_wr||'?'}%</div><div class="kpi-label">OTP WR (${ov.otp_games||'?'}g)</div></div>
    <div class="kpi-card"><div class="kpi-value">${ov.otd_wr||'?'}%</div><div class="kpi-label">OTD WR (${ov.otd_games||'?'}g)</div></div>
    <div class="kpi-card"><div class="kpi-value">${ov.gap||'?'}pp</div><div class="kpi-label">Gap OTP/OTD</div></div>
    <div class="kpi-card"><div class="kpi-value">${(ov.wins||0)+(ov.losses||0)}</div><div class="kpi-label">Match Analizzati</div></div>
  </div>`;

  if (ov.lore_progression && ov.lore_progression.length) {
    content += `<div class="card" style="padding:12px;margin-bottom:20px"><canvas id="chart-lore" height="100"></canvas></div>`;
  }

  // 2. Playbook Avversario — accordion, closed default
  if (pb.length > 0) {
    let pbBody = `<div class="card" style="padding:20px 20px 12px 20px"><div class="playbook">`;
    pb.forEach((t, i) => {
      const plays = t.plays || [];
      const kills = t.impact?.killed_per_game || 0;
      const lore = t.impact?.lore_quested || 0;
      const danger = kills >= 0.8 || lore >= 2.0 ? 'high' : kills >= 0.3 || lore >= 1.0 ? 'mid' : 'low';
      const cardsStr = plays.slice(0,3).map(p => `<strong>${p.card}</strong> <span class="pct">${p.pct}%</span>`).join(' · ');
      const statsHtml = (kills > 0 || lore > 0) ? `<div class="pb-stats">${kills > 0 ? `<span class="kill">${kills} kill/g</span>` : ''}${lore > 0 ? `<span class="lore">${lore} lore</span>` : ''}</div>` : '';

      pbBody += `<div class="pb-turn" onclick="this.classList.toggle('open')">
        <div class="pb-dot ${danger}"></div>
        <div class="pb-header">
          <span class="pb-turn-num">${t.turn}</span>
          <div class="pb-cards">${cardsStr}</div>
          ${statsHtml}
        </div>
        <div class="pb-expand">`;
      if (plays.length > 0) {
        pbBody += `<table class="deck-table" style="margin-bottom:6px"><tr><th>Carta</th><th>Costo</th><th>Freq</th><th>Effetto</th></tr>`;
        plays.forEach(p => { pbBody += `<tr><td><strong>${p.card}</strong></td><td>${p.cost}</td><td>${p.pct}%</td><td style="color:var(--text2)">${p.effect}</td></tr>`; });
        pbBody += `</table>`;
      }
      if (t.combos && t.combos.length) {
        pbBody += `<div class="pb-combo"><strong>Combo:</strong> `;
        pbBody += t.combos.map(c => `${c.cards} (${c.freq}x)`).join(' · ');
        pbBody += `</div>`;
      }
      if (t.impact?.killed_top) {
        pbBody += `<div class="pb-impact">Target: ${t.impact.killed_top}</div>`;
      }
      pbBody += `</div></div>`;
    });
    pbBody += `</div></div>`;
    content += `<div class="section">
      ${monAccordion('acc-pb', 'Opponent Playbook', '', pbBody, {
        desktopOpen: false,
        info: { title: 'About Opponent Playbook', body: '<p>Turn-by-turn breakdown of what the opponent typically plays in this matchup.</p><p>Each turn shows top cards + frequency, combos, and impact (kills / lore). Click a turn row to see full details.</p><p>Color dots: <span style="color:#F85149">red</span> = high danger turn, <span style="color:#D29922">yellow</span> = mid, <span style="color:var(--text2)">grey</span> = low.</p>' }
      })}
    </div>`;
  }

  // 3. How to Respond — OTP vs OTD — accordion, closed default
  if (kr.length > 0) {
    let krBody = '';
    kr.forEach(k => {
      let kHtml = `<div class="threat-card" onclick="this.classList.toggle('open')">
        <div class="threat-header">
          <span class="threat-name">#${k.id} ${k.name}</span>
          <span class="freq-badge">${k.pct}% losses (${k.losses})</span>
        </div>
        <div class="threat-detail">`;
      if (k.curve) kHtml += `<div style="font-size:0.85em;color:var(--text2);margin-bottom:8px"><strong>Curva tipica:</strong> ${k.curve}</div>`;
      if (k.our_wr_vs_curve) kHtml += `<div style="font-size:0.85em;margin-bottom:10px">Our WR vs this curve: <strong class="${k.our_wr_vs_curve>=50?'wr-good':'wr-bad'}">${k.our_wr_vs_curve}%</strong></div>`;
      // OTP table
      if (k.otp && k.otp.length) {
        kHtml += `<div class="response-card" style="margin-bottom:8px"><h4 style="color:var(--green)">OTP — Going First</h4>
          <table class="deck-table"><tr><th>Turno</th><th style="color:var(--green)">Gioca</th><th style="color:var(--red)">NON giocare</th></tr>`;
        k.otp.forEach(r => { kHtml += `<tr><td><strong>${r.turn}</strong></td><td style="color:var(--green)">${r.play}</td><td style="color:var(--red)">${r.trap}</td></tr>`; });
        kHtml += `</table></div>`;
      }
      // OTD table
      if (k.otd && k.otd.length) {
        kHtml += `<div class="response-card"><h4 style="color:var(--sapphire)">OTD — Going Second</h4>
          <table class="deck-table"><tr><th>Turno</th><th style="color:var(--green)">Gioca</th><th style="color:var(--red)">NON giocare</th></tr>`;
        k.otd.forEach(r => { kHtml += `<tr><td><strong>${r.turn}</strong></td><td style="color:var(--green)">${r.play}</td><td style="color:var(--red)">${r.trap}</td></tr>`; });
        kHtml += `</table></div>`;
      }
      if (k.targets) kHtml += `<div style="margin-top:8px;font-size:0.85em"><strong>Target prioritari:</strong> ${k.targets}</div>`;
      kHtml += `</div></div>`;
      krBody += kHtml;
    });
    content += `<div class="section">
      ${monAccordion('acc-howrespond', 'How to Respond — OTP vs OTD', '', krBody, {
        desktopOpen: false,
        info: { title: 'About How to Respond', body: '<p>For each loss pattern in this matchup, what to play and what to avoid — split by OTP (going first) and OTD (going second).</p><p>Click a pattern to see the full turn-by-turn table.</p>' }
      })}
    </div>`;
  }

  // 4. Killer Curves — accordion, closed default
  const kc = mu.killer_curves || [];
  if (kc.length > 0) {
    let kcBody = '';
    kc.forEach(curve => {
      const seq = curve.sequence || {};
      const resp = curve.response || {};
      let cHtml = `<div class="threat-card" onclick="this.classList.toggle('open')">
        <div class="threat-header">
          <span class="threat-name">${curve.name}</span>
          <span class="freq-badge">${curve.frequency?.pct||'?'}% losses (${curve.frequency?.loss_count||'?'})</span>
        </div>
        <div class="threat-detail">
          <div style="margin-bottom:8px;font-size:0.85em;color:var(--text2)">
            Type: <strong>${curve.type||'?'}</strong> | Critical turn: <strong>T${curve.critical_turn?.turn||'?'}</strong> (${curve.critical_turn?.component||'?'}) | Swing: ${curve.critical_turn?.swing||'?'}
          </div>
          <div class="turn-timeline">`;
      Object.entries(seq).forEach(([t, s]) => {
        // Support both old format (s.card) and new format (s.plays[])
        const plays = s.plays || (s.card ? [{card: s.card, ink_cost: s.ink_cost, role: s.role, is_shift: s.is_shift, is_sung: s.is_sung}] : []);
        // Card images for all plays
        const imgsHtml = plays.map(p => {
          const url = cardImgUrlFuzzy(p.card);
          return url ? `<img src="${url}" alt="${p.card}" style="width:65px;height:auto;border-radius:4px;opacity:0.9" loading="lazy" onerror="this.style.display='none'">` : '';
        }).filter(Boolean).join('');
        // Card names with tags
        const cardsText = plays.map(p => {
          let tag = '';
          if (p.is_shift) tag = ' <span style="color:var(--amethyst);font-weight:700">[SHIFT]</span>';
          if (p.is_sung) tag = ' <span style="color:var(--sapphire);font-weight:700">[SONG]</span>';
          return `${p.card}${tag} <span style="color:var(--gold)">(${p.ink_cost})</span>`;
        }).join('<br>');
        const totalInk = s.total_ink != null ? s.total_ink : plays.reduce((a, p) => a + (p.ink_cost||0), 0);
        const loreText = s.lore_this_turn ? ` · <span style="color:var(--emerald)">${s.lore_this_turn}L</span>` : '';
        cHtml += `<div class="turn-step">
          <div class="turn-label">${t}</div>
          <div style="display:flex;gap:3px;justify-content:center;flex-wrap:wrap;margin:4px 0">${imgsHtml}</div>
          <div style="font-size:0.82em">${cardsText}</div>
          <div style="color:var(--gold);font-size:0.75em">${totalInk} ink${loreText}</div>
        </div>`;
      });
      cHtml += `</div>`;
      // Response
      if (resp.strategy || kcResponseSections(resp).length) {
        cHtml += `<div class="response-card">
          <h4>How to Respond</h4>
          ${kcRenderResponse(resp)}`;
        cHtml += `</div>`;
      }
      cHtml += `</div></div>`;
      kcBody += cHtml;
    });
    content += `<div class="section">
      ${monAccordion('acc-kc', 'Killer Curves — Opponent Worst Case', '', kcBody, {
        desktopOpen: false,
        info: { title: 'About Killer Curves', body: '<p>The most dangerous opponent sequences in this matchup, extracted from real losses.</p><p>Each curve shows: card-by-card turn timeline (with ink cost + lore), critical turn, and a validated <strong>response strategy</strong>.</p><p>Click a curve to expand the full sequence.</p>' }
      })}
    </div>`;
  }

  // 4c. Key Threats (LLM tactical analysis) — accordion, OPEN by default on desktop
  const tl = mu.threats_llm || {};
  if (tl.threats && tl.threats.length > 0) {
    let ktBody = '';
    if (tl.type_summary) ktBody += `<div class="section-subtitle" style="font-style:italic;color:var(--gold)">${tl.type_summary}</div>`;

    tl.threats.forEach(t => {
      let tHtml = `<div class="threat-card" onclick="this.classList.toggle('open')">
        <div class="threat-header">
          <span class="threat-name">#${t.id} ${t.name}</span>
          <span class="freq-badge">${t.pct}% (${t.losses}/${t.total_losses})</span>
        </div>
        <div class="threat-detail">`;
      if (t.critical_turn) tHtml += `<div style="margin-bottom:6px;font-size:0.88em"><strong style="color:var(--red)">Critical turn: ${t.critical_turn}</strong></div>`;
      if (t.description) tHtml += `<div style="margin-bottom:10px;font-size:0.88em;color:var(--text2)">${t.description}</div>`;

      // Sections (Prevention, Response, Mitigazione)
      (t.sections || []).forEach(s => {
        const typeColor = s.type === 'Prevention' ? 'var(--green)' : s.type === 'Response' ? 'var(--sapphire)' : 'var(--yellow)';
        tHtml += `<div class="response-card" style="border-color:${typeColor};margin-bottom:8px">
          <h4 style="color:${typeColor}">${s.type} — ${s.label}${s.games ? ` (${s.games}g)` : ''}</h4>`;
        if (s.plans && s.plans.length > 0) {
          tHtml += `<table class="deck-table" style="font-size:0.85em"><tr><th>Turno</th><th>Avversario</th><th style="color:var(--green)">Piano A</th><th style="color:var(--sapphire)">Piano B</th>${s.plans[0].plan_c ? '<th style="color:var(--yellow)">Piano C</th>' : ''}</tr>`;
          s.plans.forEach(p => {
            tHtml += `<tr><td><strong>${p.turn}</strong></td><td style="color:var(--text2)">${p.opponent}</td><td>${p.plan_a || '—'}</td><td>${p.plan_b || '—'}</td>${p.plan_c !== undefined ? `<td>${p.plan_c || '—'}</td>` : ''}</tr>`;
          });
          tHtml += `</table>`;
        }
        tHtml += `</div>`;
      });

      // Notes
      if (t.notes) tHtml += `<div style="margin-top:8px;padding:8px;background:rgba(210,153,34,0.08);border-radius:6px;font-size:0.85em;color:var(--yellow)"><strong>Note:</strong> ${t.notes}</div>`;
      // Mitigation text
      if (t.mitigation) tHtml += `<div style="margin-top:6px;font-size:0.85em;color:var(--text2)"><strong>Mitigation:</strong> ${t.mitigation}</div>`;
      tHtml += `</div></div>`;
      ktBody += tHtml;
    });

    // Riepilogo table
    if (tl.riepilogo && tl.riepilogo.length > 0) {
      ktBody += `<div class="card" style="padding:16px;margin-top:12px">
        <h4 style="color:var(--gold);margin-bottom:10px">Riepilogo Risposte</h4>
        <table class="deck-table"><tr><th>Minaccia</th><th>Turno</th><th style="color:var(--green)">Piano A</th><th style="color:var(--sapphire)">Piano B</th><th style="color:var(--yellow)">Piano C</th></tr>`;
      tl.riepilogo.forEach(r => {
        ktBody += `<tr><td><strong>${r.threat}</strong></td><td>${r.turn}</td><td style="font-size:0.85em">${r.plan_a}</td><td style="font-size:0.85em">${r.plan_b}</td><td style="font-size:0.85em">${r.plan_c}</td></tr>`;
      });
      ktBody += `</table></div>`;
    }
    content += `<div class="section">
      ${monAccordion('acc-kt', 'Key Threats', '', ktBody, {
        desktopOpen: true,
        info: { title: 'About Key Threats', body: '<p>Tactical LLM analysis of the biggest threats in this matchup.</p><p>For each threat: critical turn, description, and a plan table split by <strong>Prevention / Response / Mitigation</strong> with Plan A/B/C per turn.</p><p>Bottom summary table pulls everything together for quick pre-match review.</p>' }
      })}
    </div>`;
  }

  // 5. Opponent's Killer Cards — accordion, closed default
  if (ac.length > 0) {
    let acBody = `<div class="card" style="padding:16px"><table class="deck-table"><tr><th>Carta</th><th>Costo</th><th>% Loss</th><th>Ability</th></tr>`;
    ac.forEach(c => {
      const cls = c.loss_pct >= 50 ? 'wr-bad' : '';
      acBody += `<tr><td><strong>${c.card}</strong></td><td>${c.cost}</td><td class="${cls}">${c.loss_pct}%</td><td style="font-size:0.8em;color:var(--text2)">${c.ability}</td></tr>`;
    });
    acBody += `</table></div>`;
    content += `<div class="section">
      ${monAccordion('acc-ackills', 'Opponent\\u2019s Killer Cards', '', acBody, {
        desktopOpen: false,
        info: { title: 'About Killer Cards', body: '<p>The opponent\\u2019s cards that appear most often in <strong>your losses</strong>.</p><p>Ranked by <em>% Loss</em> = percentage of your defeats where this card was played. High values = top priority to remove, bodyguard, or trade against.</p>' }
      })}
    </div>`;
  }

  // 6. Trend by Turn — accordion, closed default (contains Chart.js canvas)
  if (la.avg_trend_components && Object.keys(la.avg_trend_components).length) {
    const trendBody = `<div class="card" style="padding:16px"><canvas id="chart-trend" height="180"></canvas></div>`;
    content += `<div class="section">
      ${monAccordion('acc-trend', 'Trend by Turn', '', trendBody, {
        desktopOpen: false,
        onOpen: monAccOnExpandResize,
        info: { title: 'About Trend by Turn', body: '<p>Per-turn breakdown of where you gain or lose advantage across 9 dimensions: board, lore, draw, clock, removal, opponent hand/filter/lore velocity/lore potential.</p><p>Positive bars = you\\u2019re ahead, negative = behind. Use it to spot <em>when</em> the matchup slips (e.g. T4-T5 lore flood, T6 board wipe).</p>' }
      })}
    </div>`;
  }

  // Replay viewer
  if (coachDeck && coachOpp) {
    content += buildReplayViewer(coachDeck, coachOpp);
  }

  main.innerHTML = content;
  renderCoachCharts(ov, la);

  // Init replay viewer
  if (coachDeck && coachOpp) {
    rvInit(coachDeck, coachOpp);
  }
}

function renderCoachCharts(ov, la) {
  // Lore progression
  if (ov.lore_progression && document.getElementById('chart-lore')) {
    const lp = ov.lore_progression;
    charts['chart-lore'] = new Chart(document.getElementById('chart-lore'), {
      type: 'line',
      data: { labels: lp.map(p => 'T'+p.t), datasets: [
        { label: DECK_NAMES[coachDeck]||coachDeck, data: lp.map(p => p.our), borderColor: '#D4A03A', backgroundColor: 'rgba(212,160,58,0.1)', fill: true, tension: 0.3, pointRadius: 4 },
        { label: DECK_NAMES[coachOpp]||coachOpp, data: lp.map(p => p.opp), borderColor: '#F85149', backgroundColor: 'rgba(248,81,73,0.1)', fill: true, tension: 0.3, pointRadius: 4 },
      ]},
      options: { responsive:true, scales: { y: { title:{display:true,text:'Lore',color:'#8B949E'}, grid:{color:'rgba(255,255,255,0.05)'}, ticks:{color:'#8B949E'} }, x: { ticks:{color:'#8B949E'}, grid:{display:false} } }, plugins: { legend:{labels:{color:'#E6EDF3'}} } }
    });
  }
  // Trend components
  if (la.avg_trend_components && document.getElementById('chart-trend')) {
    const tc = la.avg_trend_components;
    const maxLen = Math.max(...Object.values(tc).map(a => a.length));
    const labels = Array.from({length: maxLen}, (_, i) => 'T'+(i+1));
    charts['chart-trend'] = new Chart(document.getElementById('chart-trend'), {
      type: 'line',
      data: { labels, datasets: [
        { label: 'Draw', data: tc.draw||[], borderColor: '#2471A3', tension: 0.3, pointRadius: 3 },
        { label: 'Board', data: tc.board||[], borderColor: '#3FB950', tension: 0.3, pointRadius: 3 },
        { label: 'Lore', data: tc.lore||[], borderColor: '#D4A03A', tension: 0.3, pointRadius: 3 },
      ]},
      options: { responsive:true, scales: { y: { title:{display:true,text:'Vantaggio',color:'#8B949E'}, grid:{color:'rgba(255,255,255,0.05)'}, ticks:{color:'#8B949E'} }, x: { ticks:{color:'#8B949E'}, grid:{display:false} } }, plugins: { legend:{labels:{color:'#E6EDF3'}} } }
    });
  }
}

// Lab extracted to lab.js
// Shared UI extracted to shared_ui.js
