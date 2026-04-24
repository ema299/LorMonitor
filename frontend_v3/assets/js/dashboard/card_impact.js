// Card Impact Preview — sheet content builder.
// Called from deck_grid.js::openSheet. Renders 5 sections per card:
// 1. Composition delta (what changes if you remove this copy)
// 2. Opening hand probability (OTP/OTD + interactive mulligan M slider)
// 3. Pro usage (how many tournament lists play it, how many by winners)
// 4. Matchup impact (WR delta from card_scores + sample size)
// 5. Threats answered (killer curves whose response.cards[] includes this card)
//
// All numbers are deterministic combinatorics (opening hand) or carry an
// explicit sample size. No projected WR, no composition-effect aggregates.

window.V3 = window.V3 || {};
window.V3.CardImpact = {
  // Hypergeometric: P(at least 1 copy seen in n cards drawn from a 60-card
  // deck that contains K copies of the target).
  _hg(K, n, deckSize = 60) {
    if (K <= 0) return 0;
    if (n <= 0) return 0;
    if (n > deckSize) n = deckSize;
    let pZero = 1;
    for (let i = 0; i < n; i++) {
      const num = deckSize - K - i;
      if (num <= 0) return 1;
      pZero *= num / (deckSize - i);
    }
    return 1 - pZero;
  },

  _pct(v) { return (v * 100).toFixed(1) + '%'; },

  _qtyInDeck(cardName) {
    return (typeof myDeckCards !== 'undefined' && myDeckCards && myDeckCards[cardName]) || 0;
  },

  _totalDeckCards() {
    if (typeof myDeckCards === 'undefined' || !myDeckCards) return 60;
    const t = Object.values(myDeckCards).reduce((s, v) => s + (Number(v) || 0), 0);
    return t > 0 ? t : 60;
  },

  _esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  },

  // --- Section 1: Composition delta ---
  _buildComposition(cardName) {
    const meta = (typeof rvCardDetailsByName === 'function') ? rvCardDetailsByName(cardName) : null;
    if (!meta) return '';
    const qty = this._qtyInDeck(cardName);
    if (qty <= 0) return '';
    const cost = parseInt(meta.cost, 10);
    const costLabel = Number.isFinite(cost) ? cost : '?';
    const ink = meta.ink || '?';
    const type = meta.type || '?';

    // Compute current totals so we can show N → N-1
    let sameCost = 0, sameInk = 0, sameType = 0;
    if (typeof myDeckCards !== 'undefined' && myDeckCards) {
      Object.entries(myDeckCards).forEach(([n, q]) => {
        const m = rvCardsDB && rvCardsDB[n];
        if (!m) return;
        const c = parseInt(m.cost, 10);
        if (Number.isFinite(c) && c === cost) sameCost += (Number(q) || 0);
        if ((m.ink || '').trim() === ink) sameInk += (Number(q) || 0);
        if ((m.type || '').trim() === type) sameType += (Number(q) || 0);
      });
    }

    return `<div class="ci-section">
      <div class="ci-sec-title">If you remove one copy</div>
      <div class="ci-delta-row">Cost ${costLabel}: <strong>${sameCost}</strong> → ${sameCost - 1}</div>
      <div class="ci-delta-row">${this._esc(ink)}: <strong>${sameInk}</strong> → ${sameInk - 1}</div>
      <div class="ci-delta-row">${this._esc(type)}s: <strong>${sameType}</strong> → ${sameType - 1}</div>
    </div>`;
  },

  // --- Section 2: Opening hand probability ---
  _buildOpeningHand(cardName) {
    const qty = this._qtyInDeck(cardName);
    if (qty <= 0) return '';
    const p = (M, extra = 0) => this._pct(this._hg(qty, 7 + M + extra));

    const idSuffix = Math.random().toString(36).slice(2, 8);
    return `<div class="ci-section" data-qty="${qty}">
      <div class="ci-sec-title">Opening hand — ${qty} cop${qty === 1 ? 'y' : 'ies'} in 60
        <span class="ci-sec-info" title="Probability is hypergeometric over a 60-card deck. 'Mulligan M' = put M cards under, draw M from top (Lorcana 'alter' rule, no shuffle). OTD adds the T1 draw.">?</span>
      </div>
      <table class="ci-mull-tbl">
        <thead><tr><th></th><th>OTP</th><th>OTD (T1 draw)</th></tr></thead>
        <tbody>
          <tr><td>No mulligan (M=0)</td><td>${p(0)}</td><td>${p(0, 1)}</td></tr>
          <tr><td>Put 3 under, draw 3</td><td>${p(3)}</td><td>${p(3, 1)}</td></tr>
          <tr><td>Mulligan all 7</td><td>${p(7)}</td><td>${p(7, 1)}</td></tr>
          <tr class="ci-mull-t3"><td>By end of T3 (M=0)</td><td>${p(2)}</td><td>${p(3)}</td></tr>
        </tbody>
      </table>
      <div class="ci-mull-custom">
        <label>Custom mulligan: <span id="ci-mull-label-${idSuffix}" class="ci-mull-val">3</span></label>
        <input type="range" min="0" max="7" value="3" class="ci-mull-slider"
               data-qty="${qty}" data-label="ci-mull-label-${idSuffix}" data-out="ci-mull-out-${idSuffix}"
               oninput="window.V3.CardImpact._onSlider(this)">
        <div class="ci-mull-out" id="ci-mull-out-${idSuffix}">
          OTP <strong>${p(3)}</strong> · OTD <strong>${p(3, 1)}</strong>
        </div>
      </div>
    </div>`;
  },

  _onSlider(el) {
    const qty = parseInt(el.dataset.qty, 10) || 0;
    const M = parseInt(el.value, 10) || 0;
    const label = document.getElementById(el.dataset.label);
    const out = document.getElementById(el.dataset.out);
    if (label) label.textContent = M;
    if (out) {
      const p = (extra) => this._pct(this._hg(qty, 7 + M + extra));
      out.innerHTML = `OTP <strong>${p(0)}</strong> · OTD <strong>${p(1)}</strong>`;
    }
  },

  // --- Section 3: Pro usage ---
  _buildProUsage(cardName) {
    // Aggregate across all archetypes in reference_decklists.
    const refs = DATA.reference_decklists || {};
    let listsWithCard = 0, totalLists = 0, winnersWith = 0, totalWinners = 0;
    const normalize = (s) => (String(s || '').split(' - ')[0] || '').toLowerCase().trim();
    const target = normalize(cardName);
    const ranksWin = new Set(['1st', 'winner', 'Winner']);
    Object.values(refs).forEach(refList => {
      (refList || []).forEach(r => {
        totalLists += 1;
        const isWinner = ranksWin.has((r.rank || '').trim());
        if (isWinner) totalWinners += 1;
        const hasCard = (r.cards || []).some(c => c && normalize(c.name) === target);
        if (hasCard) {
          listsWithCard += 1;
          if (isWinner) winnersWith += 1;
        }
      });
    });
    if (totalLists === 0) return '';
    const pct = (listsWithCard / totalLists * 100).toFixed(0);
    const winnerLine = totalWinners > 0
      ? `${winnersWith} / ${totalWinners} winners`
      : 'no winner data';
    return `<div class="ci-section">
      <div class="ci-sec-title">Pro tournament usage</div>
      <div class="ci-line">Played in <strong>${listsWithCard}</strong> / ${totalLists} lists (${pct}%)</div>
      <div class="ci-line ci-sub">${winnerLine}</div>
    </div>`;
  },

  // --- Section 4: Matchup impact (current opponent) ---
  _buildMatchupImpact(cardName, opponentCode) {
    if (!opponentCode) return '';
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opponentCode) : null;
    if (!mu || !mu.card_scores) return '';
    const entry = mu.card_scores[cardName];
    if (!entry || typeof entry.delta !== 'number') return '';
    const pp = entry.delta * 100;
    const sample = entry.games != null ? Number(entry.games) : null;
    const MIN_SAMPLE = 30;
    let line;
    if (sample != null && sample < MIN_SAMPLE) {
      line = `<span class="ci-low-sample">Low sample (${sample} games) — not reliable</span>`;
    } else {
      const sign = pp >= 0 ? '+' : '';
      const cls = pp >= 2 ? 'ds-green' : pp <= -2 ? 'ds-red' : 'ds-yellow';
      line = `<span class="${cls}">${sign}${pp.toFixed(1)}pp${sample != null ? ` · ${sample} games` : ''}</span>`;
    }
    return `<div class="ci-section">
      <div class="ci-sec-title">Win rate impact · vs ${this._esc(opponentCode)}</div>
      <div class="ci-line">${line}</div>
    </div>`;
  },

  // --- Section 5: Threats answered ---
  _buildThreatsAnswered(cardName, opponentCode) {
    if (!opponentCode) return '';
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opponentCode) : null;
    if (!mu || !Array.isArray(mu.killer_curves)) return '';
    const normalize = (s) => (String(s || '').split(' - ')[0] || '').toLowerCase().trim();
    const target = normalize(cardName);
    const hits = [];
    mu.killer_curves.forEach(curve => {
      const answers = (curve.response && Array.isArray(curve.response.cards)) ? curve.response.cards : [];
      if (answers.some(ac => normalize(ac) === target)) {
        const critTurn = curve.critical_turn && curve.critical_turn.turn ? `T${curve.critical_turn.turn}` : '';
        const pct = curve.frequency && curve.frequency.pct != null ? Math.round(curve.frequency.pct) : null;
        hits.push({ name: curve.name, turn: critTurn, pct });
      }
    });
    if (!hits.length) return '';
    const rows = hits.map(h => `<div class="ci-threat-row">
      <span class="ci-check">✓</span>
      <span class="ci-threat-name">${this._esc(h.name)}</span>
      ${h.turn ? `<span class="ci-threat-turn">${h.turn}</span>` : ''}
      ${h.pct != null ? `<span class="ci-threat-pct">${h.pct}%</span>` : ''}
    </div>`).join('');
    return `<div class="ci-section">
      <div class="ci-sec-title">Threats answered · vs ${this._esc(opponentCode)}</div>
      ${rows}
    </div>`;
  },

  buildSheet(cardName, opponentCode) {
    const deckCode = (typeof coachDeck !== 'undefined') ? coachDeck : null;
    // Composition delta + opening-hand math moved to the standalone Math Tool
    // (accessible via the "Math" button in the deck header). Keep the sheet
    // focused on card-level signals that depend on the opponent context.
    return this._buildMatchupImpact(cardName, opponentCode)
      + this._buildThreatsAnswered(cardName, opponentCode)
      + this._buildProUsage(cardName, deckCode);
  },
};
