// Winning cards + Opening hand impact accordions.
// Moved from Deck tab → Improve tab (Study section) on 2026-04-23.
// Deck tab now surfaces per-card stats inline via the tap sheet in deck_grid.js.
// These accordions still live for users who want the full ranked list.

window.V3 = window.V3 || {};
window.V3.CardAnalysis = {
  _buildWinningCardsBody(mu) {
    const cs = (mu && mu.card_scores) || {};
    const entries = Object.entries(cs)
      .filter(([, v]) => v && typeof v.delta === 'number')
      .sort((a, b) => b[1].delta - a[1].delta);
    if (!entries.length) return '<div class="lab-impact-empty" style="padding:16px;color:var(--text2);font-size:0.85em">No card-level data for this matchup yet.</div>';
    const maxDelta = Math.max(...entries.map(([, v]) => Math.abs(v.delta)), 0.01);
    let body = '<div class="lab-impact-list">';
    entries.slice(0, 24).forEach(([name, v]) => {
      const pct = Math.abs(v.delta) / maxDelta * 50;
      const cls = v.delta >= 0 ? 'pos' : 'neg';
      const val = (v.delta >= 0 ? '+' : '') + (v.delta * 100).toFixed(1) + '%';
      const shortName = name.length > 22 ? name.slice(0, 20) + '..' : name;
      body += `<div class="lab-impact-row">
        <span class="li-name">${shortName}</span>
        <div class="li-bar-wrap"><div class="li-bar-center"></div><div class="li-bar ${cls}" style="width:${pct}%"></div></div>
        <span class="li-val ${cls}">${val}</span>
      </div>`;
    });
    body += '</div>';
    return body;
  },

  buildSections() {
    const havePair = typeof coachDeck !== 'undefined' && coachDeck
      && typeof labOpp !== 'undefined' && labOpp
      && typeof getMatchupData === 'function';
    if (!havePair) {
      return `<div class="card" style="padding:16px;color:var(--text2);font-size:0.85em">
        Pick an opponent in the <strong>Deck</strong> tab to see per-card analysis for that matchup.
      </div>`;
    }
    const mu = getMatchupData(labOpp);
    if (!mu) return '';

    const winningBody = this._buildWinningCardsBody(mu);
    const winningAcc = (typeof monAccordion === 'function')
      ? monAccordion(
          'acc-ci-corr-improve',
          'Winning cards',
          'Cards that appear more often in your wins than in your losses.',
          winningBody,
          {
            desktopOpen: false,
            info: { title: 'About Winning Cards', body: '<p>For each card: how often it appears in <strong>winning</strong> vs <strong>losing</strong> games in this matchup.</p><p><code>delta = WR(games with card) - WR(games without)</code></p><p>This is a <strong>correlation</strong> signal. For a stronger causal signal, see <strong>Opening hand impact</strong> below.</p>' }
          }
        )
      : winningBody;

    const iwdAcc = (typeof monAccordion === 'function')
      ? monAccordion(
          'acc-iwd-improve',
          'Opening hand impact',
          'Cards whose early draw actually changes the outcome.',
          '<div class="iwd-wrap" id="iwd-wrap"></div>',
          {
            desktopOpen: false,
            onOpen: () => { if (typeof iwdLoad === 'function') iwdLoad(); },
            info: { title: 'About Opening Hand Impact', body: '<p>For each card: how does our winrate change when the card is seen in hand <strong>by turn 3</strong> vs when it is not?</p><p><code>delta = WR(drawn by T3) - WR(not drawn by T3)</code></p><p>Stronger signal than "Winning cards": this is <strong>causal</strong>, not just correlation. Also called <strong>IWD</strong> — Improvement When Drawn.</p>' }
          }
        )
      : '';

    return `<div class="section">${winningAcc}</div><div class="section">${iwdAcc}</div>`;
  },
};
