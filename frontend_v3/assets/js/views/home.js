(function () {
  'use strict';

  function mount(container) {
    const ui = window.V3.UI;
    const data = window.V3.LiveAdapter;

    container.innerHTML = [
      ui.renderHero({
        title: 'Basi V3 operative',
        summary: 'Questa preview non prova ancora a copiare il live: prepara shell, IA e punti di aggancio per il lavoro successivo.',
        legacyCount: '8+',
        focus: 'scaffold',
      }),
      ui.renderBlueprint(data.IA_BLUEPRINT),
      '<section class="v3-panel">',
      '<div class="v3-section-head">',
      '<h2>Traccia di migrazione</h2>',
      '<p>La sequenza resta: baseline fedele, isolamento, slim, nuova IA, riposizionamento e solo dopo restyling.</p>',
      '</div>',
      '<div class="v3-stage-list">' + ui.renderStageList(data.MIGRATION_TRACK) + '</div>',
      '</section>',
    ].join('');
  }

  window.V3 = window.V3 || {};
  window.V3.Views = window.V3.Views || {};
  window.V3.Views.Home = { mount: mount };
})();
