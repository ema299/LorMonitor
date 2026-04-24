(function () {
  'use strict';

  function mount(container) {
    const view = window.V3.LiveAdapter.IA_BLUEPRINT.find(function (item) { return item.id === 'community'; });
    container.innerHTML = window.V3.UI.renderHero({
      title: view.label,
      summary: 'Superficie dedicata ai segnali community, pronta a ricevere feed e discovery senza invadere le aree analytical.',
      legacyCount: String(view.legacy.length),
      focus: 'signals',
    }) + window.V3.UI.renderPlaceholder(view);
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Community = { mount: mount };
})();
