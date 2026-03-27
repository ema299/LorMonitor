/**
 * Lorcana Monitor — SPA app logic.
 */

// State
let currentTab = 'monitor';
let currentFormat = 'core';
let currentDays = 7;
let coachOur = null;
let coachOpp = null;

// Charts registry (for cleanup)
const charts = {};
function destroyChart(id) { if (charts[id]) { charts[id].destroy(); delete charts[id]; } }

// --- Tab routing ---

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    currentTab = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
    document.getElementById('tab-' + currentTab).classList.add('active');
    loadTab();
  });
});

document.getElementById('format-select').addEventListener('change', e => {
  currentFormat = e.target.value;
  loadTab();
});
document.getElementById('days-select').addEventListener('change', e => {
  currentDays = parseInt(e.target.value);
  loadTab();
});

function loadTab() {
  if (currentTab === 'monitor') loadMonitor();
  else if (currentTab === 'coach') loadCoach();
  else if (currentTab === 'lab') loadLab();
}

// --- KPI Bar ---

async function loadKPI() {
  try {
    const h = await API.health();
    const bar = document.getElementById('kpi-bar');
    bar.innerHTML = `
      <span>Match: <b class="val">${h.tables.matches.toLocaleString()}</b></span>
      <span>Curves: <b class="val">${h.tables.killer_curves}</b></span>
      <span>Status: <b class="val" style="color:var(--green)">${h.status}</b></span>
    `;
  } catch (e) { console.error('KPI error', e); }
}

// =====================
// MONITOR TAB
// =====================

async function loadMonitor() {
  const el = document.getElementById('tab-monitor');
  el.innerHTML = '<div class="loading">Caricamento</div>';

  try {
    const [meta, matrix, trend, leaders] = await Promise.all([
      API.meta(currentFormat, currentDays),
      API.matrix(currentFormat, null, currentDays),
      API.trend(currentFormat, Math.min(currentDays, 7)),
      API.leaderboard(currentFormat, currentDays, 30),
    ]);

    el.innerHTML = '';

    // Meta share + WR
    const metaCard = document.createElement('div');
    metaCard.className = 'grid-2';
    metaCard.innerHTML = `
      <div class="card">
        <h2>Meta Share</h2>
        <div class="chart-wrap"><canvas id="chart-meta"></canvas></div>
      </div>
      <div class="card">
        <h2>Win Rate per Deck</h2>
        <div id="wr-list"></div>
      </div>
    `;
    el.appendChild(metaCard);
    renderMetaChart(meta);
    renderWRList(meta);

    // Matchup matrix
    const matrixCard = document.createElement('div');
    matrixCard.className = 'card';
    matrixCard.innerHTML = '<h2>Matchup Matrix</h2><div id="matrix-wrap"></div>';
    el.appendChild(matrixCard);
    renderMatrix(matrix, meta);

    // Trend
    const trendCard = document.createElement('div');
    trendCard.className = 'card';
    trendCard.innerHTML = '<h2>Trend</h2><div class="chart-wrap"><canvas id="chart-trend"></canvas></div>';
    el.appendChild(trendCard);
    renderTrendChart(trend, meta);

    // Leaderboard
    const lbCard = document.createElement('div');
    lbCard.className = 'card';
    lbCard.innerHTML = '<h2>Leaderboard</h2><div id="lb-wrap"></div>';
    el.appendChild(lbCard);
    renderLeaderboard(leaders);

  } catch (e) {
    el.innerHTML = `<div class="card"><p style="color:var(--red)">Errore: ${e.message}</p></div>`;
  }
}

function renderMetaChart(meta) {
  destroyChart('meta');
  const ctx = document.getElementById('chart-meta');
  if (!ctx) return;
  const top8 = meta.slice(0, 8);
  const rest = meta.slice(8);
  const labels = top8.map(d => d.deck);
  const data = top8.map(d => d.meta_share);
  const colors = top8.map(d => {
    const inks = DECK_INKS[d.deck] || [];
    return INK_COLORS[inks[0]] || '#666';
  });
  if (rest.length) {
    labels.push('Others');
    data.push(rest.reduce((s, d) => s + d.meta_share, 0));
    colors.push('#444');
  }
  charts['meta'] = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'right', labels: { color: '#E6EDF3', font: { size: 11 }, padding: 8 } },
      },
    },
  });
}

function renderWRList(meta) {
  const el = document.getElementById('wr-list');
  if (!el) return;
  el.innerHTML = meta.map(d => `
    <div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--border)">
      <span style="width:60px">${inkDots(d.deck)} ${d.deck}</span>
      <div style="flex:1;background:var(--bg3);border-radius:3px;height:18px;position:relative">
        <div style="width:${Math.max(d.wr, 5)}%;height:100%;background:${wrColor(d.wr)};border-radius:3px;opacity:0.7"></div>
      </div>
      <span class="${wrClass(d.wr)}" style="width:45px;text-align:right">${d.wr}%</span>
      <span style="color:var(--text2);font-size:0.75em;width:40px;text-align:right">${d.games}g</span>
    </div>
  `).join('');
}

function renderMatrix(matrix, meta) {
  const el = document.getElementById('matrix-wrap');
  if (!el) return;
  const decks = meta.map(d => d.deck).filter(d => matrix[d]);
  if (!decks.length) { el.innerHTML = '<p style="color:var(--text2)">Nessun dato</p>'; return; }

  let html = '<table class="matrix-table"><tr><th></th>';
  decks.forEach(d => { html += `<th>${d}</th>`; });
  html += '</tr>';
  decks.forEach(our => {
    html += `<tr><td style="font-weight:600">${inkDots(our)} ${our}</td>`;
    decks.forEach(opp => {
      if (our === opp) { html += '<td style="color:var(--text2)">-</td>'; return; }
      const m = (matrix[our] || {})[opp];
      if (!m || !m.games) { html += '<td style="color:var(--text2)">-</td>'; return; }
      html += `<td><span class="matrix-cell" style="background:${wrColor(m.wr)}22;color:${wrColor(m.wr)}">${m.wr}%</span></td>`;
    });
    html += '</tr>';
  });
  html += '</table>';
  el.innerHTML = html;
}

function renderTrendChart(trend, meta) {
  destroyChart('trend');
  const ctx = document.getElementById('chart-trend');
  if (!ctx) return;
  const days = Object.keys(trend).sort();
  const topDecks = meta.slice(0, 6).map(d => d.deck);
  const datasets = topDecks.map(deck => {
    const inks = DECK_INKS[deck] || [];
    return {
      label: deck,
      data: days.map(day => (trend[day] || {})[deck] ? trend[day][deck].wr : null),
      borderColor: INK_COLORS[inks[0]] || '#666',
      backgroundColor: 'transparent',
      tension: 0.3,
      pointRadius: 3,
      spanGaps: true,
    };
  });
  charts['trend'] = new Chart(ctx, {
    type: 'line',
    data: { labels: days.map(d => d.slice(5)), datasets },
    options: {
      responsive: true,
      scales: {
        y: { min: 35, max: 65, ticks: { color: '#9BA4AE', callback: v => v + '%' }, grid: { color: '#21262D' } },
        x: { ticks: { color: '#9BA4AE' }, grid: { color: '#21262D' } },
      },
      plugins: { legend: { labels: { color: '#E6EDF3', font: { size: 11 } } } },
    },
  });
}

function renderLeaderboard(leaders) {
  const el = document.getElementById('lb-wrap');
  if (!el) return;
  el.innerHTML = `<table>
    <tr><th>#</th><th>Player</th><th>Deck</th><th>MMR</th><th>WR</th><th>Games</th></tr>
    ${leaders.map(p => `
      <tr>
        <td>${p.rank}</td>
        <td style="font-weight:600">${p.player}</td>
        <td>${inkDots(p.main_deck)} ${p.main_deck}</td>
        <td>${p.mmr}</td>
        <td class="${wrClass(p.wr)}">${p.wr}%</td>
        <td style="color:var(--text2)">${p.games}</td>
      </tr>
    `).join('')}
  </table>`;
}

// =====================
// COACH TAB
// =====================

async function loadCoach() {
  const el = document.getElementById('tab-coach');

  // Deck picker
  const decks = Object.keys(DECK_INKS);
  el.innerHTML = `
    <div class="card">
      <h2>Seleziona Matchup</h2>
      <div style="margin-bottom:8px"><label style="color:var(--text2);font-size:0.8em">IL TUO DECK</label></div>
      <div class="matchup-picker" id="pick-our">
        ${decks.map(d => `<button class="deck-btn" data-deck="${d}">${inkDots(d)} ${d}</button>`).join('')}
      </div>
      <div style="margin-bottom:8px"><label style="color:var(--text2);font-size:0.8em">AVVERSARIO</label></div>
      <div class="matchup-picker" id="pick-opp">
        ${decks.map(d => `<button class="deck-btn" data-deck="${d}">${inkDots(d)} ${d}</button>`).join('')}
      </div>
    </div>
    <div id="coach-content"></div>
  `;

  document.querySelectorAll('#pick-our .deck-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#pick-our .deck-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      coachOur = btn.dataset.deck;
      if (coachOur && coachOpp) loadMatchupDetail();
    });
  });
  document.querySelectorAll('#pick-opp .deck-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#pick-opp .deck-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      coachOpp = btn.dataset.deck;
      if (coachOur && coachOpp) loadMatchupDetail();
    });
  });
}

async function loadMatchupDetail() {
  const el = document.getElementById('coach-content');
  el.innerHTML = '<div class="loading">Caricamento matchup</div>';

  try {
    const [detail, curves] = await Promise.allSettled([
      API.matchup(coachOur, coachOpp, currentFormat, currentDays),
      API.killerCurves(coachOur, coachOpp, currentFormat),
    ]);

    let html = '';

    // KPI strip
    if (detail.status === 'fulfilled') {
      const d = detail.value;
      html += `<div class="card">
        <h2>${inkDots(coachOur)} ${coachOur} vs ${inkDots(coachOpp)} ${coachOpp}</h2>
        <div class="kpi-strip">
          <div class="kpi-box"><div class="kpi-val ${wrClass(d.wr)}">${d.wr}%</div><div class="kpi-label">Win Rate</div></div>
          <div class="kpi-box"><div class="kpi-val">${d.games}</div><div class="kpi-label">Games</div></div>
          <div class="kpi-box"><div class="kpi-val">${d.wins}-${d.losses}</div><div class="kpi-label">W-L</div></div>
          <div class="kpi-box"><div class="kpi-val">${d.avg_turns}</div><div class="kpi-label">Avg Turns</div></div>
          <div class="kpi-box"><div class="kpi-val">${d.fast_wins}</div><div class="kpi-label">Fast Wins</div></div>
          <div class="kpi-box"><div class="kpi-val">${d.fast_losses}</div><div class="kpi-label">Fast Losses</div></div>
        </div>
      </div>`;
    } else {
      html += `<div class="card"><p style="color:var(--text2)">Nessun dato per questo matchup nei ${currentDays} giorni selezionati</p></div>`;
    }

    // Killer curves
    if (curves.status === 'fulfilled') {
      const c = curves.value;
      html += `<div class="card">
        <h2>Killer Curves</h2>
        <p style="color:var(--text2);font-size:0.8em;margin-bottom:12px">
          Basate su ${c.match_count} partite, ${c.loss_count} sconfitte | Generato: ${c.generated_at}
        </p>
        ${(c.curves || []).map(renderCurve).join('')}
      </div>`;
    }

    el.innerHTML = html || '<div class="card"><p style="color:var(--text2)">Nessun dato disponibile</p></div>';
  } catch (e) {
    el.innerHTML = `<div class="card"><p style="color:var(--red)">Errore: ${e.message}</p></div>`;
  }
}

function renderCurve(curve) {
  const freq = curve.frequency || {};
  const ct = curve.critical_turn || {};
  const seq = curve.sequence || {};
  const turns = Object.keys(seq).sort();

  return `
    <div class="threat-card">
      <h4>${curve.id || ''}. ${curve.name || 'Curve'}</h4>
      <div class="threat-meta">
        Tipo: ${curve.type || '?'} |
        Frequenza: ${freq.pct || '?'}% delle sconfitte (${freq.loss_count || '?'}/${freq.total_loss || '?'}) |
        Turno critico: ${ct.turn || '?'} (${ct.component || ''} ${ct.swing ? (ct.swing > 0 ? '+' : '') + ct.swing : ''})
      </div>
      ${curve.key_cards ? `<div style="margin-bottom:6px"><b style="font-size:0.8em;color:var(--text2)">Key cards:</b> ${curve.key_cards.join(', ')}</div>` : ''}
      ${turns.length ? `
        <div class="threat-seq">
          ${turns.map(t => {
            const turn = seq[t];
            const plays = (turn.plays || []).map(p => `${p.card} (${p.ink_cost})`).join(', ');
            return `<div><span class="turn-label">${t}:</span> ${plays || '-'} | Lore: ${turn.lore_this_turn || 0} (cum: ${turn.cumulative_lore || 0})</div>`;
          }).join('')}
        </div>
      ` : ''}
    </div>
  `;
}

// =====================
// LAB TAB
// =====================

async function loadLab() {
  const el = document.getElementById('tab-lab');
  el.innerHTML = `<div class="card">
    <h2>Lab</h2>
    <p style="color:var(--text2)">Card scores e analisi avanzate — seleziona un matchup nel tab Coach per attivare.</p>
    <p style="color:var(--text2);margin-top:8px">Funzionalita' in sviluppo: Mulligan Trainer, Card Impact, Deck Optimizer.</p>
  </div>`;
}

// =====================
// INIT
// =====================

loadKPI();
loadTab();
