(function () {
  'use strict';

  const TABS = window.V3.LiveAdapter.IA_BLUEPRINT.map(item => ({
    id: item.id,
    label: item.label,
  }));
  const TAB_IDS = new Set(TABS.map(tab => tab.id));
  const DEFAULT_TAB = 'home';
  const listeners = new Set();

  function parseHash() {
    const raw = String(window.location.hash || '').replace(/^#/, '');
    if (!raw) return { tab: DEFAULT_TAB };
    return { tab: TAB_IDS.has(raw) ? raw : DEFAULT_TAB };
  }

  function navigate(tab) {
    const nextTab = TAB_IDS.has(tab) ? tab : DEFAULT_TAB;
    const hash = '#' + nextTab;
    if (window.location.hash !== hash) {
      window.location.hash = hash;
      return;
    }
    notify(parseHash());
  }

  function subscribe(listener) {
    if (typeof listener !== 'function') return function () {};
    listeners.add(listener);
    return function () {
      listeners.delete(listener);
    };
  }

  function notify(route) {
    listeners.forEach(listener => {
      try {
        listener(route);
      } catch (_) {
        // One bad subscriber should not break navigation.
      }
    });
  }

  function start() {
    window.addEventListener('hashchange', function () {
      notify(parseHash());
    });
    if (!window.location.hash) {
      window.history.replaceState(null, '', '#' + DEFAULT_TAB);
    }
    notify(parseHash());
  }

  window.V3 = window.V3 || {};
  window.V3.Router = {
    TABS,
    DEFAULT_TAB,
    parseHash,
    navigate,
    subscribe,
    start,
  };
})();
