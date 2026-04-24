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

  const MIN_SAMPLE = 30;
  const STRONG_DELTA_PP = 2;
  const MATRIX_MIN_GAMES = 15;
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
    const batches = [
      _priority1_responseGaps(deckCode, opponentCode),
      _priority2_consensusDiff(deckCode, opponentCode),
      _priority3_metaDeck(deckCode),
    ];
    batches.forEach(function (batch) {
      batch.forEach(function (a) {
        if (out.length >= MAX_ACTIONS) return;
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
    const short = String(a.card || '').split(' - ')[0];
    const headline = 'Data suggests ' + verb + ' ' + a.qty + '× ' + short;
    const reasonsHtml = (a.reasons || []).map(function (r) {
      return '<li>' + r + '</li>';
    }).join('');
    const badge = (a.sample && window.V3 && window.V3.HonestyBadge)
      ? window.V3.HonestyBadge.renderBadgeOnly(a.sample, DEFAULT_DAYS)
      : '';
    return '<div class="rec-action rec-p' + a.priority + '">' +
      '<div class="rec-head">' + headline +
      (a.opponent ? ' <span class="rec-opp">vs ' + a.opponent + '</span>' : '') +
      '</div>' +
      (reasonsHtml ? '<ul class="rec-reasons">' + reasonsHtml + '</ul>' : '') +
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
