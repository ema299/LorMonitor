(function () {
  'use strict';

  function mount(container) {
    const view = window.V3.LiveAdapter.IA_BLUEPRINT.find(function (item) { return item.id === 'meta'; });
    container.innerHTML = window.V3.UI.renderHero({
      title: view.label,
      summary: 'Qui finiranno share, trend e matrix quando inizieremo a staccare la baseline dal dashboard live.',
      legacyCount: String(view.legacy.length),
      focus: 'field',
    }) + window.V3.UI.renderPlaceholder(view);
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Meta = { mount: mount };
})();
