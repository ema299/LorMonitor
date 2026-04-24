// Saved decks — persistent user-named decklists stored in localStorage.
// Used by: Deck tab (Save button in edit mode header) + Home tab (My Decklists section).
// Storage key: 'v3_saved_decks'. Each entry: {id, name, deckCode, format, cards, createdAt, updatedAt}.

window.V3 = window.V3 || {};
window.V3.SavedDecks = {
  STORAGE_KEY: 'v3_saved_decks',
  _delegateInstalled: false,

  _read() {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) { return []; }
  },
  _write(list) {
    try { localStorage.setItem(this.STORAGE_KEY, JSON.stringify(list)); } catch (e) {}
  },
  _genId() { return 'dk_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); },

  list() { return this._read(); },

  nameExists(name, excludeId) {
    const n = String(name || '').trim().toLowerCase();
    if (!n) return false;
    return this.list().some(d => d.name.trim().toLowerCase() === n && d.id !== excludeId);
  },

  save(name, deckCode, cards) {
    const cleanName = String(name || '').trim();
    if (!cleanName) return { ok: false, error: 'Name required' };
    if (this.nameExists(cleanName)) return { ok: false, error: 'Name already used' };
    const now = new Date().toISOString();
    const entry = {
      id: this._genId(),
      name: cleanName,
      deckCode: deckCode || null,
      format: (typeof currentFormat !== 'undefined') ? currentFormat : 'core',
      cards: Object.assign({}, cards || {}),
      createdAt: now, updatedAt: now,
    };
    const list = this.list();
    list.push(entry);
    this._write(list);
    return { ok: true, id: entry.id };
  },

  update(id, patch) {
    const list = this.list();
    const idx = list.findIndex(d => d.id === id);
    if (idx < 0) return { ok: false };
    if (patch.name != null) {
      const n = String(patch.name).trim();
      if (!n) return { ok: false, error: 'Name required' };
      if (this.nameExists(n, id)) return { ok: false, error: 'Name already used' };
      list[idx].name = n;
    }
    if (patch.cards != null) list[idx].cards = Object.assign({}, patch.cards);
    list[idx].updatedAt = new Date().toISOString();
    this._write(list);
    return { ok: true };
  },

  remove(id) {
    this._write(this.list().filter(d => d.id !== id));
  },

  load(id) {
    const deck = this.list().find(d => d.id === id);
    if (!deck) return;
    myDeckCards = Object.assign({}, deck.cards);
    myDeckMode = 'custom';
    if (deck.deckCode) {
      if (typeof coachDeck !== 'undefined') coachDeck = deck.deckCode;
      if (typeof selectedDeck !== 'undefined') selectedDeck = deck.deckCode;
    }
    if (typeof currentTab !== 'undefined') currentTab = 'deck';
    if (typeof render === 'function') render();
  },

  // True when myDeckCards (custom) differs from consensus for deckCode.
  isDirty(deckCode) {
    if (typeof myDeckMode === 'undefined' || myDeckMode !== 'custom') return false;
    if (typeof myDeckCards === 'undefined' || !myDeckCards) return false;
    const consensus = (DATA.consensus || {})[deckCode] || {};
    const names = new Set([...Object.keys(myDeckCards), ...Object.keys(consensus)]);
    for (const n of names) {
      const a = Math.round(Number(myDeckCards[n] || 0));
      const b = Math.round(Number(consensus[n] || 0));
      if (a !== b) return true;
    }
    return false;
  },

  _esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); },

  _totalCards(cards) { return Object.values(cards || {}).reduce((s, v) => s + (Number(v) || 0), 0); },

  _timeAgo(iso) {
    if (!iso) return '';
    const ms = Date.now() - new Date(iso).getTime();
    const m = Math.floor(ms / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 7) return `${d}d ago`;
    return new Date(iso).toLocaleDateString();
  },

  // --- Save dialog (Deck tab edit mode) ---
  openSaveDialog() {
    this._installDelegate();
    const deckCode = (typeof coachDeck !== 'undefined') ? coachDeck : '';
    const defaultName = `${deckCode || 'My deck'} · ${new Date().toLocaleDateString()}`;
    this._closeDialog();
    const host = document.createElement('div');
    host.id = 'sd-dialog-host';
    host.innerHTML = `<div class="sd-dialog-backdrop" onclick="if(event.target===this)window.V3.SavedDecks._closeDialog()">
      <div class="sd-dialog" role="dialog" aria-label="Save deck">
        <div class="sd-dialog-title">Save decklist</div>
        <div class="sd-dialog-sub">${this._esc(deckCode)} · ${this._totalCards(typeof myDeckCards !== 'undefined' ? myDeckCards : {})} cards</div>
        <label class="sd-dialog-label">Name</label>
        <input id="sd-dialog-name" class="sd-dialog-input" type="text" maxlength="60" value="${this._esc(defaultName)}" placeholder="e.g. My EmSa tournament"
               onkeydown="if(event.key==='Enter')window.V3.SavedDecks._confirmSave();if(event.key==='Escape')window.V3.SavedDecks._closeDialog()">
        <div id="sd-dialog-err" class="sd-dialog-err"></div>
        <div class="sd-dialog-btns">
          <button class="sd-btn sd-btn--ghost" onclick="window.V3.SavedDecks._closeDialog()">Cancel</button>
          <button class="sd-btn sd-btn--primary" onclick="window.V3.SavedDecks._confirmSave()">Save</button>
        </div>
      </div>
    </div>`;
    document.body.appendChild(host);
    requestAnimationFrame(() => {
      host.classList.add('open');
      const el = document.getElementById('sd-dialog-name');
      if (el) { el.focus(); el.select(); }
    });
  },

  _confirmSave() {
    const input = document.getElementById('sd-dialog-name');
    const err = document.getElementById('sd-dialog-err');
    if (!input) return;
    const name = input.value;
    const deckCode = (typeof coachDeck !== 'undefined') ? coachDeck : null;
    const cards = (typeof myDeckCards !== 'undefined' && myDeckCards) ? myDeckCards : {};
    const res = this.save(name, deckCode, cards);
    if (!res.ok) {
      if (err) err.textContent = res.error || 'Could not save';
      return;
    }
    this._closeDialog();
    this._toast(`Saved as '${name.trim()}'`);
  },

  _openRenameDialog(id) {
    const deck = this.list().find(d => d.id === id);
    if (!deck) return;
    this._closeDialog();
    const host = document.createElement('div');
    host.id = 'sd-dialog-host';
    host.innerHTML = `<div class="sd-dialog-backdrop" onclick="if(event.target===this)window.V3.SavedDecks._closeDialog()">
      <div class="sd-dialog" role="dialog" aria-label="Rename deck">
        <div class="sd-dialog-title">Rename decklist</div>
        <label class="sd-dialog-label">New name</label>
        <input id="sd-dialog-name" class="sd-dialog-input" type="text" maxlength="60" value="${this._esc(deck.name)}"
               onkeydown="if(event.key==='Enter')window.V3.SavedDecks._confirmRename('${id}');if(event.key==='Escape')window.V3.SavedDecks._closeDialog()">
        <div id="sd-dialog-err" class="sd-dialog-err"></div>
        <div class="sd-dialog-btns">
          <button class="sd-btn sd-btn--ghost" onclick="window.V3.SavedDecks._closeDialog()">Cancel</button>
          <button class="sd-btn sd-btn--primary" onclick="window.V3.SavedDecks._confirmRename('${id}')">Rename</button>
        </div>
      </div>
    </div>`;
    document.body.appendChild(host);
    requestAnimationFrame(() => {
      host.classList.add('open');
      const el = document.getElementById('sd-dialog-name');
      if (el) { el.focus(); el.select(); }
    });
  },

  _confirmRename(id) {
    const input = document.getElementById('sd-dialog-name');
    const err = document.getElementById('sd-dialog-err');
    if (!input) return;
    const res = this.update(id, { name: input.value });
    if (!res.ok) { if (err) err.textContent = res.error || 'Could not rename'; return; }
    this._closeDialog();
    this._toast('Renamed');
    if (typeof render === 'function') render();
  },

  _closeDialog() {
    const host = document.getElementById('sd-dialog-host');
    if (host) host.remove();
  },

  _toast(msg) {
    let t = document.getElementById('sd-toast');
    if (!t) { t = document.createElement('div'); t.id = 'sd-toast'; t.className = 'db-cap-toast'; document.body.appendChild(t); }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._tid);
    t._tid = setTimeout(() => t.classList.remove('show'), 1800);
  },

  // --- Home section ---
  buildHomeSection() {
    const list = this.list();
    if (!list.length) {
      return `<div class="sd-home-section">
        <div class="sd-home-title">My decklists</div>
        <div class="sd-home-empty">No saved decks yet. Build one in the <strong>Deck</strong> tab and click <strong>Save</strong>.</div>
      </div>`;
    }
    const sorted = list.slice().sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''));
    const tiles = sorted.map(d => {
      const count = this._totalCards(d.cards);
      const under = count < 60;
      const inks = (typeof DECK_INKS !== 'undefined' && DECK_INKS[d.deckCode]) || [];
      const dots = inks.map(ink => {
        const c = (typeof INK_COLORS !== 'undefined' && INK_COLORS[ink]) || '#888';
        return `<span class="sd-dot" style="background:${c}"></span>`;
      }).join('');
      return `<div class="sd-tile" data-id="${d.id}">
        <div class="sd-tile-main" onclick="window.V3.SavedDecks.load('${d.id}')">
          <div class="sd-tile-top">
            <span class="sd-tile-inks">${dots}</span>
            <span class="sd-tile-name">${this._esc(d.name)}</span>
          </div>
          <div class="sd-tile-meta">
            <span>${this._esc(d.deckCode || '?')}</span>
            <span class="${under ? 'sd-under' : ''}">${count} cards${under ? ' · &lt;60' : ''}</span>
            <span>Updated ${this._timeAgo(d.updatedAt)}</span>
          </div>
        </div>
        <div class="sd-tile-actions">
          <button class="sd-icon-btn" onclick="window.V3.SavedDecks._openRenameDialog('${d.id}')" title="Rename">✏</button>
          <button class="sd-icon-btn sd-icon-btn--danger" onclick="if(confirm('Delete this decklist?')){window.V3.SavedDecks.remove('${d.id}');if(typeof render==='function')render();}" title="Delete">✕</button>
        </div>
      </div>`;
    }).join('');
    return `<div class="sd-home-section">
      <div class="sd-home-title">My decklists <span class="sd-home-count">${list.length}</span></div>
      <div class="sd-home-tiles">${tiles}</div>
    </div>`;
  },

  _installDelegate() {
    if (this._delegateInstalled) return;
    this._delegateInstalled = true;
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-bld-action="save-deck"]');
      if (btn) { e.stopPropagation(); e.preventDefault(); this.openSaveDialog(); }
    });
  },
};

// Install delegate at script load so the Save button works before any dialog is opened.
if (window.V3 && window.V3.SavedDecks) window.V3.SavedDecks._installDelegate();
