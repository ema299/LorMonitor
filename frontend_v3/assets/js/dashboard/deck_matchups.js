// Deck tab — Area C Matchups heatmap (merged with Improve).
// Contract: docs/DECK_REFACTOR_PARITY.md rows 8, 12, 14, 18, 47.
//
// Compact table: one row per observed opp with ≥15 games, sorted by WR asc
// (worst first = most to study). Tap a row → expand with pill-tab control:
//   [Curves]  [Cards ▼]   ← default = Cards (card_scores / in_deck_rate)
// "Curves" tab = killer_curves + response coverage + inline P1/P3 leaks.
// "Cards"  tab = card_scores trending (over/under) with in_deck_rate sample.
// Cross-matchup P2 OTP/OTD gap surfaces as a strip above the row list.
//
// Consumes: perimeters[p].matrix[deck], perimeters[p].otp_otd[deck],
//   matchup_analyzer[deck].vs_<opp>.killer_curves / .card_scores,
//   DECK_INKS, INK_COLORS.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const MATRIX_MIN_GAMES = 15;
  const DAYS = 3;
  const TOP_CURVES = 5;
  const EXPANDED = new Set();
  const TAB_STATE = {};            // opp → 'curves' | 'cards'  (default 'cards')
  const OTP_OTD_GAP_PP = 10;
  const MIN_SAMPLE_CARDS = 15;     // Cards trending admission
  const STRONG_DELTA_PP = 2;
  const MAX_CARDS_PER_BUCKET = 5;

  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function _short(n) { return (n || '').split(' - ')[0]; }
  function _hb() { return window.V3 && window.V3.HonestyBadge; }

  function _inkDots(inks) {
    return (inks || []).map(function (i) {
      const col = (typeof INK_COLORS !== 'undefined' && INK_COLORS[i]) || '#888';
      return '<span class="mh-dot" style="background:' + col + '"></span>';
    }).join('');
  }

  function _rate(wr) {
    if (wr == null) return { label: 'Unknown', cls: 'mh-unk' };
    if (wr < 42) return { label: 'Bad', cls: 'mh-bad' };
    if (wr < 48) return { label: 'Hard', cls: 'mh-hard' };
    if (wr <= 52) return { label: 'Even', cls: 'mh-even' };
    if (wr <= 58) return { label: 'Good', cls: 'mh-good' };
    return { label: 'Great', cls: 'mh-great' };
  }

  function _rows(deckCode, pd) {
    if (!pd || !pd.matrix || !pd.matrix[deckCode]) return [];
    const matrixRow = pd.matrix[deckCode];
    const out = [];
    Object.keys(matrixRow).forEach(function (opp) {
      const cell = matrixRow[opp];
      if (!cell) return;
      const t = cell.t || 0;
      if (t < MATRIX_MIN_GAMES) return;
      const wr = (cell.w || 0) / t * 100;
      out.push({ opp: opp, wr: wr, games: t });
    });
    out.sort(function (a, b) { return a.wr - b.wr; });
    return out;
  }

  // ---------------------- Shared helpers ----------------------

  function _deckMap(deckCode) {
    if (!(window.V3 && window.V3.DeckGrid && window.V3.DeckGrid._resolveCards)) return {};
    const map = {};
    (window.V3.DeckGrid._resolveCards(deckCode, null) || []).forEach(function (c) {
      const raw = String(c.card || '').trim();
      const base = raw.includes(' - ') ? raw.split(' - ')[0] : raw;
      const k = base.toLowerCase();
      if (!k) return;
      map[k] = (map[k] || 0) + (c.qty || 0);
    });
    return map;
  }

  // Aggregate row-level coverage signal from the top killer curves:
  //   red    — any curve has 0 copies of its listed answers (P1 leak)
  //   yellow — all curves ≥1 copy, none reaches the green 3-copy threshold
  //   null   — at least one green, nothing red → silent (clean)
  function _coverageSignalForOpp(opp, deckCode) {
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    const rc = window.V3 && window.V3.ResponseCheck;
    if (!rc || !curves.length) return null;
    const deckMap = _deckMap(deckCode);
    const top = curves.slice().sort(function (a, b) {
      return ((b.frequency && b.frequency.pct) || 0) - ((a.frequency && a.frequency.pct) || 0);
    }).slice(0, TOP_CURVES);
    let anyRed = false, anyGreen = false, anyYellow = false;
    top.forEach(function (c) {
      const cov = rc._coverageForCurve(c, deckMap);
      if (!cov || cov.totalAnswers === 0) return;
      if (cov.status === 'red') anyRed = true;
      else if (cov.status === 'yellow') anyYellow = true;
      else if (cov.status === 'green') anyGreen = true;
    });
    if (anyRed) return 'red';
    if (anyYellow && !anyGreen) return 'yellow';
    return null;
  }

  function _coverageBadgeHtml(signal) {
    if (signal === 'red') return '<span class="mh-cov-sig mh-cov-red">🔴 No answer</span>';
    if (signal === 'yellow') return '<span class="mh-cov-sig mh-cov-yel">🟡 Partial</span>';
    return '';
  }

  // Cross-matchup OTP/OTD gap — rendered once above the row list.
  function _otpOtdStrip(deckCode) {
    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    if (!pd || !pd.otp_otd || !pd.otp_otd[deckCode]) return '';
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
    if (otpT < MATRIX_MIN_GAMES || otdT < MATRIX_MIN_GAMES) return '';
    const otpWr = otpW / otpT * 100;
    const otdWr = otdW / otdT * 100;
    const gap = otpWr - otdWr;
    if (Math.abs(gap) < OTP_OTD_GAP_PP) return '';
    const weaker = gap > 0 ? 'OTD (going second)' : 'OTP (going first)';
    const weakerWr = gap > 0 ? otdWr : otpWr;
    const weakerT = gap > 0 ? otdT : otpT;
    const strongerWr = gap > 0 ? otpWr : otdWr;
    return '<div class="mh-struct-strip">' +
      '<span class="mh-struct-icon">!</span>' +
      '<span class="mh-struct-body">' +
      '<strong>Structural gap on ' + weaker + '</strong> · ' +
      Math.round(weakerWr) + '% vs ' + Math.round(strongerWr) + '% the other side · ' +
      Math.abs(gap).toFixed(1) + 'pp swing on ' + weakerT + ' observed games' +
      '</span></div>';
  }

  // ---------------------- Cards trending (bucket grid) ----------------------

  function _cardsTrendingRows(opp) {
    if (!opp) return null;
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
    const scores = (mu && mu.card_scores) || {};
    const over = [], under = [];
    Object.keys(scores).forEach(function (name) {
      const entry = scores[name];
      if (!entry) return;
      const games = Number(entry.apps != null ? entry.apps : (entry.games || 0));
      if (games < MIN_SAMPLE_CARDS) return;
      const delta = Number(entry.delta || 0);
      const pp = delta * 100;
      const decksWith = entry.decks_with != null ? Number(entry.decks_with) : null;
      const decksTotal = entry.decks_total != null ? Number(entry.decks_total) : null;
      const row = { name: name, pp: pp, games: games, decksWith: decksWith, decksTotal: decksTotal };
      if (pp >= STRONG_DELTA_PP) over.push(row);
      else if (pp <= -STRONG_DELTA_PP) under.push(row);
    });
    over.sort(function (a, b) { return b.pp - a.pp; });
    under.sort(function (a, b) { return a.pp - b.pp; });
    return { over: over.slice(0, MAX_CARDS_PER_BUCKET), under: under.slice(0, MAX_CARDS_PER_BUCKET) };
  }

  function _cardSampleLabel(r) {
    if (r.decksTotal && r.decksTotal > 0) {
      return 'in ' + r.decksWith + '/' + r.decksTotal + ' decks (' +
        Math.round(r.decksWith / r.decksTotal * 100) + '%)';
    }
    return 'on ' + r.games + ' appearances';
  }

  function _cardOnclick(r) {
    return 'event.stopPropagation();window.V3.HonestyBadge.openAppearancesExplainer(' +
      (r.games || 0) + ',' + (r.decksWith || 0) + ',' + (r.decksTotal || 0) + ')';
  }

  function _cardsBucketGridHtml(opp) {
    const t = _cardsTrendingRows(opp);
    if (!t || (!t.over.length && !t.under.length)) {
      return '<div class="mh-cards-empty">No card shows a ±' + STRONG_DELTA_PP +
        'pp signal on ≥' + MIN_SAMPLE_CARDS + ' appearances vs ' + _esc(opp) + '.</div>';
    }
    const hb = _hb();
    const renderRow = function (r, isOver) {
      const dot = isOver ? '🟢' : '🔴';
      const deltaFmt = hb ? hb.formatDelta(r.pp, r.games) : (r.pp >= 0 ? '+' : '') + r.pp.toFixed(1) + 'pp';
      const confCls = hb ? hb.confidenceClass(r.games) : 'hb-med';
      const confLbl = hb ? hb.confidenceLabel(r.games) : 'Medium';
      return '<li class="mh-cards-row">' +
        '<span class="mh-cards-dot">' + dot + '</span>' +
        '<span class="mh-cards-name">' + _esc(_short(r.name)) + '</span>' +
        '<span class="mh-cards-stat">' + deltaFmt +
        ' <span class="mh-cards-sample" role="button" tabindex="0" onclick="' + _cardOnclick(r) + '">' +
        _cardSampleLabel(r) + '</span>' +
        ' <span class="hb-conf ' + confCls + '" role="button" tabindex="0" onclick="' + _cardOnclick(r) + '">' + confLbl + '</span>' +
        '</span></li>';
    };
    const overHtml = t.over.length
      ? '<ul class="mh-cards-list">' + t.over.map(function (r) { return renderRow(r, true); }).join('') + '</ul>'
      : '<div class="mh-cards-inline-empty">No overperformer ≥+' + STRONG_DELTA_PP + 'pp.</div>';
    const underHtml = t.under.length
      ? '<ul class="mh-cards-list">' + t.under.map(function (r) { return renderRow(r, false); }).join('') + '</ul>'
      : '<div class="mh-cards-inline-empty">No underperformer ≤−' + STRONG_DELTA_PP + 'pp.</div>';
    return '<div class="mh-cards-grid">' +
      '<div class="mh-cards-bucket"><div class="mh-cards-bucket-head">🟢 Overperforming</div>' + overHtml + '</div>' +
      '<div class="mh-cards-bucket"><div class="mh-cards-bucket-head">🔴 Underperforming</div>' + underHtml + '</div>' +
      '</div>';
  }

  // ---------------------- Row HTML ----------------------

  function _rowHtml(r, selectedOpp, deckCode) {
    const hb = _hb();
    const wrFmt = hb ? hb.formatPct(r.wr, r.games) : Math.round(r.wr) + '%';
    const confCls = hb ? hb.confidenceClass(r.games) : 'hb-med';
    const confLbl = hb ? hb.confidenceLabel(r.games) : 'Medium';
    const rate = _rate(r.wr);
    const inks = (typeof DECK_INKS !== 'undefined' && DECK_INKS[r.opp]) || [];
    const isSel = r.opp === selectedOpp;
    const isOpen = EXPANDED.has(r.opp);
    const selCls = isSel ? ' mh-row--sel' : '';
    const openCls = isOpen ? ' mh-row--open' : '';
    const chev = isOpen ? '▾' : '▸';
    const covBadge = _coverageBadgeHtml(_coverageSignalForOpp(r.opp, deckCode));
    return '<div class="mh-row ' + rate.cls + selCls + openCls + '" role="button" tabindex="0" ' +
      'data-opp="' + _esc(r.opp) + '" ' +
      'onclick="window.V3.DeckMatchups.toggle(\'' + _esc(r.opp) + '\')" ' +
      'onkeydown="if(event.key===\'Enter\'||event.key===\' \')window.V3.DeckMatchups.toggle(\'' + _esc(r.opp) + '\')">' +
      '<span class="mh-stripe"></span>' +
      '<span class="mh-chev">' + chev + '</span>' +
      '<span class="mh-opp-block">' +
      '<span class="mh-inks">' + _inkDots(inks) + '</span>' +
      '<span class="mh-opp-name">' + _esc(r.opp) + '</span>' +
      '</span>' +
      '<span class="mh-wr">' + wrFmt + '</span>' +
      '<span class="mh-games">on ' + r.games + ' obs.</span>' +
      '<span class="mh-conf ' + confCls + '">' + confLbl + '</span>' +
      '<span class="mh-rate-tag">' + rate.label + '</span>' +
      covBadge +
      '</div>';
  }

  // ---------------------- Curves block ----------------------

  function _covBadge(cov) {
    if (!cov) return { icon: '⚪', cls: 'mh-cov-unk', label: 'no data' };
    if (cov.status === 'green')  return { icon: '🟢', cls: 'mh-cov-good', label: 'covered' };
    if (cov.status === 'yellow') return { icon: '🟡', cls: 'mh-cov-mid',  label: 'partial' };
    return { icon: '🔴', cls: 'mh-cov-bad', label: 'missing' };
  }

  function _inlineLeakForOpp(opp) {
    if (!(window.V3 && window.V3.DeckImprove && window.V3.DeckImprove._buildLeaks)) return '';
    const deck = (typeof coachDeck !== 'undefined') ? coachDeck : null;
    if (!deck) return '';
    const leaks = window.V3.DeckImprove._buildLeaks(deck) || [];
    const hits = leaks.filter(function (l) { return l.opp === opp; });
    if (!hits.length) return '';
    return hits.map(function (l) {
      return '<div class="mh-inline-leak mh-inline-leak--p' + l.priority + '">' +
        '<span class="mh-inline-leak-icon">⚠</span>' +
        '<span class="mh-inline-leak-body"><strong>' + _esc(l.title) + '</strong><br>' +
        _esc(l.detail) + '</span></div>';
    }).join('');
  }

  function _curvesBlockHtml(opp, deckCode) {
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    if (!curves.length) {
      return '<div class="mh-exp-empty">No killer-curve data reported for this matchup yet.</div>';
    }
    const rc = window.V3 && window.V3.ResponseCheck;
    const deckMap = _deckMap(deckCode);
    const sorted = curves.slice().sort(function (a, b) {
      return ((b.frequency && b.frequency.pct) || 0) - ((a.frequency && a.frequency.pct) || 0);
    }).slice(0, TOP_CURVES);
    const leakInset = _inlineLeakForOpp(opp);
    const rows = sorted.map(function (curve) {
      const cov = rc && typeof rc._coverageForCurve === 'function'
        ? rc._coverageForCurve(curve, deckMap) : null;
      const bad = _covBadge(cov);
      const pct = (curve.frequency && curve.frequency.pct != null)
        ? Math.round(curve.frequency.pct) + '%' : '—';
      const tturn = curve.critical_turn && curve.critical_turn.turn
        ? 'T' + curve.critical_turn.turn : '';
      const name = _esc(curve.name || 'Unnamed curve');
      let covLine = 'No listed answers';
      if (cov && cov.totalAnswers > 0) {
        covLine = cov.copies + (cov.copies === 1 ? ' copy' : ' copies') +
          ' covering · ' + cov.present.length + '/' + cov.totalAnswers + ' answer cards';
      }
      const haveChips = cov && cov.present.length
        ? '<div class="mh-exp-chips"><span class="mh-exp-chip-lbl">Have:</span>' +
          cov.present.map(function (p) {
            return '<span class="mh-chip mh-chip--have">' + p.qty + '× ' + _esc(_short(p.name)) + '</span>';
          }).join('') + '</div>'
        : '';
      const missChips = cov && cov.missing.length
        ? '<div class="mh-exp-chips"><span class="mh-exp-chip-lbl">Missing:</span>' +
          cov.missing.slice(0, 4).map(function (m) {
            return '<span class="mh-chip mh-chip--miss">' + _esc(_short(m)) + '</span>';
          }).join('') + '</div>'
        : '';
      return '<div class="mh-exp-curve ' + bad.cls + '">' +
        '<div class="mh-exp-curve-head">' +
        '<span class="mh-exp-icon">' + bad.icon + '</span>' +
        '<span class="mh-exp-curve-name">' + name + '</span>' +
        (tturn ? '<span class="mh-exp-turn">' + tturn + '</span>' : '') +
        '<span class="mh-exp-freq">' + pct + ' observed</span>' +
        '</div>' +
        '<div class="mh-exp-cov-line">' + covLine + '</div>' +
        haveChips + missChips +
        '</div>';
    }).join('');
    return leakInset + rows;
  }

  function _workspaceCtaHtml(opp) {
    return '<div class="mh-exp-cta">' +
      '<button class="mh-exp-btn" type="button" ' +
      'onclick="event.stopPropagation();window.V3.DeckMatchups.openWorkspace(\'' + _esc(opp) + '\')">' +
      'Open full workspace →</button>' +
      '</div>';
  }

  // ---------------------- Expand (pill-tab: Cards default) ----------------------

  function _expandHtml(opp, deckCode) {
    // Default tab = 'cards': card-level signals are the most actionable
    // takeaway per-matchup for a player tuning their list.
    const active = TAB_STATE[opp] || 'cards';
    const curvesTab = active === 'curves';
    const tabsHtml = '<div class="mh-tab-ctrl" role="tablist">' +
      '<button class="mh-tab ' + (curvesTab ? 'mh-tab--on' : '') + '" type="button" role="tab" aria-selected="' + curvesTab + '" ' +
      'onclick="event.stopPropagation();window.V3.DeckMatchups.setTab(\'' + _esc(opp) + '\',\'curves\')">Curves</button>' +
      '<button class="mh-tab ' + (!curvesTab ? 'mh-tab--on' : '') + '" type="button" role="tab" aria-selected="' + (!curvesTab) + '" ' +
      'onclick="event.stopPropagation();window.V3.DeckMatchups.setTab(\'' + _esc(opp) + '\',\'cards\')">Cards</button>' +
      '</div>';
    let inner;
    if (curvesTab) {
      inner = '<div class="mh-exp-head">Top killer curves · how this deck answers</div>' +
        _curvesBlockHtml(opp, deckCode);
    } else {
      inner = '<div class="mh-exp-head">Cards trending <span class="mh-exp-sub">vs ' + _esc(opp) + ' · card_scores · 14d</span></div>' +
        _cardsBucketGridHtml(opp);
    }
    return '<div class="mh-expand" onclick="event.stopPropagation()">' +
      tabsHtml + inner + _workspaceCtaHtml(opp) + '</div>';
  }

  // ---------------------- Public API ----------------------

  function toggle(opp) {
    if (!opp) return;
    if (EXPANDED.has(opp)) EXPANDED.delete(opp);
    else EXPANDED.add(opp);
    try { if (typeof labOpp !== 'undefined') labOpp = opp; } catch (e) {}
    if (typeof syncOppInksFromDeck === 'function') {
      try { syncOppInksFromDeck(opp); } catch (e) {}
    }
    if (typeof render === 'function') render();
  }

  function setTab(opp, tab) {
    if (!opp) return;
    TAB_STATE[opp] = (tab === 'curves') ? 'curves' : 'cards';
    if (typeof render === 'function') render();
  }

  function openWorkspace(opp) {
    if (!opp) return;
    const deck = (typeof coachDeck !== 'undefined') ? coachDeck : null;
    if (deck && window.V3 && window.V3.MatchupWorkspace &&
        typeof window.V3.MatchupWorkspace.open === 'function') {
      window.V3.MatchupWorkspace.open(deck, opp);
    }
  }

  function selectOpp(opp) {
    if (!opp) return;
    try { if (typeof labOpp !== 'undefined') labOpp = opp; } catch (e) {}
    if (typeof syncOppInksFromDeck === 'function') {
      try { syncOppInksFromDeck(opp); } catch (e) {}
    }
    if (typeof render === 'function') render();
    else {
      const host = document.getElementById('main-content');
      if (host && typeof renderLabTab === 'function') renderLabTab(host);
    }
  }

  function openMatchup(opp) {
    if (!opp) return;
    const deck = (typeof coachDeck !== 'undefined') ? coachDeck : null;
    if (deck && window.V3 && window.V3.MatchupWorkspace &&
        typeof window.V3.MatchupWorkspace.open === 'function') {
      window.V3.MatchupWorkspace.open(deck, opp);
    } else {
      selectOpp(opp);
    }
  }

  function build(deckCode, selectedOpp) {
    if (!deckCode) return '';
    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    const rows = _rows(deckCode, pd);
    if (!rows.length) {
      return '<div class="mh-card">' +
        '<div class="mh-head">Matchups</div>' +
        '<div class="mh-empty">No observed matchup has ≥' + MATRIX_MIN_GAMES +
        ' games in the current scope.</div>' +
        '</div>';
    }
    const otpStrip = _otpOtdStrip(deckCode);
    const body = rows.map(function (r) {
      const row = _rowHtml(r, selectedOpp, deckCode);
      const exp = EXPANDED.has(r.opp) ? _expandHtml(r.opp, deckCode) : '';
      return row + exp;
    }).join('');
    const hint = '<div class="mh-hint">Sorted by win rate (worst first). Tap a row to expand · Open full workspace for the deep dive.</div>';
    return '<div class="mh-card">' +
      '<div class="mh-head">Matchups ' +
      '<span class="mh-head-sub">' + rows.length + ' observed · ' + DAYS + 'd</span></div>' +
      otpStrip +
      '<div class="mh-list">' + body + '</div>' +
      hint +
      '</div>';
  }

  window.V3.DeckMatchups = {
    MATRIX_MIN_GAMES: MATRIX_MIN_GAMES,
    build: build,
    selectOpp: selectOpp,
    openMatchup: openMatchup,
    openWorkspace: openWorkspace,
    toggle: toggle,
    setTab: setTab,
    _rows: _rows,
    _expanded: EXPANDED,
  };
})();
