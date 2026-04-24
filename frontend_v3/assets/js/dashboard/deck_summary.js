// Deck tab — Area A Summary (above the fold).
// Contract: docs/DECK_REFACTOR_PARITY.md §Parity table rows 1-11, 20.
// Renders:
//   1. Deck header (inks + name + tier badge)
//   2. Main KPI (archetype WR) with honesty badge + WR sparkline
//   3. Secondary row: Games · Meta Share · Fitness Rank · Worst Matchup
//   4. Response Coverage mini-block (Rule 2, always above the fold)
//   5. Recommended Actions (Data suggests... via RecommendationEngine)
//
// Depends on:
//   window.V3.HonestyBadge      (honesty_badge.js)
//   window.V3.RecommendationEngine (deck_recommendation_engine.js)
//   window.V3.DeckOverview.computeTier (reused for S/A/B/C derivation)
//   window.V3.ResponseCheck     (deck_response_check.js, mini-renderer)
// Globals consumed: DATA, getPerimData, getScopeContext, getMatchupData,
//   DECK_INKS, INK_COLORS.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const DEFAULT_DAYS = 3;          // matches snapshot_assembler DAYS
  const MATRIX_MIN_GAMES = 15;
  const RC_GREEN = 3;              // ≥3 answer copies → green
  const RC_YELLOW = 1;

  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function _shortCard(name) {
    return (name || '').split(' - ')[0];
  }

  function _inkDots(inks) {
    return (inks || []).map(function (i) {
      const col = (typeof INK_COLORS !== 'undefined' && INK_COLORS[i]) || '#888';
      return '<span class="sm-ink-dot" style="background:' + col + '" title="' + _esc(i) + '"></span>';
    }).join('');
  }

  function _inksLabel(inks) {
    return (inks || []).map(function (i) {
      return i.charAt(0).toUpperCase() + i.slice(1);
    }).join(' · ');
  }

  // Find fitness rank for a deck in the current perimeter.
  function _fitnessRank(deckCode, pd) {
    if (!pd || !Array.isArray(pd.fitness)) return null;
    const row = pd.fitness.find(function (r) { return r.deck === deckCode; });
    if (!row) return null;
    return { rank: row.rank, total: pd.fitness.length, fitness: row.fitness };
  }

  // Worst observed matchup from perimeters[p].matrix[deck] with min N guard.
  function _worstMatchup(deckCode, pd) {
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return null;
    const row = pd.matrix[deckCode];
    let worst = null;
    Object.keys(row).forEach(function (opp) {
      const cell = row[opp];
      if (!cell) return;
      const t = cell.t || 0;
      if (t < MATRIX_MIN_GAMES) return;
      const wr = (cell.w || 0) / t * 100;
      if (worst == null || wr < worst.wr) {
        worst = { opp: opp, wr: wr, games: t };
      }
    });
    return worst;
  }

  // Build a WR sparkline from perimeters[p].trend: trend[day][deck] = {w,l}.
  // Returns inline SVG (20x8 viewBox scaled to 100x28 display) or '' if <2 points.
  function _sparkline(deckCode, pd) {
    if (!pd || !pd.trend) return '';
    const days = Object.keys(pd.trend).sort(function (a, b) {
      // day format "DD/MM" — sort by parts
      const pa = a.split('/').map(Number); const pb = b.split('/').map(Number);
      if (pa[1] !== pb[1]) return pa[1] - pb[1];
      return pa[0] - pb[0];
    });
    const points = [];
    days.forEach(function (d) {
      const entry = pd.trend[d] && pd.trend[d][deckCode];
      if (!entry) return;
      const g = (entry.w || 0) + (entry.l || 0);
      if (g < 5) return; // skip low-sample days
      const wr = (entry.w || 0) / g * 100;
      points.push({ d: d, wr: wr, g: g });
    });
    if (points.length < 2) return '';
    const width = 80;
    const height = 24;
    const min = Math.min.apply(null, points.map(function (p) { return p.wr; }));
    const max = Math.max.apply(null, points.map(function (p) { return p.wr; }));
    const range = Math.max(1, max - min);
    const stepX = width / (points.length - 1);
    const coords = points.map(function (p, i) {
      const x = i * stepX;
      const y = height - ((p.wr - min) / range) * (height - 4) - 2;
      return x.toFixed(1) + ',' + y.toFixed(1);
    });
    const last = points[points.length - 1];
    const first = points[0];
    const cls = last.wr > first.wr ? 'sm-spark-up' : last.wr < first.wr ? 'sm-spark-down' : 'sm-spark-flat';
    return '<svg class="sm-spark ' + cls + '" viewBox="0 0 ' + width + ' ' + height + '" ' +
      'preserveAspectRatio="none" aria-label="WR trend over ' + points.length + ' days">' +
      '<polyline fill="none" stroke-width="2" points="' + coords.join(' ') + '"></polyline>' +
      '</svg>';
  }

  // Response Coverage mini-block inline, reusing the existing response_check
  // logic but in compact form. Auto-derives worst matchup if no opp selected.
  function _responseCoverageMini(deckCode, opponentCode, pd) {
    let opp = opponentCode;
    let autoDerived = false;
    let worst = null;
    if (!opp) {
      worst = _worstMatchup(deckCode, pd);
      if (worst) { opp = worst.opp; autoDerived = true; }
    }
    if (!opp) return '';

    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    if (!curves.length) return '';

    const sorted = curves.slice().sort(function (a, b) {
      return ((b.frequency && b.frequency.pct) || 0) - ((a.frequency && a.frequency.pct) || 0);
    }).slice(0, 5);

    let covered = 0;
    let totalCopies = 0;
    sorted.forEach(function (curve) {
      const cov = window.V3.ResponseCheck
        ? window.V3.ResponseCheck._coverageForCurve(curve, _deckMap(deckCode, mu))
        : null;
      if (!cov) return;
      if (cov.status === 'green' || cov.status === 'yellow') covered += 1;
      totalCopies += cov.copies;
    });

    const statusCls = covered >= 4 ? 'sm-rc--good' : covered >= 2 ? 'sm-rc--mid' : 'sm-rc--bad';
    const statusLabel = covered >= 4 ? 'Good coverage' : covered >= 2 ? 'Medium coverage' : 'Low coverage';
    const statusDot = covered >= 4 ? '🟢' : covered >= 2 ? '🟡' : '🔴';

    const contextBits = [];
    const muWr = (pd && pd.matrix && pd.matrix[deckCode] && pd.matrix[deckCode][opp])
      ? pd.matrix[deckCode][opp] : null;
    if (muWr) {
      const mwr = (muWr.w || 0) / Math.max(1, muWr.t);
      const games = muWr.t;
      const wrText = (window.V3 && window.V3.HonestyBadge)
        ? window.V3.HonestyBadge.formatPct(mwr * 100, games)
        : (mwr * 100).toFixed(0) + '%';
      contextBits.push(wrText + ' on ' + games + ' observed games');
    }
    if (autoDerived) contextBits.push('worst observed matchup');

    const hint = contextBits.length ? ' <span class="sm-rc-context">(' + contextBits.join(' · ') + ')</span>' : '';

    return '<div class="sm-rc ' + statusCls + '">' +
      '<div class="sm-rc-head">Response coverage vs <strong>' + _esc(opp) + '</strong>' + hint + '</div>' +
      '<div class="sm-rc-body">' +
      '<span class="sm-rc-dot">' + statusDot + '</span>' +
      '<span class="sm-rc-text">Covers ' + covered + '/' + sorted.length +
      ' top threat lines · ' + statusLabel + '</span>' +
      '<a class="sm-rc-cta" href="#" onclick="window.V3.DeckSummary._requestWorkspace(\'' + _esc(opp) + '\');return false">View details →</a>' +
      '</div></div>';
  }

  // Share the same deck map logic as ResponseCheck._deckCardMap (private), so
  // we rebuild it here to avoid cross-module private access.
  function _deckMap(deckCode, mu) {
    if (!(window.V3 && window.V3.DeckGrid)) return {};
    const cards = window.V3.DeckGrid._resolveCards(deckCode, mu) || [];
    const map = {};
    cards.forEach(function (c) {
      const raw = String(c.card || '').trim();
      const base = raw.includes(' - ') ? raw.split(' - ')[0] : raw;
      const k = base.toLowerCase();
      if (!k) return;
      map[k] = (map[k] || 0) + (c.qty || 0);
    });
    return map;
  }

  function _recommendedActions(deckCode, opponentCode) {
    if (!(window.V3 && window.V3.RecommendationEngine)) return '';
    const actions = window.V3.RecommendationEngine.compute(deckCode, opponentCode);
    if (!actions.length) return '';
    const rows = actions.map(function (a) {
      return window.V3.RecommendationEngine.renderAction(a);
    }).join('');
    return '<div class="sm-rec">' +
      '<div class="sm-rec-title">Recommended actions <span class="sm-rec-sub">data-driven</span></div>' +
      '<div class="sm-rec-list">' + rows + '</div>' +
      '</div>';
  }

  function _emptyState(deckCode) {
    return '<div class="sm-empty">' +
      '<div class="sm-empty-title">' + _esc(deckCode || 'No deck selected') + '</div>' +
      '<div class="sm-empty-sub">No observed data for this deck in the current scope.</div>' +
      '</div>';
  }

  // Store last build inputs so external handlers (e.g. matchup workspace CTA)
  // can reach back. Kept minimal — no real state, just an escape hatch.
  let _lastBuild = { deck: null, opp: null };

  function _requestWorkspace(opp) {
    // PR5: open the Matchup Workspace overlay. Falls back to setting labOpp
    // and re-rendering if the workspace module isn't loaded yet.
    const deck = _lastBuild.deck || (typeof coachDeck !== 'undefined' ? coachDeck : null);
    if (deck && opp && window.V3 && window.V3.MatchupWorkspace &&
        typeof window.V3.MatchupWorkspace.open === 'function') {
      window.V3.MatchupWorkspace.open(deck, opp);
      return;
    }
    if (typeof labOpp !== 'undefined' && opp) {
      try { labOpp = opp; } catch (e) {}
    }
    if (typeof render === 'function') render();
  }

  function build(deckCode, opponentCode) {
    _lastBuild = { deck: deckCode, opp: opponentCode || null };
    if (!deckCode) return _emptyState(null);

    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    if (!pd || !pd.wr || !pd.wr[deckCode]) return _emptyState(deckCode);

    const scope = (typeof getScopeContext === 'function') ? getScopeContext() : {};
    const wrEntry = pd.wr[deckCode];
    const wr = Number(wrEntry.wr || 0);
    const games = Number(wrEntry.games || 0);
    const share = pd.meta_share && pd.meta_share[deckCode] != null
      ? Number(pd.meta_share[deckCode].share) : null;
    const inks = (typeof DECK_INKS !== 'undefined' && DECK_INKS[deckCode]) || [];
    const allWrs = Object.values(pd.wr).map(function (v) { return Number(v.wr || 0); });
    const tier = (window.V3 && window.V3.DeckOverview)
      ? window.V3.DeckOverview.computeTier(wr, allWrs)
      : { label: '?', cls: 'tier-unk' };
    const fit = _fitnessRank(deckCode, pd);
    const worst = _worstMatchup(deckCode, pd);

    const hb = window.V3 && window.V3.HonestyBadge;
    const wrStr = hb ? hb.formatPct(wr, games) : wr.toFixed(1) + '%';
    const confCls = hb ? hb.confidenceClass(games) : 'hb-med';
    const confLabel = hb ? hb.confidenceLabel(games) : 'Medium';

    const spark = _sparkline(deckCode, pd);
    const scopeName = (scope.perimeter || '').toUpperCase();

    const header = '<div class="sm-header">' +
      '<div class="sm-header-left">' +
      '<div class="sm-inks">' + _inkDots(inks) + '</div>' +
      '<div>' +
      '<div class="sm-title">' + _esc(deckCode) + '</div>' +
      '<div class="sm-sub">' + _esc(_inksLabel(inks)) + (scopeName ? ' · ' + scopeName : '') + '</div>' +
      '</div>' +
      '</div>' +
      '<div class="sm-tier ' + tier.cls + '" title="Tier derived from WR percentile in observed sample">' +
      tier.label +
      '</div>' +
      '</div>';

    const mainKpi = '<div class="sm-main">' +
      '<div class="sm-main-wr">' + wrStr + '</div>' +
      '<div class="sm-main-meta">' +
      'on ' + games.toLocaleString() + ' observed games · ' + DEFAULT_DAYS + 'd · ' +
      '<span class="hb-conf ' + confCls + '">' + confLabel + ' confidence</span>' +
      '</div>' +
      (spark ? '<div class="sm-main-spark">' + spark + '</div>' : '') +
      '</div>';

    const secondary = '<div class="sm-kpis">' +
      '<div class="sm-kpi"><div class="sm-kpi-v">' + games.toLocaleString() + '</div><div class="sm-kpi-l">Games</div></div>' +
      '<div class="sm-kpi"><div class="sm-kpi-v">' + (share != null ? share.toFixed(1) + '%' : '—') + '</div><div class="sm-kpi-l">Meta share</div></div>' +
      '<div class="sm-kpi"><div class="sm-kpi-v">' + (fit && fit.rank != null ? '#' + fit.rank + ' / ' + fit.total : '—') + '</div><div class="sm-kpi-l">Fitness rank</div></div>' +
      '<div class="sm-kpi"><div class="sm-kpi-v">' + (worst ? Math.round(worst.wr) + '%' : '—') + '</div><div class="sm-kpi-l">' + (worst ? 'Worst vs ' + _esc(worst.opp) : 'Worst matchup') + '</div></div>' +
      '</div>';

    const rcMini = _responseCoverageMini(deckCode, opponentCode, pd);
    const recs = _recommendedActions(deckCode, opponentCode);

    return '<div class="sm-card">' +
      header + mainKpi + secondary + rcMini + recs +
      '</div>';
  }

  window.V3.DeckSummary = {
    build: build,
    _requestWorkspace: _requestWorkspace,
    _worstMatchup: _worstMatchup,
  };
})();
