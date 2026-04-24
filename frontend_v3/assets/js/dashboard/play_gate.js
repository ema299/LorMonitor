/**
 * Play soft gate — A.3 isolated paywall for Play tab only.
 *
 * First 3 distinct matchups per day are free. 4th+ gates the "How to Respond"
 * block with a custom overlay. Click overlay → recordPaywallIntent('pro')
 * + session unlock for Play only (resets on tab close).
 *
 * Does NOT touch PRO_UNLOCKED global, wrapPremium, or other tabs.
 * Storage: localStorage key `play_matchups_viewed_YYYY-MM-DD` (UTC date).
 * Old keys auto-cleared on rollover.
 *
 * API (window globals):
 *   playRegisterMatchupView(deck, opp)  -> void  (call on matchup render)
 *   playShouldGateResponse(deck, opp)   -> bool  (true if current matchup gated)
 *   playMatchupsViewedCount()           -> int   (distinct matchups seen today)
 *   playSoftUnlock()                    -> void  (unlock Play for session + POST intent)
 */

(function (global) {
  'use strict';

  let _sessionUnlock = false;

  function _todayKey() {
    const d = new Date();
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, '0');
    const day = String(d.getUTCDate()).padStart(2, '0');
    return `play_matchups_viewed_${y}-${m}-${day}`;
  }

  function _read() {
    // Robust: null → [], parse error → [], non-array → [].
    try {
      const raw = localStorage.getItem(_todayKey());
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  function _cleanupOldKeys() {
    const cur = _todayKey();
    try {
      const toRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith('play_matchups_viewed_') && k !== cur) {
          toRemove.push(k);
        }
      }
      toRemove.forEach(k => localStorage.removeItem(k));
    } catch (_) {}
  }

  function playRegisterMatchupView(deck, opp) {
    if (!deck || !opp) return;
    const sig = `${deck}|${opp}`;
    const viewed = _read();
    if (!viewed.includes(sig)) {
      viewed.push(sig);
      try { localStorage.setItem(_todayKey(), JSON.stringify(viewed)); } catch (_) {}
      _cleanupOldKeys();
    }
  }

  function playShouldGateResponse(deck, opp) {
    if (_sessionUnlock) return false;
    if (!deck || !opp) return false;
    const viewed = _read();
    const idx = viewed.indexOf(`${deck}|${opp}`);
    if (idx >= 0 && idx < 3) return false;   // in first 3 distinct → free
    if (idx >= 3) return true;                // beyond quota
    return viewed.length >= 3;                // new matchup beyond quota
  }

  function playMatchupsViewedCount() {
    return _read().length;
  }

  function playSoftUnlock() {
    _sessionUnlock = true;
    if (typeof recordPaywallIntent === 'function') recordPaywallIntent('pro');
    if (typeof render === 'function') render();
  }

  global.playRegisterMatchupView = playRegisterMatchupView;
  global.playShouldGateResponse = playShouldGateResponse;
  global.playMatchupsViewedCount = playMatchupsViewedCount;
  global.playSoftUnlock = playSoftUnlock;

})(typeof window !== 'undefined' ? window : this);
