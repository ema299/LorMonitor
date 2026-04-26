// Matchup Workspace (PR5) — full-screen overlay consolidating the 12
// report_type fields into 6 canonical sections.
// Contract: docs/DECK_REFACTOR_PARITY.md Rule 5 + rows 21-25, 34, 37-44, 46-48.
//   Sections (fixed order):
//     1. Snapshot           — overview, matrix, otp_otd, matchup_trend
//     2. How to win         — playbook, winning_hands
//     3. Danger sequences   — killer_curves, threats_llm, board_state
//     4. Your answers       — killer_responses, response.cards, ResponseCheck
//     5. Card optimization  — decklist, card_scores, IWD endpoint, ability_cards
//     6. Loss review        — loss_analysis, failure_state, what_to_avoid
//
// Sticky header with: close · deck vs opp · opp switcher dropdown · KPIs.
// CTAs at the bottom: Mulligan Trainer in Play · Replay viewer in Play.
//
// Entry points:
//   window.V3.MatchupWorkspace.open(deckCode, oppCode)
//   — called from deck_matchups.js (row tap) and deck_summary.js (CTA).
//
// Rendered as a body-level portal (#mw-portal) so it is independent of
// lab.js re-renders. Dismissed via close() or ESC key.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const PORTAL_ID = 'mw-portal';
  const STATE = { deck: null, opp: null, open: false };

  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function _short(n) { return (n || '').split(' - ')[0]; }
  function _hb() { return window.V3 && window.V3.HonestyBadge; }

  // -------------------- Data helpers --------------------

  function _perim() {
    return (typeof getPerimData === 'function') ? getPerimData() : null;
  }
  function _muFor(opp) {
    return (typeof getMatchupData === 'function') ? getMatchupData(opp) : null;
  }
  function _matchupCell(deck, opp) {
    const pd = _perim();
    return pd && pd.matrix && pd.matrix[deck] && pd.matrix[deck][opp] || null;
  }
  function _otpOtd(deck, opp) {
    const pd = _perim();
    return pd && pd.otp_otd && pd.otp_otd[deck] && pd.otp_otd[deck][opp] || null;
  }
  function _matchupTrend(deck, opp) {
    const mt = window.DATA && window.DATA.matchup_trend;
    return mt && mt[deck] && mt[deck][opp] || null;
  }
  function _availableOpps(deck) {
    const pd = _perim();
    if (!pd || !pd.matrix || !pd.matrix[deck]) return [];
    return Object.keys(pd.matrix[deck])
      .map(function (opp) {
        const c = pd.matrix[deck][opp];
        return c ? { opp: opp, games: c.t || 0 } : null;
      })
      .filter(Boolean)
      .sort(function (a, b) { return b.games - a.games; });
  }

  // -------------------- Section renderers --------------------

  function _sectionSnapshot(deck, opp, mu) {
    const cell = _matchupCell(deck, opp);
    const otp = _otpOtd(deck, opp);
    const trend = _matchupTrend(deck, opp);
    const hb = _hb();

    const wr = cell && cell.t ? (cell.w || 0) / cell.t * 100 : null;
    const games = cell ? cell.t : 0;
    const wrFmt = hb ? hb.formatPct(wr, games) : (wr != null ? wr.toFixed(1) + '%' : '—');
    const confCls = hb ? hb.confidenceClass(games) : 'hb-med';
    const confLbl = hb ? hb.confidenceLabel(games) : 'Medium';

    const otpWr = otp && otp.otp_t ? (otp.otp_w / otp.otp_t * 100) : null;
    const otdWr = otp && otp.otd_t ? (otp.otd_w / otp.otd_t * 100) : null;

    const kpis =
      '<div class="mw-kpis">' +
      '<div class="mw-kpi"><div class="mw-kpi-v">' + wrFmt + '</div><div class="mw-kpi-l">Observed WR</div></div>' +
      '<div class="mw-kpi"><div class="mw-kpi-v">' + games.toLocaleString() + '</div><div class="mw-kpi-l">Observed games</div></div>' +
      '<div class="mw-kpi"><div class="mw-kpi-v">' + (otpWr != null ? Math.round(otpWr) + '%' : '—') +
      '</div><div class="mw-kpi-l">OTP (' + (otp ? otp.otp_t : 0) + 'g)</div></div>' +
      '<div class="mw-kpi"><div class="mw-kpi-v">' + (otdWr != null ? Math.round(otdWr) + '%' : '—') +
      '</div><div class="mw-kpi-l">OTD (' + (otp ? otp.otd_t : 0) + 'g)</div></div>' +
      '</div>';

    const ov = (mu && mu.overview) || {};
    const ovText = (typeof ov === 'string') ? ov
      : (ov.summary || ov.text || '');

    let trendHtml = '';
    if (trend && (trend.recent_wr != null || trend.prev_wr != null)) {
      const recent = trend.recent_wr != null ? Math.round(trend.recent_wr) + '%' : '—';
      const prev = trend.prev_wr != null ? Math.round(trend.prev_wr) + '%' : '—';
      const delta = (trend.recent_wr != null && trend.prev_wr != null)
        ? (trend.recent_wr - trend.prev_wr).toFixed(1) + 'pp' : '';
      trendHtml = '<div class="mw-trend">7d trend: <strong>' + recent + '</strong> recent vs ' + prev + ' prior' +
        (delta ? ' · <span>' + delta + '</span>' : '') + '</div>';
    }

    return kpis +
      (ovText ? '<div class="mw-prose">' + _esc(ovText) + '</div>' : '') +
      trendHtml +
      '<div class="mw-footnote">Confidence: <span class="hb-conf ' + confCls + '">' + confLbl +
      '</span> · based on ' + games + ' observed games</div>';
  }

  function _sectionHowToWin(deck, opp, mu) {
    const pb = (mu && mu.playbook) || [];
    const wh = (mu && mu.winning_hands) || {};

    let playbookHtml = '';
    if (Array.isArray(pb) && pb.length) {
      const items = pb.slice(0, 8).map(function (t) {
        const turn = t.turn || '?';
        const text = t.text || t.plan || t.description || '';
        return '<li class="mw-pb"><span class="mw-pb-turn">' + _esc(turn) + '</span>' +
          '<span class="mw-pb-text">' + _esc(text) + '</span></li>';
      }).join('');
      playbookHtml = '<h4 class="mw-h4">Playbook</h4><ul class="mw-pb-list">' + items + '</ul>';
    }

    let handsHtml = '';
    const handList = wh.hands || wh.list || (Array.isArray(wh) ? wh : []);
    if (Array.isArray(handList) && handList.length) {
      const items = handList.slice(0, 4).map(function (h) {
        const cards = (h.cards || h.hand || []).map(function (c) {
          return _esc(_short(typeof c === 'string' ? c : c.name || ''));
        }).join(', ');
        const ctx = [h.otp === true ? 'OTP' : h.otp === false ? 'OTD' : null, h.result || null]
          .filter(Boolean).join(' · ');
        return '<li class="mw-hand"><span class="mw-hand-cards">' + cards + '</span>' +
          (ctx ? '<span class="mw-hand-ctx">' + ctx + '</span>' : '') + '</li>';
      }).join('');
      handsHtml = '<h4 class="mw-h4">Winning hands <span class="mw-hint">(' + handList.length + ' observed)</span></h4>' +
        '<ul class="mw-hand-list">' + items + '</ul>';
    }

    const mullCta =
      '<div class="mw-cta-row">' +
      '<button class="mw-cta" type="button" onclick="window.V3.MatchupWorkspace._jumpToPlay(\'mulligan\')">' +
      'Open Mulligan Trainer in Play →</button>' +
      '</div>';

    const body = (playbookHtml || handsHtml)
      ? (playbookHtml + handsHtml + mullCta)
      : '<div class="mw-empty">No playbook or winning-hands report for this matchup yet.</div>' + mullCta;
    return body;
  }

  function _sectionDanger(deck, opp, mu) {
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    const threats = (mu && mu.threats_llm && Array.isArray(mu.threats_llm.threats))
      ? mu.threats_llm.threats : [];
    const board = (mu && mu.board_state) || null;

    let curvesHtml = '';
    if (curves.length) {
      const items = curves.slice().sort(function (a, b) {
        return ((b.frequency && b.frequency.pct) || 0) - ((a.frequency && a.frequency.pct) || 0);
      }).slice(0, 5).map(function (c) {
        const freq = (c.frequency && c.frequency.pct != null) ? Math.round(c.frequency.pct) + '%' : '—';
        const crit = c.critical_turn && c.critical_turn.turn ? 'T' + c.critical_turn.turn : '';
        const seq = (c.sequence && Array.isArray(c.sequence.plays))
          ? c.sequence.plays.slice(0, 6).map(function (p) {
              return _esc((p.turn || '?') + ': ' + (p.card || p.play || ''));
            }).join(' → ')
          : '';
        const keys = (c.key_cards || []).slice(0, 4).map(function (k) {
          return '<span class="mw-chip">' + _esc(_short(k)) + '</span>';
        }).join('');
        return '<li class="mw-curve">' +
          '<div class="mw-curve-head">' +
          '<span class="mw-curve-name">' + _esc(c.name || 'Unnamed curve') + '</span>' +
          (crit ? '<span class="mw-curve-turn">' + crit + '</span>' : '') +
          '<span class="mw-curve-freq">' + freq + '</span>' +
          '</div>' +
          (seq ? '<div class="mw-curve-seq">' + seq + '</div>' : '') +
          (keys ? '<div class="mw-curve-keys">' + keys + '</div>' : '') +
          '</li>';
      }).join('');
      curvesHtml = '<h4 class="mw-h4">Killer curves <span class="mw-hint">(top ' + Math.min(5, curves.length) + ')</span></h4>' +
        '<ul class="mw-curve-list">' + items + '</ul>';
    }

    let threatsHtml = '';
    if (threats.length) {
      const items = threats.slice(0, 4).map(function (t) {
        return '<li class="mw-threat">' +
          '<div class="mw-threat-name">' + _esc(t.name || 'Threat') + '</div>' +
          (t.description ? '<div class="mw-threat-desc">' + _esc(t.description) + '</div>' : '') +
          (t.mitigation ? '<div class="mw-threat-mit">Mitigation: ' + _esc(t.mitigation) + '</div>' : '') +
          '</li>';
      }).join('');
      threatsHtml = '<h4 class="mw-h4">LLM threats</h4><ul class="mw-threat-list">' + items + '</ul>';
    }

    let boardHtml = '';
    if (board && (typeof board === 'object')) {
      const keys = Object.keys(board).slice(0, 6);
      if (keys.length) {
        const items = keys.map(function (k) {
          const v = board[k];
          const s = (typeof v === 'string') ? v : JSON.stringify(v);
          return '<li><strong>' + _esc(k) + '</strong>: ' + _esc(s.slice(0, 140)) + '</li>';
        }).join('');
        boardHtml = '<h4 class="mw-h4">Typical board state</h4><ul class="mw-kv">' + items + '</ul>';
      }
    }

    return (curvesHtml || threatsHtml || boardHtml)
      ? (curvesHtml + threatsHtml + boardHtml)
      : '<div class="mw-empty">No danger-sequence reports for this matchup yet.</div>';
  }

  function _sectionAnswers(deck, opp, mu) {
    if (window.V3 && window.V3.ResponseCheck && typeof window.V3.ResponseCheck.build === 'function') {
      return window.V3.ResponseCheck.build(deck, opp);
    }
    return '<div class="mw-empty">Response coverage module not loaded.</div>';
  }

  function _sectionCardOpt(deck, opp, mu) {
    const dl = (mu && mu.decklist) || {};
    const scores = (mu && mu.card_scores) || {};

    let listHtml = '';
    if (Array.isArray(dl.full_list) && dl.full_list.length) {
      const total = dl.full_list.reduce(function (s, c) { return s + (c.qty || 0); }, 0);
      const rows = dl.full_list.slice().sort(function (a, b) {
        return (b.score || 0) - (a.score || 0);
      }).map(function (c) {
        const score = c.score != null ? (c.score >= 0 ? '+' + c.score : String(c.score)) : '';
        const scoreCls = c.score > 0 ? 'mw-pos' : c.score < 0 ? 'mw-neg' : '';
        return '<tr><td>' + (c.qty || 1) + '×</td>' +
          '<td>' + _esc(_short(c.card)) + '</td>' +
          '<td class="' + scoreCls + '">' + score + '</td></tr>';
      }).join('');
      listHtml = '<h4 class="mw-h4">Optimized decklist <span class="mw-hint">(' + total + '/60)</span>' +
        ' <button class="mw-mini-btn" type="button" onclick="window.V3.MatchupWorkspace._copyList(\'' + _esc(deck) + '\',\'' + _esc(opp) + '\')">Copy</button>' +
        '</h4>' +
        '<table class="mw-dl-table"><thead><tr><th>Qty</th><th>Card</th><th>Score</th></tr></thead>' +
        '<tbody>' + rows + '</tbody></table>';
    }

    const scoreKeys = Object.keys(scores).slice(0, 12);
    let scoresHtml = '';
    if (scoreKeys.length) {
      const rows = scoreKeys.map(function (k) { return { name: k, entry: scores[k] }; })
        .filter(function (r) { return r.entry && typeof r.entry.delta === 'number'; })
        .sort(function (a, b) { return Math.abs(b.entry.delta) - Math.abs(a.entry.delta); })
        .slice(0, 10)
        .map(function (r) {
          const pp = r.entry.delta * 100;
          const fmt = (pp >= 0 ? '+' : '') + pp.toFixed(1) + 'pp';
          const cls = pp >= 2 ? 'mw-pos' : pp <= -2 ? 'mw-neg' : '';
          const apps = r.entry.apps != null ? r.entry.apps : (r.entry.games || 0);
          const dw = r.entry.decks_with;
          const dt = r.entry.decks_total;
          const sampleLabel = (dt && dt > 0)
            ? 'in ' + dw + '/' + dt + ' decks (' + Math.round(dw / dt * 100) + '%)'
            : 'on ' + apps + ' appearances';
          const onclick = 'window.V3.HonestyBadge.openAppearancesExplainer(' +
            apps + ',' + (dw || 0) + ',' + (dt || 0) + ')';
          return '<tr><td>' + _esc(_short(r.name)) + '</td>' +
            '<td class="' + cls + '">' + fmt + '</td>' +
            '<td><span class="im-card-sample" role="button" tabindex="0" onclick="' + onclick + '">' +
            sampleLabel + '</span></td></tr>';
        }).join('');
      scoresHtml = '<h4 class="mw-h4">Card scores <span class="mw-hint">(top absolute delta · ' +
        '<span class="im-conf-hint-link" role="button" tabindex="0" ' +
        'onclick="window.V3.HonestyBadge.openAppearancesExplainer(0)">what do appearances mean?</span>)</span></h4>' +
        '<table class="mw-sc-table"><tbody>' + rows + '</tbody></table>';
    }

    const iwdCta =
      '<div class="mw-cta-row">' +
      '<button class="mw-cta" type="button" onclick="window.V3.MatchupWorkspace._loadIwd()">' +
      'Compute IWD (Improvement When Drawn) →</button>' +
      '<div class="mw-iwd-host" id="mw-iwd-host"></div>' +
      '</div>';

    const body = (listHtml + scoresHtml + iwdCta) ||
      '<div class="mw-empty">No card-optimization data for this matchup yet.</div>';
    return body;
  }

  function _sectionLossReview(deck, opp, mu) {
    const la = (mu && mu.loss_analysis) || null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];

    let laHtml = '';
    if (la) {
      if (typeof la === 'string' && la.length > 10) {
        laHtml = '<h4 class="mw-h4">Loss analysis</h4><div class="mw-prose">' + _esc(la) + '</div>';
      } else if (typeof la === 'object') {
        const summary = la.summary || la.text;
        const reasons = la.reasons || la.causes || [];
        if (summary) laHtml += '<div class="mw-prose">' + _esc(summary) + '</div>';
        if (Array.isArray(reasons) && reasons.length) {
          laHtml += '<ul class="mw-bullet">' +
            reasons.slice(0, 6).map(function (r) { return '<li>' + _esc(r) + '</li>'; }).join('') +
            '</ul>';
        }
        if (laHtml) laHtml = '<h4 class="mw-h4">Loss analysis</h4>' + laHtml;
      }
    }

    const failStates = curves.map(function (c) {
      return c && c.response && typeof c.response.failure_state === 'string'
        && c.response.failure_state.trim() ? c.response.failure_state.trim() : null;
    }).filter(Boolean);
    let fsHtml = '';
    if (failStates.length) {
      const uniq = [];
      const seen = {};
      failStates.forEach(function (s) { if (!seen[s]) { seen[s] = true; uniq.push(s); } });
      fsHtml = '<h4 class="mw-h4">Failure states</h4><ul class="mw-bullet">' +
        uniq.slice(0, 5).map(function (s) { return '<li>' + _esc(s) + '</li>'; }).join('') +
        '</ul>';
    }

    const avoid = curves.map(function (c) {
      return c && c.response && typeof c.response.what_to_avoid === 'string'
        && c.response.what_to_avoid.trim() ? c.response.what_to_avoid.trim() : null;
    }).filter(Boolean);
    let avoidHtml = '';
    if (avoid.length) {
      const uniq = [];
      const seen = {};
      avoid.forEach(function (s) { if (!seen[s]) { seen[s] = true; uniq.push(s); } });
      avoidHtml = '<h4 class="mw-h4">What to avoid</h4><ul class="mw-bullet">' +
        uniq.slice(0, 5).map(function (s) { return '<li>' + _esc(s) + '</li>'; }).join('') +
        '</ul>';
    }

    return (laHtml + fsHtml + avoidHtml) ||
      '<div class="mw-empty">No loss-review data for this matchup yet.</div>';
  }

  // -------------------- Sticky header --------------------

  function _switcherHtml(deck, opp) {
    const opts = _availableOpps(deck);
    if (!opts.length) return '';
    const items = opts.map(function (o) {
      const sel = o.opp === opp ? ' selected' : '';
      return '<option value="' + _esc(o.opp) + '"' + sel + '>' + _esc(o.opp) +
        ' · ' + o.games + 'g</option>';
    }).join('');
    return '<select class="mw-switch" onchange="window.V3.MatchupWorkspace.switchOpp(this.value)" ' +
      'aria-label="Switch opponent">' + items + '</select>';
  }

  function _headerHtml(deck, opp) {
    const cell = _matchupCell(deck, opp);
    const wr = cell && cell.t ? (cell.w || 0) / cell.t * 100 : null;
    const games = cell ? cell.t : 0;
    const hb = _hb();
    const wrFmt = hb ? hb.formatPct(wr, games) : (wr != null ? Math.round(wr) + '%' : '—');
    const confCls = hb ? hb.confidenceClass(games) : 'hb-med';
    return '<header class="mw-header">' +
      '<button class="mw-close" type="button" ' +
      'onclick="window.V3.MatchupWorkspace.close()" aria-label="Close">&times;</button>' +
      '<div class="mw-header-title">' +
      '<span class="mw-hdr-deck">' + _esc(deck) + '</span>' +
      '<span class="mw-hdr-vs">vs</span>' +
      _switcherHtml(deck, opp) +
      '</div>' +
      '<div class="mw-header-stats">' +
      '<span class="mw-hdr-wr">' + wrFmt + '</span>' +
      '<span class="mw-hdr-games">on ' + games + ' obs.</span>' +
      '<span class="hb-conf ' + confCls + '">' + (hb ? hb.confidenceLabel(games) : 'Medium') + '</span>' +
      '</div>' +
      '</header>';
  }

  // -------------------- Render / lifecycle --------------------

  function _section(id, title, bodyHtml, intro) {
    const introHtml = intro
      ? '<div class="deck-intro deck-intro--above mw-sec-intro">' + intro + '</div>'
      : '';
    return introHtml +
      '<section class="mw-sec" data-sec="' + id + '">' +
      '<h3 class="mw-sec-title">' + title + '</h3>' +
      '<div class="mw-sec-body">' + bodyHtml + '</div>' +
      '</section>';
  }

  function _render() {
    const existing = document.getElementById(PORTAL_ID);
    if (existing) existing.remove();
    if (!STATE.open || !STATE.deck || !STATE.opp) return;

    const mu = _muFor(STATE.opp) || {};
    const header = _headerHtml(STATE.deck, STATE.opp);
    const body =
      _section('snap', '1. Snapshot', _sectionSnapshot(STATE.deck, STATE.opp, mu),
        '<strong>Headline numbers for this specific pairing</strong> — overall win rate, ' +
        'OTP / OTD split (who goes first matters), and the 3-day vs 3-day-before trend. ' +
        'All figures come from the observed sample in the current scope. Use the OTP/OTD ' +
        'gap as the first red flag: a 10pp+ swing means the matchup quality depends ' +
        'heavily on the coin flip, not on play skill.') +
      _section('win',  '2. How to win', _sectionHowToWin(STATE.deck, STATE.opp, mu),
        '<strong>Opening hands and early-turn patterns the archetype wins with</strong>, ' +
        'pulled from the last 30 days of matches where this deck beat this opponent. ' +
        'These are <em>observed patterns</em>, not a recipe: they tell you what ended up ' +
        'on the board in wins, not necessarily what caused them. Use together with the ' +
        'Mulligan Trainer in the Play tab for drillable reps.') +
      _section('dng',  '3. Danger sequences', _sectionDanger(STATE.deck, STATE.opp, mu),
        '<strong>Opponent killer curves</strong> — the recurring multi-turn lines that ' +
        'close the game from their side, ranked by observed frequency. Each shows its ' +
        'critical turn (the one where if unanswered, the game typically ends). The ' +
        'coverage badge on each curve is computed against the reference decklist: ' +
        '🟢 ≥3 copies of a listed answer, 🟡 1–2 copies, 🔴 no listed answer.') +
      _section('ans',  '4. Your answers', _sectionAnswers(STATE.deck, STATE.opp, mu),
        '<strong>The same killer curves as above, viewed from the response side</strong> — ' +
        'which answer cards are already in the list and which would need to be added to ' +
        'cover each threat line. Copy counts aggregate across reprints (any version of ' +
        'the card with the same base name counts toward the total).') +
      _section('opt',  '5. Card optimization', _sectionCardOpt(STATE.deck, STATE.opp, mu),
        '<strong>Two signals side by side for tuning the 60 cards vs this matchup.</strong> ' +
        '<em>Card scores</em> (correlation): win rate delta when the card is played vs when ' +
        'it isn’t — directional, not causal, biased by game duration. <em>IWD</em> ' +
        '(Improvement When Drawn): win rate delta when the card lands in hand by turn 3 vs ' +
        'later — closer to causal. The optimized list applies the card-scores add/cut logic ' +
        'to the consensus baseline.') +
      _section('loss', '6. Loss review', _sectionLossReview(STATE.deck, STATE.opp, mu),
        '<strong>Where this archetype tends to lose against this opponent</strong> — ' +
        'primary loss causes, failure states extracted from killer curves, and a textual ' +
        'summary if the LLM pipeline has run. Read this after Snapshot flags the matchup ' +
        'as weak: it tells you <em>why</em>, not just that the WR is bad.');

    const footer =
      '<footer class="mw-footer">' +
      '<button class="mw-cta" type="button" onclick="window.V3.MatchupWorkspace._jumpToPlay(\'replay\')">' +
      'Open Replay Viewer in Play →</button>' +
      '</footer>';

    const portal = document.createElement('div');
    portal.id = PORTAL_ID;
    portal.className = 'mw-portal';
    portal.setAttribute('role', 'dialog');
    portal.setAttribute('aria-label', 'Matchup workspace');
    portal.innerHTML =
      '<div class="mw-backdrop" onclick="if(event.target===this)window.V3.MatchupWorkspace.close()">' +
      '<div class="mw-panel">' + header + '<div class="mw-body">' + body + '</div>' + footer + '</div>' +
      '</div>';
    document.body.appendChild(portal);
    document.body.classList.add('mw-open');
    requestAnimationFrame(function () { portal.classList.add('mw-on'); });
  }

  function open(deckCode, oppCode) {
    if (!deckCode || !oppCode) return;
    STATE.deck = deckCode;
    STATE.opp = oppCode;
    STATE.open = true;
    // Keep labOpp in sync so closing the workspace leaves the opp selected.
    try { if (typeof labOpp !== 'undefined') labOpp = oppCode; } catch (e) {}
    _render();
  }

  function close() {
    STATE.open = false;
    const p = document.getElementById(PORTAL_ID);
    if (p) {
      p.classList.remove('mw-on');
      setTimeout(function () { if (p.parentNode) p.parentNode.removeChild(p); }, 150);
    }
    document.body.classList.remove('mw-open');
    if (typeof render === 'function') render();
  }

  function switchOpp(newOpp) {
    if (!newOpp) return;
    STATE.opp = newOpp;
    try { if (typeof labOpp !== 'undefined') labOpp = newOpp; } catch (e) {}
    if (typeof syncOppInksFromDeck === 'function') {
      try { syncOppInksFromDeck(newOpp); } catch (e) {}
    }
    _render();
  }

  // CTA hooks — Play tab navigation. Uses legacy switchToTab() if available.
  function _jumpToPlay(mode) {
    close();
    if (typeof switchToTab === 'function') {
      try { switchToTab('play'); } catch (e) {}
    }
  }

  function _copyList(deck, opp) {
    const mu = _muFor(opp);
    const dl = mu && mu.decklist;
    if (!dl || !Array.isArray(dl.full_list)) return;
    const txt = dl.import_text ||
      dl.full_list.map(function (c) { return (c.qty || 1) + ' ' + c.card; }).join('\n');
    try {
      navigator.clipboard.writeText(txt);
      const btns = document.querySelectorAll('.mw-mini-btn');
      btns.forEach(function (b) {
        if (b.textContent === 'Copy') { b.textContent = 'Copied!'; setTimeout(function () { b.textContent = 'Copy'; }, 1500); }
      });
    } catch (e) {}
  }

  function _loadIwd() {
    const host = document.getElementById('mw-iwd-host');
    if (!host) return;
    if (!STATE.deck || !STATE.opp) return;
    host.innerHTML = '<div class="mw-empty">Loading IWD…</div>';
    const fmt = (typeof currentFormat !== 'undefined') ? currentFormat : 'core';
    fetch('/api/v1/lab/iwd/' + encodeURIComponent(STATE.deck) + '/' + encodeURIComponent(STATE.opp) +
          '?game_format=' + fmt + '&days=14')
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) {
        if (data.low_sample) {
          host.innerHTML = '<div class="mw-empty">Low sample (' + data.total_matches +
            ' games, need ≥' + (data.min_total_matches || 80) + ').</div>';
          return;
        }
        const cards = (data.cards || []).slice(0, 10);
        if (!cards.length) { host.innerHTML = '<div class="mw-empty">No IWD signal.</div>'; return; }
        const rows = cards.map(function (c) {
          const pp = (c.delta || 0);
          const cls = pp >= 2 ? 'mw-pos' : pp <= -2 ? 'mw-neg' : '';
          return '<tr><td>' + _esc(_short(c.card || c.name || '')) + '</td>' +
            '<td class="' + cls + '">' + (pp >= 0 ? '+' : '') + pp.toFixed(1) + 'pp</td>' +
            '<td>on ' + (c.sample || c.games || 0) + ' obs.</td></tr>';
        }).join('');
        host.innerHTML = '<table class="mw-sc-table"><tbody>' + rows + '</tbody></table>';
      })
      .catch(function (e) {
        host.innerHTML = '<div class="mw-empty">IWD unavailable (' + String(e).slice(0, 60) + ').</div>';
      });
  }

  // ESC key closes workspace
  document.addEventListener('keydown', function (e) {
    if (STATE.open && e.key === 'Escape') close();
  });

  window.V3.MatchupWorkspace = {
    open: open,
    close: close,
    switchOpp: switchOpp,
    _jumpToPlay: _jumpToPlay,
    _copyList: _copyList,
    _loadIwd: _loadIwd,
    state: STATE,
  };
})();
