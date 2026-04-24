(function () {
  'use strict';

  const VIEW_BINDINGS = {
    home: function () { return window.V3.Views.Home; },
    play: function () { return window.V3.Views.Play; },
    meta: function () { return window.V3.Views.Meta; },
    deck: function () { return window.V3.Views.Deck; },
    improve: function () { return window.V3.Views.Improve; },
    pro: function () { return window.V3.Views.Pro; },
    community: function () { return window.V3.Views.Community; },
    events: function () { return window.V3.Views.Events; },
  };

  function bootstrap() {
    const root = document.getElementById('v3-root');
    if (!root) return;

    root.innerHTML = window.V3.Layout.renderShell(window.V3.State.get());
    wireNav();
    wireControls();
    window.V3.Router.subscribe(onRouteChange);
    window.V3.State.subscribe(onStateChange);
    renderRail();
    window.V3.Router.start();
  }

  function wireNav() {
    const nav = document.querySelector('.v3-nav__inner');
    if (!nav) return;
    nav.addEventListener('click', function (event) {
      const button = event.target.closest('[data-tab]');
      if (!button) return;
      window.V3.Router.navigate(button.getAttribute('data-tab'));
    });
  }

  function wireControls() {
    const topbar = document.querySelector('.v3-topbar');
    if (!topbar) return;

    topbar.addEventListener('click', function (event) {
      const modeButton = event.target.closest('[data-mode]');
      if (modeButton) {
        window.V3.State.set({ mode: modeButton.getAttribute('data-mode') });
        return;
      }

      const densityButton = event.target.closest('[data-density]');
      if (densityButton) {
        window.V3.State.set({ density: densityButton.getAttribute('data-density') });
      }
    });
  }

  function onRouteChange(route) {
    setActiveTab(route.tab);
    const main = document.getElementById('v3-main');
    if (!main) return;
    const pick = VIEW_BINDINGS[route.tab];
    const view = pick ? pick() : null;
    if (!view || typeof view.mount !== 'function') return;
    view.mount(main);
  }

  function onStateChange() {
    const root = document.getElementById('v3-root');
    if (!root) return;

    const route = window.V3.Router.parseHash();
    root.innerHTML = window.V3.Layout.renderShell(window.V3.State.get());
    wireNav();
    wireControls();
    renderRail();
    onRouteChange(route);
  }

  function setActiveTab(tabId) {
    const tabs = document.querySelectorAll('.v3-nav__tab');
    tabs.forEach(function (tab) {
      tab.classList.toggle('is-active', tab.getAttribute('data-tab') === tabId);
    });
  }

  function renderRail() {
    const state = window.V3.State.get();
    const rail = document.getElementById('v3-rail');
    if (!rail) return;

    const foundations = window.V3.UI.renderRailCard(
      state.mode === 'baseline' ? 'Fondazioni operative' : 'Fondazioni della nuova IA',
      window.V3.LiveAdapter.FOUNDATIONS
    );

    const migration = [
      '<section class="v3-rail-card">',
      '<div class="v3-section-head">',
      '<h2>Milestone</h2>',
      '</div>',
      '<div class="v3-stage-list v3-stage-list--rail">',
      window.V3.UI.renderStageList(window.V3.LiveAdapter.MIGRATION_TRACK),
      '</div>',
      '</section>',
    ].join('');

    rail.innerHTML = foundations + migration;
    rail.setAttribute('data-density', state.density);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap, { once: true });
  } else {
    bootstrap();
  }
})();
