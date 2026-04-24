// Killer Curve Response Check.
// For the currently-selected opponent, checks how many "answer cards" the
// user's deck holds against each of the opponent's top killer curves.
// Data source: mu.killer_curves[].response.cards[] (backend-provided).
// Scope: read-only for now — will become dynamic when builder mode lands (B3).

window.V3 = window.V3 || {};
window.V3.ResponseCheck = {
  // Thresholds for the traffic-light status per curve.
  // Counts are in "copies" (sum of qty across all cards that are listed as answers).
  GREEN_MIN: 3,
  YELLOW_MIN: 1,

  // Normalize a card name for matching: strips version suffix " - Subtitle",
  // lowercases, trims whitespace. Lets us match "Mickey Mouse" to
  // "Mickey Mouse - Brave Little Tailor" entries.
  _normalize(name) {
    if (!name) return '';
    const raw = String(name).trim();
    const base = raw.includes(' - ') ? raw.split(' - ')[0] : raw;
    return base.toLowerCase();
  },

  _deckCardMap(deckCode, mu) {
    if (!(window.V3 && window.V3.DeckGrid)) return {};
    const cards = window.V3.DeckGrid._resolveCards(deckCode, mu);
    const map = {};
    cards.forEach(c => {
      const k = this._normalize(c.card);
      if (!k) return;
      map[k] = (map[k] || 0) + (c.qty || 0);
    });
    return map;
  },

  _coverageForCurve(curve, deckMap) {
    const answers = (curve && curve.response && Array.isArray(curve.response.cards))
      ? curve.response.cards
      : [];
    let copies = 0;
    const present = [];
    const missing = [];
    answers.forEach(cardName => {
      const key = this._normalize(cardName);
      const qty = deckMap[key] || 0;
      if (qty > 0) {
        copies += qty;
        present.push({ name: cardName, qty });
      } else {
        missing.push(cardName);
      }
    });
    let status = 'red';
    if (copies >= this.GREEN_MIN) status = 'green';
    else if (copies >= this.YELLOW_MIN) status = 'yellow';
    return { status, copies, present, missing, totalAnswers: answers.length };
  },

  build(deckCode, opponentCode) {
    if (!deckCode) return '';
    if (!opponentCode) {
      return `<div class="rc-panel rc-panel--empty">
        <div class="rc-title">Response coverage</div>
        <div class="rc-empty">Pick an opponent above to see how your deck answers their killer curves.</div>
      </div>`;
    }
    const mu = (typeof getMatchupData === 'function') ? getMatchupData(opponentCode) : null;
    const curves = (mu && Array.isArray(mu.killer_curves)) ? mu.killer_curves : [];
    if (!curves.length) {
      return `<div class="rc-panel rc-panel--empty">
        <div class="rc-title">Response coverage</div>
        <div class="rc-empty">No killer curves available for this matchup yet.</div>
      </div>`;
    }

    const deckMap = this._deckCardMap(deckCode, mu);
    const sorted = curves.slice().sort((a, b) =>
      ((b.frequency && b.frequency.pct) || 0) - ((a.frequency && a.frequency.pct) || 0)
    );

    const rows = sorted.slice(0, 5).map(curve => {
      const cov = this._coverageForCurve(curve, deckMap);
      const cls = cov.status === 'green' ? 'rc-green'
                : cov.status === 'yellow' ? 'rc-yellow'
                : 'rc-red';
      const pct = (curve.frequency && curve.frequency.pct != null) ? Math.round(curve.frequency.pct) : null;
      const critTurn = curve.critical_turn && curve.critical_turn.turn ? `T${curve.critical_turn.turn}` : '';
      const name = curve.name || 'Unnamed curve';

      const presentHtml = cov.present.length
        ? cov.present.map(p => `<span class="rc-chip rc-chip--have">${p.qty}× ${p.name.split(' - ')[0]}</span>`).join('')
        : '';

      const missingHtml = cov.missing.length
        ? cov.missing.slice(0, 3).map(m => `<span class="rc-chip rc-chip--miss">+ ${m.split(' - ')[0]}</span>`).join('')
        : '';

      const coverageLabel = cov.totalAnswers === 0
        ? 'no listed answers'
        : `${cov.copies} cop${cov.copies === 1 ? 'y' : 'ies'} · ${cov.present.length}/${cov.totalAnswers} answer cards`;

      return `<div class="rc-row ${cls}">
        <div class="rc-dot"></div>
        <div class="rc-main">
          <div class="rc-head">
            <span class="rc-name">${name}</span>
            ${critTurn ? `<span class="rc-turn">${critTurn}</span>` : ''}
            ${pct != null ? `<span class="rc-freq">${pct}%</span>` : ''}
          </div>
          <div class="rc-cov">${coverageLabel}</div>
          ${(presentHtml || missingHtml) ? `<div class="rc-chips">${presentHtml}${missingHtml}</div>` : ''}
        </div>
      </div>`;
    }).join('');

    return `<div class="rc-panel">
      <div class="rc-title">Response coverage <small>vs ${opponentCode}</small></div>
      <div class="rc-rows">${rows}</div>
      <div class="rc-hint">🟢 ≥3 copies · 🟡 1-2 · 🔴 0 of the listed answer cards</div>
    </div>`;
  },
};
