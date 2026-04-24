(function () {
  'use strict';

  function renderShell(state) {
    const tabs = window.V3.Router.TABS.map(function (tab) {
      return '<button class="v3-nav__tab" type="button" data-tab="' + tab.id + '">' + tab.label + '</button>';
    }).join('');

    return [
      '<div class="v3-app">',
      '<header class="v3-topbar">',
      '<div class="v3-brand">',
      '<span class="v3-brand__eyebrow">Experimental track</span>',
      '<div class="v3-brand__row">',
      '<strong>Lorcana Intelligence</strong>',
      '<span class="v3-brand__seal">V3</span>',
      '</div>',
      '</div>',
      '<div class="v3-topbar__controls">',
      '<div class="v3-toggle" role="tablist" aria-label="Operating mode">',
      '<button class="v3-toggle__btn' + (state.mode === 'baseline' ? ' is-active' : '') + '" type="button" data-mode="baseline">Baseline</button>',
      '<button class="v3-toggle__btn' + (state.mode === 'ia' ? ' is-active' : '') + '" type="button" data-mode="ia">IA target</button>',
      '</div>',
      '<div class="v3-toggle" role="tablist" aria-label="Density">',
      '<button class="v3-toggle__btn' + (state.density === 'rich' ? ' is-active' : '') + '" type="button" data-density="rich">Rich</button>',
      '<button class="v3-toggle__btn' + (state.density === 'compact' ? ' is-active' : '') + '" type="button" data-density="compact">Compact</button>',
      '</div>',
      '</div>',
      '</header>',
      '<nav class="v3-nav" aria-label="Primary">',
      '<div class="v3-nav__inner">' + tabs + '</div>',
      '</nav>',
      '<div class="v3-workbench">',
      '<aside class="v3-rail" id="v3-rail"></aside>',
      '<main class="v3-main" id="v3-main"></main>',
      '</div>',
      '</div>',
    ].join('');
  }

  window.V3 = window.V3 || {};
  window.V3.Layout = window.V3.Layout || {};
  window.V3.Layout.renderShell = renderShell;
})();
