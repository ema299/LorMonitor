// Builder live status bar — 3 sticky semafori during edit mode.
// Shown above the deck grid + builder panel when V3.Builder.editMode is on.
// Rebuilt every render cycle (i.e. on every add/remove), so colors update
// live as the user edits.
//
// Semantics (docs/DECK_REFACTOR_PARITY.md Rule 4):
//   1. Deck size — green 60/60, yellow 58-62, red otherwise
//   2. Inkable   — inkable vs non-ink count + ratio; meta healthy ≈ 50-80% ink
//   3. Colors    — per-ink breakdown for the deck's two colors + dual-ink total
//
// Consumes: myDeckCards, DATA.consensus, rvCardsDB (for ink + inkable),
//   DECK_INKS (archetype → [ink1, ink2]).

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

  function _inkableStatus(entries) {
    if (typeof rvCardsDB === 'undefined' || !rvCardsDB) {
      return { cls: 'bs-gray', icon: '⚪', title: 'Inkable', label: 'Loading card DB' };
    }
    let inkable = 0, nonInk = 0, unknown = 0;
    entries.forEach(function (e) {
      const meta = rvCardsDB[e.card];
      const qty = e.qty || 0;
      if (!meta || meta.inkable === undefined || meta.inkable === null) {
        unknown += qty; return;
      }
      if (meta.inkable === true || meta.inkable === 'true' || meta.inkable === 1) inkable += qty;
      else nonInk += qty;
    });
    const known = inkable + nonInk;
    if (!known && !unknown) return { cls: 'bs-gray', icon: '⚪', title: 'Inkable', label: 'No cards' };
    if (!known) return { cls: 'bs-gray', icon: '⚪', title: 'Inkable', label: unknown + ' unknown' };

    const pct = Math.round((inkable / known) * 100);
    // Deck-building heuristic: ~60-80% inkable is typical meta. Below 50% is
    // often a tempo trap (not enough ink to pay for cards); above 85% is
    // stats-heavy and light on tech answers.
    let cls, icon;
    if (pct >= 60 && pct <= 80) { cls = 'bs-green'; icon = '🟢'; }
    else if (pct >= 50 && pct <= 85) { cls = 'bs-yellow'; icon = '🟡'; }
    else { cls = 'bs-red'; icon = '🔴'; }
    const note = unknown ? ' · ' + unknown + ' unknown' : '';
    return {
      cls: cls, icon: icon, title: 'Inkable',
      label: inkable + ' ink · ' + nonInk + ' no-ink · ' + pct + '%' + note,
    };
  }

  // Deck color breakdown. Lorcana decks use two inks; cards are either
  // single-ink (one of the two) or dual-ink (both). Shown as:
  //   "Em 31 · Sa 24 · Dual 5"
  // Out-of-color ink appears only if misplayed builds have it (tracked as
  // warning yellow). Unknown / Inkless / Location-neutral cards go in a
  // trailing "other N" bucket.
  function _colorsStatus(entries, deckCode) {
    if (typeof rvCardsDB === 'undefined' || !rvCardsDB) {
      return { cls: 'bs-gray', icon: '⚪', title: 'Colors', label: 'Loading card DB' };
    }
    const targetInks = (typeof DECK_INKS !== 'undefined' && DECK_INKS[deckCode]) || [];
    if (targetInks.length < 2) {
      return { cls: 'bs-gray', icon: '⚪', title: 'Colors', label: 'No archetype colors' };
    }
    const ink1 = String(targetInks[0] || '').toLowerCase();
    const ink2 = String(targetInks[1] || '').toLowerCase();

    let c1 = 0, c2 = 0, dual = 0, other = 0, offColor = 0;
    entries.forEach(function (e) {
      const meta = rvCardsDB[e.card];
      const qty = e.qty || 0;
      if (!meta) { other += qty; return; }
      const inkRaw = String(meta.ink || '').toLowerCase();
      if (!inkRaw) { other += qty; return; }
      if (inkRaw.includes('/')) {
        // duels.ink encoding for dual ink (e.g. "amethyst/sapphire")
        const parts = inkRaw.split('/').map(function (s) { return s.trim(); });
        const hitsDeck = (parts.indexOf(ink1) >= 0) || (parts.indexOf(ink2) >= 0);
        if (hitsDeck) dual += qty; else offColor += qty;
        return;
      }
      if (inkRaw === ink1) c1 += qty;
      else if (inkRaw === ink2) c2 += qty;
      else if (inkRaw === 'dual ink') dual += qty;
      else if (inkRaw === 'inkless' || inkRaw === 'location') other += qty;
      else offColor += qty;
    });

    const bits = [
      _inkLabel(targetInks[0]) + ' ' + c1,
      _inkLabel(targetInks[1]) + ' ' + c2,
    ];
    if (dual) bits.push('Dual ' + dual);
    if (other) bits.push('Other ' + other);
    if (offColor) bits.push('Off-color ' + offColor);

    let cls, icon;
    if (offColor > 0) { cls = 'bs-red'; icon = '🔴'; }
    else if (other > 4) { cls = 'bs-yellow'; icon = '🟡'; }
    else { cls = 'bs-green'; icon = '🟢'; }
    return { cls: cls, icon: icon, title: 'Colors', label: bits.join(' · ') };
  }

  // Short ink label suitable for the strip — uppercase 3-letter abbreviation.
  function _inkLabel(ink) {
    const s = String(ink || '').toLowerCase();
    const map = {
      amber: 'Amb', amethyst: 'Amy', emerald: 'Em',
      ruby: 'Rub', sapphire: 'Sap', steel: 'Stl',
    };
    return map[s] || ink;
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
    const inkable = _inkableStatus(entries);
    const colors = _colorsStatus(entries, deckCode);

    return '<div class="bs-bar" role="status" aria-live="polite">' +
      _pill(size) + _pill(inkable) + _pill(colors) +
      '</div>';
  }

  window.V3.BuilderStatus = {
    MATRIX_MIN_GAMES: MATRIX_MIN_GAMES,
    build: build,
    _worstObservedOpp: _worstObservedOpp,
  };
})();
