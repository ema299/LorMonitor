// Deck Lens — bottom panel with live deck-level analytics.
// Two sections:
//   1. Δ vs consensus (adds/cuts vs archetype consensus list, with WR impact
//      badge per row when a matchup is selected)
//   2. Class breakdown (removal/bounce/wipe/evasive/draw/ramp counts via
//      ability-text regex — ~80% accuracy, flagged as heuristic)
//
// Updates live on each edit because render() rebuilds the tab.

window.V3 = window.V3 || {};
window.V3.DeckLens = {
  // Ability-text regex classifiers. Heuristic, not authoritative —
  // disclaimer shown in the UI tooltip.
  CLASSES: [
    { id: 'removal', icon: '⚔', label: 'Removal',
      re: /banish\s+(chosen|target|each|all)|deal\s+\d+\s+damage\s+to\s+(chosen|each|all)/i,
      exclude: /banish this/i },
    { id: 'bounce', icon: '↩', label: 'Bounce',
      re: /return\s+(chosen|target|an?\s+opposing|each|all).*\bhand/i },
    { id: 'wipe', icon: '💥', label: 'Board wipe',
      re: /banish\s+(all|each\s+(opposing|other)?\s*character)|deal\s+\d+\s+damage\s+to\s+each\s+(character|opposing)/i },
    { id: 'evasive', icon: '🪽', label: 'Evasive',
      re: /\bEvasive\b/ },
    { id: 'draw', icon: '📚', label: 'Draw',
      re: /\bdraw\s+(a|an|\d+|that\s+many|cards\s+equal)\s+card/i,
      exclude: /if you draw|when you draw/i },
    { id: 'ramp', icon: '⛏', label: 'Ramp / ink',
      re: /(put|play).{0,40}into\s+your\s+inkwell|additional\s+card\s+into\s+your\s+inkwell/i },
  ],

  _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  },

  _resolvedCards(deckCode, opp) {
    if (!(window.V3 && window.V3.DeckGrid)) return [];
    const mu = opp && typeof getMatchupData === 'function' ? getMatchupData(opp) : null;
    return window.V3.DeckGrid._resolveCards(deckCode, mu);
  },

  _classCount(cls, cards) {
    if (typeof rvCardsDB === 'undefined' || !rvCardsDB) return 0;
    let count = 0;
    cards.forEach(c => {
      const meta = rvCardsDB[c.card];
      if (!meta || !meta.ability) return;
      const ab = meta.ability;
      if (cls.exclude && cls.exclude.test(ab)) return;
      if (cls.re.test(ab)) count += Number(c.qty) || 0;
    });
    return count;
  },

  buildClassBreakdown(cards) {
    const tiles = this.CLASSES.map(cls => {
      const n = this._classCount(cls, cards);
      const state = n === 0 ? 'dl-zero' : n >= 3 ? 'dl-good' : 'dl-warn';
      return `<div class="dl-class-tile ${state}">
        <div class="dl-class-icon" aria-hidden="true">${cls.icon}</div>
        <div class="dl-class-body">
          <div class="dl-class-label">${cls.label}</div>
          <div class="dl-class-count">${n}</div>
        </div>
      </div>`;
    }).join('');
    return `<div class="dl-section">
      <div class="dl-sec-title">Class breakdown
        <span class="dl-sec-info" title="Heuristic based on ability text — ~80% accurate. Some cards may be miscategorized. Use as a directional signal.">?</span>
      </div>
      <div class="dl-class-grid">${tiles}</div>
    </div>`;
  },

  _deltaVsConsensus(deckCode) {
    const consensus = (DATA.consensus || {})[deckCode] || {};
    const my = (typeof myDeckCards !== 'undefined' && myDeckCards && typeof myDeckMode !== 'undefined' && myDeckMode === 'custom')
      ? myDeckCards : null;
    if (!my) return { adds: [], cuts: [], empty: true };
    const names = new Set([...Object.keys(my), ...Object.keys(consensus)]);
    const adds = [], cuts = [];
    names.forEach(n => {
      const myQty = Math.round(Number(my[n] || 0));
      const consQty = Math.round(Number(consensus[n] || 0));
      const d = myQty - consQty;
      if (d > 0) adds.push({ name: n, delta: d, myQty, consQty });
      else if (d < 0) cuts.push({ name: n, delta: -d, myQty, consQty });
    });
    adds.sort((a, b) => b.delta - a.delta || a.name.localeCompare(b.name));
    cuts.sort((a, b) => b.delta - a.delta || a.name.localeCompare(b.name));
    return { adds, cuts, empty: false };
  },

  _deltaRow(item, isAdd, opp) {
    const short = this._esc(item.name.split(' - ')[0]);
    let wrBadge = '';
    if (opp) {
      const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
      if (mu && mu.card_scores && mu.card_scores[item.name]) {
        const delta = Number(mu.card_scores[item.name].delta || 0);
        const sample = Number(mu.card_scores[item.name].games || 0);
        if (sample >= 30) {
          const pp = (delta * 100).toFixed(1);
          const sign = delta >= 0 ? '+' : '';
          const cls = delta >= 0.02 ? 'ds-green' : delta <= -0.02 ? 'ds-red' : 'ds-yellow';
          wrBadge = `<span class="dl-wr ${cls}">${sign}${pp}pp</span>`;
        }
      }
    }
    const sign = isAdd ? '+' : '−';
    const dir = isAdd ? 'dl-add' : 'dl-cut';
    return `<div class="dl-delta-row ${dir}">
      <span class="dl-delta-qty">${sign}${item.delta}</span>
      <span class="dl-delta-name">${short}</span>
      <span class="dl-delta-meta">${item.myQty}↔${item.consQty}${wrBadge}</span>
    </div>`;
  },

  buildDelta(deckCode, opp) {
    const { adds, cuts, empty } = this._deltaVsConsensus(deckCode);
    if (empty) {
      return `<div class="dl-section">
        <div class="dl-sec-title">Your list vs consensus</div>
        <div class="dl-empty">You're playing the consensus list. Click <strong>Edit</strong> to customize and see diff.</div>
      </div>`;
    }
    const addsHtml = adds.length
      ? adds.slice(0, 12).map(a => this._deltaRow(a, true, opp)).join('')
      : '<div class="dl-empty">No extras vs consensus.</div>';
    const cutsHtml = cuts.length
      ? cuts.slice(0, 12).map(c => this._deltaRow(c, false, opp)).join('')
      : '<div class="dl-empty">Nothing cut vs consensus.</div>';
    return `<div class="dl-section">
      <div class="dl-sec-title">Your list vs consensus${opp ? ` · WR impact vs ${this._esc(opp)}` : ''}</div>
      <div class="dl-delta-cols">
        <div class="dl-delta-col">
          <div class="dl-delta-head dl-delta-head--add">Adds · ${adds.length}</div>
          ${addsHtml}
        </div>
        <div class="dl-delta-col">
          <div class="dl-delta-head dl-delta-head--cut">Cuts · ${cuts.length}</div>
          ${cutsHtml}
        </div>
      </div>
    </div>`;
  },

  build(deckCode, opponentCode) {
    if (!deckCode) return '';
    const cards = this._resolvedCards(deckCode, opponentCode);
    if (!cards.length) return '';
    return `<div class="dl-panel">
      <div class="dl-panel-title">Deck Lens</div>
      ${this.buildDelta(deckCode, opponentCode)}
      ${this.buildClassBreakdown(cards)}
    </div>`;
  },
};
