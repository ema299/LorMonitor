// Deck tab — builder mode (add/remove cards, live stat recompute).
// Search section renders INSIDE the deck box (.dg-wrap), below the grid.
// Card pool is filtered to:
//   (a) the archetype's 2 inks (from DECK_INKS)
//   (b) cards that appear in ANY DATA.consensus or reference_decklists for the
//       current format — this approximates core/infinity legality without
//       needing a backend legality endpoint.
//
// No upper cap on total card count — Lorcana requires 60 minimum, user can
// go above freely. Per-card cap stays at 4 (game rule).

window.V3 = window.V3 || {};
window.V3.Builder = {
  editMode: true,
  _state: { query: '', costs: new Set(), types: new Set(), proOnly: false },
  _MAX_PER_CARD: 4,
  _LEGAL_MIN: 60,
  _delegateInstalled: false,
  _legalCache: null,
  _legalCacheKey: null,

  _seedFromCurrentDeck(deckCode) {
    if (typeof myDeckCards !== 'undefined' && myDeckCards && Object.keys(myDeckCards).length) return;
    const consensus = (DATA.consensus || {})[deckCode] || {};
    const seed = {};
    Object.entries(consensus).forEach(([name, qty]) => {
      const q = Math.max(1, Math.round(Number(qty) || 0));
      if (q > 0) seed[name] = Math.min(this._MAX_PER_CARD, q);
    });
    myDeckCards = seed;
    myDeckMode = 'custom';
  },

  enter(deckCode) {
    this._installDelegate();
    this._seedFromCurrentDeck(deckCode);
    this.editMode = true;
    this._state = { query: '', costs: new Set(), types: new Set(), proOnly: false };
    if (typeof render === 'function') render();
  },

  exit() {
    this.editMode = false;
    if (typeof render === 'function') render();
  },

  resetToConsensus(deckCode) {
    myDeckCards = null;
    myDeckMode = 'standard';
    this._seedFromCurrentDeck(deckCode);
    if (typeof render === 'function') render();
  },

  totalCopies() {
    if (typeof myDeckCards === 'undefined' || !myDeckCards) return 0;
    return Object.values(myDeckCards).reduce((s, v) => s + (Number(v) || 0), 0);
  },

  _toast(msg) {
    let t = document.getElementById('bld-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'bld-toast';
      t.className = 'db-cap-toast';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._tid);
    t._tid = setTimeout(() => t.classList.remove('show'), 1600);
  },

  addCard(name) {
    if (!name) return;
    if (typeof myDeckCards === 'undefined' || !myDeckCards) myDeckCards = {};
    const cur = Number(myDeckCards[name] || 0);
    if (cur >= this._MAX_PER_CARD) { this._toast('Max 4 copies of a card'); return; }
    myDeckCards[name] = cur + 1;
    myDeckMode = 'custom';
    if (typeof render === 'function') render();
  },

  removeCard(name) {
    if (!name || typeof myDeckCards === 'undefined' || !myDeckCards) return;
    const cur = Number(myDeckCards[name] || 0);
    if (cur <= 0) return;
    if (cur === 1) delete myDeckCards[name];
    else myDeckCards[name] = cur - 1;
    if (typeof render === 'function') render();
  },

  _installDelegate() {
    if (this._delegateInstalled) return;
    this._delegateInstalled = true;
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-bld-action]');
      if (!btn) return;
      const action = btn.dataset.bldAction;
      const host = btn.closest('[data-card]');
      const card = host ? host.dataset.card : null;
      if (!card && action !== 'reset' && action !== 'exit') return;
      e.stopPropagation();
      e.preventDefault();
      if (action === 'add') this.addCard(card);
      else if (action === 'remove') this.removeCard(card);
      else if (action === 'reset') {
        const dk = btn.dataset.deck;
        if (dk && confirm('Reset to consensus? All your edits will be lost.')) this.resetToConsensus(dk);
      } else if (action === 'exit') this.exit();
    });
  },

  setSearch(q) {
    this._state.query = String(q || '').trim().toLowerCase();
    this._refreshResults();
  },
  setProOnly(v) {
    this._state.proOnly = !!v;
    this._refreshResults();
    document.querySelectorAll('.bld-pro-seg').forEach(el => {
      el.classList.toggle('active', el.dataset.pro === String(this._state.proOnly));
    });
  },
  setCostFilter(c) {
    if (this._state.costs.has(c)) this._state.costs.delete(c);
    else this._state.costs.add(c);
    this._refreshResults();
    this._refreshFilterChips();
  },
  setTypeFilter(t) {
    if (this._state.types.has(t)) this._state.types.delete(t);
    else this._state.types.add(t);
    this._refreshResults();
    this._refreshFilterChips();
  },
  _refreshFilterChips() {
    document.querySelectorAll('.bld-filter-chip').forEach(el => {
      const c = el.dataset.cost;
      const t = el.dataset.type;
      if (c != null) el.classList.toggle('active', this._state.costs.has(c));
      if (t != null) el.classList.toggle('active', this._state.types.has(t));
    });
  },

  // Legal card pool: every card that appears in any consensus list or tournament
  // reference list for the active format. Cached per format to avoid rescans.
  _legalCardNames() {
    const fmt = (typeof currentFormat !== 'undefined') ? currentFormat : 'core';
    if (this._legalCacheKey === fmt && this._legalCache) return this._legalCache;
    const set = new Set();
    const consensus = DATA.consensus || {};
    Object.values(consensus).forEach(list => {
      Object.keys(list || {}).forEach(name => set.add(name));
    });
    const refs = DATA.reference_decklists || {};
    Object.values(refs).forEach(refList => {
      (refList || []).forEach(r => {
        (r && r.cards ? r.cards : []).forEach(c => { if (c && c.name) set.add(c.name); });
      });
    });
    // Keep cards currently in the user's deck even if not in consensus (they
    // were manually added earlier — the builder should still show +1 on them).
    if (typeof myDeckCards !== 'undefined' && myDeckCards) {
      Object.keys(myDeckCards).forEach(name => set.add(name));
    }
    this._legalCache = set;
    this._legalCacheKey = fmt;
    return set;
  },

  invalidateLegalCache() { this._legalCache = null; this._legalCacheKey = null; },

  _filteredCards(deckCode) {
    if (typeof rvCardsDB === 'undefined' || !rvCardsDB) return [];
    const deckInks = (typeof DECK_INKS !== 'undefined' && DECK_INKS[deckCode]) || [];
    // Pro-only gate: when enabled, restrict to cards present in any consensus
    // or tournament reference list (pool of ~200-300 cards that pros actually run).
    const proPool = this._state.proOnly ? this._legalCardNames() : null;
    const out = [];
    Object.keys(rvCardsDB).forEach(name => {
      if (proPool && !proPool.has(name)) return;
      const c = rvCardsDB[name];
      const ink = (c.ink || '').trim().toLowerCase();
      if (deckInks.length && !deckInks.includes(ink)) return;
      if (this._state.query && !name.toLowerCase().includes(this._state.query)) return;
      const costNum = parseInt(c.cost, 10);
      if (this._state.costs.size) {
        const hit = [...this._state.costs].some(v => {
          if (v === '8+') return Number.isFinite(costNum) && costNum >= 8;
          return costNum === parseInt(v, 10);
        });
        if (!hit) return;
      }
      if (this._state.types.size) {
        const cardType = (c.type || '').toLowerCase();
        const hit = [...this._state.types].some(t => cardType === t.toLowerCase());
        if (!hit) return;
      }
      out.push({ _name: name, cost: c.cost, type: c.type, ink });
    });
    out.sort((a, b) => {
      const ca = parseInt(a.cost, 10); const cb = parseInt(b.cost, 10);
      const costA = Number.isFinite(ca) ? ca : 99;
      const costB = Number.isFinite(cb) ? cb : 99;
      if (costA !== costB) return costA - costB;
      return a._name.localeCompare(b._name);
    });
    return out;
  },

  _resultTile(c) {
    const img = (typeof cardImgUrlFuzzy === 'function') ? cardImgUrlFuzzy(c._name) : '';
    const qty = (typeof myDeckCards !== 'undefined' && myDeckCards && myDeckCards[c._name]) || 0;
    const attrName = c._name.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const short = c._name.split(' - ')[0].replace(/&/g, '&amp;').replace(/</g, '&lt;');
    const disabled = qty >= this._MAX_PER_CARD;
    const art = img
      ? `<img src="${img}" loading="lazy" alt="${attrName}">`
      : `<div class="pf-std-vph">${short.slice(0,2)}</div>`;
    return `<div class="pf-std-vcard bld-tile ${qty > 0 ? 'has' : ''}" data-card="${attrName}" title="${attrName}">
      <div class="pf-std-vart">
        ${art}
        <span class="bld-cost">${c.cost != null ? c.cost : '?'}</span>
        ${qty > 0 ? `<span class="pf-std-vqty">×${qty}</span>` : ''}
        <button class="bld-tile-add" data-bld-action="add" ${disabled ? 'disabled' : ''} title="${disabled ? 'Max reached' : 'Add copy'}">+</button>
      </div>
    </div>`;
  },

  _resultsHtml(deckCode) {
    const cards = this._filteredCards(deckCode);
    if (!cards.length) return '<div class="bld-empty">No cards match.</div>';
    return `<div class="pf-std-gallery bld-results-grid">${cards.slice(0, 90).map(c => this._resultTile(c)).join('')}</div>`;
  },

  _refreshResults() {
    const host = document.getElementById('bld-results');
    if (!host) return;
    const deckCode = (typeof coachDeck !== 'undefined') ? coachDeck : null;
    host.innerHTML = this._resultsHtml(deckCode);
  },

  // Side-by-side builder panel (aside on the right of the deck grid).
  buildPanel(deckCode) {
    if (!this.editMode) return '';
    this._installDelegate();
    const deckInks = (typeof DECK_INKS !== 'undefined' && DECK_INKS[deckCode]) || [];
    const inkLabel = deckInks.map(i => i.charAt(0).toUpperCase() + i.slice(1)).join(' · ') || '—';
    const costs = ['0','1','2','3','4','5','6','7','8+'];
    const types = ['Character','Action','Item','Song','Location'];
    const costChips = costs.map(c => {
      const active = this._state.costs.has(c) ? ' active' : '';
      return `<button class="bld-filter-chip${active}" data-cost="${c}" onclick="event.stopPropagation();window.V3.Builder.setCostFilter('${c}')">${c}</button>`;
    }).join('');
    const typeChips = types.map(t => {
      const active = this._state.types.has(t) ? ' active' : '';
      return `<button class="bld-filter-chip${active}" data-type="${t}" onclick="event.stopPropagation();window.V3.Builder.setTypeFilter('${t}')">${t}</button>`;
    }).join('');
    const proActive = this._state.proOnly;
    return `<aside class="bld-panel" role="complementary">
      <div class="bld-panel-hdr">
        <span class="bld-panel-label">Add cards</span>
        <span class="bld-panel-ink">${inkLabel}</span>
      </div>
      <div class="bld-pool-seg" role="tablist" aria-label="Card pool">
        <button class="bld-pro-seg ${!proActive ? 'active' : ''}" data-pro="false" onclick="window.V3.Builder.setProOnly(false)">All cards</button>
        <button class="bld-pro-seg ${proActive ? 'active' : ''}" data-pro="true" onclick="window.V3.Builder.setProOnly(true)" title="Only cards currently played in pro tournament lists">Pro only</button>
      </div>
      <input class="bld-search" type="search" placeholder="Search card name…"
             oninput="window.V3.Builder.setSearch(this.value)"
             value="${this._state.query.replace(/"/g, '&quot;')}">
      <div class="bld-filter-group">
        <span class="bld-filter-label">Cost</span>
        <div class="bld-filter-row">${costChips}</div>
      </div>
      <div class="bld-filter-group">
        <span class="bld-filter-label">Type</span>
        <div class="bld-filter-row">${typeChips}</div>
      </div>
      <div class="bld-results" id="bld-results">${this._resultsHtml(deckCode)}</div>
    </aside>`;
  },
};
