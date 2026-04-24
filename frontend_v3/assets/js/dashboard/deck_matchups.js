// Deck tab — Area C Matchups heatmap.
// Contract: docs/DECK_REFACTOR_PARITY.md rows 8, 12, 47.
// Compact table: one row per observed opp with ≥15 games, sorted by WR asc
// (worst first = most to study). Tap a row to set labOpp and re-render
// (PR4). Later in PR5 the tap will instead open the Matchup Workspace.
//
// Consumes: perimeters[p].matrix[deck], perimeters[p].otp_otd[deck],
//   perimeters[p].matchup_trend[deck][opp], DECK_INKS, INK_COLORS.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const MATRIX_MIN_GAMES = 15;
  const DAYS = 3;
  const TOP_CURVES = 5;
  const EXPANDED = new Set();

  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function _short(n) { return (n || '').split(' - ')[0]; }

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

  function _rowHtml(r, selectedOpp) {
    const hb = window.V3 && window.V3.HonestyBadge;
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
      '</div>';
  }

  // Coverage badge per curve: 🟢 ≥3 copies · 🟡 1-2 · 🔴 0.
  function _covBadge(cov) {
    if (!cov) return { icon: '⚪', cls: 'mh-cov-unk', label: 'no data' };
    if (cov.status === 'green')  return { icon: '🟢', cls: 'mh-cov-good', label: 'covered' };
    if (cov.status === 'yellow') return { icon: '🟡', cls: 'mh-cov-mid',  label: 'partial' };
    return { icon: '🔴', cls: 'mh-cov-bad', label: 'missing' };
  }

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

  function _expandHtml(opp, deckCode) {
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    const rc = window.V3 && window.V3.ResponseCheck;

    if (!curves.length) {
      return '<div class="mh-expand">' +
        '<div class="mh-exp-empty">No killer-curve data reported for this matchup yet.</div>' +
        '<div class="mh-exp-cta">' +
        '<button class="mh-exp-btn" type="button" ' +
        'onclick="event.stopPropagation();window.V3.DeckMatchups.openWorkspace(\'' + _esc(opp) + '\')">' +
        'Open full workspace →</button>' +
        '</div></div>';
    }

    const deckMap = _deckMap(deckCode);
    const sorted = curves.slice().sort(function (a, b) {
      return ((b.frequency && b.frequency.pct) || 0) - ((a.frequency && a.frequency.pct) || 0);
    }).slice(0, TOP_CURVES);

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

    return '<div class="mh-expand">' +
      '<div class="mh-exp-head">Top killer curves · how this deck answers</div>' +
      rows +
      '<div class="mh-exp-cta">' +
      '<button class="mh-exp-btn" type="button" ' +
      'onclick="event.stopPropagation();window.V3.DeckMatchups.openWorkspace(\'' + _esc(opp) + '\')">' +
      'Open full workspace →</button>' +
      '</div></div>';
  }

  function toggle(opp) {
    if (!opp) return;
    if (EXPANDED.has(opp)) EXPANDED.delete(opp);
    else EXPANDED.add(opp);
    // Also select the opp so any downstream component keyed to labOpp gets
    // the intuitive "I'm focusing on this matchup" feedback. Does NOT open
    // the workspace — that needs the explicit button inside the expand.
    try { if (typeof labOpp !== 'undefined') labOpp = opp; } catch (e) {}
    if (typeof syncOppInksFromDeck === 'function') {
      try { syncOppInksFromDeck(opp); } catch (e) {}
    }
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

  // Row tap opens Matchup Workspace (PR5). Falls back to selectOpp if the
  // workspace module is not loaded.
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
    const body = rows.map(function (r) {
      const row = _rowHtml(r, selectedOpp);
      const exp = EXPANDED.has(r.opp) ? _expandHtml(r.opp, deckCode) : '';
      return row + exp;
    }).join('');
    const hint = '<div class="mh-hint">Sorted by win rate (worst first). Tap a row to expand · Open full workspace for the deep dive.</div>';
    return '<div class="mh-card">' +
      '<div class="mh-head">Matchups ' +
      '<span class="mh-head-sub">' + rows.length + ' observed · ' + DAYS + 'd</span></div>' +
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
    _rows: _rows,
    _expanded: EXPANDED,
  };
})();
