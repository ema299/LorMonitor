(function () {
  'use strict';

  function mount(container) {
    const view = window.V3.LiveAdapter.IA_BLUEPRINT.find(function (item) { return item.id === 'deck'; });
    container.innerHTML = window.V3.UI.renderHero({
      title: view.label,
      summary: 'Base dedicata alla superficie deckbuilding, gia separata dalla lettura meta e dalla coaching loop.',
      legacyCount: String(view.legacy.length),
      focus: 'builds',
    }) + window.V3.UI.renderPlaceholder(view);
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Deck = { mount: mount };
})();
