(function () {
  'use strict';

  function mount(container) {
    const view = window.V3.LiveAdapter.IA_BLUEPRINT.find(function (item) { return item.id === 'play'; });
    container.innerHTML = window.V3.UI.renderHero({
      title: view.label,
      summary: 'Superficie pronta per raccogliere coach, piani matchup e decision support senza portarsi dietro il vecchio monolite.',
      legacyCount: String(view.legacy.length),
      focus: 'decisions',
    }) + window.V3.UI.renderPlaceholder(view);
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Play = { mount: mount };
})();
