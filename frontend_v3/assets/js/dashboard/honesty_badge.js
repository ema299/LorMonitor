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
  };
})();
