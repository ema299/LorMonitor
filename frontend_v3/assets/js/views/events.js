(function () {
  'use strict';

  function mount(container) {
    const view = window.V3.LiveAdapter.IA_BLUEPRINT.find(function (item) { return item.id === 'events'; });
    container.innerHTML = window.V3.UI.renderHero({
      title: view.label,
      summary: 'Spazio pronto per tornei e calendario, separato dal lavoro deck e dal lavoro meta.',
      legacyCount: String(view.legacy.length),
      focus: 'calendar',
    }) + window.V3.UI.renderPlaceholder(view);
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Events = { mount: mount };
})();
