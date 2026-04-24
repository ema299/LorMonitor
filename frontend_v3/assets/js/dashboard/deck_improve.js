// Deck tab — Area B Improve.
// Contract: docs/DECK_REFACTOR_PARITY.md rows 14, 16, 17, 18, 46 + open q #1.
// Two sub-sections:
//   1. Cards trending in this archetype — 🟢 overperforming / 🔴 underperforming
//      per card_scores delta (requires opp selected; otherwise prompts).
//      Same engine as deck_grid._statusDot (MIN_SAMPLE=30, ±2pp).
//   2. Archetype Leak Detector — observed patterns where this list
//      underperforms. Default ranking (PR3 decision on open q #1):
//        1. Response gaps in top-3 worst observed matchups (most actionable)
//        2. OTP/OTD structural gap > 10pp aggregated across observed opps
//        3. Killer curve failure states in worst matchups (tactical)
//        4. Loss analysis extract if available
//      Cap at 4 leaks. Copy is observed-not-personal (Rule 1).
//
// Globals consumed: DATA, getPerimData, getMatchupData, currentFormat.
// Depends on: window.V3.HonestyBadge for format helpers.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const MIN_SAMPLE = 30;
  const STRONG_DELTA_PP = 2;
  const MATRIX_MIN_GAMES = 15;
  const OTP_OTD_GAP_PP = 10;
  const MAX_PER_BUCKET = 5;
  const MAX_LEAKS = 4;
  const DEFAULT_DAYS = 14;

  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function _short(name) { return (name || '').split(' - ')[0]; }

  function _hb() { return window.V3 && window.V3.HonestyBadge; }

  // ---------------------- Cards trending ----------------------

  function _trendRows(deckCode, oppCode) {
    if (!oppCode) return null;
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(oppCode) : null;
    const scores = (mu && mu.card_scores) || {};
    const over = [];
    const under = [];
    Object.keys(scores).forEach(function (name) {
      const entry = scores[name];
      if (!entry) return;
      const games = Number(entry.games || 0);
      if (games < MIN_SAMPLE) return;
      const delta = Number(entry.delta || 0);
      const pp = delta * 100;
      if (pp >= STRONG_DELTA_PP) over.push({ name: name, pp: pp, games: games });
      else if (pp <= -STRONG_DELTA_PP) under.push({ name: name, pp: pp, games: games });
    });
    over.sort(function (a, b) { return b.pp - a.pp; });
    under.sort(function (a, b) { return a.pp - b.pp; });
    return { over: over.slice(0, MAX_PER_BUCKET), under: under.slice(0, MAX_PER_BUCKET) };
  }

  function _cardRow(r, isOver) {
    const hb = _hb();
    const dot = isOver ? '🟢' : '🔴';
    const deltaFmt = hb ? hb.formatDelta(r.pp, r.games) : (r.pp >= 0 ? '+' : '') + r.pp.toFixed(1) + 'pp';
    return '<li class="im-card-row ' + (isOver ? 'im-over' : 'im-under') + '">' +
      '<span class="im-dot">' + dot + '</span>' +
      '<span class="im-card-name">' + _esc(_short(r.name)) + '</span>' +
      '<span class="im-card-stat">' + deltaFmt +
      ' <span class="im-card-sample">on ' + r.games + ' observed games</span>' +
      '</span></li>';
  }

  function _trendingSection(deckCode, oppCode) {
    if (!oppCode) {
      return '<div class="im-section">' +
        '<div class="im-sec-title">Cards trending in this archetype</div>' +
        '<div class="im-empty">Pick an opponent above to see per-card signals in the observed sample.</div>' +
        '</div>';
    }
    const t = _trendRows(deckCode, oppCode);
    if (!t || (!t.over.length && !t.under.length)) {
      return '<div class="im-section">' +
        '<div class="im-sec-title">Cards trending in this archetype <span class="im-sec-sub">vs ' + _esc(oppCode) + '</span></div>' +
        '<div class="im-empty">No card shows a ±' + STRONG_DELTA_PP + 'pp signal on ≥' + MIN_SAMPLE + ' observed games vs ' + _esc(oppCode) + '.</div>' +
        '</div>';
    }
    const overHtml = t.over.length
      ? '<ul class="im-card-list">' + t.over.map(function (r) { return _cardRow(r, true); }).join('') + '</ul>'
      : '<div class="im-empty-inline">No card with ≥+' + STRONG_DELTA_PP + 'pp signal.</div>';
    const underHtml = t.under.length
      ? '<ul class="im-card-list">' + t.under.map(function (r) { return _cardRow(r, false); }).join('') + '</ul>'
      : '<div class="im-empty-inline">No card with ≤−' + STRONG_DELTA_PP + 'pp signal.</div>';

    return '<div class="im-section">' +
      '<div class="im-sec-title">Cards trending in this archetype ' +
      '<span class="im-sec-sub">vs ' + _esc(oppCode) + ' · card_scores · ' + DEFAULT_DAYS + 'd</span></div>' +
      '<div class="im-bucket-grid">' +
      '<div class="im-bucket"><div class="im-bucket-head">🟢 Overperforming</div>' + overHtml + '</div>' +
      '<div class="im-bucket"><div class="im-bucket-head">🔴 Underperforming</div>' + underHtml + '</div>' +
      '</div></div>';
  }

  // ---------------------- Archetype Leak Detector ----------------------

  // Leak 1: top-3 worst observed matchups with visible response gaps.
  function _leaksFromResponseGaps(deckCode, pd) {
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return [];
    const row = pd.matrix[deckCode];
    const opps = Object.keys(row).map(function (opp) {
      const cell = row[opp];
      if (!cell || (cell.t || 0) < MATRIX_MIN_GAMES) return null;
      return { opp: opp, wr: (cell.w || 0) / cell.t * 100, games: cell.t };
    }).filter(Boolean).sort(function (a, b) { return a.wr - b.wr; }).slice(0, 3);

    const deckMap = (window.V3 && window.V3.DeckGrid && window.V3.DeckGrid._resolveCards)
      ? (function () {
          const map = {};
          (window.V3.DeckGrid._resolveCards(deckCode, null) || []).forEach(function (c) {
            const raw = String(c.card || '').trim();
            const base = raw.includes(' - ') ? raw.split(' - ')[0] : raw;
            const k = base.toLowerCase();
            if (k) map[k] = (map[k] || 0) + (c.qty || 0);
          });
          return map;
        })()
      : {};

    const leaks = [];
    opps.forEach(function (o) {
      const mu = (typeof getMatchupData === 'function') ? getMatchupData(o.opp) : null;
      const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves.slice(0, 3) : [];
      let uncoveredCurve = null;
      curves.forEach(function (curve) {
        if (uncoveredCurve) return;
        const answers = (curve && curve.response && Array.isArray(curve.response.cards))
          ? curve.response.cards : [];
        if (!answers.length) return;
        let copies = 0;
        answers.forEach(function (a) {
          const raw = String(a).trim();
          const base = raw.includes(' - ') ? raw.split(' - ')[0] : raw;
          copies += deckMap[base.toLowerCase()] || 0;
        });
        if (copies < 1) uncoveredCurve = curve;
      });
      if (uncoveredCurve) {
        leaks.push({
          priority: 1,
          title: 'No listed answers for ' + (uncoveredCurve.name || 'top line') + ' vs ' + o.opp,
          detail: 'Observed WR ' + Math.round(o.wr) + '% on ' + o.games +
            ' games · critical turn T' + (uncoveredCurve.critical_turn && uncoveredCurve.critical_turn.turn || '?'),
          opp: o.opp,
        });
      }
    });
    return leaks;
  }

  // Leak 2: OTP/OTD structural gap aggregated across observed matchups.
  function _leakFromOtpOtd(deckCode, pd) {
    if (!pd || !pd.otp_otd || !pd.otp_otd[deckCode]) return [];
    const row = pd.otp_otd[deckCode];
    let otpW = 0, otpT = 0, otdW = 0, otdT = 0;
    Object.keys(row).forEach(function (opp) {
      const cell = row[opp];
      if (!cell) return;
      otpW += Number(cell.otp_w || 0);
      otpT += Number(cell.otp_t || 0);
      otdW += Number(cell.otd_w || 0);
      otdT += Number(cell.otd_t || 0);
    });
    if (otpT < MIN_SAMPLE || otdT < MIN_SAMPLE) return [];
    const otpWr = otpW / otpT * 100;
    const otdWr = otdW / otdT * 100;
    const gap = otpWr - otdWr;
    if (Math.abs(gap) < OTP_OTD_GAP_PP) return [];
    const weaker = gap > 0 ? 'OTD (going second)' : 'OTP (going first)';
    const weakerWr = gap > 0 ? otdWr : otpWr;
    const weakerGames = gap > 0 ? otdT : otpT;
    const strongerWr = gap > 0 ? otpWr : otdWr;
    return [{
      priority: 2,
      title: 'Structural gap on ' + weaker,
      detail: Math.round(weakerWr) + '% ' + weaker + ' vs ' + Math.round(strongerWr) + '% the other side · ' +
        Math.abs(gap).toFixed(1) + 'pp swing on ' + weakerGames + ' observed games',
    }];
  }

  // Leak 3: failure_state from killer_curves in worst matchups.
  function _leaksFromFailureStates(deckCode, pd) {
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return [];
    const row = pd.matrix[deckCode];
    const opps = Object.keys(row).map(function (opp) {
      const cell = row[opp];
      if (!cell || (cell.t || 0) < MATRIX_MIN_GAMES) return null;
      return { opp: opp, wr: (cell.w || 0) / cell.t * 100 };
    }).filter(Boolean).sort(function (a, b) { return a.wr - b.wr; }).slice(0, 2);

    const leaks = [];
    opps.forEach(function (o) {
      const mu = (typeof getMatchupData === 'function') ? getMatchupData(o.opp) : null;
      const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
      const hit = curves.find(function (c) {
        return c && c.response && typeof c.response.failure_state === 'string' && c.response.failure_state.trim();
      });
      if (hit && hit.response && hit.response.failure_state) {
        leaks.push({
          priority: 3,
          title: 'Failure state vs ' + o.opp,
          detail: String(hit.response.failure_state).trim(),
          opp: o.opp,
        });
      }
    });
    return leaks;
  }

  // Leak 4: loss_analysis text extract from worst matchup.
  function _leakFromLossAnalysis(deckCode, pd) {
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return [];
    const row = pd.matrix[deckCode];
    let worst = null;
    Object.keys(row).forEach(function (opp) {
      const cell = row[opp];
      if (!cell || (cell.t || 0) < MATRIX_MIN_GAMES) return;
      const wr = (cell.w || 0) / cell.t;
      if (worst == null || wr < worst.wr) worst = { opp: opp, wr: wr };
    });
    if (!worst) return [];
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(worst.opp) : null;
    const la = mu && mu.loss_analysis;
    if (!la) return [];
    let snippet = '';
    if (typeof la === 'string') snippet = la;
    else if (la.summary) snippet = la.summary;
    else if (Array.isArray(la.reasons) && la.reasons.length) snippet = la.reasons[0];
    if (!snippet || snippet.length < 10) return [];
    if (snippet.length > 140) snippet = snippet.slice(0, 137) + '…';
    return [{
      priority: 4,
      title: 'Loss analysis vs ' + worst.opp,
      detail: snippet,
      opp: worst.opp,
    }];
  }

  function _buildLeaks(deckCode) {
    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    if (!pd) return [];
    const leaks = []
      .concat(_leaksFromResponseGaps(deckCode, pd))
      .concat(_leakFromOtpOtd(deckCode, pd))
      .concat(_leaksFromFailureStates(deckCode, pd))
      .concat(_leakFromLossAnalysis(deckCode, pd));
    // dedupe by title
    const seen = Object.create(null);
    const out = [];
    leaks.forEach(function (l) {
      if (seen[l.title]) return;
      seen[l.title] = true;
      out.push(l);
    });
    return out.slice(0, MAX_LEAKS);
  }

  function _leakDetectorSection(deckCode) {
    const leaks = _buildLeaks(deckCode);
    if (!leaks.length) {
      return '<div class="im-section">' +
        '<div class="im-sec-title">Archetype Leak Detector</div>' +
        '<div class="im-empty">No structural leaks detected in the observed sample yet.</div>' +
        '</div>';
    }
    const rows = leaks.map(function (l) {
      return '<li class="im-leak im-leak-p' + l.priority + '">' +
        '<div class="im-leak-head">' + _esc(l.title) + '</div>' +
        '<div class="im-leak-body">' + _esc(l.detail) + '</div>' +
        '</li>';
    }).join('');
    return '<div class="im-section">' +
      '<div class="im-sec-title">Archetype Leak Detector ' +
      '<span class="im-sec-sub">observed patterns where this list underperforms</span></div>' +
      '<ul class="im-leak-list">' + rows + '</ul>' +
      '</div>';
  }

  function build(deckCode, opponentCode) {
    if (!deckCode) return '';
    const header =
      '<div class="im-header">' +
      '<div class="im-header-title">Improve</div>' +
      '<div class="im-header-sub">What the observed sample says about this list</div>' +
      '</div>';
    return '<div class="im-card">' +
      header +
      _trendingSection(deckCode, opponentCode) +
      _leakDetectorSection(deckCode) +
      '</div>';
  }

  window.V3.DeckImprove = {
    MIN_SAMPLE: MIN_SAMPLE,
    STRONG_DELTA_PP: STRONG_DELTA_PP,
    OTP_OTD_GAP_PP: OTP_OTD_GAP_PP,
    build: build,
    _buildLeaks: _buildLeaks,
    _trendRows: _trendRows,
  };
})();
