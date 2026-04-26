// Deck tab — Area D Your list (collapsed by default).
// Contract: docs/DECK_REFACTOR_PARITY.md rows 13, 26-27, 33.
// Collapsed head shows summary stats; "View list" expands the deck grid,
// "Edit deck" enters Builder (which force-expands), "Compare to pros"
// opens the existing Tournament Decks drawer.
//
// Honest rule: not a block-to-edit, just a container for existing renderers:
//   - window.V3.DeckGrid.buildGrid()       (PR2)
//   - window.V3.DeckLens.build()           (PR0 legacy)
//   - openTournamentDecks()                (legacy lab.js)
//   - window.V3.Builder.enter()            (legacy)
// Nothing new is computed here — Area D is a shell.

(function () {
  'use strict';
  window.V3 = window.V3 || {};

  const KEY = 'v3_deck_list_expanded';

  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function _isExpanded() {
    try {
      const v = localStorage.getItem(KEY);
      return v === '1';
    } catch (e) { return false; }
  }

  function _setExpanded(on) {
    try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) {}
  }

  function _summaryStats(deckCode) {
    if (!(window.V3 && window.V3.DeckGrid && window.V3.DeckGrid._resolveCards)) {
      return { total: 0, unique: 0, deltaCount: 0 };
    }
    const cards = window.V3.DeckGrid._resolveCards(deckCode, null) || [];
    let total = 0;
    cards.forEach(function (c) { total += (c.qty || 0); });

    let deltaCount = 0;
    const consensus = (window.DATA && window.DATA.consensus && window.DATA.consensus[deckCode]) || null;
    const my = (typeof myDeckCards !== 'undefined' && myDeckCards &&
                typeof myDeckMode !== 'undefined' && myDeckMode === 'custom') ? myDeckCards : null;
    if (my && consensus) {
      const names = new Set([].concat(Object.keys(my), Object.keys(consensus)));
      names.forEach(function (n) {
        const a = Math.round(Number(my[n] || 0));
        const b = Math.round(Number(consensus[n] || 0));
        if (a !== b) deltaCount += Math.abs(a - b);
      });
    }

    return { total: total, unique: cards.length, deltaCount: deltaCount };
  }

  function toggle() {
    const inEdit = !!(window.V3 && window.V3.Builder && window.V3.Builder.editMode);
    // Compute the CURRENT visible state (edit mode force-expands), then flip.
    const currentlyExpanded = inEdit || _isExpanded();
    const nextExpanded = !currentlyExpanded;
    _setExpanded(nextExpanded);
    // Collapsing while in edit mode should also exit edit (otherwise the
    // force-expand rule keeps the list visible and the click looks inert).
    if (!nextExpanded && inEdit && typeof window.V3.Builder.exit === 'function') {
      window.V3.Builder.exit(); // exit() calls render() itself
      return;
    }
    if (typeof render === 'function') render();
  }

  function triggerEdit() {
    const inEdit = !!(window.V3 && window.V3.Builder && window.V3.Builder.editMode);
    // Second click on the button while editing = exit edit mode.
    if (inEdit && typeof window.V3.Builder.exit === 'function') {
      window.V3.Builder.exit();
      return;
    }
    _setExpanded(true); // force expand so builder aside has a host
    if (window.V3 && window.V3.Builder && typeof window.V3.Builder.enter === 'function') {
      const deck = (typeof coachDeck !== 'undefined') ? coachDeck : null;
      window.V3.Builder.enter(deck);
    }
  }

  function triggerCompare() {
    if (typeof openTournamentDecks === 'function') openTournamentDecks();
  }

  function build(deckCode, opponentCode) {
    if (!deckCode) return '';
    const inEdit = !!(window.V3 && window.V3.Builder && window.V3.Builder.editMode);
    const expanded = inEdit || _isExpanded();
    const stats = _summaryStats(deckCode);

    const summaryBits = [];
    summaryBits.push(stats.total + ' cards');
    summaryBits.push(stats.unique + ' unique');
    if (stats.deltaCount > 0) summaryBits.push(stats.deltaCount + ' changes vs consensus');

    const summaryLine = summaryBits.join(' · ');
    const chevron = expanded ? '▾' : '▸';
    const toggleLabel = expanded ? 'Hide list' : 'View list';

    // Loaded saved-deck indicator — "Loaded: <name>" (or "· modified" if
    // myDeckCards has diverged from the loaded list since load).
    let loadedIndicator = '';
    if (window.V3 && window.V3.SavedDecks && window.V3.SavedDecks.getLoadedDeck) {
      const loaded = window.V3.SavedDecks.getLoadedDeck();
      if (loaded) {
        const dirty = window.V3.SavedDecks.isDirtyVsLoaded && window.V3.SavedDecks.isDirtyVsLoaded();
        loadedIndicator = '<span class="dlv-loaded' + (dirty ? ' dlv-loaded--dirty' : '') + '" ' +
          'title="Currently loaded saved deck">' +
          '<span class="dlv-loaded-lbl">Loaded:</span> ' +
          '<strong>' + _esc(loaded.name) + '</strong>' +
          (dirty ? ' <span class="dlv-loaded-tag">modified</span>' : '') +
          '</span>';
      }
    }

    const head =
      '<div class="dlv-head">' +
      '<button class="dlv-toggle" type="button" onclick="window.V3.DeckListView.toggle()" ' +
      'aria-expanded="' + expanded + '">' +
      '<span class="dlv-chevron">' + chevron + '</span>' +
      '<span class="dlv-title">Your list</span>' +
      '<span class="dlv-sum">' + _esc(summaryLine) + '</span>' +
      loadedIndicator +
      '</button>' +
      '<div class="dlv-actions">' +
      '<button class="dlv-btn dlv-btn--ghost" type="button" onclick="window.V3.DeckListView.toggle()">' +
      toggleLabel +
      '</button>' +
      '<button class="dlv-btn dlv-btn--ghost" type="button" ' +
      'onclick="window.V3.SavedDecks && window.V3.SavedDecks.openLoadPopover()" ' +
      'title="Load one of your saved decks into the editor">' +
      'Load…' +
      '</button>' +
      '<button class="dlv-btn dlv-btn--gold" type="button" onclick="window.V3.DeckListView.triggerEdit()">' +
      (inEdit ? 'Done editing' : 'Edit deck') +
      '</button>' +
      '<button class="dlv-btn dlv-btn--ghost" type="button" onclick="window.V3.DeckListView.triggerCompare()">' +
      'Compare to pros' +
      '</button>' +
      '</div>' +
      '</div>';

    const intro = '<div class="deck-intro deck-intro--above">' +
      '<strong>The consensus 60-card decklist</strong> for this archetype, aggregated ' +
      'from the top-performing observed lists. Expand to see every card with its ' +
      'in-matchup score (how much playing the card shifts the observed win rate in ' +
      'wins vs losses), compare against the latest tournament decklists, or hit ' +
      '<em>Edit deck</em> to build your own variant with consensus as the baseline. ' +
      'Edits are saved locally in the browser — no account required.' +
      '</div>';
    if (!expanded) return intro + '<div class="dlv-card dlv-collapsed">' + head + '</div>';

    const gridHtml = (window.V3 && window.V3.DeckGrid)
      ? window.V3.DeckGrid.buildGrid(deckCode, opponentCode)
      : '';
    const builderHtml = (inEdit && window.V3 && window.V3.Builder && window.V3.Builder.buildPanel)
      ? window.V3.Builder.buildPanel(deckCode)
      : '';
    const lensHtml = (window.V3 && window.V3.DeckLens)
      ? window.V3.DeckLens.build(deckCode, opponentCode)
      : '';

    // PR6 (Mod 1) — live status bar sticky above the builder layout, only
    // while editing. Recomputed on every render so it reflects each +/-.
    const statusHtml = (inEdit && window.V3 && window.V3.BuilderStatus)
      ? window.V3.BuilderStatus.build(deckCode, opponentCode)
      : '';

    // PR6 (Mod 2) — on mobile (CSS order) the builder-side comes first,
    // then grid, then lens (wrapped in <details> so it collapses).
    // Desktop layout unchanged: main | lens | side columns via existing
    // .deck-lab-layout--edit grid rules.
    const lensWrap = lensHtml
      ? '<details class="deck-lab-lens" open><summary class="dlv-lens-summary">Deck Lens</summary>' +
        lensHtml + '</details>'
      : '';

    const bodyLayout = inEdit
      ? '<div class="deck-lab-layout deck-lab-layout--edit dlv-mobile-reorder">' +
        '<div class="deck-lab-main">' + gridHtml + '</div>' +
        lensWrap +
        '<div class="deck-lab-side">' + builderHtml + '</div>' +
        '</div>'
      : lensHtml
        ? '<div class="deck-lab-layout">' +
          '<div class="deck-lab-main">' + gridHtml + '</div>' +
          '<div class="deck-lab-lens">' + lensHtml + '</div>' +
          '</div>'
        : gridHtml;

    // Cross-matchup suggestions live at the bottom of the expanded Your
    // list card. Engine runs without an opp hint → ranked by aggregate
    // coverage gained / weighted-delta across the whole observed matrix.
    let suggHtml = '';
    if (window.V3 && window.V3.RecommendationEngine) {
      const actions = window.V3.RecommendationEngine.compute(deckCode) || [];
      const suggBody = actions.length
        ? actions.map(function (a) { return window.V3.RecommendationEngine.renderAction(a); }).join('')
        : '<div class="dlv-sugg-empty">No strong add / cut suggestions from the observed sample in the current scope.</div>';
      suggHtml = '<div class="dlv-sugg">' +
        '<div class="dlv-sugg-head">Suggested adds / cuts ' +
        '<span class="dlv-sugg-sub">cross-matchup · observed sample · data-driven</span>' +
        '</div>' +
        '<div class="dlv-sugg-list">' + suggBody + '</div>' +
        '</div>';
    }

    return intro + '<div class="dlv-card dlv-expanded">' +
      head +
      '<div class="dlv-body">' + statusHtml + bodyLayout + '</div>' +
      suggHtml +
      '</div>';
  }

  window.V3.DeckListView = {
    build: build,
    toggle: toggle,
    triggerEdit: triggerEdit,
    triggerCompare: triggerCompare,
    isExpanded: _isExpanded,
    setExpanded: _setExpanded,
  };
})();
