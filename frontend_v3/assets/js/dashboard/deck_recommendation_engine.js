// Recommendation engine — produces up to 3 "Data suggests..." actions for a deck.
// Contract: docs/DECK_REFACTOR_PARITY.md Rule 1 — observed, not personal.
// Consumes ONLY archetype-level observed fields from the blob; never reads
// player_lookup or any personal stats.
//
// Priority order (DECK_REFACTOR_PARITY open question #4, default confirmed PR1):
//   1. Missing response cards vs top killer curves of the worst observed
//      matchup (or the opp_hint passed in). Differentiator vs inkdecks.
//   2. Pro consensus diff on cards with a strong card_scores delta
//      (|delta| ≥ 2pp over ≥30 observed games).
//   3. meta_deck cuts/adds fallback when opp-specific signal is missing.
//
// Thresholds are aligned with honesty_badge.js (MIN_SAMPLE=30, MED=100)
// and deck_grid._statusDot (±2pp).

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const MIN_SAMPLE = 30;              // opp-specific mode (strict)
  const STRONG_DELTA_PP = 2;
  const MATRIX_MIN_GAMES = 15;        // opp-specific mode (strict)
  // Cross-matchup mode uses looser gates so rare pairings (RS, RSt, ER…)
  // don't drop out of the Applies-to badge list entirely. They weigh less
  // in the weighted average anyway (sample size is the weight).
  const CROSS_MATRIX_MIN_GAMES = 5;
  const CROSS_MIN_SAMPLE = 10;
  const MAX_ACTIONS = 3;
  const DEFAULT_DAYS = 14;

  function _normalize(name) {
    if (!name) return '';
    const raw = String(name).trim();
    const base = raw.includes(' - ') ? raw.split(' - ')[0] : raw;
    return base.toLowerCase();
  }

  function _deckMap(deckCode) {
    if (window.V3 && window.V3.DeckGrid && typeof window.V3.DeckGrid._resolveCards === 'function') {
      const cards = window.V3.DeckGrid._resolveCards(deckCode, null) || [];
      const map = {};
      cards.forEach(function (c) {
        const k = _normalize(c.card);
        if (!k) return;
        if (!map[k]) map[k] = { name: c.card, qty: 0 };
        map[k].qty += (c.qty || 0);
      });
      return map;
    }
    return {};
  }

  // Every opp observed with ≥minGames games in the current scope. Default
  // threshold is the cross-matchup one (loose), opp-specific callers pass
  // the strict MATRIX_MIN_GAMES.
  function _allObservedOpps(deckCode, minGames) {
    const gate = (typeof minGames === 'number') ? minGames : CROSS_MATRIX_MIN_GAMES;
    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return [];
    const row = pd.matrix[deckCode];
    return Object.keys(row).filter(function (opp) {
      return (row[opp] && (row[opp].t || 0) >= gate);
    });
  }

  // Scan perimeters[p].matrix[deckCode] → opp with lowest WR (min 15 games).
  function _worstObservedOpp(deckCode) {
    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return null;
    const row = pd.matrix[deckCode];
    let worst = null;
    Object.keys(row).forEach(function (opp) {
      const cell = row[opp];
      if (!cell) return;
      const t = cell.t || 0;
      if (t < MATRIX_MIN_GAMES) return;
      const wr = (cell.w || 0) / t;
      if (worst == null || wr < worst.wr) {
        worst = { opp: opp, wr: wr * 100, games: t };
      }
    });
    return worst;
  }

  function _priority1_responseGaps(deckCode, oppHint) {
    const oppInfo = oppHint ? { opp: oppHint } : _worstObservedOpp(deckCode);
    if (!oppInfo || !oppInfo.opp) return [];
    const opp = oppInfo.opp;
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    if (!curves.length) return [];

    const deckMap = _deckMap(deckCode);
    const sortedCurves = curves.slice().sort(function (a, b) {
      const fa = (a && a.frequency && a.frequency.pct) || 0;
      const fb = (b && b.frequency && b.frequency.pct) || 0;
      return fb - fa;
    });

    const actions = [];
    sortedCurves.slice(0, 3).forEach(function (curve) {
      const answers = (curve && curve.response && Array.isArray(curve.response.cards))
        ? curve.response.cards
        : [];
      if (!answers.length) return;
      let copies = 0;
      answers.forEach(function (a) {
        copies += (deckMap[_normalize(a)] && deckMap[_normalize(a)].qty) || 0;
      });
      if (copies >= 3) return; // already covered
      const missing = answers.find(function (a) {
        return !(deckMap[_normalize(a)] && deckMap[_normalize(a)].qty);
      });
      if (!missing) return;

      const critTurn = curve.critical_turn && curve.critical_turn.turn;
      const freq = curve.frequency && curve.frequency.pct;
      const reasons = [
        'improves response coverage vs ' + (curve.name || 'top threat line'),
        critTurn ? 'critical turn T' + critTurn : null,
        (freq != null) ? Math.round(freq) + '% of observed ' + opp + ' games show this curve' : null,
      ].filter(Boolean);

      actions.push({
        action: 'add',
        card: missing,
        qty: Math.min(2, 3 - copies),
        reasons: reasons,
        opponent: opp,
        sample: (mu.overview && mu.overview.games) || null,
        priority: 1,
      });
    });
    return actions;
  }

  function _priority2_consensusDiff(deckCode, oppHint) {
    const deckMap = _deckMap(deckCode);
    const consensus = (window.DATA && window.DATA.consensus && window.DATA.consensus[deckCode]) || {};
    if (!Object.keys(consensus).length) return [];
    const mu = oppHint && typeof getMatchupData === 'function' ? getMatchupData(oppHint) : null;
    const scores = (mu && mu.card_scores) || {};

    const actions = [];
    Object.keys(consensus).forEach(function (name) {
      const consQty = Math.round(Number(consensus[name]) || 0);
      const myQty = (deckMap[_normalize(name)] && deckMap[_normalize(name)].qty) || 0;
      const diff = consQty - myQty;
      if (Math.abs(diff) < 2) return;

      const sc = scores[name];
      const deltaPp = (sc && typeof sc.delta === 'number') ? sc.delta * 100 : null;
      // card_scores entries use `apps` for sample size (legacy fallback to `games`)
      const sample = sc
        ? Number(sc.apps != null ? sc.apps : (sc.games != null ? sc.games : 0))
        : null;
      const strong = deltaPp != null && sample != null && sample >= MIN_SAMPLE
        && Math.abs(deltaPp) >= STRONG_DELTA_PP;
      if (!strong) return;

      const isAdd = diff > 0 && deltaPp > 0;
      const isCut = diff < 0 && deltaPp < 0;
      if (!isAdd && !isCut) return;

      const sign = deltaPp >= 0 ? '+' : '−';
      const confLabel = (window.V3 && window.V3.HonestyBadge)
        ? window.V3.HonestyBadge.confidenceLabel(sample)
        : (sample >= 100 ? 'High' : 'Medium');

      actions.push({
        action: isAdd ? 'add' : 'cut',
        card: name,
        qty: Math.abs(diff),
        reasons: [
          'closer to pro consensus (avg ' + consQty + ' copies in observed sample)',
          sign + Math.abs(deltaPp).toFixed(1) + 'pp when drawn in observed sample',
          confLabel + ' confidence (' + sample + ' observed games)',
        ],
        opponent: oppHint || null,
        sample: sample,
        priority: 2,
      });
    });
    return actions;
  }

  // Cross-matchup response gap — same logic as P1 but aggregated over ALL
  // observed matchups instead of the worst one. Each candidate card is
  // credited once per uncovered curve across the whole matrix; winning
  // suggestions are the ones that patch the most holes at once.
  function _priority1_cross_responseGap(deckCode) {
    const opps = _allObservedOpps(deckCode);
    if (!opps.length) return [];
    const deckMap = _deckMap(deckCode);
    const candidates = {};

    opps.forEach(function (opp) {
      const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
      const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
      curves.forEach(function (curve) {
        const answers = (curve && curve.response && Array.isArray(curve.response.cards))
          ? curve.response.cards : [];
        if (!answers.length) return;
        let copies = 0;
        answers.forEach(function (a) {
          copies += (deckMap[_normalize(a)] && deckMap[_normalize(a)].qty) || 0;
        });
        if (copies >= 3) return;
        answers.forEach(function (a) {
          const k = _normalize(a);
          if (deckMap[k] && deckMap[k].qty) return;
          if (!candidates[a]) candidates[a] = { opps: new Set(), curves: 0, freq: 0 };
          candidates[a].opps.add(opp);
          candidates[a].curves += 1;
          candidates[a].freq += (curve.frequency && curve.frequency.pct) || 0;
        });
      });
    });

    const ranked = Object.keys(candidates)
      .map(function (c) { return Object.assign({ card: c }, candidates[c]); })
      .sort(function (a, b) {
        if (b.curves !== a.curves) return b.curves - a.curves;
        return b.freq - a.freq;
      });

    return ranked.slice(0, 3).map(function (r) {
      return {
        action: 'add',
        card: r.card,
        qty: 2,
        reasons: [
          'covers ' + r.curves + ' threat line' + (r.curves === 1 ? '' : 's') +
            ' currently without an answer',
        ],
        opps: Array.from(r.opps),
        opponent: null,
        sample: null,
        priority: 1,
      };
    });
  }

  // Cross-matchup consensus diff — same spirit as P2 but aggregates
  // card_scores.delta across ALL observed matchups, weighted by observed
  // sample per matchup. Suggestion fires only when the weighted average is
  // ≥ STRONG_DELTA_PP AND the consensus/mine diff is ≥ 2.
  function _priority2_cross_consensus(deckCode) {
    const consensus = (window.DATA && window.DATA.consensus && window.DATA.consensus[deckCode]) || {};
    if (!Object.keys(consensus).length) return [];
    const deckMap = _deckMap(deckCode);
    const opps = _allObservedOpps(deckCode);
    if (!opps.length) return [];

    const actions = [];
    Object.keys(consensus).forEach(function (name) {
      const consQty = Math.round(Number(consensus[name]) || 0);
      const myQty = (deckMap[_normalize(name)] && deckMap[_normalize(name)].qty) || 0;
      const diff = consQty - myQty;
      if (Math.abs(diff) < 2) return;

      let totalWeight = 0;
      let weightedDelta = 0;
      const oppsAgreeing = [];
      opps.forEach(function (opp) {
        const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
        const sc = mu && mu.card_scores && mu.card_scores[name];
        if (!sc) return;
        const sample = Number(sc.apps != null ? sc.apps : (sc.games || 0));
        if (sample < CROSS_MIN_SAMPLE) return;
        const delta = Number(sc.delta) || 0;
        weightedDelta += delta * sample;
        totalWeight += sample;
        if ((diff > 0 && delta > 0) || (diff < 0 && delta < 0)) oppsAgreeing.push(opp);
      });
      if (totalWeight === 0 || !oppsAgreeing.length) return;
      const avgDeltaPp = (weightedDelta / totalWeight) * 100;
      if (Math.abs(avgDeltaPp) < STRONG_DELTA_PP) return;

      const isAdd = diff > 0 && avgDeltaPp > 0;
      const isCut = diff < 0 && avgDeltaPp < 0;
      if (!isAdd && !isCut) return;

      const sign = avgDeltaPp >= 0 ? '+' : '−';
      const confLabel = (window.V3 && window.V3.HonestyBadge)
        ? window.V3.HonestyBadge.confidenceLabel(totalWeight)
        : (totalWeight >= 100 ? 'High' : 'Medium');

      actions.push({
        action: isAdd ? 'add' : 'cut',
        card: name,
        qty: Math.abs(diff),
        reasons: [
          'closer to consensus (avg ' + consQty + ' cop' + (consQty === 1 ? 'y' : 'ies') +
            ' across observed lists)',
          'weighted avg ' + sign + Math.abs(avgDeltaPp).toFixed(1) + 'pp across ' +
            oppsAgreeing.length + ' observed matchup' + (oppsAgreeing.length === 1 ? '' : 's'),
          confLabel + ' confidence (' + totalWeight + ' observed games total)',
        ],
        opps: oppsAgreeing,
        opponent: null,
        sample: totalWeight,
        priority: 2,
      });
    });

    actions.sort(function (a, b) { return (b.sample || 0) - (a.sample || 0); });
    return actions.slice(0, 4);
  }

  function _priority3_metaDeck(deckCode) {
    const md = (window.DATA && window.DATA.meta_deck && window.DATA.meta_deck[deckCode]) || null;
    if (!md) return [];
    const actions = [];
    (md.adds || []).slice(0, 2).forEach(function (a) {
      if (!a || !a.card) return;
      actions.push({
        action: 'add',
        card: a.card,
        qty: Number(a.qty) || 1,
        reasons: ['suggested by meta-deck analysis across observed sample'],
        opponent: null,
        sample: null,
        priority: 3,
      });
    });
    (md.cuts || []).slice(0, 2).forEach(function (c) {
      if (!c || !c.card) return;
      actions.push({
        action: 'cut',
        card: c.card,
        qty: Number(c.qty) || 1,
        reasons: ['cut by meta-deck analysis across observed sample'],
        opponent: null,
        sample: null,
        priority: 3,
      });
    });
    return actions;
  }

  function compute(deckCode, opponentCode) {
    if (!deckCode) return [];
    const out = [];
    const seen = Object.create(null);
    // Without an opp hint the engine runs cross-matchup: suggestions are
    // ranked by aggregate coverage and weighted-delta across the whole
    // observed matrix. With an opp hint the legacy opp-specific scorers
    // still fire so the matchup workspace CTAs keep working.
    const batches = opponentCode
      ? [
          _priority1_responseGaps(deckCode, opponentCode),
          _priority2_consensusDiff(deckCode, opponentCode),
          _priority3_metaDeck(deckCode),
        ]
      : [
          _priority1_cross_responseGap(deckCode),
          _priority2_cross_consensus(deckCode),
          _priority3_metaDeck(deckCode),
        ];
    const cap = opponentCode ? MAX_ACTIONS : 6;
    batches.forEach(function (batch) {
      batch.forEach(function (a) {
        if (out.length >= cap) return;
        const key = a.action + ':' + _normalize(a.card);
        if (seen[key]) return;
        seen[key] = true;
        out.push(a);
      });
    });
    return out;
  }

  // Render a single action. Copy obeys Rule 1: "Data suggests ..." third person.
  // CSS selectors (styled in PR3): .rec-action, .rec-p1/p2/p3, .rec-head,
  //   .rec-opp, .rec-reasons, .rec-foot.
  function renderAction(a) {
    if (!a) return '';
    const verb = a.action === 'cut' ? 'cutting' : 'adding';
    const actionCls = a.action === 'cut' ? 'rec-cut' : 'rec-add';
    const short = String(a.card || '').split(' - ')[0];
    const headline = 'Data suggests ' + verb + ' ' + a.qty + '× ' + short;
    const reasonsHtml = (a.reasons || []).map(function (r) {
      return '<li>' + r + '</li>';
    }).join('');
    const badge = (a.sample && window.V3 && window.V3.HonestyBadge)
      ? window.V3.HonestyBadge.renderBadgeOnly(a.sample, DEFAULT_DAYS)
      : '';
    // Deck PNG badges for every matchup the suggestion applies to.
    let oppsHtml = '';
    if (Array.isArray(a.opps) && a.opps.length && typeof deckImg === 'function') {
      const max = 10;
      const shown = a.opps.slice(0, max).map(function (o) {
        return '<span class="rec-opp-badge" title="' + o + '">' + deckImg(o, 22) + '</span>';
      }).join('');
      const more = a.opps.length > max ? '<span class="rec-opps-more">+' + (a.opps.length - max) + '</span>' : '';
      oppsHtml = '<div class="rec-opps"><span class="rec-opps-lbl">Applies to:</span>' + shown + more + '</div>';
    }
    return '<div class="rec-action rec-p' + a.priority + ' ' + actionCls + '">' +
      '<div class="rec-head">' + headline +
      (a.opponent ? ' <span class="rec-opp">vs ' + a.opponent + '</span>' : '') +
      '</div>' +
      (reasonsHtml ? '<ul class="rec-reasons">' + reasonsHtml + '</ul>' : '') +
      oppsHtml +
      (badge ? '<div class="rec-foot">' + badge + '</div>' : '') +
      '</div>';
  }

  window.V3.RecommendationEngine = {
    MIN_SAMPLE: MIN_SAMPLE,
    STRONG_DELTA_PP: STRONG_DELTA_PP,
    MATRIX_MIN_GAMES: MATRIX_MIN_GAMES,
    MAX_ACTIONS: MAX_ACTIONS,
    compute: compute,
    renderAction: renderAction,
    _worstObservedOpp: _worstObservedOpp,
  };
})();
