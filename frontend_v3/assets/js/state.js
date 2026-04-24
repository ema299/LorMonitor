(function () {
  'use strict';

  const STORAGE_PREFIX = 'v3_';
  const DEFAULT_STATE = {
    mode: 'baseline',
    density: 'rich',
  };

  const listeners = new Set();
  const state = hydrate();

  function hydrate() {
    const next = Object.assign({}, DEFAULT_STATE);
    try {
      const mode = window.localStorage.getItem(STORAGE_PREFIX + 'mode');
      const density = window.localStorage.getItem(STORAGE_PREFIX + 'density');
      if (mode === 'baseline' || mode === 'ia') next.mode = mode;
      if (density === 'compact' || density === 'rich') next.density = density;
    } catch (_) {
      return next;
    }
    return next;
  }

  function get() {
    return Object.assign({}, state);
  }

  function set(patch) {
    if (!patch || typeof patch !== 'object') return;

    const changed = {};
    Object.keys(patch).forEach(key => {
      if (!(key in state)) return;
      const value = patch[key];
      if (state[key] === value) return;
      state[key] = value;
      changed[key] = value;
      try {
        window.localStorage.setItem(STORAGE_PREFIX + key, String(value));
      } catch (_) {
        // Storage disabled: fail closed without blocking UI.
      }
    });

    if (!Object.keys(changed).length) return;
    listeners.forEach(listener => {
      try {
        listener(get(), changed);
      } catch (_) {
        // Keep the store resilient to subscriber errors.
      }
    });
  }

  function subscribe(listener) {
    if (typeof listener !== 'function') return function () {};
    listeners.add(listener);
    return function () {
      listeners.delete(listener);
    };
  }

  window.V3 = window.V3 || {};
  window.V3.State = { get, set, subscribe };
})();
