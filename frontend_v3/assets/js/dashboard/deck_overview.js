// Deck tab — Hero KPI strip + tier derivation.
// Shows deck name + inks + 4 tiles: WR, Games, Popularity, Meta Tier.
// Tier is derived frontend-side from WR vs meta median (no backend field needed).

window.V3 = window.V3 || {};
window.V3.DeckOverview = {
  // Compute S/A/B/C tier from deck's WR vs all decks in perimeter.
  // S = top 15%, A = next 25%, B = next 35%, C = rest.
  computeTier(deckWr, allWrs) {
    const clean = (allWrs || []).filter(v => typeof v === 'number' && !isNaN(v));
    if (!clean.length || deckWr == null) return { label: '?', cls: 'tier-unk' };
    const sorted = clean.slice().sort((a, b) => b - a);
    const n = sorted.length;
    const rank = sorted.findIndex(v => v <= deckWr);
    const pct = rank < 0 ? 1 : rank / n;
    if (pct <= 0.15) return { label: 'S', cls: 'tier-s' };
    if (pct <= 0.40) return { label: 'A', cls: 'tier-a' };
    if (pct <= 0.75) return { label: 'B', cls: 'tier-b' };
    return { label: 'C', cls: 'tier-c' };
  },

  buildHero(deckCode) {
    if (!deckCode) return '';
    const scope = (typeof getScopeContext === 'function') ? getScopeContext() : null;
    const pd = (typeof getPerimData === 'function') ? getPerimData() : null;
    if (!pd || !pd.wr || !pd.wr[deckCode]) {
      return `<div class="deck-hero deck-hero--empty">
        <div class="deck-hero-title">${deckCode}</div>
        <div class="deck-hero-sub">No data for this deck in the current scope.</div>
      </div>`;
    }
    const wrEntry = pd.wr[deckCode];
    const wr = Number(wrEntry.wr || 0);
    const games = Number(wrEntry.games || 0);
    const share = pd.meta_share && pd.meta_share[deckCode] != null
      ? Number(pd.meta_share[deckCode])
      : null;
    const allWrs = Object.values(pd.wr).map(v => Number(v.wr || 0));
    const tier = this.computeTier(wr, allWrs);

    const inks = (typeof DECK_INKS !== 'undefined' && DECK_INKS[deckCode]) || [];
    const dots = inks.map(i => {
      const color = (typeof INK_COLORS !== 'undefined' && INK_COLORS[i]) || '#888';
      return `<span class="deck-hero-ink-dot" style="background:${color}"></span>`;
    }).join('');
    const inksLabel = inks.map(i => i.charAt(0).toUpperCase() + i.slice(1)).join(' · ');

    const wrCls = wr >= 52 ? 'tile-good' : wr <= 47 ? 'tile-bad' : '';
    const scopeName = scope ? (scope.perimeter || '').toUpperCase() : '';

    return `<div class="deck-hero">
      <div class="deck-hero-top">
        <div class="deck-hero-inks">${dots}</div>
        <div>
          <div class="deck-hero-title">${deckCode}</div>
          <div class="deck-hero-sub">${inksLabel}${scopeName ? ' · ' + scopeName : ''}</div>
        </div>
      </div>
      <div class="deck-hero-kpis">
        <div class="deck-kpi ${wrCls}">
          <div class="deck-kpi-v">${wr.toFixed(1)}%</div>
          <div class="deck-kpi-l">Win Rate</div>
        </div>
        <div class="deck-kpi">
          <div class="deck-kpi-v">${games.toLocaleString()}</div>
          <div class="deck-kpi-l">Games</div>
        </div>
        <div class="deck-kpi">
          <div class="deck-kpi-v">${share != null ? share.toFixed(1) + '%' : '—'}</div>
          <div class="deck-kpi-l">Popularity</div>
        </div>
        <div class="deck-kpi">
          <div class="deck-kpi-v ${tier.cls}">${tier.label}</div>
          <div class="deck-kpi-l">Meta Tier</div>
        </div>
      </div>
    </div>`;
  },

  // Quick visuals row: cost curve + ink split + type split.
  // Deterministic counts from card DB — zero statistics risk.
  buildVisuals(deckCode, opponentCode) {
    if (!deckCode) return '';
    if (!(window.V3 && window.V3.DeckGrid)) return '';
    const mu = opponentCode && typeof getMatchupData === 'function' ? getMatchupData(opponentCode) : null;
    const cards = window.V3.DeckGrid._resolveCards(deckCode, mu);
    if (!cards.length) return '';
    if (typeof rvCardsDB === 'undefined' || !rvCardsDB) {
      return '<div class="deck-vis deck-vis--loading">Loading card database…</div>';
    }

    const costBuckets = {};
    const inkCounts = {};
    const typeCounts = {};
    let total = 0;
    cards.forEach(c => {
      const meta = rvCardsDB[c.card];
      const qty = c.qty || 1;
      total += qty;
      if (meta) {
        const cost = parseInt(meta.cost, 10);
        if (Number.isFinite(cost)) {
          const k = cost >= 8 ? '8+' : String(cost);
          costBuckets[k] = (costBuckets[k] || 0) + qty;
        }
        const ink = (meta.ink || '').trim().toLowerCase();
        if (ink) inkCounts[ink] = (inkCounts[ink] || 0) + qty;
        const type = (meta.type || '').trim();
        if (type) typeCounts[type] = (typeCounts[type] || 0) + qty;
      }
    });

    // Cost curve bars (0..8+)
    const costOrder = ['0','1','2','3','4','5','6','7','8+'];
    const maxCost = Math.max(1, ...costOrder.map(k => costBuckets[k] || 0));
    const costBars = costOrder.map(k => {
      const v = costBuckets[k] || 0;
      const h = v === 0 ? 2 : Math.max(6, (v / maxCost) * 100);
      return `<div class="dv-cc-bar" title="${v} card${v === 1 ? '' : 's'} at cost ${k}">
        <div class="dv-cc-fill" style="height:${h}%"></div>
        <div class="dv-cc-v">${v || ''}</div>
        <div class="dv-cc-l">${k}</div>
      </div>`;
    }).join('');

    // Ink stacked bar
    const inkPalette = (typeof INK_COLORS !== 'undefined') ? INK_COLORS : {};
    const inkEntries = Object.entries(inkCounts).sort((a, b) => b[1] - a[1]);
    const inkBar = inkEntries.map(([ink, v]) => {
      const pct = (v / total) * 100;
      const col = inkPalette[ink] || '#888';
      const label = ink.charAt(0).toUpperCase() + ink.slice(1);
      return `<span class="dv-ink-seg" style="width:${pct}%;background:${col}" title="${label}: ${v} (${pct.toFixed(0)}%)"></span>`;
    }).join('');
    const inkLegend = inkEntries.map(([ink, v]) => {
      const pct = (v / total) * 100;
      const col = inkPalette[ink] || '#888';
      return `<span class="dv-ink-li"><span class="dv-ink-swatch" style="background:${col}"></span>${ink.charAt(0).toUpperCase() + ink.slice(1)} ${pct.toFixed(0)}%</span>`;
    }).join('');

    // Type stacked bar
    const typeColors = {
      Character: '#D4A03A', Action: '#58A6FF', Item: '#8B949E',
      Song: '#B168C6', Location: '#3FB950',
    };
    const typeEntries = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
    const typeBar = typeEntries.map(([t, v]) => {
      const pct = (v / total) * 100;
      const col = typeColors[t] || '#6B7280';
      return `<span class="dv-ink-seg" style="width:${pct}%;background:${col}" title="${t}: ${v} (${pct.toFixed(0)}%)"></span>`;
    }).join('');
    const typeLegend = typeEntries.map(([t, v]) => {
      const pct = (v / total) * 100;
      const col = typeColors[t] || '#6B7280';
      return `<span class="dv-ink-li"><span class="dv-ink-swatch" style="background:${col}"></span>${t} ${pct.toFixed(0)}%</span>`;
    }).join('');

    return `<div class="deck-vis">
      <div class="dv-panel">
        <div class="dv-title">Cost curve</div>
        <div class="dv-cc">${costBars}</div>
      </div>
      <div class="dv-panel">
        <div class="dv-title">Ink split</div>
        <div class="dv-ink-bar">${inkBar}</div>
        <div class="dv-ink-legend">${inkLegend}</div>
      </div>
      <div class="dv-panel">
        <div class="dv-title">Type split</div>
        <div class="dv-ink-bar">${typeBar}</div>
        <div class="dv-ink-legend">${typeLegend}</div>
      </div>
    </div>`;
  },
};
