// Builder live status bar — 3 sticky semafori during edit mode.
// Shown above the deck grid + builder panel when V3.Builder.editMode is on.
// Rebuilt every render cycle (i.e. on every add/remove), so colors update
// live as the user edits.
//
// Semantics (docs/DECK_REFACTOR_PARITY.md Rule 4):
//   1. Deck size    — green 60/60, yellow 58-62, red otherwise
//   2. Curve health — balanced / top-heavy / low-curve (from cost distribution)
//   3. Response cov — 🟢 ≥4 of top 5 curves covered / 🟡 2-3 / 🔴 0-1
//                     Uses worst observed matchup when no opp is set.
//
// Consumes: myDeckCards, DATA.consensus, rvCardsDB (for costs), getPerimData,
//   getMatchupData, V3.ResponseCheck._coverageForCurve.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const MATRIX_MIN_GAMES = 15;

  function _deckEntries(deckCode) {
    if (window.V3 && window.V3.DeckGrid && typeof window.V3.DeckGrid._resolveCards === 'function') {
      return window.V3.DeckGrid._resolveCards(deckCode, null) || [];
    }
    return [];
  }

  function _sizeStatus(entries) {
    const total = entries.reduce(function (s, c) { return s + (c.qty || 0); }, 0);
    if (total === 60) return { cls: 'bs-green', icon: '🟢', title: 'Deck size', label: total + ' / 60 cards' };
    if (total >= 58 && total <= 62) return { cls: 'bs-yellow', icon: '🟡', title: 'Deck size', label: total + ' / 60 cards' };
    return { cls: 'bs-red', icon: '🔴', title: 'Deck size', label: total + ' / 60 cards' };
  }

  function _curveStatus(entries) {
    if (typeof rvCardsDB === 'undefined' || !rvCardsDB) {
      return { cls: 'bs-gray', icon: '⚪', title: 'Curve', label: 'Loading card DB' };
    }
    const buckets = {};
    let total = 0;
    let weightedCost = 0;
    entries.forEach(function (e) {
      const meta = rvCardsDB[e.card];
      if (!meta) return;
      const cost = parseInt(meta.cost, 10);
      if (!Number.isFinite(cost)) return;
      const qty = e.qty || 0;
      buckets[cost] = (buckets[cost] || 0) + qty;
      total += qty;
      weightedCost += qty * cost;
    });
    if (!total) return { cls: 'bs-gray', icon: '⚪', title: 'Curve', label: 'No cost data' };

    const avg = weightedCost / total;
    const lowShare = ((buckets[0] || 0) + (buckets[1] || 0) + (buckets[2] || 0)) / total;
    const highShare = Object.keys(buckets)
      .map(Number)
      .filter(function (c) { return c >= 6; })
      .reduce(function (s, c) { return s + (buckets[c] || 0); }, 0) / total;

    // Heuristic bands. Lorcana decks typically want avg cost 3.3-4.0.
    let label, cls, icon;
    if (avg < 2.8 || lowShare > 0.55) { label = 'Low-curve'; cls = 'bs-yellow'; icon = '🟡'; }
    else if (avg > 4.3 || highShare > 0.30) { label = 'Top-heavy'; cls = 'bs-yellow'; icon = '🟡'; }
    else if (avg >= 3.2 && avg <= 4.0 && lowShare >= 0.25) { label = 'Balanced'; cls = 'bs-green'; icon = '🟢'; }
    else { label = 'Workable'; cls = 'bs-green'; icon = '🟢'; }

    if (avg < 2.2 || avg > 5.0) { label = 'Skewed'; cls = 'bs-red'; icon = '🔴'; }

    return { cls: cls, icon: icon, title: 'Curve', label: label + ' · avg ' + avg.toFixed(1) };
  }

  function _worstObservedOpp(deckCode) {
    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return null;
    const row = pd.matrix[deckCode];
    let worst = null;
    Object.keys(row).forEach(function (opp) {
      const cell = row[opp];
      if (!cell || (cell.t || 0) < MATRIX_MIN_GAMES) return;
      const wr = (cell.w || 0) / cell.t;
      if (worst == null || wr < worst.wr) worst = { opp: opp, wr: wr, games: cell.t };
    });
    return worst;
  }

  function _deckMap(deckCode) {
    const map = {};
    _deckEntries(deckCode).forEach(function (e) {
      const raw = String(e.card || '').trim();
      const base = raw.includes(' - ') ? raw.split(' - ')[0] : raw;
      const k = base.toLowerCase();
      if (!k) return;
      map[k] = (map[k] || 0) + (e.qty || 0);
    });
    return map;
  }

  function _coverageStatus(deckCode, oppCode) {
    let opp = oppCode;
    let autoDerived = false;
    if (!opp) {
      const worst = _worstObservedOpp(deckCode);
      if (worst) { opp = worst.opp; autoDerived = true; }
    }
    if (!opp) return { cls: 'bs-gray', icon: '⚪', title: 'Coverage', label: 'No observed matchup' };

    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    if (!curves.length) return { cls: 'bs-gray', icon: '⚪', title: 'Coverage', label: 'No curves vs ' + opp };

    const sorted = curves.slice().sort(function (a, b) {
      return ((b.frequency && b.frequency.pct) || 0) - ((a.frequency && a.frequency.pct) || 0);
    }).slice(0, 5);

    const map = _deckMap(deckCode);
    let covered = 0;
    sorted.forEach(function (curve) {
      if (!(window.V3 && window.V3.ResponseCheck &&
            typeof window.V3.ResponseCheck._coverageForCurve === 'function')) return;
      const cov = window.V3.ResponseCheck._coverageForCurve(curve, map);
      if (cov && (cov.status === 'green' || cov.status === 'yellow')) covered += 1;
    });

    const suffix = ' of top 5 vs ' + opp + (autoDerived ? ' (worst)' : '');
    let cls, icon;
    if (covered >= 4) { cls = 'bs-green'; icon = '🟢'; }
    else if (covered >= 2) { cls = 'bs-yellow'; icon = '🟡'; }
    else { cls = 'bs-red'; icon = '🔴'; }
    return { cls: cls, icon: icon, title: 'Coverage', label: covered + suffix };
  }

  function _pill(s) {
    return '<div class="bs-pill ' + s.cls + '" title="' + s.title + '">' +
      '<span class="bs-icon">' + s.icon + '</span>' +
      '<span class="bs-text"><span class="bs-pill-title">' + s.title + '</span>' +
      '<span class="bs-pill-label">' + s.label + '</span></span>' +
      '</div>';
  }

  function build(deckCode, oppCode) {
    if (!deckCode) return '';
    const entries = _deckEntries(deckCode);
    const size = _sizeStatus(entries);
    const curve = _curveStatus(entries);
    const cov = _coverageStatus(deckCode, oppCode);

    return '<div class="bs-bar" role="status" aria-live="polite">' +
      _pill(size) + _pill(curve) + _pill(cov) +
      '</div>';
  }

  window.V3.BuilderStatus = {
    MATRIX_MIN_GAMES: MATRIX_MIN_GAMES,
    build: build,
    _worstObservedOpp: _worstObservedOpp,
  };
})();
