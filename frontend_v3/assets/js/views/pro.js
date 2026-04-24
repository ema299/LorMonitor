(function () {
  'use strict';

  function mount(container) {
    const view = window.V3.LiveAdapter.IA_BLUEPRINT.find(function (item) { return item.id === 'pro'; });
    container.innerHTML = window.V3.UI.renderHero({
      title: view.label,
      summary: 'La base distingue subito gli strumenti deep-work dalle superfici di primo ingresso, che era uno dei nodi della IA precedente.',
      legacyCount: String(view.legacy.length),
      focus: 'deep work',
    }) + window.V3.UI.renderPlaceholder(view);
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Pro = { mount: mount };
})();
