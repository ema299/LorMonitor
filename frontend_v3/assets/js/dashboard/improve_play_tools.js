// Mulligan Trainer + Replay Viewer mounted in the Improve tab.
// Reuses the existing builders from lab.js (buildMulliganTrainer, initMullCarousel)
// and team_coaching.js (buildReplayViewer, rvInit). The Play tab no longer renders
// these sections as of 2026-04-23.

window.V3 = window.V3 || {};
window.V3.ImprovePlayTools = {
  buildSections() {
    const havePair = typeof coachDeck !== 'undefined' && coachDeck
      && typeof coachOpp !== 'undefined' && coachOpp;
    if (!havePair) {
      return `<div class="card" style="padding:16px;color:var(--text2);font-size:0.85em">
        Pick a matchup in the <strong>Play</strong> tab to see Mulligan Trainer and Replay Viewer here.
      </div>`;
    }
    let html = '';
    if (typeof getMatchupData === 'function' && typeof buildMulliganTrainer === 'function') {
      const mu = getMatchupData(coachOpp);
      const proMulls = (mu && mu.pro_mulligans) || [];
      if (proMulls.length) html += buildMulliganTrainer(proMulls);
    }
    if (typeof buildReplayViewer === 'function') {
      html += buildReplayViewer(coachDeck, coachOpp);
    }
    return html;
  },

  init() {
    const havePair = typeof coachDeck !== 'undefined' && coachDeck
      && typeof coachOpp !== 'undefined' && coachOpp;
    if (!havePair) return;
    if (typeof initMullCarousel === 'function') {
      try { initMullCarousel(); } catch (e) { console.error('[Improve Mulligan] init:', e); }
    }
    if (typeof rvInit === 'function') {
      try { rvInit(coachDeck, coachOpp); } catch (e) { console.error('[Improve Replay] init:', e); }
    }
  },
};
