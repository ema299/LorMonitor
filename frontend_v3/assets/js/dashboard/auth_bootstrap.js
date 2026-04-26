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
