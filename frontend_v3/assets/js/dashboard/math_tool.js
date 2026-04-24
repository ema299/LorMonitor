// Math Tool — standalone modal for opening-hand probability with the
// Lorcana "alter" mulligan rule. Opened from the deck header "Math" button.
//
// Reuses the hypergeometric helper on window.V3.CardImpact._hg so we don't
// duplicate math across files. If CardImpact isn't loaded it falls back to
// a local implementation.

window.V3 = window.V3 || {};
window.V3.MathTool = {
  _activeCard: null,
  _M: 3,

  _hg(K, n, deckSize = 60) {
    if (window.V3.CardImpact && typeof window.V3.CardImpact._hg === 'function') {
      return window.V3.CardImpact._hg(K, n, deckSize);
    }
    if (K <= 0 || n <= 0) return 0;
    if (n > deckSize) n = deckSize;
    let p = 1;
    for (let i = 0; i < n; i++) {
      const num = deckSize - K - i;
      if (num <= 0) return 1;
      p *= num / (deckSize - i);
    }
    return 1 - p;
  },

  _pct(v) { return (v * 100).toFixed(1) + '%'; },

  _deckMap() {
    if (typeof myDeckCards !== 'undefined' && myDeckCards && typeof myDeckMode !== 'undefined' && myDeckMode === 'custom') {
      return myDeckCards;
    }
    const dk = (typeof coachDeck !== 'undefined') ? coachDeck : null;
    if (!dk) return {};
    const consensus = (DATA.consensus || {})[dk] || {};
    const map = {};
    Object.entries(consensus).forEach(([n, q]) => { map[n] = Math.round(Number(q) || 0); });
    return map;
  },

  _esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); },

  open(preselectCard) {
    const map = this._deckMap();
    const names = Object.keys(map).filter(n => (map[n] || 0) > 0).sort();
    if (!names.length) return;
    this._activeCard = preselectCard && map[preselectCard] ? preselectCard : names[0];
    this._M = 3;
    this._close();
    const host = document.createElement('div');
    host.id = 'mt-host';
    host.innerHTML = this._shellHtml(names);
    document.body.appendChild(host);
    requestAnimationFrame(() => host.classList.add('open'));
    this._updateResults();
  },

  _close() {
    const host = document.getElementById('mt-host');
    if (host) host.remove();
  },

  _shellHtml(names) {
    const options = names.map(n => {
      const sel = n === this._activeCard ? ' selected' : '';
      const short = n.split(' - ')[0];
      return `<option value="${this._esc(n)}"${sel}>${this._esc(short)}</option>`;
    }).join('');
    return `<div class="mt-backdrop" onclick="if(event.target===this)window.V3.MathTool._close()">
      <div class="mt-dialog" role="dialog" aria-label="Opening Hand Math">
        <button class="mt-close" onclick="window.V3.MathTool._close()" aria-label="Close">&times;</button>
        <div class="mt-title">Opening Hand Math</div>
        <div class="mt-sub">Hypergeometric probability on a 60-card deck with Lorcana "alter" mulligan rule.</div>

        <div class="mt-row">
          <label class="mt-label">Card</label>
          <select class="mt-select" id="mt-card" onchange="window.V3.MathTool._onCardChange(this.value)">${options}</select>
          <span class="mt-qty-badge" id="mt-qty-badge">—</span>
        </div>

        <div class="mt-row mt-row--slider">
          <label class="mt-label">Mulligan (put under / draw): <strong id="mt-m-label">${this._M}</strong></label>
          <input type="range" min="0" max="7" value="${this._M}" class="mt-slider"
                 oninput="window.V3.MathTool._onSlider(this.value)">
        </div>

        <div class="mt-results" id="mt-results"></div>

        <div class="mt-hint">
          <strong>Alter rule</strong>: you put M cards from your initial 7 under the deck and draw M fresh from the top (no shuffle). OTD adds the T1 draw (+1 card seen).
        </div>
      </div>
    </div>`;
  },

  _onCardChange(name) {
    this._activeCard = name;
    this._updateResults();
  },
  _onSlider(v) {
    this._M = parseInt(v, 10) || 0;
    const lbl = document.getElementById('mt-m-label');
    if (lbl) lbl.textContent = this._M;
    this._updateResults();
  },

  _updateResults() {
    const out = document.getElementById('mt-results');
    const badge = document.getElementById('mt-qty-badge');
    if (!out) return;
    const map = this._deckMap();
    const qty = Math.round(Number(map[this._activeCard] || 0));
    if (badge) badge.textContent = qty + '×';
    if (qty <= 0) { out.innerHTML = '<div class="mt-empty">Card not in current deck.</div>'; return; }

    // Cards seen post-mulligan at start of T1:
    //   OTP = 7 + M  (no T1 draw)
    //   OTD = 7 + M + 1  (T1 draw)
    // By end of T3: add 2 more draws for OTP (T2+T3), 3 for OTD (T1+T2+T3 — T1 already counted though)
    // Simpler: by end of T3 = start of T4, OTP saw 7+M+2, OTD saw 7+M+3.
    const P = (seen) => this._pct(this._hg(qty, seen));

    out.innerHTML = `<table class="mt-tbl">
      <thead>
        <tr>
          <th></th>
          <th>OTP</th>
          <th>OTD <small>(T1 draw)</small></th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Opening hand<br><small>after mulligan M=${this._M}</small></td>
          <td>${P(7 + this._M)}</td>
          <td>${P(8 + this._M)}</td>
        </tr>
        <tr><td>By end of turn 3</td>
          <td>${P(9 + this._M)}</td>
          <td>${P(10 + this._M)}</td>
        </tr>
        <tr class="mt-ref"><td>Raw (no mulligan)</td>
          <td>${P(7)}</td>
          <td>${P(8)}</td>
        </tr>
        <tr class="mt-ref"><td>Full mulligan (M=7)</td>
          <td>${P(14)}</td>
          <td>${P(15)}</td>
        </tr>
      </tbody>
    </table>`;
  },
};
