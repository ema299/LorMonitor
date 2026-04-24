// Honesty badge utility — observed-sample confidence layer shared across Deck tab.
// Contract: docs/DECK_REFACTOR_PARITY.md Rule 1.
//   Every stat derived from archetype-level observed data must render as
//   "NN% on N observed games · Xd · {Low|Medium|High} confidence".
//
// Confidence threshold decision (DECK_REFACTOR_PARITY open question #2):
//   MIN_SAMPLE 30 is the canonical threshold for CARD-LEVEL signals across
//   the Deck tab (aligned with deck_grid.MIN_SAMPLE=30 for the status dot).
//   Monitor's _compute_fitness uses 15 because it aggregates across all
//   opponents — different measurement, kept intentionally separate.
//
// CSS selectors used (styled in PR2): .hb-badge, .hb-pct, .hb-conf,
//   .hb-low, .hb-med, .hb-high, .hb-heuristic.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const LOW_MAX = 30;   // N <  30           → Low confidence
  const MED_MAX = 100;  // 30 ≤ N < 100      → Medium confidence
                        // N ≥  100          → High confidence

  function confidenceLabel(sample) {
    if (sample == null || sample < LOW_MAX) return 'Low';
    if (sample < MED_MAX) return 'Medium';
    return 'High';
  }

  function confidenceClass(sample) {
    const lbl = confidenceLabel(sample);
    return lbl === 'Low' ? 'hb-low' : lbl === 'Medium' ? 'hb-med' : 'hb-high';
  }

  // No decimals below N=100 (DECK_REFACTOR_PARITY Rule 1 honesty table).
  function formatPct(value, sample) {
    if (value == null || !Number.isFinite(value)) return '—';
    return sample != null && sample >= MED_MAX
      ? value.toFixed(1) + '%'
      : Math.round(value) + '%';
  }

  function formatDelta(ppDelta, sample) {
    if (ppDelta == null || !Number.isFinite(ppDelta)) return '—';
    const abs = Math.abs(ppDelta);
    const sign = ppDelta >= 0 ? '+' : '−';
    const digits = sample != null && sample >= MED_MAX ? abs.toFixed(1) : Math.round(abs);
    return sign + digits + 'pp';
  }

  // Full inline badge: WR + "on N observed games · Xd · {label} confidence"
  function render(wrPct, sample, days, opts) {
    opts = opts || {};
    const cls = confidenceClass(sample);
    const label = confidenceLabel(sample);
    const pct = formatPct(wrPct, sample);
    const gamesPart = sample != null
      ? 'on ' + Number(sample).toLocaleString() + ' observed games'
      : 'no observed games';
    const daysPart = days ? ' · ' + days + 'd' : '';
    const confPart = ' · <span class="hb-conf ' + cls + '">' + label + ' confidence</span>';
    const prefix = opts.hidePct
      ? ''
      : '<span class="hb-pct">' + pct + '</span> ';
    const onclick = 'window.V3.HonestyBadge.openExplainer(' +
      (sample || 0) + ',' + (days || 0) + ')';
    return '<span class="hb-badge" role="button" tabindex="0" onclick="' + onclick + '">' +
      prefix + gamesPart + daysPart + confPart +
      '</span>';
  }

  // Badge without the WR prefix (when the number is rendered as a separate KPI).
  function renderBadgeOnly(sample, days) {
    return render(null, sample, days, { hidePct: true });
  }

  // Heuristic flag for regex-based classifications (Deck Lens class breakdown).
  function renderHeuristic(reason) {
    const msg = reason || 'ability text scan';
    return '<span class="hb-heuristic" role="button" tabindex="0" ' +
      'onclick="window.V3.HonestyBadge.openHeuristicExplainer()" ' +
      'title="Keyword match on ability text — ~80% coverage">' +
      '⚠ Heuristic · ' + msg + '</span>';
  }

  function openExplainer(sample, days) {
    const s = Number(sample) || 0;
    const d = Number(days) || 0;
    const label = confidenceLabel(s);
    const daysLabel = d ? ' in the last ' + d + ' day' + (d === 1 ? '' : 's') : '';
    const tail = label === 'Low'
      ? ' Small samples can move quickly — treat values as directional.'
      : label === 'Medium'
        ? ' Enough data to see trends, but swings of a few percentage points are normal.'
        : ' Large sample — estimates are stable.';
    const body =
      '<p>Based on <strong>' + s.toLocaleString() + ' observed games</strong>' + daysLabel + '. ' +
      'These numbers describe the archetype or list — not a specific player.</p>' +
      '<p>Confidence: <strong>' + label + '</strong>.' + tail + '</p>';
    if (typeof showInfoSheet === 'function') showInfoSheet('Confidence', body);
    else alert(body.replace(/<[^>]+>/g, ''));
  }

  function openHeuristicExplainer() {
    const body =
      '<p>This classification uses keyword matching on the card ability text. ' +
      'Coverage is roughly 80% — cards with unusual wording may be missed or miscategorized.</p>' +
      '<p>Use as a directional signal, not a source of truth.</p>';
    if (typeof showInfoSheet === 'function') showInfoSheet('Heuristic', body);
    else alert(body.replace(/<[^>]+>/g, ''));
  }

  // Explainer for the card_scores "appearances" metric. Clarifies that
  // it measures in-play visibility of the card, NOT how many decks ran it.
  // Exposed because the distinction is non-obvious and biases signal reading
  // (zero appearances ≠ card not in deck, just card not drawn / not played).
  // When decksWith/decksTotal are provided, renders the richer in_deck_rate
  // explainer (native card_scores from App_tool generator, post-D3).
  function openAppearancesExplainer(sample, decksWith, decksTotal) {
    const s = Number(sample) || 0;
    const dw = Number(decksWith) || 0;
    const dt = Number(decksTotal) || 0;
    const label = confidenceLabel(s);
    const hasDeckRate = dt > 0;
    const pct = hasDeckRate ? Math.round(dw / dt * 100) : 0;

    const appsPara = hasDeckRate
      ? '<p><strong>' + s.toLocaleString() + ' appearances</strong> = times the card was ' +
        'played, revealed, or inkwelled across observed matches in this matchup window.</p>'
      : '<p><strong>' + s.toLocaleString() + ' appearances</strong> means this card was ' +
        'seen played, revealed, or inkwelled in that many observed matches.</p>';

    const deckRatePara = hasDeckRate
      ? '<p><strong>In ' + dw + ' of ' + dt + ' observed decks (' + pct + '%)</strong>. ' +
        'A "deck" here is a distinct (player, archetype) pair in the last 30 days. ' +
        'This is a <strong>lower bound</strong>: a card that is in the 60-card list but ' +
        'never drawn/played in any match by that player will not be counted.</p>'
      : '<p><strong>It does NOT mean ' + s.toLocaleString() + ' decks ran this card.</strong> ' +
        'Cards that stay in hand, sit in the deck, or arrive late in a short game never ' +
        'appear — so 0 appearances is compatible with the card being in the decklist.</p>';

    const body =
      appsPara +
      deckRatePara +
      '<p>Both numbers carry two biases:</p>' +
      '<ul>' +
      '<li><strong>Duration bias</strong>: long games reveal more cards, so late-game ' +
      'cards are over-represented in wins.</li>' +
      '<li><strong>Survival bias</strong>: fast decks that end by turn 5 under-reveal ' +
      'their tech slots.</li>' +
      '</ul>' +
      '<p>Confidence: <strong>' + label + '</strong>. At N below 30, the WR delta has a ' +
      '~±10pp margin — read as directional, not proof.</p>';
    if (typeof showInfoSheet === 'function') showInfoSheet('Card appearances', body);
    else alert(body.replace(/<[^>]+>/g, ''));
  }

  window.V3.HonestyBadge = {
    LOW_MAX: LOW_MAX,
    MED_MAX: MED_MAX,
    confidenceLabel: confidenceLabel,
    confidenceClass: confidenceClass,
    formatPct: formatPct,
    formatDelta: formatDelta,
    render: render,
    renderBadgeOnly: renderBadgeOnly,
    renderHeuristic: renderHeuristic,
    openExplainer: openExplainer,
    openHeuristicExplainer: openHeuristicExplainer,
    openAppearancesExplainer: openAppearancesExplainer,
  };
})();
