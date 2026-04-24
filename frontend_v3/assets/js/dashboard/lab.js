// === LAB TAB ===
// === DECK BROWSER — fullscreen modal + inner COMPARATOR overlay ===
function openTournamentDecks() {
  const d = document.getElementById('td-drawer');
  if (!d) return;
  d.classList.add('open');
  d.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}
function closeTournamentDecks() {
  const d = document.getElementById('td-drawer');
  const c = document.getElementById('td-compare-overlay');
  if (d) { d.classList.remove('open'); d.setAttribute('aria-hidden', 'true'); }
  if (c) c.classList.remove('open');
  document.body.style.overflow = '';
}
function openDeckCompare() {
  const c = document.getElementById('td-compare-overlay');
  const body = document.getElementById('td-compare-body');
  const title = document.getElementById('td-compare-title');
  if (!c) return;
  if (body) body.innerHTML = _dbRenderCompareDiff();
  if (title) {
    title.textContent = _dbOpenDecks.length
      ? `Comparator — ${_dbOpenDecks.length} deck${_dbOpenDecks.length > 1 ? 's' : ''}`
      : 'Comparator';
  }
  c.classList.add('open');
  c.setAttribute('aria-hidden', 'false');
}
function closeDeckCompare() {
  const c = document.getElementById('td-compare-overlay');
  if (c) c.classList.remove('open');
}

// === MULLIGAN CAROUSEL ===
var _mullData = [], _mullFilter = 'all', _mullIdx = 0;
var _mullUserSelected = new Set(); // cards the user clicked
var _mullRevealed = false; // whether pro's mull is shown

// Fuzzy card image lookup: try exact, then normalize punctuation
function cardImgUrlFuzzy(cardName) {
  if (!cardName) return '';
  const imgs = DATA.card_images || {};
  const mkUrl = (v) => { const [s,n] = v.split('/'); return `https://cards.duels.ink/lorcana/en/thumbnail/${s}-${n.replace(/^0+/,'')}.webp`; };

  // 1. Exact match
  let ci = imgs[cardName];
  if (ci) return mkUrl(ci);

  // 2. Normalized exact match (smart quotes + Oxford comma variants)
  const norm = cardName.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"');
  // Also try with/without Oxford comma: "Mean, and" ↔ "Mean and"
  const normAlt = norm.includes(', and ') ? norm.replace(', and ', ' and ') : norm.replace(' and ', ', and ');
  for (const [k, v] of Object.entries(imgs)) {
    const kn = k.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"');
    if (kn === norm || kn === normAlt) return mkUrl(v);
  }

  // 3. rvCardsDB fallback (exact name match)
  if (rvCardsDB) {
    const url = rvCardImgByName(cardName);
    if (url) return url;
  }
  return '';
}

function initMullCarousel() {
  var holder = document.getElementById('mull-data-holder');
  if (!holder) return;
  try { _mullData = JSON.parse(holder.getAttribute('data-mulls') || '[]'); } catch(e) { _mullData = []; }
  _mullFilter = 'blind'; _mullIdx = 0;
  _mullUserSelected = new Set(); _mullRevealed = false;
  renderMullHand();
}

function getFilteredMulls() {
  if (_mullFilter === 'blind') return _mullData.filter(function(h) { return !h.game || h.game === 1; }); // ladder (Bo1) + G1 Bo3
  if (_mullFilter === 'otp') return _mullData.filter(function(h) { return h.otp === true && h.game >= 2; }); // OTP in G2/G3 only
  if (_mullFilter === 'otd') return _mullData.filter(function(h) { return h.otp === false && h.game >= 2; }); // OTD in G2/G3 only
  return _mullData;
}

function setMullFilter(f) {
  _mullFilter = f; _mullIdx = 0;
  _mullUserSelected = new Set(); _mullRevealed = false;
  document.querySelectorAll('.mf-btn').forEach(function(b) { b.classList.toggle('active', b.dataset.f === f); });
  renderMullHand();
}

function mullNav(dir) {
  var list = getFilteredMulls();
  if (!list.length) return;
  _mullIdx = (_mullIdx + dir + list.length) % list.length;
  _mullUserSelected = new Set(); _mullRevealed = false;
  renderMullHand();
}

function mullToggleCard(idx) {
  if (_mullRevealed) return; // locked after reveal
  if (_mullUserSelected.has(idx)) _mullUserSelected.delete(idx);
  else _mullUserSelected.add(idx);
  renderMullHand();
}

function mullReveal() {
  _mullRevealed = true;
  renderMullHand();
}

function mullReset() {
  _mullUserSelected = new Set(); _mullRevealed = false;
  renderMullHand();
}

function renderMullHand() {
  var list = getFilteredMulls();
  var counter = document.getElementById('mull-counter');
  var player = document.getElementById('mull-player');
  var result = document.getElementById('mull-result');
  var badge = document.getElementById('mull-otp-badge');
  var container = document.getElementById('mull-cards');
  var revealArea = document.getElementById('mull-reveal-area');
  if (!counter || !container) return;

  if (!list.length) {
    counter.textContent = 'No hands for this filter';
    container.innerHTML = '';
    if (player) player.textContent = '';
    if (result) result.textContent = '';
    if (badge) badge.textContent = '';
    if (revealArea) revealArea.innerHTML = '';
    return;
  }

  var h = list[_mullIdx];
  counter.textContent = (_mullIdx + 1) + ' / ' + list.length;
  player.textContent = h.player;

  // Hide result until revealed
  if (_mullRevealed) {
    result.textContent = h.won ? 'W' : 'L';
    result.className = h.won ? 'wr-good' : 'wr-bad';
    result.style.display = '';
  } else {
    result.textContent = '';
    result.style.display = 'none';
  }

  badge.textContent = h.otp === true ? 'OTP' : h.otp === false ? 'OTD' : '';
  badge.style.background = h.otp === true ? 'rgba(63,185,80,0.2)' : 'rgba(36,113,163,0.2)';
  badge.style.color = h.otp === true ? 'var(--green)' : 'var(--sapphire)';

  // Build cards
  var html = '';
  var proSent = h.sent || [];
  (h.initial || []).forEach(function(card, idx) {
    var isUserSelected = _mullUserSelected.has(idx);
    var isProMulled = _mullRevealed && proSent.indexOf(card) >= 0;
    var classes = 'mull-card-wrap';
    if (isUserSelected) classes += ' user-selected';
    if (isProMulled) classes += ' pro-mulled';

    var url = cardImgUrlFuzzy(card);
    var imgHtml = url
      ? '<img src="' + url + '" alt="' + card.replace(/"/g,'') + '" loading="lazy" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
        + '<div class="mull-placeholder" style="display:none">' + card.split(' - ')[0] + '</div>'
      : '<div class="mull-placeholder">' + card.split(' - ')[0] + '</div>';

    var shortName = card.split(' - ');
    var displayName = shortName[0];
    if (shortName[1]) displayName += '<br><span style="font-size:0.85em;opacity:0.7">' + shortName[1] + '</span>';

    html += '<div class="' + classes + '" onclick="mullToggleCard(' + idx + ')">'
      + imgHtml
      + '<div class="mull-x-overlay">\u2715</div>'
      + '<div class="mull-pro-badge">MULL</div>'
      + '<div class="mull-card-name">' + card.split(' - ')[0] + '</div>'
      + '</div>';
  });
  container.innerHTML = html;

  // Reveal area: button + result message
  if (!revealArea) return;
  var hasMull = h.mull > 0;
  if (!_mullRevealed) {
    var userCount = _mullUserSelected.size;
    var hint = userCount > 0 ? userCount + ' card' + (userCount > 1 ? 's' : '') + ' selected' : 'Click cards to mulligan';
    revealArea.innerHTML = '<div style="text-align:center;margin-top:12px">'
      + '<div style="font-size:0.8em;color:var(--text2);margin-bottom:8px">' + hint + '</div>'
      + '<button class="mull-btn-reveal" onclick="mullReveal()">'
      + (hasMull ? 'Mulligan' : 'Mulligan') + '</button>'
      + '</div>';
  } else {
    // Compare user selection vs pro's actual mull
    var proSet = new Set();
    proSent.forEach(function(card) {
      (h.initial || []).forEach(function(c, i) { if (c === card && !proSet.has(i)) proSet.add(i); });
    });

    var msgHtml = '';
    if (!hasMull) {
      // Pro kept all
      if (_mullUserSelected.size === 0) {
        msgHtml = '<span class="mull-result-msg correct">Perfect! TOP also kept all (Keep)</span>';
      } else {
        msgHtml = '<span class="mull-result-msg wrong">TOP kept all (Keep) &mdash; you would have mulliganed ' + _mullUserSelected.size + '</span>';
      }
    } else {
      // Compare sets
      var correct = 0, missed = 0, extra = 0;
      _mullUserSelected.forEach(function(i) { if (proSet.has(i)) correct++; else extra++; });
      proSet.forEach(function(i) { if (!_mullUserSelected.has(i)) missed++; });
      var total = proSet.size;

      if (correct === total && extra === 0) {
        msgHtml = '<span class="mull-result-msg correct">Perfect! You mulliganed the same ' + total + ' cards as TOP</span>';
      } else if (correct > 0) {
        msgHtml = '<span class="mull-result-msg partial">' + correct + '/' + total + ' correct';
        if (missed > 0) msgHtml += ' &mdash; ' + missed + ' missed';
        if (extra > 0) msgHtml += ' &mdash; ' + extra + ' extra';
        msgHtml += '</span>';
      } else {
        msgHtml = '<span class="mull-result-msg wrong">None in common with TOP (mulliganed ' + total + ' cards)</span>';
      }
    }

    revealArea.innerHTML = '<div style="text-align:center;margin-top:12px">'
      + msgHtml
      + '</div>';
  }
}

// Coach V2 extracted to coach_v2.js
// ── Deck Browser (Lab tab) ──
let _dbOpenDecks = []; // ordered array of {deck, refIdx}; refIdx=-1 = consensus, 0..N = tournament ref; max 3 slots, same archetype can appear multiple times with different refIdx
let _dbInkFilter = new Set();
let _dbRankFilter = ''; // '', 'winner', 'top4', 'top8', 'top16'
let _dbDateFilter = ''; // '', '3d', '7d', '30d'
let _dbEventSearch = ''; // free-text event name filter (lowercase)
const _DB_RANK_GROUPS = {
  winner: ['1st','2nd'],
  top4: ['1st','2nd','3rd','Top4'],
  top8: ['1st','2nd','3rd','Top4','Top8'],
  top16: ['1st','2nd','3rd','Top4','Top8','Top16'],
};
const _DB_DATE_WINDOWS = { '3d': 3, '7d': 7, '30d': 30 };

function _dbDateCutoff() {
  const win = _DB_DATE_WINDOWS[_dbDateFilter];
  if (!win) return null;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - win);
  return d.toISOString().slice(0, 10); // YYYY-MM-DD
}

function dbSetDate(win) {
  _dbDateFilter = (_dbDateFilter === win) ? '' : win;
  _dbRefreshAll();
}
function dbSetEventSearch(q) {
  _dbEventSearch = String(q || '').trim().toLowerCase();
  _dbRefreshAll();
}

function _dbShowCapToast() {
  let t = document.getElementById('db-cap-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'db-cap-toast';
    t.className = 'db-cap-toast';
    t.textContent = 'Max 3 decks — remove one to add another';
    document.body.appendChild(t);
  }
  t.classList.add('show');
  clearTimeout(t._tid);
  t._tid = setTimeout(() => t.classList.remove('show'), 1800);
}

function dbToggleSlot(dk, refIdx) {
  const idx = _dbOpenDecks.findIndex(s => s.deck === dk && s.refIdx === refIdx);
  if (idx >= 0) {
    _dbOpenDecks.splice(idx, 1);
  } else {
    if (_dbOpenDecks.length >= 3) { _dbShowCapToast(); return; }
    _dbOpenDecks.push({ deck: dk, refIdx: refIdx });
  }
  _dbRefreshAll();
}

function dbCloseSlot(slotIdx) {
  if (slotIdx >= 0 && slotIdx < _dbOpenDecks.length) {
    _dbOpenDecks.splice(slotIdx, 1);
    _dbRefreshAll();
  }
}

function dbToggleInk(ink) {
  if (_dbInkFilter.has(ink)) _dbInkFilter.delete(ink);
  else _dbInkFilter.add(ink);
  _dbRefreshAll();
}

function dbSetRank(rank) {
  _dbRankFilter = (_dbRankFilter === rank) ? '' : rank;
  _dbRefreshAll();
}

function dbClearFilters() {
  _dbInkFilter.clear();
  _dbRankFilter = '';
  _dbDateFilter = '';
  _dbEventSearch = '';
  const search = document.getElementById('db-event-search');
  if (search) search.value = '';
  _dbRefreshAll();
}

function dbCopyDeck(dk, idx) {
  const refs = DATA.reference_decklists || {};
  const consensus = DATA.consensus || {};
  const refList = refs[dk] || [];
  const ref = refList[idx || 0];
  let text = '';
  if (ref && ref.cards) {
    text = ref.cards.map(c => `${c.qty} ${c.name}`).join('\n');
  } else if (consensus[dk]) {
    text = Object.entries(consensus[dk]).sort((a,b) => b[1]-a[1]).map(([n,q]) => `${Math.round(q)} ${n}`).join('\n');
  }
  if (text) {
    navigator.clipboard.writeText(text);
    const btn = document.getElementById('db-copy-' + dk);
    if (btn) { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy', 1500); }
  }
}

function _dbRefreshAll() {
  const pillsEl = document.getElementById('db-deck-pills');
  if (pillsEl) pillsEl.innerHTML = buildDeckBrowser__pills();
  const mount = document.getElementById('db-browser-content');
  if (mount) mount.innerHTML = _dbRenderCards();
  document.querySelectorAll('.db-deck-pill').forEach(p => {
    const rIdx = parseInt(p.dataset.ref, 10);
    p.classList.toggle('active', _dbOpenDecks.some(s => s.deck === p.dataset.dk && s.refIdx === rIdx));
  });
  document.querySelectorAll('.db-ink-btn').forEach(b => {
    b.classList.toggle('selected', _dbInkFilter.has(b.dataset.ink));
  });
  document.querySelectorAll('.db-rank-btn[data-rank]').forEach(b => {
    b.classList.toggle('active', b.dataset.rank === _dbRankFilter);
  });
  document.querySelectorAll('.db-rank-btn[data-date]').forEach(b => {
    b.classList.toggle('active', b.dataset.date === _dbDateFilter);
  });
}

function _dbRefMatchesFilters(r) {
  // Rank filter
  if (_dbRankFilter) {
    const allowed = _DB_RANK_GROUPS[_dbRankFilter] || [];
    if (!allowed.includes(r.rank)) return false;
  }
  // Date filter
  const cutoff = _dbDateCutoff();
  if (cutoff) {
    if (!r.event_date || r.event_date < cutoff) return false;
  }
  // Event name search
  if (_dbEventSearch) {
    const haystack = `${r.event || ''} ${r.player || ''}`.toLowerCase();
    if (!haystack.includes(_dbEventSearch)) return false;
  }
  return true;
}

// Returns list of {deck, refIdx, ref} — one entry per pickable variant.
// refIdx = -1 means consensus; otherwise index into reference_decklists[deck].
// Returns empty list when no filter is active (ink/rank/date/search) — the user
// must pick at least one filter to see decks. Prevents flooding with ~90+ pills.
function _dbGetFilteredVariants() {
  const hasAnyFilter = _dbInkFilter.size || _dbRankFilter || _dbDateFilter || _dbEventSearch;
  if (!hasAnyFilter) return [];
  const refs = DATA.reference_decklists || {};
  const consensus = DATA.consensus || {};
  const allDecks = [...new Set([...Object.keys(refs), ...Object.keys(consensus)])].sort();
  const hasRefFilter = _dbRankFilter || _dbDateFilter || _dbEventSearch;
  const out = [];
  for (const dk of allDecks) {
    if (_dbInkFilter.size) {
      const inks = DECK_INKS[dk] || [];
      if (![..._dbInkFilter].every(f => inks.includes(f))) continue;
    }
    if (!hasRefFilter && consensus[dk]) {
      out.push({ deck: dk, refIdx: -1, ref: null });
    }
    const refList = refs[dk] || [];
    for (let i = 0; i < refList.length; i++) {
      if (hasRefFilter && !_dbRefMatchesFilters(refList[i])) continue;
      out.push({ deck: dk, refIdx: i, ref: refList[i] });
    }
  }
  return out;
}

function _dbGetFilteredDecks() {
  const refs = DATA.reference_decklists || {};
  const consensus = DATA.consensus || {};
  const allDecks = [...new Set([...Object.keys(refs), ...Object.keys(consensus)])].sort();
  const hasRefFilter = _dbRankFilter || _dbDateFilter || _dbEventSearch;
  return allDecks.filter(dk => {
    // Ink filter (deck-level)
    if (_dbInkFilter.size) {
      const inks = DECK_INKS[dk] || [];
      if (![..._dbInkFilter].every(f => inks.includes(f))) return false;
    }
    // Ref-level filters: deck must have at least one ref matching all active filters
    if (hasRefFilter) {
      const refList = refs[dk] || [];
      if (!refList.some(_dbRefMatchesFilters)) return false;
    }
    return true;
  });
}

function _dbEnsureCardsDB() {
  if (rvCardsDB) return;
  fetch('/api/replay/cards_db').then(r => r.json()).then(db => {
    rvCardsDB = db;
    _dbRefreshAll();
  }).catch(() => {});
}

function _dbBuildGallery(cards) {
  return cards.map(c => {
    const imgUrl = rvCardsDB ? rvCardImgByName(c.name) : '';
    const shortName = c.name.includes(' - ') ? c.name.split(' - ')[0] : c.name;
    const safeName = _bpEsc(c.name);
    const safeShort = _bpEsc(shortName.length > 18 ? shortName.slice(0,16) + '..' : shortName);
    const art = imgUrl
      ? `<img src="${imgUrl}" alt="${safeName}" loading="lazy">`
      : `<div class="pf-std-vph">${safeShort}</div>`;
    const zoom = imgUrl ? ` data-zoom="${imgUrl}"` : '';
    return `<div class="pf-std-vcard">
      <div class="pf-std-vart"${zoom} onclick="if(this.dataset.zoom)pfZoomCard(this)" title="${safeName}">
        ${art}<span class="pf-std-vqty">${c.qty}x</span>
      </div>
      <div class="pf-std-vname">${safeShort}</div>
    </div>`;
  }).join('');
}

const _dbSelRef = {};

function dbPickRef(dk, idx) {
  _dbSelRef[dk] = idx;
  _dbRefreshAll();
}

function _dbRenderCards() {
  if (!_dbOpenDecks.length) return '<div style="color:var(--text2);font-size:0.85em;padding:16px 0;text-align:center">Select up to 3 decks to compare side by side.</div>';
  const refs = DATA.reference_decklists || {};
  const consensus = DATA.consensus || {};

  let html = '<div class="db-decks-row">';
  for (let i = 0; i < _dbOpenDecks.length; i++) {
    const slot = _dbOpenDecks[i];
    const dk = slot.deck;
    const refList = refs[dk] || [];
    const std = consensus[dk] || {};
    const inks = DECK_INKS[dk] || [];
    const dots = inks.map(ink => `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${INK_COLORS[ink]};vertical-align:middle"></span>`).join(' ');

    const ref = slot.refIdx >= 0 ? refList[slot.refIdx] : null;
    let cards = [];
    let sourceLabel = '';
    let variantChip = '';

    if (ref && ref.cards && ref.cards.length) {
      cards = ref.cards.map(c => ({ name: c.name, qty: c.qty }));
      const eventShort = (ref.event || '').split('@')[0].trim().substring(0, 30);
      const playerShort = (ref.player || '?').split(' ')[0];
      variantChip = `<span class="db-variant-chip">${_bpEsc(playerShort)} · ${_bpEsc(ref.rank || '?')}</span>`;
      sourceLabel = `<div class="db-source">${_bpEsc(ref.player || '?')} · <strong>${_bpEsc(ref.rank || '?')}</strong></div>
        <div class="db-event">${_bpEsc(eventShort)}</div>
        ${ref.record ? `<div class="db-event">${ref.record}${ref.event_date ? ' · ' + ref.event_date : ''}</div>` : ''}`;
    } else {
      cards = Object.entries(std).sort((a,b) => b[1]-a[1]).map(([n,q]) => ({ name: n, qty: Math.round(q) }));
      variantChip = `<span class="db-variant-chip db-variant-chip--consensus">Consensus</span>`;
      sourceLabel = '<div class="db-source">Consensus average</div>';
    }

    const totalCards = cards.reduce((s,c) => s + c.qty, 0);

    html += `<div class="db-deck-card">
      <div class="db-deck-hdr">
        <span class="db-deck-name">${dots} ${dk} ${variantChip}</span>
        <span class="db-deck-total">${totalCards} cards</span>
        <button class="db-deck-close" onclick="dbCloseSlot(${i})" title="Remove">&times;</button>
      </div>
      ${sourceLabel}
      <div class="pf-std-list"><div class="pf-std-gallery">${_dbBuildGallery(cards)}</div></div>
      <div class="db-deck-footer">
        <button class="db-copy-btn" id="db-copy-slot-${i}" onclick="dbCopySlot(${i})">Copy</button>
      </div>
    </div>`;
  }
  html += '</div>';
  return html;
}

function dbCopySlot(slotIdx) {
  const slot = _dbOpenDecks[slotIdx];
  if (!slot) return;
  const refs = DATA.reference_decklists || {};
  const consensus = DATA.consensus || {};
  const refList = refs[slot.deck] || [];
  const ref = slot.refIdx >= 0 ? refList[slot.refIdx] : null;
  let text = '';
  if (ref && ref.cards) {
    text = ref.cards.map(c => `${c.qty} ${c.name}`).join('\n');
  } else if (consensus[slot.deck]) {
    text = Object.entries(consensus[slot.deck]).sort((a,b) => b[1]-a[1]).map(([n,q]) => `${Math.round(q)} ${n}`).join('\n');
  }
  if (text) {
    navigator.clipboard.writeText(text);
    const btn = document.getElementById('db-copy-slot-' + slotIdx);
    if (btn) { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy', 1500); }
  }
}

// Resolve a {deck, refIdx} slot to a full card list (from ref.cards or consensus)
function _dbSlotCards(slot) {
  const refs = DATA.reference_decklists || {};
  const consensus = DATA.consensus || {};
  if (slot.refIdx >= 0) {
    const r = (refs[slot.deck] || [])[slot.refIdx];
    if (r && r.cards && r.cards.length) return r.cards.map(c => ({ name: c.name, qty: c.qty }));
  }
  return _ldcNormalizeTo60(consensus[slot.deck] || {});
}

function _dbSlotLabel(slot) {
  if (slot.refIdx >= 0) {
    const ref = ((DATA.reference_decklists || {})[slot.deck] || [])[slot.refIdx];
    if (ref) return `${_bpEsc(ref.player || '?')} · ${_bpEsc(ref.rank || '?')}`;
  }
  return 'Consensus';
}

// Comparator overlay: base (user's current deck — custom list or consensus) on top,
// diff (adds/cuts) for every cart slot below. Base is NOT a cart slot; it is pulled
// from the user's active deck (coachDeck || selectedDeck), same rule as the ldc flow.
function _dbRenderCompareDiff() {
  const baseDeckCode = (typeof coachDeck !== 'undefined' && coachDeck)
    || (typeof selectedDeck !== 'undefined' && selectedDeck)
    || null;
  if (!baseDeckCode) return '<div class="db-pills-empty">Pick a deck on the Home or Deck tab first, then come back here to compare.</div>';
  const base = _ldcBaseDeck(baseDeckCode);
  if (!base.cards.length) return '<div class="db-pills-empty">No base list available for this deck yet.</div>';
  const baseTotal = base.cards.reduce((s, c) => s + c.qty, 0);
  const baseInks = DECK_INKS[baseDeckCode] || [];
  const baseDots = baseInks.map(i => `<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${INK_COLORS[i]};vertical-align:middle"></span>`).join(' ');
  const baseCopy = encodeURIComponent(_ldcDeckText(base.cards));
  const baseCard = `<div class="ldc-card base">
    <div class="ldc-top">
      <div><div class="ldc-title">${baseDots} ${baseDeckCode}</div><div class="ldc-sub">Base — ${_bpEsc(base.label)} · ${_bpEsc(base.sub)}</div></div>
      <div class="ldc-total">${baseTotal}/60</div>
    </div>
    <div class="ldc-base-list"><div class="ldc-base-grid">${_ldcGallery(base.cards, { badgeMode: 'qty', baseClass: 'base' })}</div></div>
    <div class="ldc-copy-row"><button class="db-copy-btn" data-copy="${baseCopy}" onclick="_ldcCopy(this.dataset.copy, this)">Copy</button></div>
  </div>`;

  const baseCards = base.cards;
  const diffCards = _dbOpenDecks.map(slot => {
    const cards = _dbSlotCards(slot);
    const total = cards.reduce((s, c) => s + c.qty, 0);
    const diff = _ldcDiff(baseCards, cards);
    const addTotal = diff.added.reduce((s, c) => s + c.qty, 0);
    const cutTotal = diff.cut.reduce((s, c) => s + c.qty, 0);
    const addHtml = diff.added.length
      ? `<div class="ldc-delta-grid">${_ldcGallery(diff.added, { badgeMode: 'add' })}</div>`
      : '<div class="ldc-delta-empty">No adds vs base</div>';
    const cutHtml = diff.cut.length
      ? `<div class="ldc-delta-grid">${_ldcGallery(diff.cut, { badgeMode: 'cut' })}</div>`
      : '<div class="ldc-delta-empty">No cuts vs base</div>';
    const inks = DECK_INKS[slot.deck] || [];
    const dots = inks.map(ik => `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${INK_COLORS[ik]};vertical-align:middle"></span>`).join(' ');
    const copyData = encodeURIComponent(_ldcDeckText(cards));
    return `<div class="ldc-card">
      <div class="ldc-top">
        <div><div class="ldc-title">${dots} ${slot.deck}</div><div class="ldc-sub">${_dbSlotLabel(slot)}</div></div>
        <div class="ldc-total">${total}/60</div>
      </div>
      <div class="ldc-delta-block">
        <div class="ldc-delta-section">
          <div class="ldc-delta-head add"><span>Adds</span><span>+${addTotal}</span></div>
          ${addHtml}
        </div>
        <div class="ldc-delta-section">
          <div class="ldc-delta-head cut"><span>Cuts</span><span>-${cutTotal}</span></div>
          ${cutHtml}
        </div>
      </div>
      <div class="ldc-actions">
        <button class="db-copy-btn" data-copy="${copyData}" onclick="_ldcCopy(this.dataset.copy, this)">Copy</button>
      </div>
    </div>`;
  }).join('');

  return `<div class="ldc-wrap">
    <div class="ldc-summit">${baseCard}</div>
    <div class="ldc-row">${diffCards || '<div class="ldc-empty">Close and pick decks from the browser to see adds/cuts vs your base.</div>'}</div>
  </div>`;
}

function buildDeckBrowser() {
  if (!DATA || !DATA.consensus) return '';
  _dbEnsureCardsDB();
  const refs = DATA.reference_decklists || {};
  const consensus = DATA.consensus || {};
  const allDecks = [...new Set([...Object.keys(refs), ...Object.keys(consensus)])].sort();
  if (!allDecks.length) return '';

  // Ink filter buttons
  const inkOrder = ['amber','amethyst','emerald','ruby','sapphire','steel'];
  const inkBtns = inkOrder.map(ink => {
    const sel = _dbInkFilter.has(ink) ? ' selected' : '';
    return `<div class="ink-icon-wrap db-ink-btn${sel}" data-ink="${ink}" onclick="dbToggleInk('${ink}')" title="${ink}">
      ${INK_SVGS[ink]}
    </div>`;
  }).join('');

  // Filtered variant pills (one pill per deck variant)
  const variants = _dbGetFilteredVariants();
  const deckPills = variants.map(v => {
    const inCart = _dbOpenDecks.some(s => s.deck === v.deck && s.refIdx === v.refIdx);
    const inks = DECK_INKS[v.deck] || [];
    const dots = inks.map(i => `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${INK_COLORS[i]}"></span>`).join(' ');
    const sub = v.ref
      ? `<span class="db-pill-sub">${_bpEsc((v.ref.player || '?').split(' ')[0])} · ${_bpEsc(v.ref.rank || '?')}</span>`
      : `<span class="db-pill-sub db-pill-sub--consensus">Consensus</span>`;
    return `<button class="db-deck-pill${inCart ? ' active' : ''}" data-dk="${v.deck}" data-ref="${v.refIdx}" onclick="dbToggleSlot('${v.deck}', ${v.refIdx})">${dots} <span class="db-pill-name">${v.deck}</span> ${sub}</button>`;
  }).join('') || '<div class="db-pills-empty">Pick inks, rank, or date above to browse decks.</div>';

  // Rank filter buttons
  const rankBtns = ['winner','top4','top8','top16'].map(r => {
    const active = _dbRankFilter === r ? ' active' : '';
    const label = {winner:'Winner',top4:'Top 4',top8:'Top 8',top16:'Top 16'}[r];
    return `<button class="db-rank-btn${active}" data-rank="${r}" onclick="dbSetRank('${r}')">${label}</button>`;
  }).join('');

  // Date filter buttons
  const dateBtns = [
    { k: '3d',  label: 'Last 3d' },
    { k: '7d',  label: 'Last week' },
    { k: '30d', label: 'Last month' },
  ].map(d => {
    const active = _dbDateFilter === d.k ? ' active' : '';
    return `<button class="db-rank-btn${active}" data-date="${d.k}" onclick="dbSetDate('${d.k}')">${d.label}</button>`;
  }).join('');

  const body = `
    <div class="db-filter-group">
      <span class="db-filter-label">Ink</span>
      <div class="db-ink-filter">${inkBtns}</div>
    </div>
    <div class="db-filter-group">
      <span class="db-filter-label">Rank</span>
      <div class="db-rank-filter">${rankBtns}</div>
    </div>
    <div class="db-filter-group">
      <span class="db-filter-label">Date</span>
      <div class="db-rank-filter">${dateBtns}</div>
    </div>
    <div class="db-filter-group">
      <span class="db-filter-label">Search</span>
      <input id="db-event-search" class="db-event-search" type="search" placeholder="Event or player name"
             value="${_bpEsc(_dbEventSearch)}" oninput="dbSetEventSearch(this.value)">
      <button class="db-clear-filter" onclick="dbClearFilters()">Clear filters</button>
    </div>
    <div class="db-pills" id="db-deck-pills">${deckPills}</div>
    <div id="db-browser-content">${_dbRenderCards()}</div>`;

  return body;
}

// Helper to rebuild just the pills (after filter change)
function buildDeckBrowser__pills() {
  const variants = _dbGetFilteredVariants();
  return variants.map(v => {
    const inCart = _dbOpenDecks.some(s => s.deck === v.deck && s.refIdx === v.refIdx);
    const inks = DECK_INKS[v.deck] || [];
    const dots = inks.map(i => `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${INK_COLORS[i]}"></span>`).join(' ');
    const sub = v.ref
      ? `<span class="db-pill-sub">${_bpEsc((v.ref.player || '?').split(' ')[0])} · ${_bpEsc(v.ref.rank || '?')}</span>`
      : `<span class="db-pill-sub db-pill-sub--consensus">Consensus</span>`;
    return `<button class="db-deck-pill${inCart ? ' active' : ''}" data-dk="${v.deck}" data-ref="${v.refIdx}" onclick="dbToggleSlot('${v.deck}', ${v.refIdx})">${dots} <span class="db-pill-name">${v.deck}</span> ${sub}</button>`;
  }).join('') || '<div class="db-pills-empty">Pick inks, rank, or date above to browse decks.</div>';
}

const _ldcCache = {};
const _ldcSel = {};
const _ldcExpanded = {};

function _ldcNormalizeTo60(consensus) {
  const entries = Object.entries(consensus || {}).map(([name, qty]) => {
    const raw = Number(qty) || 0;
    const floor = Math.floor(raw);
    return { name, raw, floor, frac: raw - floor };
  }).filter(x => x.raw > 0);
  if (!entries.length) return [];

  let total = entries.reduce((sum, x) => sum + x.floor, 0);
  let delta = 60 - total;

  if (delta > 0) {
    entries.sort((a, b) => b.frac - a.frac || a.name.localeCompare(b.name));
    for (let i = 0; i < entries.length && delta > 0; i++, delta--) entries[i].floor += 1;
  } else if (delta < 0) {
    entries.sort((a, b) => a.frac - b.frac || a.name.localeCompare(b.name));
    for (let i = 0; i < entries.length && delta < 0; i++) {
      if (entries[i].floor > 0) {
        entries[i].floor -= 1;
        delta += 1;
      }
    }
  }

  return entries
    .filter(x => x.floor > 0)
    .sort((a, b) => b.floor - a.floor || a.name.localeCompare(b.name))
    .map(x => ({ name: x.name, qty: x.floor }));
}

function _ldcBaseDeck(deckCode) {
  if (myDeckMode === 'custom' && myDeckCards) {
    const cards = Object.entries(myDeckCards).map(([name, qty]) => ({ name, qty }));
    return { label: 'My Deck', sub: 'Saved personal list', cards };
  }
  const consensus = (DATA.consensus || {})[deckCode] || {};
  const cards = _ldcNormalizeTo60(consensus);
  return { label: 'Consensus', sub: 'Current standard reference', cards };
}

function _ldcCardDict(cards) {
  const out = {};
  (cards || []).forEach(c => { out[c.name] = c.qty; });
  return out;
}

function _ldcDiff(baseCards, refCards) {
  const base = _ldcCardDict(baseCards);
  const ref = _ldcCardDict(refCards);
  const added = [];
  const cut = [];
  Object.entries(ref).forEach(([name, qty]) => {
    const delta = qty - (base[name] || 0);
    if (delta > 0) added.push({ name, qty: delta });
  });
  Object.entries(base).forEach(([name, qty]) => {
    const delta = qty - (ref[name] || 0);
    if (delta > 0) cut.push({ name, qty: delta });
  });
  added.sort((a, b) => b.qty - a.qty || a.name.localeCompare(b.name));
  cut.sort((a, b) => b.qty - a.qty || a.name.localeCompare(b.name));
  return { added, cut };
}

function _ldcDeckText(cards) {
  return (cards || []).map(c => `${c.qty} ${c.name}`).join('\n');
}

function _ldcGallery(cards, opts = {}) {
  const {
    badgeMode = 'qty',
    baseClass = '',
    emptyText = '',
  } = opts;
  if (!cards || !cards.length) return emptyText || '';
  return cards.map(c => {
    const imgUrl = rvCardsDB ? rvCardImgByName(c.name) : '';
    const shortName = c.name.includes(' - ') ? c.name.split(' - ')[0] : c.name;
    const safeName = _bpEsc(c.name);
    const safeShort = _bpEsc(shortName.length > 18 ? shortName.slice(0, 16) + '..' : shortName);
    const art = imgUrl
      ? `<img src="${imgUrl}" alt="${safeName}" loading="lazy">`
      : `<div class="ldc-vph">${safeShort}</div>`;
    const zoom = imgUrl ? ` data-zoom="${imgUrl}"` : '';
    let badgeCls = 'qty';
    let badgeLabel = `${c.qty}x`;
    if (badgeMode === 'add') {
      badgeCls = 'add';
      badgeLabel = `+${c.qty}`;
    } else if (badgeMode === 'cut') {
      badgeCls = 'cut';
      badgeLabel = `-${c.qty}`;
    }
    return `<div class="ldc-vcard${baseClass ? ` ${baseClass}` : ''}">
      <div class="ldc-vart"${zoom} onclick="if(this.dataset.zoom)pfZoomCard(this)" title="${safeName}">
        ${art}
        <span class="ldc-badge-corner ${badgeCls}">${badgeLabel}</span>
      </div>
      <div class="ldc-vname">${safeShort}</div>
    </div>`;
  }).join('');
}

function _ldcCopy(encoded, btn) {
  const text = decodeURIComponent(encoded || '');
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    if (!btn) return;
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = orig, 1500);
  });
}

async function ldcLoad(deckCode) {
  const wrap = document.getElementById('ldc-wrap');
  if (!wrap || !deckCode) return;
  const key = `${deckCode}`;
  if (_ldcCache[key]) { ldcRender(deckCode, _ldcCache[key]); return; }
  wrap.innerHTML = '<div class="ldc-empty">Loading tournament lists…</div>';
  try {
    const resp = await fetch(`/api/v1/lab/tournament-lists/${encodeURIComponent(deckCode)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    _ldcCache[key] = data;
    ldcRender(deckCode, data);
  } catch (e) {
    wrap.innerHTML = `<div class="ldc-empty">Tournament lists unavailable (${String(e).slice(0, 60)}).</div>`;
  }
}

function ldcPick(deckCode, idx) {
  _ldcSel[deckCode] = idx;
  const data = _ldcCache[deckCode];
  if (data) ldcRender(deckCode, data);
}

function ldcToggleExpand(deckCode, idx) {
  const key = `${deckCode}:${idx}`;
  _ldcExpanded[key] = !_ldcExpanded[key];
  const data = _ldcCache[deckCode];
  if (data) ldcRender(deckCode, data);
}

function ldcRender(deckCode, data) {
  const wrap = document.getElementById('ldc-wrap');
  if (!wrap) return;
  const lists = (data && data.lists) ? data.lists.slice(0, 4) : [];
  const base = _ldcBaseDeck(deckCode);
  if (!base.cards.length) {
    wrap.innerHTML = '<div class="ldc-empty">No base deck available for comparison.</div>';
    return;
  }
  if (!lists.length) {
    wrap.innerHTML = '<div class="ldc-empty">No tournament lists available for this deck in the latest snapshot.</div>';
    return;
  }

  const baseCard = `<div class="ldc-card base">
    <div class="ldc-top">
      <div>
        <div class="ldc-title">${base.label}</div>
        <div class="ldc-sub">${base.sub}</div>
      </div>
      <div class="ldc-total">${base.cards.reduce((s, c) => s + c.qty, 0)}/60</div>
    </div>
    <div class="ldc-base-list"><div class="ldc-base-grid">${_ldcGallery(base.cards, { badgeMode: 'qty', baseClass: 'base' })}</div></div>
    <div class="ldc-copy-row"><button class="db-copy-btn" data-copy="${encodeURIComponent(_ldcDeckText(base.cards))}" onclick="_ldcCopy(this.dataset.copy, this)">Copy</button></div>
  </div>`;

  const refCards = lists.map((item, idx) => {
    const cards = (item.cards || []).map(c => ({ name: c.name, qty: c.qty }));
    const diff = _ldcDiff(base.cards, cards);
    const addTotal = diff.added.reduce((sum, c) => sum + (c.qty || 0), 0);
    const cutTotal = diff.cut.reduce((sum, c) => sum + (c.qty || 0), 0);
    const expanded = !!_ldcExpanded[`${deckCode}:${idx}`];
    const addHtml = diff.added.length
      ? `<div class="ldc-delta-grid">${_ldcGallery(diff.added, { badgeMode: 'add' })}</div>`
      : '<div class="ldc-delta-empty">No adds vs base</div>';
    const cutHtml = diff.cut.length
      ? `<div class="ldc-delta-grid">${_ldcGallery(diff.cut, { badgeMode: 'cut' })}</div>`
      : '<div class="ldc-delta-empty">No cuts vs base</div>';
    const expandHtml = expanded
      ? `<div class="ldc-expand"><div class="pf-std-gallery">${_dbBuildGallery(cards)}</div></div>`
      : '';
    return `<div class="ldc-card">
      <div class="ldc-top">
        <div>
          <div class="ldc-title">${_bpEsc(item.player || '?')}</div>
          <div class="ldc-sub">${_bpEsc(item.rank || '?')} · ${_bpEsc((item.event || '').substring(0, 28) || 'Tournament list')}</div>
        </div>
        <div class="ldc-total">${cards.reduce((s, c) => s + c.qty, 0)}/60</div>
      </div>
      <div class="ldc-delta-block">
        <div class="ldc-delta-section">
          <div class="ldc-delta-head add"><span>Adds</span><span>+${addTotal}</span></div>
          ${addHtml}
        </div>
        <div class="ldc-delta-section">
          <div class="ldc-delta-head cut"><span>Cuts</span><span>-${cutTotal}</span></div>
          ${cutHtml}
        </div>
      </div>
      <div class="ldc-actions">
        <button class="ldc-mini-btn" onclick="ldcToggleExpand('${deckCode}', ${idx})">${expanded ? 'Hide List' : 'Expand'}</button>
        <button class="db-copy-btn" data-copy="${encodeURIComponent(_ldcDeckText(cards))}" onclick="_ldcCopy(this.dataset.copy, this)">Copy</button>
      </div>
      ${expandHtml}
    </div>`;
  }).join('');

  wrap.innerHTML = `<div class="ldc-wrap">
    <div class="ldc-header">
      <strong>${deckCode}</strong>
      <span class="ldc-source-pill">${_bpEsc(data.source || 'snapshot')}</span>
      <span class="ldc-summary">${lists.length} tournament lists</span>
    </div>
    <div class="ldc-summit">
      ${baseCard}
    </div>
    <div class="ldc-row">
      ${refCards}
    </div>
  </div>`;
}

function buildLabDeckComparator(deckCode) {
  if (!deckCode) return '';
  return `<div class="section">
    ${monAccordion('acc-ldc', 'Deck Comparator', '', '<div id="ldc-wrap" class="ldc-empty">Loading comparator…</div>', {
      desktopOpen: true,
      onOpen: () => ldcLoad(deckCode),
      info: { title: 'About Deck Comparator', body: '<p>Compare your current base list against tournament reference lists from the latest inkdecks snapshot.</p><p><strong>Base</strong> = your saved deck if enabled, otherwise the current consensus list.</p><p>Green badges show additions vs base, red badges show cuts.</p>' }
    })}
  </div>`;
}

/**
 * Mulligan Trainer accordion — estratto da renderLabTab il 22/04 (V3-5 P0).
 * Ora renderizzato primariamente in Play (coach_v2.js renderCoachV2Tab).
 * Resta esposto globalmente via window per permettere ad altri moduli di chiamarlo.
 *
 * @param {Array} proMulls - mu.pro_mulligans dal matchup corrente
 * @returns {string} HTML stringa (accordion con carousel) o '' se nessun dato
 */
function buildMulliganTrainer(proMulls) {
  if (!proMulls || proMulls.length === 0) return '';
  const mullBody = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap">
      <div class="mull-filter" id="mull-filter">
        <button class="mf-btn active" data-f="blind" onclick="setMullFilter('blind')">Blind</button>
        <button class="mf-btn" data-f="otp" onclick="setMullFilter('otp')">OTP</button>
        <button class="mf-btn" data-f="otd" onclick="setMullFilter('otd')">OTD</button>
      </div>
      <span id="mull-counter" style="font-size:0.85em;color:var(--text2)"></span>
      <div style="display:flex;gap:4px;margin-left:auto">
        <button onclick="mullNav(-1)" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:1.1em">&#9664;</button>
        <button onclick="mullNav(1)" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:1.1em">&#9654;</button>
      </div>
    </div>
    <div class="card" style="padding:20px">
      <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">
        <span id="mull-player" style="font-weight:600;font-size:1.05em"></span>
        <span id="mull-otp-badge" style="font-size:0.8em;padding:3px 10px;border-radius:6px;font-weight:600"></span>
        <span id="mull-result" style="font-weight:700;font-size:1.1em"></span>
      </div>
      <div id="mull-cards" class="mull-hand"></div>
      <div id="mull-reveal-area"></div>
    </div>
    <div id="mull-data-holder" data-mulls='${JSON.stringify(proMulls).replace(/'/g, "&#39;")}'></div>`;
  return `<div class="section">
    ${monAccordion('acc-mull', 'Mulligan Trainer', '', mullBody, {
      desktopOpen: true,
      info: { title: 'About Mulligan Trainer', body: '<p>Real opening hands from <strong>PRO players</strong> in this matchup.</p><p>Tap cards you would mulligan, then reveal to compare with the PRO\\u2019s actual decision and the game outcome.</p><p>• <strong>Blind</strong>: G1 of Bo3 (unknown matchup)</p><p>• <strong>OTP</strong>: G2/G3 when on the play</p><p>• <strong>OTD</strong>: G2/G3 when on the draw</p>' }
    })}
  </div>`;
}

function renderLabTab(main) {
  const az = getAnalyzerData();
  const deckWorkspace = typeof pfBuildDeckWorkspace === 'function' ? pfBuildDeckWorkspace() : '';
  const labDeck = coachDeck || selectedDeck;
  const deckComparator = buildLabDeckComparator(labDeck);
  const deckBrowser = buildDeckBrowser();
  const matchups = (az[coachDeck]||{}).available_matchups || [];
  if (!labOpp || !matchups.includes(labOpp)) {
    labOpp = matchups[0] || null;
    syncOppInksFromDeck(labOpp);
  }

  const selectorHtml = buildMatchupSelector('lab');

  // PR2 + PR3: build Summary and Improve BEFORE the matchup-data early returns
  // so the user always sees the above-the-fold (even when no opp has matchup
  // reports yet). Both modules handle opp=null gracefully.
  // See docs/DECK_REFACTOR_PARITY.md rows 1-11, 14, 16-18, 20, 46.
  const _deckSummaryHtml = (coachDeck && window.V3 && window.V3.DeckSummary)
    ? window.V3.DeckSummary.build(coachDeck, labOpp)
    : '';
  const _deckImproveHtml = (coachDeck && window.V3 && window.V3.DeckImprove)
    ? window.V3.DeckImprove.build(coachDeck, labOpp)
    : '';

  if (!az[coachDeck] || !labOpp) {
    main.innerHTML = _deckSummaryHtml
      + selectorHtml
      + _deckImproveHtml
      + deckWorkspace
      + deckComparator
      + deckBrowser
      + `<div class="section"><div class="section-title">Matchup Prep</div><div class="coming-soon-card"><div class="lock-emoji">🔒</div><h3>Coming Soon</h3><p>Select opponent using the ink icons above.</p></div></div>`;
    return;
  }

  const mu = getMatchupData(labOpp);
  if (!mu) {
    main.innerHTML = _deckSummaryHtml
      + selectorHtml
      + _deckImproveHtml
      + deckWorkspace
      + deckComparator
      + deckBrowser
      + `<div class="section"><div class="section-title">Matchup Prep</div><div class="coming-soon-card"><div class="lock-emoji">📊</div><h3>Data not available</h3></div></div>`;
    return;
  }

  const dl = mu.decklist || {};
  const wh = mu.winning_hands || {};
  const cs = mu.card_scores || {};

  // Lab base mode syncs with global myDeckMode
  labBaseMode = (myDeckMode === 'custom' && myDeckCards) ? 'personal' : 'standard';

  // PR7 cleanup: right-column "Optimized Deck" panel and replay CTA
  // removed. Their surfaces are now reached from the Matchup Workspace
  // (PR5 → Card optimization section and footer CTA).

  // === ASSEMBLE ===
  // Summary + Improve already built above early-return guards. Fallback to
  // legacy hero+visuals if DeckSummary module is absent (progressive load).
  const summaryHtml = _deckSummaryHtml || ((window.V3 && window.V3.DeckOverview)
    ? window.V3.DeckOverview.buildHero(coachDeck)
      + (window.V3.DeckOverview.buildVisuals ? window.V3.DeckOverview.buildVisuals(coachDeck, labOpp) : '')
    : '');
  const improveHtml = _deckImproveHtml;

  // Area C Matchups (PR4) — compact heatmap. Tap a row sets labOpp.
  const matchupsHtml = (coachDeck && window.V3 && window.V3.DeckMatchups)
    ? window.V3.DeckMatchups.build(coachDeck, labOpp)
    : '';

  let content = summaryHtml + selectorHtml + improveHtml + matchupsHtml;

  // Area D Your list (PR4) — collapsed container for deck grid + lens +
  // builder panel, with header buttons View list / Edit deck / Compare to pros.
  // Replaces the always-visible Tournament Decks button + deck-lab-layout.
  if (window.V3 && window.V3.DeckListView) {
    content += window.V3.DeckListView.build(coachDeck, labOpp);
  } else {
    // Legacy fallback (pre-PR4): flat layout without collapse.
    content += `<div class="td-btn-row">
      <button class="td-open-btn" type="button" onclick="openTournamentDecks()" aria-label="Open Tournament Decks panel" title="Tournament decklists & comparator">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/></svg>
        <span>Tournament Decks</span>
      </button>
    </div>`;
    const inEditLegacy = !!(window.V3 && window.V3.Builder && window.V3.Builder.editMode);
    const gridLegacy = (window.V3 && window.V3.DeckGrid)
      ? window.V3.DeckGrid.buildGrid(coachDeck, labOpp) : '';
    const builderLegacy = (inEditLegacy && window.V3.Builder)
      ? window.V3.Builder.buildPanel(coachDeck) : '';
    const lensLegacy = (window.V3 && window.V3.DeckLens)
      ? window.V3.DeckLens.build(coachDeck, labOpp) : '';
    if (gridLegacy) {
      const lensWrap = lensLegacy ? `<div class="deck-lab-lens">${lensLegacy}</div>` : '';
      if (inEditLegacy) {
        content += `<div class="deck-lab-layout deck-lab-layout--edit">
          <div class="deck-lab-main">${gridLegacy}</div>
          ${lensWrap}
          <div class="deck-lab-side">${builderLegacy}</div>
        </div>`;
      } else if (lensLegacy) {
        content += `<div class="deck-lab-layout">
          <div class="deck-lab-main">${gridLegacy}</div>
          ${lensWrap}
        </div>`;
      } else {
        content += gridLegacy;
      }
    }
  }

  // PR7 cleanup: Response coverage inline, Matchup-optimized accordion,
  // Optimized Deck panel, and replay CTA are all absorbed by the Matchup
  // Workspace (PR5) and the Summary mini-block (PR2). Removed from the
  // always-on render path to eliminate the legacy scroll tail.

  // Deck Browser modal (fullscreen) + inner Comparator overlay (layer 2).
  content += `<aside class="td-drawer" id="td-drawer" role="dialog" aria-label="Deck Browser" aria-hidden="true">
    <header class="td-drawer-hdr">
      <h2>Deck Browser</h2>
      <div class="td-drawer-hdr-actions">
        <button class="td-compare-btn" type="button" onclick="openDeckCompare()" aria-label="Open Comparator">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7h12M8 7l-4 4M8 7l-4-4M16 17H4M16 17l4 4M16 17l4-4"/></svg>
          <span>Comparator</span>
        </button>
        <button class="td-close-btn" onclick="closeTournamentDecks()" aria-label="Close">&times;</button>
      </div>
    </header>
    <div class="td-drawer-body">
      <div class="td-drawer-hint">Pick up to <strong>3</strong> decks to compare against your current list.</div>
      ${deckBrowser}
    </div>

    <div class="td-compare-overlay" id="td-compare-overlay" role="dialog" aria-label="Comparator" aria-hidden="true">
      <header class="td-drawer-hdr">
        <h2 id="td-compare-title">Comparator</h2>
        <button class="td-close-btn" onclick="closeDeckCompare()" aria-label="Close comparator">&times;</button>
      </header>
      <div class="td-drawer-body td-compare-body" id="td-compare-body">
        <!-- populated on openDeckCompare -->
      </div>
    </div>
  </aside>`;

  main.innerHTML = content;
  // initMullCarousel() non piu' necessario qui (Mulligan Trainer spostato in Play V3-5)
  if (labDeck) {
    ldcLoad(labDeck);
  }
  // rvInit non piu' chiamato in Deck (viewer moved to Play V3-5)
}

// ── Card Impact IWD (Lab tab, lazy loaded) ──
const _iwdCache = {};
let _iwdSort = 'abs';       // 'abs' | 'pos' | 'neg' | 'sample'
let _iwdShowAll = false;

async function iwdLoad() {
  const our = coachDeck || selectedDeck;
  const opp = labOpp;
  const wrap = document.getElementById('iwd-wrap');
  if (!wrap || !our || !opp) return;
  const key = `${our}_${opp}_${currentFormat || 'core'}`;
  if (_iwdCache[key]) { iwdRender(_iwdCache[key]); return; }
  wrap.innerHTML = '<div class="iwd-loading">Computing IWD… this may take a few seconds.</div>';
  try {
    const fmt = currentFormat || 'core';
    const resp = await fetch(`/api/v1/lab/iwd/${encodeURIComponent(our)}/${encodeURIComponent(opp)}?game_format=${fmt}&days=14`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    _iwdCache[key] = data;
    iwdRender(data);
  } catch (e) {
    wrap.innerHTML = `<div class="iwd-empty">IWD data unavailable (${String(e).slice(0,60)}).</div>`;
  }
}

function iwdRender(data) {
  const wrap = document.getElementById('iwd-wrap');
  if (!wrap) return;
  if (data.low_sample) {
    wrap.innerHTML = `<div class="iwd-empty">
      <span class="iwd-empty-icon">📊</span>
      Low sample for this matchup (${data.total_matches} games).<br>
      IWD needs at least ${data.min_total_matches || 80} games to be reliable.
    </div>`;
    return;
  }
  const cards = (data.cards || []).slice();
  if (!cards.length) {
    wrap.innerHTML = `<div class="iwd-empty">
      <span class="iwd-empty-icon">📊</span>
      No cards passed the sample threshold (20 drawn / 20 not drawn).
    </div>`;
    return;
  }

  // Apply sort
  if (_iwdSort === 'pos') {
    cards.sort((a, b) => b.delta_wr - a.delta_wr);
  } else if (_iwdSort === 'neg') {
    cards.sort((a, b) => a.delta_wr - b.delta_wr);
  } else if (_iwdSort === 'sample') {
    cards.sort((a, b) => b.drawn_games - a.drawn_games);
  } else { // abs
    cards.sort((a, b) => Math.abs(b.delta_wr) - Math.abs(a.delta_wr));
  }

  const visible = _iwdShowAll ? cards : cards.slice(0, 5);

  const header = `<div class="iwd-header">
    <span class="iwd-kpi"><strong>${data.total_matches}</strong> games · <strong>${data.overall_wr}%</strong> overall WR</span>
    <span class="iwd-kpi" style="color:var(--text2)">· last ${data.days}d</span>
    <div class="iwd-sort" role="group" aria-label="Sort cards">
      <button class="iwd-sort-btn ${_iwdSort==='abs'?'active':''}"    onclick="iwdSetSort('abs')"    title="Biggest impact, positive or negative">|Δ|</button>
      <button class="iwd-sort-btn ${_iwdSort==='pos'?'active':''}"    onclick="iwdSetSort('pos')"    title="Best when drawn">+Δ</button>
      <button class="iwd-sort-btn ${_iwdSort==='neg'?'active':''}"    onclick="iwdSetSort('neg')"    title="Worst when drawn (traps)">−Δ</button>
      <button class="iwd-sort-btn ${_iwdSort==='sample'?'active':''}" onclick="iwdSetSort('sample')" title="Sort by sample size">N</button>
    </div>
  </div>`;

  const rows = visible.map(c => {
    const deltaSign = c.delta_wr > 0 ? '+' : '';
    const deltaCls = c.delta_wr > 1.5 ? 'pos' : c.delta_wr < -1.5 ? 'neg' : 'neutral';
    const confDots = [1, 2, 3].map(i => {
      const filled = (c.confidence === 'high' && i <= 3) || (c.confidence === 'med' && i <= 2) || (c.confidence === 'low' && i <= 1);
      return `<span class="iwd-conf-dot ${filled ? 'filled' : 'empty'}"></span>`;
    }).join('');
    const lowConfClass = c.confidence === 'low' ? 'low-conf' : '';
    const drawnW = Math.max(2, Math.min(100, c.wr_drawn));
    const notW = Math.max(2, Math.min(100, c.wr_not_drawn));
    const shortName = c.card.length > 44 ? c.card.slice(0, 42) + '…' : c.card;
    return `<div class="iwd-row ${lowConfClass}" title="${c.card}: WR ${c.wr_drawn}% when drawn (${c.drawn_games}g) vs ${c.wr_not_drawn}% not drawn (${c.not_drawn_games}g)">
      <div class="iwd-row-main">
        <span class="iwd-name">${shortName}</span>
        <div class="iwd-bars">
          <span class="iwd-bar-label">drawn</span>
          <div class="iwd-bar-track"><div class="iwd-bar-fill drawn" style="width:${drawnW}%"></div></div>
          <span class="iwd-bar-val">${c.wr_drawn}%</span>
          <span class="iwd-bar-games">${c.drawn_games}g</span>
        </div>
        <div class="iwd-bars">
          <span class="iwd-bar-label">not drawn</span>
          <div class="iwd-bar-track"><div class="iwd-bar-fill not-drawn" style="width:${notW}%"></div></div>
          <span class="iwd-bar-val">${c.wr_not_drawn}%</span>
          <span class="iwd-bar-games">${c.not_drawn_games}g</span>
        </div>
      </div>
      <span class="iwd-delta ${deltaCls}">${deltaSign}${c.delta_wr.toFixed(1)}%</span>
      <span class="iwd-conf" aria-label="confidence ${c.confidence}">${confDots}</span>
    </div>`;
  }).join('');

  const showMoreBtn = cards.length > 5
    ? `<button class="iwd-showmore" onclick="iwdToggleShowAll()">${_iwdShowAll ? 'Show top 5' : `Show all ${cards.length} cards`}</button>`
    : '';

  wrap.innerHTML = `${header}<div class="iwd-list">${rows}</div>${showMoreBtn}`;
}

function iwdSetSort(mode) {
  _iwdSort = mode;
  const our = coachDeck || selectedDeck;
  const opp = labOpp;
  const key = `${our}_${opp}_${currentFormat || 'core'}`;
  if (_iwdCache[key]) iwdRender(_iwdCache[key]);
}

function iwdToggleShowAll() {
  _iwdShowAll = !_iwdShowAll;
  const our = coachDeck || selectedDeck;
  const opp = labOpp;
  const key = `${our}_${opp}_${currentFormat || 'core'}`;
  if (_iwdCache[key]) iwdRender(_iwdCache[key]);
}
