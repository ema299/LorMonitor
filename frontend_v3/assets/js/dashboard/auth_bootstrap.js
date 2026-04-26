/**
 * V3 auth bootstrap (B.7.0.5).
 *
 * Reads JWT from localStorage and loads /api/v1/user/profile to populate
 * window.LM_USER for tier-aware rendering (B.7.1 layered rendering tab Team).
 *
 * Pattern: lazy + non-blocking. Initial render fires with LM_USER=null
 * (baseline / free-tier view), then we re-render once profile loads.
 *
 * monolith.js is frozen (anti-monolith rules); this module never touches it.
 * Tier-aware code reads window.LM_USER at render time, defaulting to null.
 *
 * Shape (when loaded):
 *   window.LM_USER = {
 *     id, email, display_name, tier, is_admin,
 *     team_view_mode,           // from preferences, default null
 *     created_at, last_login,
 *   }
 *
 * Shape (anonymous / failed): null
 */
(function () {
  'use strict';

  window.LM_USER = null;

  function readToken() {
    try {
      const keys = ['lm_access_token', 'access_token', 'auth_access_token'];
      for (const k of keys) {
        const v = window.localStorage.getItem(k);
        if (v) return v;
      }
    } catch (_) {
      // localStorage may be blocked
    }
    return null;
  }

  async function loadProfile() {
    const token = readToken();
    if (!token) return null;
    try {
      const resp = await fetch('/api/v1/user/profile', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      if (!resp.ok) return null;
      const profile = await resp.json();
      const prefs = profile.preferences || {};
      return {
        id: profile.id,
        email: profile.email,
        display_name: profile.display_name,
        tier: profile.tier || 'free',
        is_admin: Boolean(profile.is_admin),
        team_view_mode: prefs.team_view_mode || null,
        created_at: profile.created_at,
        last_login: profile.last_login,
      };
    } catch (_) {
      return null;
    }
  }

  // Compute the effective tier capability level (alias 'team' to coach).
  // Used by tier-gating code to make decisions without hardcoding the alias.
  window.lmTierLevel = function lmTierLevel(tier) {
    const map = { free: 0, pro: 1, team: 2, coach: 2, admin: 3 };
    return Object.prototype.hasOwnProperty.call(map, tier) ? map[tier] : 0;
  };

  // Effective view for tab Team layered rendering (B.7.1).
  // Returns 'free' | 'pro' | 'coach' | 'coach_player'.
  // - 'coach_player' = tier=coach (or alias team) but team_view_mode='player'
  //   → render same as pro (lighter view).
  window.lmEffectiveTeamView = function lmEffectiveTeamView() {
    const u = window.LM_USER;
    if (!u) return 'free';
    const lvl = window.lmTierLevel(u.tier);
    if (lvl >= 2) {
      return u.team_view_mode === 'player' ? 'coach_player' : 'coach';
    }
    if (lvl >= 1) return 'pro';
    return 'free';
  };

  // ── A.7 step 1: fetch wrapper with auto Authorization header ─────────────
  // Wraps window.fetch so every request to /api/v1/* automatically carries the
  // current JWT. Auto-refreshes on 401 once if a refresh_token is present.
  // Public endpoints (e.g. /api/v1/dashboard-data) ignore the header server-side
  // — adding it is harmless. External requests (cards.duels.ink, etc.) skip the
  // wrap entirely.

  function readRefreshToken() {
    try {
      return window.localStorage.getItem('lm_refresh_token') || null;
    } catch (_) {
      return null;
    }
  }

  function writeTokens(access, refresh) {
    try {
      if (access) window.localStorage.setItem('lm_access_token', access);
      if (refresh) window.localStorage.setItem('lm_refresh_token', refresh);
    } catch (_) {
      // storage blocked; in-memory tokens still work for current session
    }
  }

  function clearTokens() {
    try {
      window.localStorage.removeItem('lm_access_token');
      window.localStorage.removeItem('lm_refresh_token');
      // Drop legacy keys readToken() looked at, to avoid stale headers
      window.localStorage.removeItem('access_token');
      window.localStorage.removeItem('auth_access_token');
    } catch (_) { /* noop */ }
    window.LM_USER = null;
  }

  window.lmAuthWriteTokens = writeTokens;
  window.lmAuthClearTokens = clearTokens;
  window.lmAuthReadToken = readToken;

  function isApiUrl(url) {
    if (typeof url !== 'string') {
      try { url = url && url.url ? url.url : String(url); } catch (_) { return false; }
    }
    if (!url) return false;
    // Match relative '/api/v1/...' or absolute on same host
    if (url.startsWith('/api/v1/') || url.startsWith('/api/')) return true;
    try {
      const u = new URL(url, window.location.origin);
      return u.origin === window.location.origin && u.pathname.startsWith('/api/');
    } catch (_) {
      return false;
    }
  }

  function withAuthHeader(init, token) {
    const next = Object.assign({}, init || {});
    const headers = new Headers((init && init.headers) || {});
    if (!headers.has('Authorization')) {
      headers.set('Authorization', 'Bearer ' + token);
    }
    next.headers = headers;
    return next;
  }

  let refreshInflight = null;

  async function tryRefresh() {
    // Coalesce concurrent refreshes into a single network call.
    if (refreshInflight) return refreshInflight;
    const refresh = readRefreshToken();
    if (!refresh) return null;
    refreshInflight = (async () => {
      try {
        const resp = await rawFetch('/api/v1/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!resp.ok) {
          clearTokens();
          return null;
        }
        const body = await resp.json();
        const access = body.access_token || body.token;
        const newRefresh = body.refresh_token;
        if (access) writeTokens(access, newRefresh);
        return access || null;
      } catch (_) {
        return null;
      } finally {
        refreshInflight = null;
      }
    })();
    return refreshInflight;
  }

  const rawFetch = window.fetch.bind(window);

  window.fetch = async function lmAuthFetch(input, init) {
    if (!isApiUrl(input)) {
      return rawFetch(input, init);
    }
    const token = readToken();
    let firstInit = init || {};
    if (token) {
      firstInit = withAuthHeader(firstInit, token);
    }
    const resp = await rawFetch(input, firstInit);
    if (resp.status !== 401 || !readRefreshToken()) {
      return resp;
    }
    // Try one refresh, then retry the original request once.
    const newAccess = await tryRefresh();
    if (!newAccess) return resp;
    const retryInit = withAuthHeader(init || {}, newAccess);
    return rawFetch(input, retryInit);
  };

  // Run async on script load. Triggers a re-render if `render` global is
  // already defined when profile lands. Safe to fire concurrently with
  // monolith.js loadData(): the latter calls render() once on its own
  // completion, this just adds a second render with fresh user state.
  loadProfile().then(function (user) {
    if (user) window.LM_USER = user;
    if (typeof window.render === 'function') {
      try { window.render(); } catch (e) { /* render not ready yet, ok */ }
    }
  });
})();
