(function () {
  'use strict';

  function mount(container) {
    const view = window.V3.LiveAdapter.IA_BLUEPRINT.find(function (item) { return item.id === 'improve'; });
    container.innerHTML = window.V3.UI.renderHero({
      title: view.label,
      summary: 'Area predisposta per metriche personali, error review e progress loop, senza restare mischiata ai tab primari.',
      legacyCount: String(view.legacy.length),
      focus: 'growth',
    }) + window.V3.UI.renderPlaceholder(view);
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Improve = { mount: mount };
})();
