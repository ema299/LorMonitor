// Deck tab — grouped card grid + detail sheet.
// Replaces the old "non-standard picks" default view (2026-04-23).
// Cards are grouped by cost (1-2 / 3-4 / 5+) and rendered as art tiles
// with qty badge + colored status dot. Tap a tile to open a bottom-sheet
// (mobile) / side-panel (desktop) with full stats.

window.V3 = window.V3 || {};
window.V3.DeckGrid = {
  // Minimum sample size below which WR delta is not reliable.
  MIN_SAMPLE: 30,

  // Resolve the card list to render. Prefers the user's custom list, falls back
  // to the matchup decklist (if an opponent is selected), else to consensus.
  _resolveCards(deckCode, mu) {
    if (typeof myDeckMode !== 'undefined' && myDeckMode === 'custom' && typeof myDeckCards !== 'undefined' && myDeckCards) {
      return Object.entries(myDeckCards).map(([name, qty]) => ({ card: name, qty: Number(qty) || 1 }));
    }
    if (mu && mu.decklist && Array.isArray(mu.decklist.full_list) && mu.decklist.full_list.length) {
      return mu.decklist.full_list.map(c => ({ card: c.card, qty: Number(c.qty) || 1 }));
    }
    const consensus = (DATA.consensus || {})[deckCode] || {};
    return Object.entries(consensus)
      .map(([name, qty]) => ({ card: name, qty: Math.max(1, Math.round(Number(qty) || 0)) }))
      .filter(c => c.qty > 0);
  },

  _cardCost(name) {
    if (typeof rvCardsDB === 'undefined' || !rvCardsDB || !rvCardsDB[name]) return null;
    const c = rvCardsDB[name].cost;
    const n = parseInt(c, 10);
    return Number.isFinite(n) ? n : null;
  },

  _cardImg(name) {
    if (typeof cardImgUrlFuzzy === 'function') return cardImgUrlFuzzy(name);
    if (typeof rvCardImgByName === 'function') return rvCardImgByName(name);
    return '';
  },

  _statusDot(wrDelta, sample) {
    if (sample != null && sample < this.MIN_SAMPLE) return { cls: 'ds-gray', label: 'Low sample' };
    if (wrDelta == null) return { cls: 'ds-gray', label: 'No data' };
    const pp = wrDelta * 100;
    if (pp >= 2) return { cls: 'ds-green', label: 'Winner' };
    if (pp <= -2) return { cls: 'ds-red', label: 'Drag' };
    return { cls: 'ds-yellow', label: 'Neutral' };
  },

  _cardStat(name, mu) {
    // card_scores entries shape: {apps, delta, win_apps, loss_apps}.
    // `apps` = observed appearances of the card in this matchup (used as sample).
    const cs = (mu && mu.card_scores) || {};
    const entry = cs[name];
    if (!entry) return { delta: null, sample: null };
    const sample = entry.apps != null ? Number(entry.apps)
                 : entry.games != null ? Number(entry.games) : null;
    return {
      delta: typeof entry.delta === 'number' ? entry.delta : null,
      sample: sample,
    };
  },

  buildGrid(deckCode, opponentCode) {
    if (!deckCode) return '';
    const mu = opponentCode && typeof getMatchupData === 'function' ? getMatchupData(opponentCode) : null;
    const cards = this._resolveCards(deckCode, mu);
    if (!cards.length) return '';

    // Single flat list sorted by cost then name. Cost comes from rvCardsDB (fallback 99).
    const enriched = cards.map(c => Object.assign({}, c, { cost: this._cardCost(c.card) }));
    enriched.sort((a, b) => (a.cost == null ? 99 : a.cost) - (b.cost == null ? 99 : b.cost)
      || a.card.localeCompare(b.card));

    const totalCopies = enriched.reduce((s, c) => s + (c.qty || 0), 0);

    const inEdit = !!(window.V3 && window.V3.Builder && window.V3.Builder.editMode);
    const tiles = enriched.map(c => {
      const img = this._cardImg(c.card);
      const stat = this._cardStat(c.card, mu);
      const dot = this._statusDot(stat.delta, stat.sample);
      const safeName = (c.card || '').replace(/"/g, '&quot;');
      const short = (c.card || '').split(' - ')[0];
      const artHtml = img
        ? `<img src="${img}" loading="lazy" alt="${safeName}">`
        : `<div class="pf-std-vph">${short}</div>`;
      const editOverlay = inEdit
        ? `<div class="dg-edit-overlay">
             <button class="dg-edit-btn dg-edit-minus" data-bld-action="remove" title="Remove one">−</button>
             <button class="dg-edit-btn dg-edit-plus" data-bld-action="add" title="Add one">+</button>
           </div>`
        : '';
      const tileOnClick = inEdit ? '' : `onclick="window.V3.DeckGrid.openSheet(this.dataset.card)"`;
      return `<div class="pf-std-vcard dg-tile${inEdit ? ' dg-tile--edit' : ''}" data-card="${safeName}" ${tileOnClick} title="${safeName}">
        <div class="pf-std-vart">
          ${artHtml}
          <span class="pf-std-vqty">×${c.qty}</span>
          <span class="dg-dot ${dot.cls}" title="${dot.label}"></span>
          ${editOverlay}
        </div>
      </div>`;
    }).join('');

    const safeDeck = String(deckCode || '').replace(/"/g, '&quot;');
    const underMin = totalCopies < 60;
    const hdrCount = `${totalCopies} cards · ${enriched.length} unique`;
    const isDirty = window.V3 && window.V3.SavedDecks && window.V3.SavedDecks.isDirty(deckCode);
    const mathBtn = `<button class="dg-hdr-btn dg-hdr-btn--math" onclick="window.V3.MathTool && window.V3.MathTool.open()" title="Opening hand math">Math</button>`;
    const hdrBtns = `${isDirty ? `<button class="dg-hdr-btn dg-hdr-btn--save" data-bld-action="save-deck" title="Save as new decklist">Save</button>` : ''}
       ${mathBtn}
       <button class="dg-hdr-btn" data-bld-action="reset" data-deck="${safeDeck}" title="Reset to consensus">↺</button>`;
    return `<div class="dg-wrap ${inEdit ? 'dg-wrap--edit' : ''}">
      <div class="dg-hdr">
        <span class="dg-hdr-label">${inEdit ? 'Editing deck' : 'Decklist'}</span>
        <span class="dg-hdr-count ${inEdit && underMin ? 'under' : ''}">${hdrCount}${inEdit && underMin ? ' · below 60' : ''}</span>
        <span class="dg-hdr-btns">${hdrBtns}</span>
      </div>
      <div class="pf-std-gallery dg-grid">${tiles}</div>
    </div>`;
  },

  openSheet(cardName) {
    if (!cardName) return;
    const opp = typeof labOpp !== 'undefined' ? labOpp : null;
    const meta = (typeof rvCardDetailsByName === 'function') ? rvCardDetailsByName(cardName) : null;
    const img = this._cardImg(cardName);
    const safeName = cardName.replace(/"/g, '&quot;');
    const esc = (typeof rvEscapeHtml === 'function') ? rvEscapeHtml : (s) => String(s || '').replace(/</g, '&lt;');

    const metaLine = meta
      ? `<div class="dg-sheet-meta">Cost ${esc(meta.cost)} · ${esc(meta.type || '?')} · ${esc(meta.ink || '?')}${meta.strength || meta.willpower ? ` · ${esc(meta.strength || '?')}/${esc(meta.willpower || '?')}` : ''}${meta.lore ? ` · ${esc(meta.lore)} lore` : ''}</div>`
      : '';

    const abilityHtml = meta && meta.ability
      ? `<div class="ci-section"><div class="ci-sec-title">Ability</div><div class="dg-sheet-ability">${esc(meta.ability)}</div></div>`
      : '';

    const impactHtml = (window.V3 && window.V3.CardImpact)
      ? window.V3.CardImpact.buildSheet(cardName, opp)
      : '';

    const sheetHtml = `<div class="dg-sheet-backdrop" onclick="if(event.target===this)window.V3.DeckGrid.closeSheet()">
      <div class="dg-sheet" role="dialog" aria-label="${safeName}">
        <button class="dg-sheet-close" onclick="window.V3.DeckGrid.closeSheet()" aria-label="Close">&times;</button>
        ${img ? `<div class="dg-sheet-art"><img src="${img.replace('/thumbnail/', '/full/')}" alt="${safeName}"></div>` : ''}
        <div class="dg-sheet-body">
          <div class="dg-sheet-title">${esc(cardName)}</div>
          ${metaLine}
          ${impactHtml}
          ${abilityHtml}
        </div>
      </div>
    </div>`;

    this.closeSheet();
    const host = document.createElement('div');
    host.id = 'dg-sheet-host';
    host.innerHTML = sheetHtml;
    document.body.appendChild(host);
    requestAnimationFrame(() => host.classList.add('open'));
  },

  closeSheet() {
    const host = document.getElementById('dg-sheet-host');
    if (host) host.remove();
  },
};
