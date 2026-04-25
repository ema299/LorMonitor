// === TEAM TRAINING TAB ===
let ttSelectedPlayer = null; // null = overview
let ttInboxFilter = '7d';   // today | 7d | 30d | all

// ── Team Tab v3: Premium Esports Dashboard ──
function ttSevConfig(type) {
  if (type === 'danger') return { cls: 'critical', icon: '!', label: 'Critical', dot: 'var(--red)', emoji: '\u26A0\uFE0F' };
  if (type === 'warning') return { cls: 'warning', icon: '~', label: 'Warning', dot: 'var(--yellow)', emoji: '\u26A0\uFE0F' };
  return { cls: 'info', icon: 'i', label: 'Info', dot: '#58a6ff', emoji: '\u2139\uFE0F' };
}

function ttAvatarStyle(wr) {
  if (wr >= 55) return 'background:rgba(63,185,80,0.18);color:var(--green);border-color:rgba(63,185,80,0.4)';
  if (wr <= 45) return 'background:rgba(248,81,73,0.18);color:var(--red);border-color:rgba(248,81,73,0.4)';
  return 'background:rgba(210,153,34,0.18);color:var(--yellow);border-color:rgba(210,153,34,0.4)';
}

function ttWrGlowClass(wr) {
  if (wr >= 55) return 'wr-glow-green';
  if (wr <= 45) return 'wr-glow-red';
  return 'wr-glow-yellow';
}

function ttToggleCard(el) {
  el.closest('.tt-player-card').classList.toggle('open');
}
function ttToggleInbox() {
  document.getElementById('tt-inbox-panel').classList.toggle('open');
  document.getElementById('tt-inbox-overlay').classList.toggle('open');
}
function ttToggleSection(id) {
  document.getElementById(id).classList.toggle('open');
}

function ttMiniSparkline(daily) {
  if (!daily || daily.length < 2) return '';
  const last7 = daily.slice(-7);
  let h = '<span class="tt-pc-spark-mini">';
  last7.forEach(d => {
    const barH = Math.max(2, Math.round(d.wr / 100 * 14));
    const col = d.wr >= 55 ? 'var(--green)' : d.wr <= 45 ? 'var(--red)' : 'var(--yellow)';
    h += `<span class="tt-pc-spark-mini-bar" style="height:${barH}px;background:${col}"></span>`;
  });
  h += '</span>';
  return h;
}

function ttHeatmapCellBg(wr) {
  if (wr >= 65) return 'rgba(63,185,80,0.25)';
  if (wr >= 55) return 'rgba(63,185,80,0.12)';
  if (wr <= 35) return 'rgba(248,81,73,0.25)';
  if (wr <= 45) return 'rgba(248,81,73,0.12)';
  return 'rgba(255,255,255,0.03)';
}

/**
 * Team tab quick-access strip — deep-link to Play / Meta (renamed 25/04 — was "Pro Tools" container).
 *
 * Eyebrow + title rimossi: questa E' la tab Team, non una sotto-categoria.
 * Killer Curves Deep e Full Matchup Matrix restano deep-link al rispettivo tab di origine
 * (Play / Meta) per evitare conflitti di chart instances e ID duplicati nel DOM.
 */
function buildProToolsHeader() {
  return `
    <div class="pt-header" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px">
      <button onclick="switchToTab('play')" style="background:transparent;border:1px solid rgba(255,215,0,0.35);color:var(--text);padding:7px 14px;border-radius:6px;font-size:0.82em;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px">
        <span style="color:var(--gold)">&#9728;</span> Killer Curves Deep <small style="opacity:0.6;font-weight:400">(in Play)</small>
      </button>
      <button onclick="switchToTab('meta')" style="background:transparent;border:1px solid rgba(255,215,0,0.35);color:var(--text);padding:7px 14px;border-radius:6px;font-size:0.82em;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px">
        <span style="color:var(--gold)">&#9638;</span> Full Matchup Matrix <small style="opacity:0.6;font-weight:400">(in Meta)</small>
      </button>
    </div>
  `;
}

/**
 * IWD section embedded in Team tab (V3-5 22/04).
 * Riusa iwdLoad() / iwdRender() esposti da lab.js. ID #iwd-wrap e' unico nel DOM
 * (Team non coesiste con Deck nello stesso istante, no conflitto runtime).
 */
function buildProToolsIWDSection() {
  const our = (typeof coachDeck !== 'undefined' && coachDeck) || (typeof selectedDeck !== 'undefined' && selectedDeck) || null;
  const opp = (typeof labOpp !== 'undefined' && labOpp) || null;
  const matchupReady = our && opp;
  const onOpen = matchupReady
    ? "if(typeof iwdLoad==='function')iwdLoad()"
    : '';
  const body = matchupReady
    ? `<div style="font-size:0.82em;color:var(--text2);margin-bottom:8px">Improvement When Drawn for <strong>${our}</strong> vs <strong>${opp}</strong>. Pick a different opponent in Deck or Play to refresh.</div>
       <div id="iwd-wrap"><div class="iwd-loading">Loading IWD…</div></div>`
    : `<div style="color:var(--text2);font-size:0.85em;padding:8px 0">
         Select a deck and an opponent (in <a onclick="switchToTab('deck')" style="color:var(--gold);cursor:pointer;text-decoration:underline">Deck</a> or <a onclick="switchToTab('play')" style="color:var(--gold);cursor:pointer;text-decoration:underline">Play</a>) first, then come back here.
       </div>`;
  return `<div class="section">${monAccordion(
    'acc-pt-iwd',
    'IWD &mdash; Improvement When Drawn',
    matchupReady ? `${our} vs ${opp}` : 'Select a matchup',
    body,
    {
      desktopOpen: false,
      onOpen,
      info: { title: 'About IWD', body: '<p>For each card, compares WR when drawn vs WR when NOT drawn.</p><p>Helps identify trap cards (-Δ) and key cards (+Δ) for the matchup.</p><p>At least 80 total games in the matchup are required for reliable data.</p>' }
    }
  )}</div>`;
}

// Board Lab is the Coach SKU anchor — must render even without a roster.
function buildBoardLabSection() {
  return '<div class="tab-section-hdr" style="margin-top:var(--sp-5)">' +
    '<span class="tab-section-hdr__eyebrow">Board Lab</span>' +
    '<span class="tab-section-hdr__title">Replay viewer &middot; game-by-game analysis</span>' +
    '</div>' +
    '<div class="tt-collapsible open" id="tt-lab-coll">' +
    '<button class="tt-coll-head" onclick="ttToggleSection(\'tt-lab-coll\')">' +
    '<span class="tt-coll-title">🧪 Board Lab</span>' +
    '<span class="tt-coll-chevron">▼</span>' +
    '</button>' +
    '<div class="tt-coll-body"><div id="tc-container"></div></div>' +
    '</div>';
}

function renderTeamTab(main) {
  const team = DATA.team;
  if (!team || !team.players || team.players.length === 0) {
    main.innerHTML = buildProToolsHeader() +
      '<div class="card" style="text-align:center;padding:60px 20px">' +
      '<div style="font-size:2.5em;margin-bottom:12px">\uD83C\uDFAE</div>' +
      '<h2 style="margin-bottom:6px;font-size:1.1em">Team Training</h2>' +
      '<p style="color:var(--text2);font-size:0.85em;max-width:360px;margin:0 auto">No team configured yet. Roster analytics unlock once players are added &mdash; Board Lab below works without a roster.</p></div>' +
      ((typeof buildProToolsIWDSection === 'function') ? buildProToolsIWDSection() : '') +
      buildBoardLabSection();
    if (typeof tcInit === 'function') tcInit('tc-container');
    return;
  }

  const players = team.players;
  const ov = team.overview || {};

  // ── Collect all alerts for inbox ──
  const allAlerts = [];
  players.forEach(p => (p.alerts || []).forEach(a => allAlerts.push({ ...a, player: p.name, isTeam: false })));
  (ov.alerts || []).forEach(a => allAlerts.push({ ...a, player: 'TEAM', isTeam: true }));
  const critCount = allAlerts.filter(a => a.type === 'danger').length;
  const warnCount = allAlerts.filter(a => a.type === 'warning').length;
  const totalAlerts = critCount + warnCount;

  // ── Team WR sparkline from player dailies ──
  const allDays = new Set();
  players.forEach(p => (p.daily || []).forEach(d => allDays.add(d.day)));
  const sortedDays = [...allDays].sort();
  const teamDailyBars = sortedDays.map(day => {
    let w = 0, t = 0;
    players.forEach(p => {
      const dd = (p.daily || []).find(d => d.day === day);
      if (dd) { w += Math.round(dd.wr * dd.games / 100); t += dd.games; }
    });
    return t > 0 ? Math.round(w / t * 100) : 50;
  });
  const sparkHtml = teamDailyBars.map(wr => {
    const h = Math.max(4, Math.round(wr / 100 * 32));
    const col = wr >= 55 ? 'var(--green)' : wr <= 45 ? 'var(--red)' : 'var(--yellow)';
    return `<div class="tt-strip-bar" style="height:${h}px;background:${col}" title="${wr}%"></div>`;
  }).join('');

  // ── KPI strip trend ──
  let trendIcon = '', trendColor = 'var(--text2)';
  if (teamDailyBars.length >= 2) {
    const last = teamDailyBars[teamDailyBars.length - 1], prev = teamDailyBars[teamDailyBars.length - 2];
    if (last > prev + 3) { trendIcon = '\uD83D\uDCC8'; trendColor = 'var(--green)'; }
    else if (last < prev - 3) { trendIcon = '\uD83D\uDCC9'; trendColor = 'var(--red)'; }
    else { trendIcon = '\u2194\uFE0F'; }
  }

  // ── Best/worst player ──
  const bestP = ov.best_player || {};
  const worstP = ov.worst_player || {};

  let html = `<div class="tt-layout">

  <div class="tab-section-hdr">
    <span class="tab-section-hdr__eyebrow">Team Overview</span>
    <span class="tab-section-hdr__title">Performance KPIs &middot; alerts</span>
  </div>`;

  // ── KPI Strip ──
  const bellSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>';
  html += `<div class="tt-strip">
    <div class="tt-strip-kpi">
      <span class="tt-strip-val">${ov.player_count || players.length}</span>
      <span class="tt-strip-lbl">Players</span>
    </div>
    <div class="tt-strip-kpi">
      <span class="tt-strip-val" style="color:${wrColor(ov.avg_wr||50)}">${(ov.avg_wr||0).toFixed(1)}%</span>
      <span class="tt-strip-lbl">Avg WR</span>
    </div>
    <div class="tt-strip-kpi">
      <span class="tt-strip-val">${(ov.total_games || 0).toLocaleString()}</span>
      <span class="tt-strip-lbl">Games</span>
    </div>
    <div class="tt-strip-kpi">
      <span class="tt-strip-val">${trendIcon}</span>
      <span class="tt-strip-lbl">Trend</span>
    </div>
    <div class="tt-strip-spacer"></div>
    <div class="tt-strip-inbox" onclick="ttToggleInbox()">
      ${bellSvg}
      ${critCount ? `<span class="tt-strip-inbox-badge crit">${critCount}</span>` : ''}
      ${warnCount ? `<span class="tt-strip-inbox-badge warn">${warnCount}</span>` : ''}
      ${!critCount && !warnCount ? '<span style="color:var(--green);font-weight:700">\u2713</span>' : ''}
    </div>
  </div>`;

  // ── Player cards in 2-col grid ──
  html += `<div class="tab-section-hdr" style="margin-top:var(--sp-5)">
    <span class="tab-section-hdr__eyebrow">Roster</span>
    <span class="tab-section-hdr__title">Player cards &middot; matchup breakdown &middot; focus areas</span>
  </div>`;
  html += '<div class="tt-cards-grid">';
  players.sort((a, b) => b.wr - a.wr).forEach((p, idx) => {
    const wr = p.wr;
    const wrCol = wrColor(wr);
    const glowCls = ttWrGlowClass(wr);
    const isBest = bestP.name && p.name === bestP.name;
    const isWorst = worstP.name && p.name === worstP.name;
    const hasAlerts = (p.alerts || []).length > 0;

    // Trend calculation
    let trendHtml = '';
    if (p.daily && p.daily.length >= 2) {
      const l = p.daily[p.daily.length - 1].wr, pr = p.daily[p.daily.length - 2].wr;
      if (l > pr + 3) trendHtml = '<span class="tt-pc-trend-icon" style="color:var(--green)">\u25B2</span>';
      else if (l < pr - 3) trendHtml = '<span class="tt-pc-trend-icon" style="color:var(--red)">\u25BC</span>';
      else trendHtml = '<span class="tt-pc-trend-icon" style="color:var(--text2)">=</span>';
    }

    // Badge icon (best/worst/alert)
    let badgeIcon = '';
    if (isBest) badgeIcon = '<span class="tt-pc-badge-icon">\uD83C\uDFC6</span>';
    else if (isWorst) badgeIcon = '<span class="tt-pc-badge-icon" style="font-size:0.75em">\u26A0\uFE0F</span>';
    else if (hasAlerts) badgeIcon = '<span class="tt-pc-badge-icon" style="font-size:0.7em">\uD83D\uDD34</span>';

    html += `<div class="tt-player-card ${glowCls}" id="tt-pc-${p.name.replace(/\W/g,'_')}">
      <div class="tt-pc-header" onclick="ttToggleCard(this)">
        <div class="tt-pc-deck-wrap">
          ${p.deck ? deckImg(p.deck, 32) : '<span style="font-size:1.2em">\uD83C\uDCCF</span>'}
          ${badgeIcon}
        </div>
        <div class="tt-pc-info">
          <div class="tt-pc-name-row">
            <span class="tt-pc-name">${p.name}</span>
            <span class="tt-pc-role">${p.role || 'player'}</span>
          </div>
          <div class="tt-pc-meta" style="justify-content:flex-start;margin-top:3px">
            <span>${p.games} games</span>
            ${p.deck ? `<span style="opacity:0.5">\u00B7</span><span>${p.deck}</span>` : ''}
          </div>
        </div>
        <div class="tt-pc-wr-block">
          <span class="tt-pc-wr" style="color:${wrCol}">${wr}%</span>
          <div class="tt-pc-meta">
            ${trendHtml}
            ${ttMiniSparkline(p.daily)}
          </div>
        </div>
        <span class="tt-pc-chevron">\u25BC</span>
      </div>
      <div class="tt-pc-body">
        <div class="tt-pc-grid">
          <div class="tt-pc-stat-box"><span class="tt-pc-stat-val">${p.mmr || '\u2014'}</span><span class="tt-pc-stat-lbl">MMR</span></div>
          <div class="tt-pc-stat-box"><span class="tt-pc-stat-val" style="color:${wrColor(p.otp_wr)}">${p.otp_wr}%</span><span class="tt-pc-stat-lbl">On the Play</span></div>
          <div class="tt-pc-stat-box"><span class="tt-pc-stat-val" style="color:${wrColor(p.otd_wr)}">${p.otd_wr}%</span><span class="tt-pc-stat-lbl">On the Draw</span></div>
          <div class="tt-pc-stat-box"><span class="tt-pc-stat-val" style="color:${p.otp_otd_gap > 5 ? 'var(--red)' : p.otp_otd_gap < -5 ? 'var(--red)' : 'var(--text)'}">${p.otp_otd_gap > 0 ? '+' : ''}${p.otp_otd_gap}pp</span><span class="tt-pc-stat-lbl">OTP/OTD Gap</span></div>
        </div>`;

    // Alerts inline
    if (p.alerts && p.alerts.length) {
      html += '<div class="tt-pc-section-title">\u26A0\uFE0F Alerts</div>';
      p.alerts.forEach(a => {
        const icon = a.type === 'danger' ? '\u274C' : '\u26A0\uFE0F';
        html += `<div class="tt-pc-alert ${a.type}"><span class="tt-pc-alert-icon">${icon}</span> ${a.msg}</div>`;
      });
    }

    // Matchup mini bars (top 6)
    const mus = Object.entries(p.matchups || {}).sort((a,b) => b[1].games - a[1].games).slice(0, 6);
    if (mus.length) {
      html += '<div class="tt-pc-section-title">\uD83C\uDFAF Top Matchups</div>';
      mus.forEach(([opp, s]) => {
        const barW = Math.max(3, Math.min(100, s.wr));
        const barCol = s.wr >= 55 ? 'var(--green)' : s.wr <= 45 ? 'var(--red)' : 'var(--yellow)';
        html += `<div class="tt-mu-row">
          <span class="tt-mu-opp">${deckImg(opp, 20)}</span>
          <div class="tt-mu-bar-wrap">
            <div class="tt-mu-50-line"></div>
            <div class="tt-mu-bar" style="width:${barW}%;background:${barCol}"></div>
          </div>
          <span class="tt-mu-val" style="color:${barCol}">${s.wr}% <span style="color:var(--text2);font-size:0.8em">${s.games}g</span></span>
        </div>`;
      });
    }

    // Focus area
    if (p.worst_matchup) {
      html += `<div class="tt-pc-section-title">\uD83D\uDD2C Focus Area</div>`;
      html += `<div style="font-size:0.84em;color:var(--text2);padding:6px 0">Weakest matchup: <strong style="color:var(--red)">${p.worst_matchup}</strong> &mdash; prioritize practice here</div>`;
    }

    html += `<div class="tt-replay-zone">\uD83D\uDCBC Upload .replay.gz in Board Lab below</div>`;
    html += `</div></div>`;
  });
  html += '</div>'; // .tt-cards-grid

  // ── Analysis: Meta Coverage + Lineup ──
  html += `<div class="tab-section-hdr" style="margin-top:var(--sp-5)">
    <span class="tab-section-hdr__eyebrow">Analysis</span>
    <span class="tab-section-hdr__title">Meta coverage &middot; lineup &middot; heatmap</span>
  </div>`;

  // ── Meta Coverage heatmap ──
  const metaWr = DATA.perimeters && DATA.perimeters.set11 ? DATA.perimeters.set11.wr : {};
  const topMeta = Object.entries(metaWr).sort((a,b) => b[1].games - a[1].games).slice(0, 8).map(e => e[0]);

  if (topMeta.length && players.length) {
    html += `<div class="tt-collapsible open" id="tt-cov-coll">
      <button class="tt-coll-head" onclick="ttToggleSection('tt-cov-coll')">
        <span class="tt-coll-title">\uD83D\uDDFA\uFE0F Meta Coverage</span>
        <span class="tt-coll-chevron">\u25BC</span>
      </button>
      <div class="tt-coll-body"><div class="tt-heatmap"><table><thead><tr><th></th>`;
    topMeta.forEach(d => html += `<th>${deckImg(d, 22)}<br><span style="font-size:0.72em;opacity:0.7">${d}</span></th>`);
    html += '</tr></thead><tbody>';

    // Per-player rows
    players.forEach(p => {
      html += `<tr><td class="tt-hm-name">${p.name}</td>`;
      topMeta.forEach(d => {
        const mu = (p.matchups || {})[d];
        if (!mu || mu.games === 0) { html += '<td style="color:var(--text2);background:rgba(255,255,255,0.01)">\u2014</td>'; }
        else {
          const bg = ttHeatmapCellBg(mu.wr);
          const color = mu.wr >= 55 ? 'var(--green)' : mu.wr <= 45 ? 'var(--red)' : 'var(--text)';
          html += `<td style="background:${bg};color:${color}" title="${mu.w}W ${mu.l}L (${mu.games}g)">${mu.wr}%</td>`;
        }
      });
      html += '</tr>';
    });

    // TEAM aggregate row
    html += '<tr class="tt-hm-team-row"><td class="tt-hm-name tt-hm-team">\uD83C\uDFC5 TEAM</td>';
    const teamBuchi = [];
    topMeta.forEach(d => {
      let tw = 0, tt = 0;
      players.forEach(p => { const mu = (p.matchups || {})[d]; if (mu) { tw += mu.w; tt += mu.games; } });
      if (tt === 0) { html += '<td class="tt-hm-team" style="color:var(--text2)">\u2014</td>'; }
      else {
        const twr = Math.round(tw / tt * 100);
        const bg = ttHeatmapCellBg(twr);
        const color = twr >= 55 ? 'var(--green)' : twr <= 45 ? 'var(--red)' : 'var(--gold)';
        const above50 = players.filter(p => { const mu = (p.matchups || {})[d]; return mu && mu.wr >= 50; }).length;
        const holeCls = above50 === 0 ? ' tt-hm-hole' : '';
        html += `<td class="tt-hm-team${holeCls}" style="background:${bg};color:${color}">${twr}%</td>`;
        if (above50 === 0) teamBuchi.push(d);
      }
    });
    html += '</tr></tbody></table></div>';

    // Buchi alert strip
    if (teamBuchi.length) {
      teamBuchi.forEach(d => {
        html += `<div class="tt-hole-alert">\uD83D\uDEA8 <strong>Coverage hole:</strong>&nbsp;vs ${d} &mdash; no player above 50%</div>`;
      });
    }
    html += '</div></div>';
  }

  // ── Lineup Suggestion ──
  const lineup = [...players].sort((a, b) => b.wr - a.wr);
  html += `<div class="tt-collapsible open" id="tt-lineup-coll">
    <button class="tt-coll-head" onclick="ttToggleSection('tt-lineup-coll')">
      <span class="tt-coll-title">\uD83D\uDCCB Lineup Suggerita</span>
      <span class="tt-coll-chevron">\u25BC</span>
    </button>
    <div class="tt-coll-body">`;
  const medals = ['\uD83E\uDD47', '\uD83E\uDD48', '\uD83E\uDD49'];
  lineup.forEach((p, i) => {
    const isSit = p.wr < 45 && i >= lineup.length - 1;
    const rank = i < 3 ? medals[i] : `<span style="color:var(--text2);font-weight:600">${i + 1}</span>`;
    const bestCoverage = p.best_matchup ? `covers ${p.best_matchup}` : '';
    html += `<div class="tt-lineup-row${isSit ? ' tt-lineup-sit' : ''}">
      <span class="tt-lineup-rank">${isSit ? '\uD83E\uDE91' : rank}</span>
      <span style="flex-shrink:0">${p.deck ? deckImg(p.deck, 28) : ''}</span>
      <div class="tt-lineup-info">
        <div class="tt-lineup-name">${p.name}${isSit ? ' <span style="font-size:0.75em;color:var(--red);font-weight:400">bench</span>' : ''}</div>
        <div class="tt-lineup-detail">${p.deck || '?'}${bestCoverage ? ' &mdash; <span class="tt-lineup-coverage-tag">' + bestCoverage + '</span>' : ''}</div>
      </div>
      <span class="tt-lineup-wr" style="color:${wrColor(p.wr)}">${p.wr}%</span>
    </div>`;
  });
  html += '</div></div>';

  // ── WR Heatmap (full, collapsed by default) ──
  const allOpps = new Set();
  players.forEach(p => Object.keys(p.matchups || {}).forEach(o => allOpps.add(o)));
  const opps = [...allOpps].sort();
  if (opps.length) {
    html += `<div class="tt-collapsible" id="tt-hm-coll">
      <button class="tt-coll-head" onclick="ttToggleSection('tt-hm-coll')">
        <span class="tt-coll-title">\uD83D\uDCCA Full WR Heatmap</span>
        <span class="tt-coll-chevron">\u25BC</span>
      </button>
      <div class="tt-coll-body"><div class="tt-heatmap"><table><thead><tr><th></th>`;
    opps.forEach(o => html += `<th>${deckImg(o, 20)}<br><span style="font-size:0.68em;opacity:0.7">${o}</span></th>`);
    html += '</tr></thead><tbody>';
    players.forEach(p => {
      html += `<tr><td class="tt-hm-name">${p.name}</td>`;
      opps.forEach(o => {
        const mu = (p.matchups || {})[o];
        if (!mu || mu.games === 0) { html += '<td style="color:var(--text2);background:rgba(255,255,255,0.01)">\u2014</td>'; }
        else {
          const bg = ttHeatmapCellBg(mu.wr);
          const color = mu.wr >= 55 ? 'var(--green)' : mu.wr <= 45 ? 'var(--red)' : 'var(--text)';
          html += `<td style="background:${bg};color:${color}" title="${mu.w}W ${mu.l}L (${mu.games}g)">${mu.wr}%</td>`;
        }
      });
      html += '</tr>';
    });
    html += '</tbody></table></div></div></div>';
  }

  // ── Board Lab ──
  html += `<div class="tab-section-hdr" style="margin-top:var(--sp-5)">
    <span class="tab-section-hdr__eyebrow">Board Lab</span>
    <span class="tab-section-hdr__title">Replay viewer &middot; game-by-game analysis</span>
  </div>`;
  html += `<div class="tt-collapsible open" id="tt-lab-coll">
    <button class="tt-coll-head" onclick="ttToggleSection('tt-lab-coll')">
      <span class="tt-coll-title">\uD83E\uDDEA Board Lab</span>
      <span class="tt-coll-chevron">\u25BC</span>
    </button>
    <div class="tt-coll-body"><div id="tc-container"></div></div>
  </div>`;

  html += '</div>'; // .tt-layout

  // ── Inbox side panel ──
  html += `<div class="tt-inbox-overlay" id="tt-inbox-overlay" onclick="ttToggleInbox()"></div>
  <div class="tt-inbox-panel" id="tt-inbox-panel">
    <div class="tt-inbox-head">
      <span class="tt-inbox-title">${bellSvg} Coaching Inbox <span style="font-size:0.7em;color:var(--text2);font-weight:400">${totalAlerts} alert${totalAlerts !== 1 ? 's' : ''}</span></span>
      <button class="tt-inbox-close" onclick="ttToggleInbox()">&times;</button>
    </div>
    <div class="tt-inbox-list">`;
  if (allAlerts.length) {
    allAlerts.sort((a, b) => (a.type === 'danger' ? 0 : 1) - (b.type === 'danger' ? 0 : 1));
    allAlerts.forEach(a => {
      const s = ttSevConfig(a.type);
      const tag = a.isTeam ? 'TEAM' : a.player;
      html += `<div class="tt-inbox-item">
        <div class="tt-sev-icon ${s.cls}">${s.icon}</div>
        <div style="flex:1;min-width:0">
          <span class="tt-inbox-player-tag">${tag}</span>
          <div class="tt-inbox-msg">${a.msg}${a.players ? ` (${a.players.join(', ')})` : ''}</div>
        </div>
      </div>`;
    });
  } else {
    html += `<div style="padding:40px 20px;text-align:center;color:var(--text2)">
      <div style="font-size:2em;margin-bottom:8px">\u2705</div>
      <div style="font-weight:600;margin-bottom:4px">All clear</div>
      <div style="font-size:0.85em">No alerts. Team is performing well.</div>
    </div>`;
  }
  html += '</div></div>';

  // V3-5 22/04: IWD inline accordion (lazy load on expand).
  const iwdSection = (typeof buildProToolsIWDSection === 'function') ? buildProToolsIWDSection() : '';

  main.innerHTML = buildProToolsHeader() + html + iwdSection;

  // Init Board Lab
  if (typeof tcInit === 'function') {
    tcInit('tc-container');
  }
}

// ── Archive helpers (kept for backward compat) ──
function ttArchiveAlert(alertId) {
  const arr = JSON.parse(localStorage.getItem('tt_archived_alerts') || '[]');
  if (!arr.includes(alertId)) arr.push(alertId);
  localStorage.setItem('tt_archived_alerts', JSON.stringify(arr));
  renderTeamTab(document.getElementById('main-content'));
}

