/**
 * API client — fetch wrapper for Lorcana Monitor backend.
 */
const API_BASE = '/api/v1';

async function api(path, params = {}) {
  const url = new URL(API_BASE + path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  });
  const resp = await fetch(url);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// Monitor endpoints
const API = {
  meta:       (fmt, days) => api('/monitor/meta', { game_format: fmt, days }),
  winrates:   (fmt, days) => api('/monitor/winrates', { game_format: fmt, days }),
  matrix:     (fmt, days) => api('/monitor/matchup-matrix', { game_format: fmt, days }),
  otpOtd:     (fmt, days) => api('/monitor/otp-otd', { game_format: fmt, days }),
  trend:      (fmt, days) => api('/monitor/trend', { game_format: fmt, days }),
  leaderboard:(fmt, days, limit) => api('/monitor/leaderboard', { game_format: fmt, days, limit }),
  deck:       (code, fmt, days) => api(`/monitor/deck/${code}`, { game_format: fmt, days }),

  // Coach endpoints
  matchup:      (our, opp, fmt, days) => api(`/coach/matchup/${our}/${opp}`, { game_format: fmt, days }),
  killerCurves: (our, opp, fmt) => api(`/coach/killer-curves/${our}/${opp}`, { game_format: fmt }),
  threats:      (our, opp, fmt) => api(`/coach/threats/${our}/${opp}`, { game_format: fmt }),
  matchupHistory:(our, opp, fmt, days) => api(`/coach/history/${our}/${opp}`, { game_format: fmt, days }),

  // Lab endpoints
  cardScores: (our, opp, fmt, days) => api(`/lab/card-scores/${our}/${opp}`, { game_format: fmt, days }),

  // Admin
  health: () => api('/admin/health'),
};

// Ink color mapping for deck codes
const DECK_INKS = {
  AS: ['amethyst','sapphire'], ES: ['emerald','sapphire'], AbS: ['amber','sapphire'],
  AmAm: ['amber','amethyst'], AbE: ['amber','emerald'], AbSt: ['amber','steel'],
  AmySt: ['amethyst','steel'], SSt: ['sapphire','steel'], AbR: ['amber','ruby'],
  AmyR: ['amethyst','ruby'], AmyE: ['amethyst','emerald'], RS: ['ruby','sapphire'],
  ER: ['emerald','ruby'], ESt: ['emerald','steel'], RSt: ['ruby','steel'],
};

const DECK_NAMES = {
  AS:'Amethyst-Sapphire', ES:'Emerald-Sapphire', AbS:'Amber-Sapphire',
  AmAm:'Amber-Amethyst', AbE:'Amber-Emerald', AbSt:'Amber-Steel',
  AmySt:'Amethyst-Steel', SSt:'Sapphire-Steel', AbR:'Amber-Ruby',
  AmyR:'Amethyst-Ruby', AmyE:'Amethyst-Emerald', RS:'Ruby-Sapphire',
  ER:'Emerald-Ruby', ESt:'Emerald-Steel', RSt:'Ruby-Steel',
};

const INK_COLORS = {
  amber: '#D4943A', amethyst: '#7B3FA0', emerald: '#2A8F4E',
  ruby: '#C0392B', sapphire: '#2471A3', steel: '#6C7A89',
};

function inkDots(deckCode) {
  const inks = DECK_INKS[deckCode] || [];
  return inks.map(i => `<span class="ink-dot" style="background:${INK_COLORS[i]}"></span>`).join('');
}

function wrClass(wr) {
  if (wr >= 55) return 'wr-high';
  if (wr <= 45) return 'wr-low';
  return 'wr-mid';
}

function wrColor(wr) {
  if (wr >= 55) return 'var(--green)';
  if (wr <= 45) return 'var(--red)';
  return 'var(--yellow)';
}
