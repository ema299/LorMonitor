// === PRE-MATCH CHEATSHEET ===
function openCheatsheet() {
  const az = getAnalyzerData();
  const mu = getMatchupData(coachOpp);
  if (!mu || !coachOpp) return;

  const ov = mu.overview || {};
  const kc = mu.killer_curves || [];
  const tl = mu.threats_llm || {};
  const pb = mu.playbook || [];
  const threats = tl.threats || [];

  const points = [];

  // 1. WR + gap summary
  const wrNote = (ov.wr||0) >= 55 ? 'Favorable matchup' : (ov.wr||0) <= 45 ? 'Unfavorable matchup' : 'Even matchup';
  const gapNote = Math.abs(ov.gap||0) > 10 ? ` (${(ov.gap||0) > 0 ? 'much better OTP' : 'suffers OTD'})` : '';
  points.push({
    text: `<strong>${wrNote}</strong> — WR ${ov.wr||'?'}%, OTP ${ov.otp_wr||'?'}% vs OTD ${ov.otd_wr||'?'}%${gapNote}`,
    plain: `${wrNote} — WR ${ov.wr||'?'}%, OTP ${ov.otp_wr||'?'}% vs OTD ${ov.otd_wr||'?'}%${gapNote}`
  });

  // 2. Top threat (killer curve #1)
  if (kc.length > 0) {
    const top = kc[0];
    const seqKeys = Object.keys(top.sequence || {});
    const keyCards = (top.key_cards || []).slice(0, 3).join(', ');
    const critT = top.critical_turn?.turn || '?';
    points.push({
      text: `<strong>Minaccia #1: ${top.name}</strong> (${top.frequency?.pct||'?'}% loss) — critica a T${critT}<div class="cs-cards">Key cards: ${keyCards}</div>`,
      plain: `Minaccia #1: ${top.name} (${top.frequency?.pct||'?'}% loss) — critica a T${critT}. Key: ${keyCards}`
    });
  }

  // 3. Response for top threat
  if (kc.length > 0 && kc[0].response) {
    const resp = kc[0].response;
    const cards = (resp.cards || []).slice(0, 3).join(', ');
    const summary = kcResponseSummary(resp) || 'N/A';
    points.push({
      text: `<strong>Response:</strong> ${summary}${cards ? `<div class="cs-cards">Key cards: ${cards}</div>` : ''}`,
      plain: `Response: ${summary}${cards ? '. Key cards: ' + cards : ''}`
    });
  }

  // 4. Early turns plan (T1-T3 from playbook)
  const earlyPlays = pb.filter(t => {
    const n = parseInt((t.turn||'').replace(/\D/g,'') || '99');
    return n >= 1 && n <= 3;
  }).map(t => {
    const topPlay = (t.plays || []).slice(0, 2).map(p => p.card).join(' / ');
    return `${t.turn}: ${topPlay || '—'}`;
  });
  if (earlyPlays.length > 0) {
    points.push({
      text: `<strong>Key opponent openers:</strong><div class="cs-cards">${earlyPlays.join(' | ')}</div>`,
      plain: `Opponent openers: ${earlyPlays.join(' | ')}`
    });
  }

  // 5. Second threat or type summary
  if (kc.length > 1) {
    const t2 = kc[1];
    const t2Summary = kcResponseSummary(t2.response || {});
    points.push({
      text: `<strong>Minaccia #2: ${t2.name}</strong> (${t2.frequency?.pct||'?'}% loss)${t2Summary ? ' — ' + t2Summary : ''}`,
      plain: `Minaccia #2: ${t2.name} (${t2.frequency?.pct||'?'}% loss)${t2Summary ? ' — ' + t2Summary : ''}`
    });
  } else if (tl.type_summary) {
    points.push({
      text: `<strong>Tipo matchup:</strong> ${tl.type_summary}`,
      plain: `Tipo matchup: ${tl.type_summary}`
    });
  }

  // Build HTML
  let html = `<div class="cheatsheet-matchup">${deckImg(coachDeck,32)} vs ${deckImg(coachOpp,32)} &mdash; ${(ov.wins||0)+(ov.losses||0)} matches analyzed</div>`;
  points.forEach((p, i) => {
    html += `<div class="cs-point"><div class="cs-num">${i+1}</div><div class="cs-text">${p.text}</div></div>`;
  });

  // Copy text
  const copyText = `PRE-MATCH: ${coachDeck} vs ${coachOpp}\n` + points.map((p,i) => `${i+1}. ${p.plain}`).join('\n');

  html += `<div class="cs-actions">
    <button class="cs-btn-copy" onclick="navigator.clipboard.writeText(\`${copyText.replace(/`/g,"'").replace(/\\/g,'\\\\')}\`);this.textContent='Copied!';">Copy to Discord</button>
    <button class="cs-btn-dismiss" onclick="closeCheatsheet()">Close</button>
  </div>`;

  document.getElementById('cheatsheet-body').innerHTML = html;
  document.getElementById('cheatsheet-overlay').classList.add('visible');
  document.body.style.overflow = 'hidden';
}

function closeCheatsheet() {
  document.getElementById('cheatsheet-overlay').classList.remove('visible');
  document.body.style.overflow = '';
}

// === EVENTS ===
// Tab switching (V3-4: skip .tab-more che apre il drawer, non e' un tab vero)
document.querySelectorAll('.tab:not(.tab-more)').forEach(tab => {
  if (!tab.dataset.tab) return;
  tab.addEventListener('click', () => {
    switchToTab(tab.dataset.tab);
  });
});

// Bottom nav (mobile) — mirrors top tabs. Skip il bottone "More" (triggera drawer)
document.querySelectorAll('.bnav-btn:not(.bnav-btn--more)').forEach(btn => {
  if (!btn.dataset.tab) return;
  btn.addEventListener('click', () => {
    btn.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    switchToTab(btn.dataset.tab);
  });
});

// Keep bottom nav in sync when top tabs are clicked
document.querySelectorAll('.tab:not(.tab-more)').forEach(tab => {
  if (!tab.dataset.tab) return;
  tab.addEventListener('click', () => {
    document.querySelectorAll('.bnav-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.tab === tab.dataset.tab);
    });
  });
});

// Perimeter buttons are now managed by syncPerimButtons()

// Format switch events
document.querySelectorAll('.format-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.disabled) return;
    setFormat(btn.dataset.format);
  });
});

// === COMMUNITY TAB ===
let commActiveFilter = 'all';
window.commArchiveFilter = '';

const COMMUNITY_CONFIG = {
  live: {
    isLive: false,
    platform: 'youtube',
    channelId: '',
    videoId: null,
    title: '',
    channel: 'Lorcana Monitor Italia',
  },
  schedule: [
    { date: '2026-04-02T20:00', title: 'Weekly Meta Analysis — Set 11 Deep Dive', channel: 'Lorcana Monitor' },
    { date: '2026-04-05T18:00', title: 'Killer Curves Explained: Amber-Steel', channel: 'Lorcana Monitor' },
    { date: '2026-04-09T20:00', title: 'Pro Player Interview — Top 30 Secrets', channel: 'Lorcana Monitor' },
  ],
  clips: [
    { id: 'demo1', platform: 'youtube', title: 'Understanding Killer Curves', duration: '8:12', tags: ['beginner'], author: 'Lorcana Monitor', coachLink: null },
    { id: 'demo2', platform: 'youtube', title: 'Amber-Steel vs Amethyst-Sapphire Breakdown', duration: '11:34', tags: ['AbSt', 'intermediate'], author: 'Lorcana Monitor', coachLink: { deck: 'AbSt', opp: 'AmSa' } },
    { id: 'demo3', platform: 'youtube', title: 'Mulligan Strategy for Beginners', duration: '6:45', tags: ['beginner'], author: 'Lorcana Monitor', coachLink: null },
    { id: 'demo4', platform: 'youtube', title: 'Emerald-Sapphire: When to Ramp vs Rush', duration: '9:20', tags: ['EmSa', 'advanced'], author: 'Lorcana Monitor', coachLink: { deck: 'EmSa', opp: 'AbSt' } },
    { id: 'demo5', platform: 'youtube', title: 'Reading the Board State — Turn 4 Decisions', duration: '7:55', tags: ['intermediate'], author: 'Lorcana Monitor', coachLink: null },
    { id: 'demo6', platform: 'youtube', title: 'Amethyst-Amethyst Combo Lines', duration: '10:18', tags: ['AmAm', 'advanced'], author: 'Lorcana Monitor', coachLink: { deck: 'AmAm', opp: 'EmSa' } },
  ],
  archive: [
    { id: 'vod1', platform: 'youtube', title: 'Full Stream — March Meta Recap', date: '2026-03-28', topics: ['AmAm','EmSa'], duration: '1:34:20' },
    { id: 'vod2', platform: 'youtube', title: 'Community Tournament Coverage', date: '2026-03-25', topics: ['AbSt','AmSa'], duration: '2:12:05' },
  ]
};

// === GUIDED TOUR ===
// Steps comuni (header/tabs/format) + steps per-tab
const TOUR_COMMON = [
  {
    target: '.header',
    title: 'Welcome!',
    body: 'This is your Lorcana dashboard. From here you monitor the meta, prepare matchups and train your team. Click Next to explore the sections of this tab.',
  },
  {
    target: '.tabs',
    title: 'Navigation',
    body: '8 specialized tabs. The tour explains the tab you are currently on. You can relaunch the Guide on every tab!',
  },
  {
    target: '.format-bar',
    title: 'Format and Ink',
    body: 'Pick Core or Infinity and your deck colors. Format and deck propagate to operational tabs; the scope is most relevant in the Monitor.',
  },
  {
    target: '.perimeter-bar',
    title: 'Data Scope',
    body: 'Filter the Monitor by competitive level: SET11 (high ELO), TOP 100, PRO 50, Friends or Community. Narrower = stronger data but smaller sample.',
  },
];

const TOUR_TAB_STEPS = {
  home: [
    { target: '.pf-hero-deck', title: 'Select Your Deck', body: 'The command center. Pick your deck by tapping 2 ink colors — deck and format propagate to the main tabs (Monitor, Coach, Lab). You can save up to 3 decks for quick access.' },
    { target: '.pf-ink-grid,.pf-hero-ink-row', title: 'Ink Picker', body: 'Tap 2 colors to select a deck. You can also import a custom decklist with the "My Deck" toggle.' },
    { target: '.pf-saved-decks-section', title: 'Saved Decks', body: 'Your saved decks. Click to switch quickly. You can pin a deck after selecting it with the inks.' },
    { target: '.pf-my-stats-section', title: 'Player lookup', body: 'Public player stats for the linked nickname over the last 3 days: all decks played with WR and worst matchup. Add a nickname in Settings to populate.' },
    { target: '.pf-hero-radar', title: 'Meta Radar', body: 'Overall deck stats in the meta: WR, share, games. Below: best/worst matchups and threats to watch.' },
    { target: '.pf-tech-flow', title: 'Non-Standard Picks', body: 'Cards outside the consensus list used by winning players (WR 52%+). Merged from PRO, TOP and Community with adoption % and confidence.' },
  ],
  meta: [
    { target: '#fit-strip', title: 'Deck Fitness', body: '0-100 score per deck, weighted by the current meta (50 = break-even). Scroll to see the full ranking.' },
    { target: '#mm-wrap', title: 'Matchup Matrix', body: 'Winrate for every deck pair. Desktop: NxN heatmap. Mobile: opponents list for the selected deck. Click any cell to open it in Coach.' },
    { target: '#deck-body', title: 'Deck Analysis', body: 'Selected deck in detail: identity card, matchup WR, OTP vs OTD gap chart.' },
    { target: '#players-body', title: 'Best Format Players', body: 'Top players from the duels.ink leaderboard. Only players in the top 100 (TOP) or top 50 (PRO) for the format.' },
    { target: '#tech-tornado-box', title: 'Non-Standard Picks', body: 'Cards added or cut from the consensus list by winning players. Green = high WR, red = low WR. Max 4+4.' },
  ],
  play: [
    { target: '.cv2-strip', title: 'Matchup KPI', body: 'Overall win rate, OTP/OTD split and gap. Specific numbers for the selected matchup above.' },
    { target: '.cv2-threat', title: 'Threats', body: 'The most dangerous opponent sequences, turn by turn. Expand to see cards, tactical responses and timeline.' },
    { target: '.cv2-columns', title: 'Killer Cards + Playbook', body: 'On the left, the opponent\'s killer cards. On the right, the turn-by-turn playbook with optimal responses.' },
    { target: '.rv-wrap', title: 'Replay Viewer', body: 'Rewatch real matches from this matchup. Visual board with cards, play/pause, W/L and OTP/OTD filters.' },
  ],
  deck: [
    { target: '.lab-left', title: 'Mulligan Trainer', body: 'Real opening hands from PROs. Filter blind/OTP/OTD, reveal to see if they kept or mulliganed and how it ended.' },
    { target: '.lab-impact-list', title: 'Card Impact', body: 'Divergent chart: how each card correlates with victory (green) or loss (red). Top 24 cards by impact.' },
    { target: '.lab-right', title: 'Optimized Decklist', body: 'Deck calibrated for this matchup with mana curve, add/cut badges and copy button to import in-game.' },
  ],
  improve: [
    { target: '.pf-header', title: 'Profile', body: 'Local preferences plus the public player lookup driven by the linked nickname.' },
    { target: '.pf-my-stats-section', title: 'Player lookup', body: 'Detailed lookup of the linked nickname\'s recent matches and decks.' },
    { target: '#pf-blind-playbook-host-improve,.bp-row', title: 'Study Review', body: 'Blind playbook and personal reviews are the core of the Improve tab.' },
  ],
  team: [
    { target: '.tt-strip', title: 'Team KPI', body: 'Quick overview: player count, average WR, total games and trend. The bell shows active alerts.' },
    { target: '.tt-cards-grid', title: 'Player Cards', body: 'Each player with WR, deck, 7d trend sparkline. Click to expand: stats, alerts, matchups and focus areas.' },
    { target: '#tt-cov-coll', title: 'Meta Coverage', body: 'Player x matchup heatmap. Cells colored by WR. "Gaps" (no one above 50%) are highlighted in red.' },
    { target: '#tt-lab-coll', title: 'Board Lab', body: 'Coaching tool: upload replay .gz from duels.ink, rewatch the match with visible hand and analyze the plays.' },
  ],
  community: [
    { target: '.comm-live-embed-wrap', title: 'Live Stream', body: 'YouTube/Twitch embed of the creator going live. Activates automatically when someone is streaming.' },
    { target: '.comm-clip-grid', title: 'Clip Highlights', body: 'The best moments from the community. Filterable by tag (combo, misplay, clutch). Click to play inline.' },
    { target: '.comm-archive-filter-row', title: 'VOD Archive', body: 'All past videos organized by topic. Filter by topic to find specific analyses.' },
  ],
  events: [
    { target: '.ev-filter-bar,.events-filter-bar', title: 'Event Filters', body: 'Format, distance from your location, text search. By default shows events within 100km of you.' },
    { target: '#ev-minimap,.events-map-pane', title: 'Store Map', body: 'Map of the stores that run tournaments. Click a pin to see details and sign up.' },
    { target: '.ev-grid,.events-list', title: 'Event List', body: 'All upcoming tournaments. Each card has date, format, store, cost and a Register button to sign up on Ravensburger.' },
  ],
};

let tourSteps = [];
let tourStep = 0;
let tourActive = false;
let tourOverlay = null;
let tourSpotlight = null;
let tourTooltip = null;

function tourGetActiveTab() {
  const active = document.querySelector('.tab.active');
  return active ? active.dataset.tab : 'home';
}

function tourStart() {
  const tab = tourGetActiveTab();
  const tabSteps = TOUR_TAB_STEPS[tab] || [];
  tourSteps = [...TOUR_COMMON, ...tabSteps];
  tourStep = 0;
  tourActive = true;
  if (!tourOverlay) {
    tourOverlay = document.createElement('div');
    tourOverlay.className = 'tour-overlay';
    tourOverlay.onclick = () => tourEnd();
    document.body.appendChild(tourOverlay);
  }
  if (!tourSpotlight) {
    tourSpotlight = document.createElement('div');
    tourSpotlight.className = 'tour-spotlight';
    document.body.appendChild(tourSpotlight);
  }
  if (!tourTooltip) {
    tourTooltip = document.createElement('div');
    tourTooltip.className = 'tour-tooltip';
    document.body.appendChild(tourTooltip);
  }
  tourOverlay.style.display = '';
  tourSpotlight.style.display = '';
  tourTooltip.style.display = '';
  tourShow(0);
}

function tourEnd() {
  tourActive = false;
  if (tourOverlay) tourOverlay.style.display = 'none';
  if (tourSpotlight) tourSpotlight.style.display = 'none';
  if (tourTooltip) tourTooltip.style.display = 'none';
}

function tourShow(idx) {
  if (idx < 0 || idx >= tourSteps.length) { tourEnd(); return; }
  tourStep = idx;
  const step = tourSteps[idx];
  requestAnimationFrame(() => {
    // Support comma-separated selectors (fallback)
    let el = null;
    for (const sel of step.target.split(',')) {
      el = document.querySelector(sel.trim());
      if (el) break;
    }
    if (!el) {
      if (idx < tourSteps.length - 1) tourShow(idx + 1);
      else tourEnd();
      return;
    }
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    setTimeout(() => tourPosition(el, step, idx), 180);
  });
}

function tourPosition(el, step, idx) {
  const rect = el.getBoundingClientRect();
  const pad = 6;
  tourSpotlight.style.left = (rect.left - pad + window.scrollX) + 'px';
  tourSpotlight.style.top = (rect.top - pad + window.scrollY) + 'px';
  tourSpotlight.style.width = (rect.width + pad * 2) + 'px';
  tourSpotlight.style.height = (rect.height + pad * 2) + 'px';
  const dots = tourSteps.map((_, i) =>
    `<div class="tour-dot${i === idx ? ' active' : ''}"></div>`
  ).join('');
  const isFirst = idx === 0;
  const isLast = idx === tourSteps.length - 1;
  tourTooltip.innerHTML = `
    <div class="tour-tooltip-title">
      ${step.title}
      <span class="tour-step-num">${idx + 1}/${tourSteps.length}</span>
    </div>
    <div class="tour-tooltip-body">${step.body}</div>
    <div class="tour-tooltip-footer">
      <div class="tour-dots">${dots}</div>
      <div class="tour-btns">
        <button class="tour-btn-skip" onclick="tourEnd()">Close</button>
        ${!isFirst ? `<button class="tour-btn" onclick="tourShow(${idx - 1})">Back</button>` : ''}
        ${isLast
          ? `<button class="tour-btn tour-btn-primary" onclick="tourEnd()">Done!</button>`
          : `<button class="tour-btn tour-btn-primary" onclick="tourShow(${idx + 1})">Next</button>`
        }
      </div>
    </div>`;
  const ttW = 320;
  let ttLeft = rect.left + rect.width / 2 - ttW / 2;
  ttLeft = Math.max(12, Math.min(ttLeft, window.innerWidth - ttW - 12));
  const spaceBelow = window.innerHeight - rect.bottom;
  let ttTop;
  if (spaceBelow > 180) {
    ttTop = rect.bottom + 14 + window.scrollY;
  } else {
    ttTop = rect.top - 14 + window.scrollY;
    requestAnimationFrame(() => {
      const ttRect = tourTooltip.getBoundingClientRect();
      tourTooltip.style.top = (rect.top - ttRect.height - 14 + window.scrollY) + 'px';
    });
  }
  tourTooltip.style.left = ttLeft + 'px';
  tourTooltip.style.top = ttTop + 'px';
}

document.addEventListener('keydown', e => {
  if (!tourActive) return;
  if (e.key === 'Escape') tourEnd();
  if (e.key === 'ArrowRight' || e.key === 'Enter') tourShow(tourStep + 1);
  if (e.key === 'ArrowLeft') tourShow(tourStep - 1);
});

// === SCROLL-TO-HIDE BOTTOM NAV (mobile only) ===
// Hides the bottom nav when scrolling down, reveals on scroll up.
// Follows Instagram/YouTube pattern. Only active when bottom nav is visible (≤768px).
(function initScrollHideNav() {
  const nav = document.querySelector('.bottom-nav');
  if (!nav) return;
  let lastY = 0;
  let ticking = false;
  const THRESHOLD = 8;

  function onScroll() {
    if (!ticking) {
      window.requestAnimationFrame(function () {
        if (window.innerWidth > 768) { nav.classList.remove('nav-hidden'); ticking = false; return; }
        const y = window.scrollY;
        if (y > lastY + THRESHOLD) {
          nav.classList.add('nav-hidden');
        } else if (y < lastY - THRESHOLD) {
          nav.classList.remove('nav-hidden');
        }
        lastY = y;
        ticking = false;
      });
      ticking = true;
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });

  // Always show nav on tab switch (user just navigated, show the nav)
  const origSwitch2 = window.switchToTab;
  if (typeof origSwitch2 === 'function') {
    window.switchToTab = function (tabId, opts) {
      nav.classList.remove('nav-hidden');
      origSwitch2(tabId, opts);
    };
  }
})();

// === INIT ===
loadData();
