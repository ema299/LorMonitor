/**
 * Team Coaching — Animated Replay Viewer + Hand Panel
 *
 * Team-coaching replay viewer with its own cards DB cache and card image helper.
 * Adds: DOM-persistent board, sequential per-action animation, drawArrow, spell overlay, hand panel
 */

// ═══ STATE ═══
let tcReplayData = null;
let tcContainer = null;
let tcSnapIdx = 0;
let tcPlaying = false;
let tcPlayTimer = null;
let tcSpeed = 0.5; // 0.5, 1, 2, 4
let tcAbort = false;
let tcAnimating = false;
let tcCardsDB = null;

const TC_SET_MAP = {TFC:1,ROTF:2,ITI:3,URR:4,SHS:5,AZS:6,ARI:7,ROJ:8,FAB:9,WITW:10,WIS:11,WUN:12,'1':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'11':11,'12':12};
const TC_INK_CLASS = {Amber:'amber',Amethyst:'amethyst',Emerald:'emerald',Ruby:'ruby',Sapphire:'sapphire',Steel:'steel'};

function tcCardImg(card) {
  if (!card || !card.set || !card.number) return '';
  const sets = card.set.split('\n').map(s => s.trim());
  const nums = card.number.split('\n').map(n => n.trim());
  for (let i = 0; i < sets.length; i++) {
    const sn = TC_SET_MAP[sets[i]];
    const cn = (nums[i] || nums[0]).replace(/^0+/, '') || '0';
    if (sn && cn !== '-' && cn !== '0') return `https://cards.duels.ink/lorcana/en/thumbnail/${sn}-${cn}.webp`;
  }
  return '';
}

async function tcEnsureCardsDB() {
  if (tcCardsDB) return tcCardsDB;
  try {
    tcCardsDB = await (await fetch('/api/replay/cards_db')).json();
  } catch (_) {
    tcCardsDB = {};
  }
  return tcCardsDB;
}

function tcShortName(name) {
  if (!name) return { b: '', s: '' };
  if (name.includes(' - ')) {
    const [b, s] = name.split(' - ', 2);
    return { b, s: s.length > 12 ? s.slice(0, 12) + '..' : s };
  }
  return { b: name.length > 18 ? name.slice(0, 18) + '..' : name, s: '' };
}

function tcDeckUser() {
  try {
    return (localStorage.getItem('pf_duels_nick') || '').trim();
  } catch (_) {
    return '';
  }
}

function tcGetAuthToken() {
  const keys = ['lm_access_token', 'access_token', 'auth_access_token'];
  for (const key of keys) {
    const val = localStorage.getItem(key);
    if (val) return val;
  }
  return '';
}

async function tcFetch(url, options = {}) {
  const token = tcGetAuthToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetch(url, { ...options, headers });
}

// ═══ INIT ═══
function tcInit(containerId) {
  tcContainer = document.getElementById(containerId);
  if (!tcContainer) return;
  tcContainer.innerHTML = `
    <div class="tc-upload-zone">
      <div class="tc-upload-inner" ondragover="event.preventDefault();this.classList.add('tc-drag-over')"
           ondragleave="this.classList.remove('tc-drag-over')"
           ondrop="event.preventDefault();this.classList.remove('tc-drag-over');tcHandleDrop(event)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:36px;height:36px;opacity:0.4;margin-bottom:6px">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
        </svg>
        <div style="font-weight:600;margin-bottom:4px">Drop .replay.gz files here</div>
        <div style="font-size:0.82em;color:var(--text2)">or <label style="color:var(--gold);cursor:pointer;text-decoration:underline">
          <input type="file" accept=".gz,.replay,.replay.gz" multiple style="display:none" onchange="tcHandleFiles(this.files)">browse</label></div>
      </div>
      <div id="tc-upload-status" style="margin-top:8px"></div>
    </div>
    <div id="tc-replay-list" style="margin-top:12px"></div>
    <div id="tc-viewer-area" style="margin-top:16px"></div>`;
  tcLoadReplayList();
}

// ═══ UPLOAD ═══
// Privacy layer §24.6: replay upload requires an explicit consent. We check
// localStorage as a fast path; on first upload per browser we show a modal
// that records the acceptance both client-side and server-side (POST
// /api/user/consent). Backend enforces consent too — client-side gating is
// UX, not security.
const TC_REPLAY_CONSENT_VERSION = '1.0';
const TC_REPLAY_CONSENT_KEY = 'tc_replay_upload_consent_v' + TC_REPLAY_CONSENT_VERSION;

async function tcHandleDrop(e) {
  if (!e.dataTransfer.files.length) return;
  if (!(await tcEnsureReplayConsent())) return;
  await tcUpload(e.dataTransfer.files);
}
async function tcHandleFiles(files) {
  if (!files.length) return;
  if (!(await tcEnsureReplayConsent())) return;
  await tcUpload(files);
}

async function tcEnsureReplayConsent() {
  if (localStorage.getItem(TC_REPLAY_CONSENT_KEY) === '1') return true;
  return new Promise((resolve) => tcShowConsentModal(resolve));
}

function tcShowConsentModal(resolve) {
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;';
  overlay.innerHTML = `
    <div style="background:var(--bg1,#1a1a1a);color:var(--text,#eee);border:1px solid var(--gold,#D4A03A);border-radius:8px;max-width:480px;padding:20px;font-size:0.92em;line-height:1.5">
      <div style="font-weight:700;color:var(--gold,#D4A03A);font-size:1.05em;margin-bottom:10px">Consent required — replay upload</div>
      <div style="margin-bottom:12px">
        Board Lab stores the replay file you upload so you (and coaches you share it with) can review it later.
        The file stays private by default. You can delete it at any time from your account.
      </div>
      <div style="margin-bottom:16px;font-size:0.85em;color:var(--text2,#aaa)">
        By clicking Accept, you allow Lorcana Monitor to keep your uploaded replays associated with your account
        for coaching and personal review. This consent version is <strong>${TC_REPLAY_CONSENT_VERSION}</strong>.
      </div>
      <div style="display:flex;gap:10px;justify-content:flex-end">
        <button id="tc-consent-cancel" style="background:transparent;border:1px solid var(--text2,#666);color:var(--text,#eee);padding:6px 12px;border-radius:4px;cursor:pointer">Cancel</button>
        <button id="tc-consent-accept" style="background:var(--gold,#D4A03A);color:#000;border:0;padding:6px 14px;border-radius:4px;cursor:pointer;font-weight:600">Accept &amp; Continue</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const close = (accepted) => {
    overlay.remove();
    resolve(accepted);
  };

  overlay.querySelector('#tc-consent-cancel').onclick = () => close(false);
  overlay.querySelector('#tc-consent-accept').onclick = async () => {
    try {
      await tcFetch('/api/user/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'replay_upload', version: TC_REPLAY_CONSENT_VERSION }),
      });
      localStorage.setItem(TC_REPLAY_CONSENT_KEY, '1');
      close(true);
    } catch (err) {
      // If server call fails, do NOT set localStorage flag — next upload will
      // re-prompt, and upload itself will fail server-side (412) without
      // consent persisted in preferences.
      const status = document.getElementById('tc-upload-status');
      if (status) status.innerHTML = `<div style="color:var(--red);font-size:0.85em">Consent save failed: ${err.message}</div>`;
      close(false);
    }
  };
}

async function tcUpload(files) {
  const status = document.getElementById('tc-upload-status');
  if (!status) return;
  status.innerHTML = '';
  for (const file of files) {
    const form = new FormData();
    form.append('file', file);
    try {
      const resp = await tcFetch('/api/v1/team/replay/upload', { method: 'POST', body: form });
      const data = await resp.json();
      if (data.status === 'ok') status.innerHTML += `<div style="color:var(--green);font-size:0.85em">\u2713 ${data.player} vs ${data.opponent} (${data.turns} turns)</div>`;
      else if (data.status === 'needs_assignment') status.innerHTML += `<div style="color:var(--gold);font-size:0.85em">\u26a0 ${file.name}: ${data.player_names['1']} vs ${data.player_names['2']}</div>`;
      else status.innerHTML += `<div style="color:var(--red);font-size:0.85em">\u2717 ${file.name}: ${data.detail || data.error || 'Error'}</div>`;
    } catch (err) { status.innerHTML += `<div style="color:var(--red);font-size:0.85em">\u2717 ${err.message}</div>`; }
  }
  tcLoadReplayList();
}

// ═══ REPLAY LIST ═══
async function tcLoadReplayList(playerFilter) {
  const el = document.getElementById('tc-replay-list'); if (!el) return;
  const url = playerFilter ? `/api/v1/team/replay/list?player=${encodeURIComponent(playerFilter)}` : '/api/v1/team/replay/list';
  try {
    const list = await (await tcFetch(url)).json();
    if (!list.length) { el.innerHTML = '<div style="color:var(--text2);font-size:0.85em;padding:8px">No replays uploaded yet</div>'; return; }
    el.innerHTML = '<div style="font-weight:600;margin-bottom:8px;font-size:0.9em">Uploaded Replays</div>' +
      list.map(r => `<div class="tc-replay-row" onclick="tcLoadReplay('${r.game_id}')">
        <span style="color:${r.winner===1?'var(--green)':'var(--red)'};font-weight:700">${r.winner===1?'W':'L'}</span>
        <strong>${r.player||'?'}</strong> vs ${r.opponent} \u2014 T${r.turns}
        <span style="color:var(--text2);font-size:0.8em;margin-left:auto">${(r.created_at||'').split('T')[0]}</span>
      </div>`).join('');
    // Auto-load first replay
    if (list.length && list[0].game_id) tcLoadReplay(list[0].game_id);
  } catch (err) { el.innerHTML = `<div style="color:var(--red);font-size:0.85em">Error: ${err.message}</div>`; }
}

// ═══ LOAD REPLAY ═══
async function tcLoadReplay(gameId) {
  const area = document.getElementById('tc-viewer-area'); if (!area) return;
  area.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text2)">Loading...</div>';
  tcAbort = true; tcPlaying = false; clearTimeout(tcPlayTimer);
  wbOpen = false;
  wbSelectedUid = null;
  wbArrowSvgs = [];

  try { tcReplayData = await (await tcFetch(`/api/v1/team/replay/${gameId}`)).json(); }
  catch (err) { area.innerHTML = `<div style="color:var(--red);padding:20px">${err.message}</div>`; return; }

  const snaps = tcReplayData.snapshots;
  if (!snaps || !snaps.length) { area.innerHTML = '<div style="color:var(--red);padding:20px">No data</div>'; return; }

  await tcEnsureCardsDB();

  const p = tcReplayData.player_names || {};
  const persp = tcReplayData.perspective || 1;
  const ourName = p[String(persp)] || 'You', oppName = p[String(persp===1?2:1)] || 'Opponent';

  // Build turn strip
  const turns = [...new Set(snaps.filter(s=>s.turn>0).map(s=>s.turn))].sort((a,b)=>a-b);
  const turnStrip = turns.map(t => `<div class="tc-turn-pill" data-turn="${t}" id="tc-tp-${t}">T${t}</div>`).join('');

  area.innerHTML = `<div class="tc-wrap">
    <div class="tc-top-bar">
      <button class="tc-close" onclick="tcStop();document.getElementById('tc-viewer-area').innerHTML=''">\u00d7</button>
      <span class="tc-title">${ourName} vs ${oppName}</span>
      <span class="tc-badge-wr" style="color:${tcReplayData.winner===persp?'var(--green)':'var(--red)'}">${tcReplayData.winner===persp?'WIN':'LOSS'}</span>
      <span class="tc-badge-hand">\ud83d\udd13 Full Hand</span>
    </div>
    <div class="tc-turn-strip" id="tc-turn-strip">${turnStrip}</div>
    <div class="tc-controls">
      <button class="tc-btn" onclick="tcGoTo(0)">\u23ee</button>
      <button class="tc-btn" onclick="tcPrev()">\u25c0</button>
      <button class="tc-btn tc-btn-play" id="tc-btn-play" onclick="tcTogglePlay()">\u25b6</button>
      <button class="tc-btn" onclick="tcNext()">\u25b6</button>
      <button class="tc-btn" onclick="tcGoTo(${snaps.length-1})">\u23ed</button>
      <button class="tc-btn tc-btn-speed" onclick="tcCycleSpeed()" id="tc-btn-speed">0.5x</button>
      <button class="tc-btn tc-btn-wb" onclick="tcToggleWhiteboard()" id="tc-btn-wb" title="Coaching sandbox">&#9998;</button>
      <input type="range" class="tc-slider" id="tc-slider" min="0" max="${snaps.length-1}" value="0" oninput="tcGoTo(+this.value)">
      <span class="tc-step-num" id="tc-step-num">1/${snaps.length}</span>
    </div>
    <div class="tc-action-bar" id="tc-action-bar">Start</div>
    <div class="tc-body">
      <div class="tc-board-wrap" id="tc-board-wrap">
        <div class="tc-field-label">${oppName}</div>
        <div class="tc-field tc-field-opp" id="tc-field-opp"></div>
        <div class="tc-midline">
          <span class="tc-cnt" id="tc-lo">\u2b50 0</span>
          <span class="tc-cnt" id="tc-io">\ud83d\udca7 0</span>
          <span class="tc-mid-sep"></span>
          <span class="tc-cnt" id="tc-iu">\ud83d\udca7 0</span>
          <span class="tc-cnt" id="tc-lu">\u2b50 0</span>
        </div>
        <div class="tc-field tc-field-our" id="tc-field-our"></div>
        <div class="tc-field-label">${ourName}</div>
      </div>
      <div class="tc-side-panel">
        <div class="tc-ink-panel" id="tc-ink-panel">
          <div class="tc-ink-section">
            <div class="tc-ink-label">${oppName} Ink <span id="tc-ink-opp-n"></span></div>
            <div class="tc-ink-cards" id="tc-ink-opp"></div>
          </div>
          <div class="tc-ink-section">
            <div class="tc-ink-label">${ourName} Ink <span id="tc-ink-our-n"></span></div>
            <div class="tc-ink-cards" id="tc-ink-our"></div>
          </div>
        </div>
        <div class="tc-events" id="tc-events"><h4>Events</h4></div>
      </div>
    </div>
    <div class="tc-hand-panel" id="tc-hand-panel">
      <div class="tc-hand-label">Hand <span id="tc-hand-n"></span></div>
      <div class="tc-hand-cards" id="tc-hand-cards"></div>
    </div>
  </div>`;

  tcAbort = false;
  tcSnapIdx = 0;
  tcApplySnap(0, true);
}

// ═══ APPLY SNAPSHOT (DOM diff + animate) ═══
let _tcApplyLock = false;
async function tcApplySnap(idx, skipAnim) {
  const snaps = tcReplayData?.snapshots;
  if (!snaps || idx < 0 || idx >= snaps.length) return;
  // Prevent concurrent calls — skip if already animating (unless skipping anim)
  if (_tcApplyLock && !skipAnim) return;
  if (skipAnim) _tcApplyLock = false; // force unlock on skip (slider drag, goTo)
  _tcApplyLock = !skipAnim;
  try {
  tcSnapIdx = idx;
  const snap = snaps[idx];
  const prev = idx > 0 ? snaps[idx - 1] : null;

  // Update controls
  const slider = document.getElementById('tc-slider');
  if (slider) slider.value = idx;
  const num = document.getElementById('tc-step-num');
  if (num) num.textContent = `${idx+1}/${snaps.length}`;
  const label = document.getElementById('tc-action-bar');
  if (label) label.textContent = snap.label || '';

  // Update turn strip
  document.querySelectorAll('.tc-turn-pill').forEach(p => {
    const t = +p.dataset.turn;
    p.classList.toggle('active', t === snap.turn);
    p.classList.toggle('past', t < snap.turn);
  });
  const activePill = document.getElementById('tc-tp-' + snap.turn);
  if (activePill) activePill.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });

  // Update counters
  const lore = snap.lore || {our:0,opp:0};
  const ink = snap.ink || {our:0,opp:0};
  const $ = id => document.getElementById(id);
  if ($('tc-lu')) $('tc-lu').textContent = '\u2b50 ' + lore.our;
  if ($('tc-lo')) $('tc-lo').textContent = '\u2b50 ' + lore.opp;
  if ($('tc-iu')) $('tc-iu').textContent = '\ud83d\udca7 ' + ink.our;
  if ($('tc-io')) $('tc-io').textContent = '\ud83d\udca7 ' + ink.opp;

  // Diff and update board
  const board = snap.board || {our:[],opp:[]};
  const items = snap.items || {our:[],opp:[]};
  const prevBoard = prev ? (prev.board || {our:[],opp:[]}) : {our:[],opp:[]};
  const prevItems = prev ? (prev.items || {our:[],opp:[]}) : {our:[],opp:[]};

  const allOur = [...board.our, ...items.our];
  const allOpp = [...board.opp, ...items.opp];
  const allPrevOur = [...prevBoard.our, ...prevItems.our];
  const allPrevOpp = [...prevBoard.opp, ...prevItems.opp];

  // ── Animations on OLD DOM (targets still exist) ──

  // Card-hero overlay: dramatic close-up for the card that drives the frame.
  // Triggered for:
  //   - PLAY_CARD character / item (not song) → 'play' or 'shift'
  //   - ACTIVATE_ABILITY                       → 'ability' (with ability name)
  //   - RESPOND_TO_PROMPT with ability_card    → 'ability' (subtle, shorter)
  // Song / action plays keep the existing tcShowSpellOverlay path (which also
  // draws arrows to damaged/removed targets).
  if (!skipAnim && prev && !tcAbort) {
    const at = snap.action_type;
    if (at === 'PLAY_CARD') {
      if (snap.is_song) {
        await tcShowSpellOverlay(snap, prev);
      } else if (snap.played_card) {
        const kind = snap.is_shift ? 'shift' : (snap.is_item ? 'item' : 'play');
        await tcShowCardHero(snap.played_card, kind, {
          subtitle: snap.is_shift ? `Shift onto ${snap.shift_base || '?'}` : null,
          hold: 650,
        });
      } else {
        // Unknown — fall back to legacy spell overlay (hand-diff based)
        await tcShowSpellOverlay(snap, prev);
      }
    } else if (at === 'ACTIVATE_ABILITY' && snap.ability_card) {
      await tcShowCardHero(snap.ability_card, 'ability', {
        subtitle: snap.ability_name || 'Ability',
        hold: 1400,
      });
    } else if (at === 'RESPOND_TO_PROMPT' && snap.ability_card) {
      await tcShowCardHero(snap.ability_card, 'ability', {
        subtitle: snap.ability_name || null,
        hold: 700,
      });
    }
  }

  // Combat arrows — ONLY for ATTACK actions (old DOM has attacker + defender)
  if (!skipAnim && prev && snap.action_type === 'ATTACK' && !tcAbort) {
    let atkIid = null, atkFieldId = null, defFieldId = null, defSideCurr = null, defSidePrev = null;
    for (const [fid, curr, prevC] of [['tc-field-our', allOur, allPrevOur], ['tc-field-opp', allOpp, allPrevOpp]]) {
      // 1) Newly exerted = clear attacker
      let attacker = curr.find(c => {
        const pc = prevC.find(p => p.iid === c.iid);
        return c.exerted && pc && !pc.exerted;
      });
      // 2) Fallback: card that died or took damage while already exerted (mutual kill)
      if (!attacker) {
        const currIids = curr.map(c => c.iid);
        const diedExerted = prevC.find(c => c.exerted && !currIids.includes(c.iid));
        if (diedExerted) attacker = diedExerted;
      }
      if (!attacker) {
        attacker = curr.find(c => {
          const pc = prevC.find(p => p.iid === c.iid);
          return pc && pc.exerted && c.damage > pc.damage;
        });
      }
      if (attacker) {
        atkIid = attacker.iid;
        atkFieldId = fid;
        defFieldId = fid === 'tc-field-our' ? 'tc-field-opp' : 'tc-field-our';
        defSideCurr = fid === 'tc-field-our' ? allOpp : allOur;
        defSidePrev = fid === 'tc-field-our' ? allPrevOpp : allPrevOur;
        break;
      }
    }
    if (atkIid && defFieldId) {
      const srcEl = document.querySelector(`#${atkFieldId} [data-iid="${atkIid}"]`);
      let defIid = null, dmgAmount = 0;
      for (const c of defSideCurr) {
        const pc = defSidePrev.find(p => p.iid === c.iid);
        if (pc && c.damage > pc.damage) { defIid = c.iid; dmgAmount = c.damage - pc.damage; break; }
      }
      if (!defIid) {
        const currIids = defSideCurr.map(c => c.iid);
        const died = defSidePrev.find(c => !currIids.includes(c.iid));
        if (died) defIid = died.iid;
      }
      const tgtEl = defIid ? document.querySelector(`#${defFieldId} [data-iid="${defIid}"]`) : null;
      if (srcEl && tgtEl && !tcAbort) {
        await tcDrawArrow(srcEl, tgtEl, '#ef4444', dmgAmount ? '-' + dmgAmount : '\u2694');
      }
    }
  }

  // Damage transfer (boost/ability): card heals AND another card takes damage or dies in same snapshot
  // If a BOOST happened recently, the boosted card is the real source (e.g. Cheshire Cat)
  if (!skipAnim && prev && snap.action_type !== 'ATTACK' && !tcAbort) {
    for (const [srcFid, srcCurr, srcPrev] of [['tc-field-our', allOur, allPrevOur], ['tc-field-opp', allOpp, allPrevOpp]]) {
      const healed = srcCurr.find(c => {
        const pc = srcPrev.find(p => p.iid === c.iid);
        return pc && c.damage < pc.damage;
      });
      if (!healed) continue;
      const healPc = srcPrev.find(p => p.iid === healed.iid);
      const dmgMoved = healPc.damage - healed.damage;

      // Find target that took damage or died
      let tgtIid = null, tgtFid = null;
      for (const [fid, tCurr, tPrev] of [['tc-field-our', allOur, allPrevOur], ['tc-field-opp', allOpp, allPrevOpp]]) {
        for (const c of tCurr) {
          if (c.iid === healed.iid) continue;
          const pc = tPrev.find(p => p.iid === c.iid);
          if (pc && c.damage > pc.damage) { tgtIid = c.iid; tgtFid = fid; break; }
        }
        if (!tgtIid) {
          const currIids = tCurr.map(c => c.iid);
          const died = tPrev.find(c => c.iid !== healed.iid && !currIids.includes(c.iid));
          if (died) { tgtIid = died.iid; tgtFid = fid; }
        }
        if (tgtIid) break;
      }

      if (tgtIid) {
        // Check if a BOOST happened in recent snapshots — use boosted card as arrow source
        let arrowSrcFid = srcFid, arrowSrcIid = healed.iid;
        const snaps = tcReplayData?.snapshots || [];
        for (let back = idx - 1; back >= Math.max(0, idx - 5); back--) {
          if (snaps[back]?.action_type === 'BOOST') {
            // Find which card was boosted: card on same side as healed, different from healed
            const boostSnap = snaps[back];
            const boostPrev = back > 0 ? snaps[back - 1] : null;
            // The boosted card is typically on the same side, not the healed card
            // We can't know exactly, so use all cards on healed's side as candidates
            // The boosted card likely didn't change stats but is the "caster"
            const sameSide = srcCurr.filter(c => c.iid !== healed.iid);
            if (sameSide.length > 0) {
              // Pick the card that's not the healed one and not the target
              const booster = sameSide.find(c => c.iid !== tgtIid) || sameSide[0];
              arrowSrcIid = booster.iid;
            }
            break;
          }
          if (snaps[back]?.action_type === 'ATTACK' || snaps[back]?.action_type === 'END_TURN') break;
        }

        const srcEl = document.querySelector(`#${arrowSrcFid} [data-iid="${arrowSrcIid}"]`);
        const tgtEl = document.querySelector(`#${tgtFid} [data-iid="${tgtIid}"]`);
        if (srcEl && tgtEl) await tcDrawArrow(srcEl, tgtEl, '#f59e0b', '-' + dmgMoved);
      }
      break;
    }
  }

  // Ability/response effects: card takes damage or dies with no clear source
  // (no attack exert, no heal/transfer, no spell) — show effect highlight
  if (!skipAnim && prev && !tcAbort &&
      (snap.action_type === 'RESPOND_TO_PROMPT' || snap.action_type === 'ACTIVATE_ABILITY') &&
      !document.querySelector('.tc-spell-overlay')) {
    let hadArrow = false; // damage transfer above may have drawn one
    for (const [fid, curr, prevC] of [['tc-field-our', allOur, allPrevOur], ['tc-field-opp', allOpp, allPrevOpp]]) {
      // Cards that took damage
      for (const c of curr) {
        const pc = prevC.find(p => p.iid === c.iid);
        if (pc && c.damage > pc.damage) {
          const el = document.querySelector(`#${fid} [data-iid="${c.iid}"]`);
          if (el) { el.classList.add('tc-ability-hit'); hadArrow = true; }
        }
      }
      // Cards that died
      const currIids = curr.map(c => c.iid);
      for (const pc of prevC) {
        if (!currIids.includes(pc.iid)) {
          const el = document.querySelector(`#${fid} [data-iid="${pc.iid}"]`);
          if (el) { el.classList.add('tc-ability-hit'); hadArrow = true; }
        }
      }
    }
    if (hadArrow) await new Promise(r => setTimeout(r, 400));
  }

  // ── Hand-out: animate the played/inked card leaving the hand BEFORE
  //    the field/hand swap, so the eye follows a clear sequence:
  //    1. card drops from hand (this step, ~280ms)
  //    2. card appears on field / ink (next step)
  //    3. any drawn card slides in from the top
  if (!skipAnim && prev && !tcAbort) {
    const leavingCard = snap.played_card || snap.inked_card;
    if (leavingCard) {
      const handEl = document.getElementById('tc-hand-cards');
      if (handEl) {
        const leavingEl = handEl.querySelector(`.tc-hc[data-name="${leavingCard}"]:not(.tc-hc-leaving)`);
        if (leavingEl) {
          leavingEl.classList.add('tc-hc-leaving');
          await new Promise(r => setTimeout(r, 260));
        }
      }
    }
  }

  // ── NOW update board (death animations + innerHTML swap) ── parallel both sides
  await Promise.all([
    tcUpdateField('tc-field-our', allOur, allPrevOur, skipAnim),
    tcUpdateField('tc-field-opp', allOpp, allPrevOpp, skipAnim)
  ]);

  // Small breath after field settles — lets the pop-in finish before numbers jump
  if (!skipAnim && !tcAbort) await new Promise(r => setTimeout(r, 120));

  // Events log
  tcUpdateEvents(snap, prev);

  // Inkwell
  tcUpdateInkwell(snap);

  // Hand (staggered draw-in for multiple new cards)
  tcUpdateHand(snap.hand || [], prev ? (prev.hand || []) : []);
  if (!skipAnim) {
    const handEl = document.getElementById('tc-hand-cards');
    if (handEl) {
      const newCards = handEl.querySelectorAll('.tc-hc-new');
      newCards.forEach((el, i) => { el.style.animationDelay = (i * 70) + 'ms'; });
    }
  }
  } finally { _tcApplyLock = false; }
}

function tcUpdateEvents(snap, prev) {
  const el = document.getElementById('tc-events'); if (!el) return;
  const at = snap.action_type || '';
  const board = snap.board || {our:[],opp:[]};
  const prevBoard = prev ? (prev.board || {our:[],opp:[]}) : {our:[],opp:[]};
  const lore = snap.lore || {our:0,opp:0};
  const prevLore = prev ? (prev.lore || {our:0,opp:0}) : {our:0,opp:0};
  const ink = snap.ink || {our:0,opp:0};
  const prevInk = prev ? (prev.ink || {our:0,opp:0}) : {our:0,opp:0};

  let events = [];

  // Detect plays (new cards on board) — match by iid
  for (const side of ['our','opp']) {
    const prevIids = prevBoard[side].map(c=>c.iid);
    const prevCopy = [...prevIids];
    for (const c of board[side]) {
      const pi = prevCopy.indexOf(c.iid);
      if (pi >= 0) { prevCopy.splice(pi, 1); }
      else { events.push({icon:'\u25b6', cls:'rv-ep-play', txt:`<b>${tcSn(c.name)}</b> played (${c.cost||'?'})`}); }
    }
    // Deaths
    const currIids = board[side].map(c=>c.iid);
    const currCopy = [...currIids];
    for (const c of prevBoard[side]) {
      const ci = currCopy.indexOf(c.iid);
      if (ci >= 0) { currCopy.splice(ci, 1); }
      else { events.push({icon:'\u2620', cls:'rv-ep-dead', txt:`<b>${tcSn(c.name)}</b> destroyed`}); }
    }
    // Damage changes
    for (const c of board[side]) {
      const pc = prevBoard[side].find(p=>p.iid===c.iid);
      if (pc && c.damage > pc.damage) {
        events.push({icon:'\ud83d\udca5', cls:'rv-ep-dead', txt:`<b>${tcSn(c.name)}</b> -${c.damage-pc.damage} (${c.damage} total)`});
      }
    }
    // Exert (quest)
    for (const c of board[side]) {
      const pc = prevBoard[side].find(p=>p.iid===c.iid && !p.exerted);
      if (pc && c.exerted && at === 'QUEST') {
        const loreDiff = lore[side] - prevLore[side];
        events.push({icon:'\u2b50', cls:'rv-ep-quest', txt:`<b>${tcSn(c.name)}</b> +${loreDiff||'?'} lore`});
      }
    }
  }

  // Ink
  if (at === 'ADD_TO_INK') {
    for (const side of ['our','opp']) {
      if (ink[side] > prevInk[side]) {
        // Find which card left hand
        if (side === 'our' && snap.hand && prev && prev.hand) {
          const prevH = [...prev.hand];
          for (const name of prevH) {
            if (!snap.hand.includes(name) || snap.hand.filter(n=>n===name).length < prevH.filter(n=>n===name).length) {
              events.push({icon:'\u25cf', cls:'', txt:`Ink: <b>${tcSn(name)}</b>`});
              break;
            }
          }
        }
        if (!events.length) events.push({icon:'\u25cf', cls:'', txt:'Ink +1'});
      }
    }
  }

  // Draw
  if (snap.hand && prev && prev.hand && snap.hand.length > prev.hand.length) {
    const prevH = [...prev.hand];
    for (const name of snap.hand) {
      const pi = prevH.indexOf(name);
      if (pi >= 0) { prevH.splice(pi, 1); }
      else { events.push({icon:'\ud83c\udccf', cls:'rv-ep-draw', txt:`Draw: <b>${tcSn(name)}</b>`}); }
    }
  }

  // Ability / Response
  if (at === 'ACTIVATE_ABILITY') events.push({icon:'\u2728', cls:'rv-ep-ab', txt:'Ability activated'});
  if (at === 'RESPOND_TO_PROMPT') events.push({icon:'\u2728', cls:'rv-ep-ab', txt:'Response'});
  if (at === 'BOOST') events.push({icon:'\u2764', cls:'', txt:'Boost'});
  if (at === 'ATTACK' && !events.some(e=>e.icon==='\u2620')) events.push({icon:'\u2694', cls:'rv-ep-chal', txt:'Attack'});

  // Render
  let html = `<h4>${snap.label || ''}</h4>`;
  if (!events.length && at !== 'END_TURN' && at !== 'INITIAL') events.push({icon:'\u2022', cls:'', txt: at.replace(/_/g,' ')});
  for (const ev of events) {
    html += `<div class="rv-ev"><span class="rv-ei ${ev.cls}">${ev.icon}</span><span>${ev.txt}</span></div>`;
  }
  el.innerHTML = html;
}

function tcSn(name) {
  if (!name) return '?';
  if (name.includes(' - ')) return name.split(' - ')[0];
  return name.length > 18 ? name.slice(0,18)+'..' : name;
}

// ═══ DOM-PERSISTENT BOARD UPDATE ═══
async function tcUpdateField(containerId, cards, prevCards, skipAnim) {
  const el = document.getElementById(containerId);
  if (!el) return;

  // 1. Animate deaths BEFORE replacing DOM — match by iid
  if (!skipAnim) {
    const currIids = cards.map(c => c.iid);
    const currCopy = [...currIids];
    for (const pc of prevCards) {
      const ci = currCopy.indexOf(pc.iid);
      if (ci >= 0) { currCopy.splice(ci, 1); }
      else {
        const deadEl = el.querySelector(`[data-iid="${pc.iid}"]`);
        if (deadEl) deadEl.classList.add('tc-dying');
      }
    }
    // Also flash damage changes on existing DOM before swap
    for (const c of cards) {
      const pc = prevCards.find(p => p.iid === c.iid);
      if (pc && c.damage > pc.damage) {
        const dmgEl = el.querySelector(`[data-iid="${c.iid}"] .rv-dmg`);
        if (dmgEl) dmgEl.classList.add('tc-dmg-flash');
      }
    }
    // Wait for death animation (fixed, clearly visible)
    if (el.querySelector('.tc-dying')) {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  // 2. Build card HTML — use data-iid for unique identification
  const prevIids = prevCards.map(c => c.iid);
  const newHtml = cards.map(c => {
    const isNew = !prevIids.includes(c.iid);
    const db = (tcCardsDB || {})[c.name] || {};
    const imgUrl = tcCardImg(db);
    const isCh = (db.type||'').toLowerCase().includes('character');
    const ink = TC_INK_CLASS[(db.ink || '').trim()] || '';
    const { b, s } = tcShortName(c.name);
    const dmg = c.damage || 0;
    const will = parseInt(db.will) || 0;
    const pc = prevCards.find(p => p.iid === c.iid);
    const dmgChanged = !skipAnim && pc && c.damage > pc.damage;

    let cls = 'rv-mc';
    if (ink) cls += ' rv-ink-' + ink;
    if (c.exerted) cls += ' rv-exerted';
    if (!skipAnim && isNew) cls += ' tc-anim-play tc-new-glow';
    const dmgCls = dmgChanged ? ' tc-dmg-flash' : '';
    const dmgHtml = isCh && dmg > 0 ? `<div class="rv-dmg${dmgCls}">-${dmg}</div>` : '';
    const style = imgUrl ? `background-image:url(${imgUrl});background-size:cover;background-position:center 15%` : '';

    return `<div class="${cls}" style="${style}" data-iid="${c.iid}" data-name="${c.name}" title="${c.name}">
      <div class="rv-cost">${db.cost||'?'}</div>${dmgHtml}
      <div class="rv-ovl"><div class="rv-cn2">${b}</div>${s?`<div style="font-size:0.45rem;color:rgba(255,255,255,0.6)">${s}</div>`:''}
      ${isCh?`<div class="rv-stats">${db.str?'<span>\u2694'+db.str+'</span>':''}${db.will?`<span>\ud83d\udee1${dmg>0?(will-dmg)+'/'+will:will}</span>`:''}${db.lore?'<span>\u2b50'+db.lore+'</span>':''}</div>`:''}</div></div>`;
  }).join('');

  el.innerHTML = newHtml;
}

// ═══ CARD HERO OVERLAY ═══
// Generic dramatic close-up of a single card. Scales with tcSpeed so the
// show-case doesn't drag on fast-forward. Kinds map to different glow colors
// in CSS: 'play' (gold), 'item' (amber), 'shift' (cyan), 'ability' (violet).
async function tcShowCardHero(cardName, kind, opts) {
  if (!cardName || tcAbort) return null;
  const db = (tcCardsDB || {})[cardName] || {};
  const img = tcCardImg(db);
  if (!img) return null;

  const boardWrap = document.getElementById('tc-board-wrap');
  if (!boardWrap) return null;

  const hold = Math.max(250, (opts?.hold ?? 700) / Math.max(tcSpeed, 0.5));
  const subtitle = opts?.subtitle || '';
  const cost = db.cost != null ? db.cost : '';

  const overlay = document.createElement('div');
  overlay.className = `tc-spell-overlay tc-hero-${kind}`;
  overlay.innerHTML = `
    <div class="tc-hero-card tc-hero-${kind}-card">
      ${cost !== '' ? `<div class="tc-hero-cost">${cost}</div>` : ''}
      <img src="${img}" alt="${cardName}">
      <div class="tc-hero-name">${cardName}</div>
      ${subtitle ? `<div class="tc-hero-sub">${subtitle}</div>` : ''}
    </div>`;
  boardWrap.style.position = 'relative';
  boardWrap.appendChild(overlay);

  // Pop-in (300ms) + hold + fade (300ms). tcAbort can interrupt any of them.
  const steps = [{t: 300}, {t: hold}];
  for (const s of steps) {
    if (tcAbort) break;
    await new Promise(r => setTimeout(r, s.t));
  }
  overlay.style.opacity = '0';
  await new Promise(r => setTimeout(r, 240));
  overlay.remove();
  return overlay;
}

// ═══ SPELL OVERLAY (song/action, with arrows to damaged targets) ═══
async function tcShowSpellOverlay(snap, prev) {
  if (!prev || snap.action_type !== 'PLAY_CARD' || tcAbort) return;
  // Find card that left hand but didn't appear on board (= spell)
  const prevH = [...(prev.hand || [])];
  const currH = [...(snap.hand || [])];  // copy to avoid mutating snapshot
  let spellName = null;
  for (const name of prevH) {
    const pi = currH.indexOf(name);
    if (pi >= 0) { currH.splice(pi, 1); }
    else { spellName = name; break; }
  }
  if (!spellName) return;
  const db = (tcCardsDB || {})[spellName] || {};
  const tp = (db.type || '').toLowerCase();
  if (!tp.includes('action') && !tp.includes('song')) return;

  const img = tcCardImg(db);
  if (!img) return;

  const boardWrap = document.getElementById('tc-board-wrap');
  if (!boardWrap) return;

  // Create overlay
  const overlay = document.createElement('div');
  overlay.className = 'tc-spell-overlay';
  const isSong = tp.includes('song');
  overlay.innerHTML = `
    <div class="tc-spell-card ${isSong ? 'tc-spell-song' : ''}">
      <img src="${img}" alt="${spellName}">
      <div class="tc-spell-name">${spellName}</div>
    </div>`;
  boardWrap.style.position = 'relative';
  boardWrap.appendChild(overlay);

  // Wait for pop-in animation, then check for effects
  await new Promise(r => setTimeout(r, 350));

  // Draw arrows from spell to affected cards (damage increased or cards died)
  if (!tcAbort) {
    const prevBoard = prev.board || {our:[], opp:[]};
    const currBoard = snap.board || {our:[], opp:[]};
    const spellEl = overlay.querySelector('.tc-spell-card');
    for (const [side, fieldId] of [['our','tc-field-our'],['opp','tc-field-opp']]) {
      // Damage targets
      for (const c of currBoard[side]) {
        const pc = prevBoard[side].find(p => p.iid === c.iid);
        if (pc && c.damage > pc.damage) {
          const tgtEl = document.querySelector(`#${fieldId} [data-iid="${c.iid}"]`);
          if (spellEl && tgtEl) await tcDrawArrow(spellEl, tgtEl, '#a855f7', '-' + (c.damage - pc.damage));
        }
      }
      // Removal targets (card was in prev but not in curr)
      const currIids = currBoard[side].map(c => c.iid);
      for (const pc of prevBoard[side]) {
        if (!currIids.includes(pc.iid)) {
          const tgtEl = document.querySelector(`#${fieldId} [data-iid="${pc.iid}"]`);
          if (spellEl && tgtEl) await tcDrawArrow(spellEl, tgtEl, '#a855f7', '\ud83d\udc80');
        }
      }
    }
  }

  // Fade out
  overlay.style.opacity = '0';
  await new Promise(r => setTimeout(r, 300));
  overlay.remove();
}

// ═══ ARROW RENDERING ═══
async function tcDrawArrow(srcEl, tgtEl, color, midLabel) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:100;width:100vw;height:100vh';
  const sR = srcEl.getBoundingClientRect(), tR = tgtEl.getBoundingClientRect();
  const x1=sR.left+sR.width/2, y1=sR.top+sR.height/2, x2=tR.left+tR.width/2, y2=tR.top+tR.height/2;
  const dx=x2-x1, dy=y2-y1, len=Math.sqrt(dx*dx+dy*dy)||1, off=Math.min(60,len*0.3);
  const cx=(x1+x2)/2+(-dy/len)*off, cy=(y1+y2)/2+(dx/len)*off;
  const mx=(x1+x2)/2, my=(y1+y2)/2;
  const d = `M${x1} ${y1} Q${cx} ${cy} ${x2} ${y2}`;
  const col = color || '#ef4444';
  svg.innerHTML = `<defs><filter id="tcag"><feGaussianBlur in="SourceGraphic" stdDeviation="6"/></filter><marker id="tcah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${col}"/></marker></defs><path d="${d}" stroke="${col}" stroke-width="16" stroke-opacity="0.12" fill="none" filter="url(#tcag)"/><path d="${d}" stroke="${col}" stroke-width="6" fill="none" marker-end="url(#tcah)" style="stroke-dasharray:1000;stroke-dashoffset:1000;animation:tcDrawArrow .35s ease forwards"/><foreignObject x="${mx-20}" y="${my-20}" width="40" height="40" style="overflow:visible"><div xmlns="http://www.w3.org/1999/xhtml" style="width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:${col};box-shadow:0 0 20px ${col};color:#fff;font-weight:800;font-size:0.9rem;animation:tcCombatPulse 0.3s ease-in-out">${midLabel||''}</div></foreignObject>`;
  document.body.appendChild(svg);
  srcEl.style.boxShadow = `0 0 14px ${col}`;
  tgtEl.style.boxShadow = `0 0 14px ${col}`;
  await new Promise(r => setTimeout(r, 500));
  srcEl.style.boxShadow = ''; tgtEl.style.boxShadow = '';
  svg.remove();
}

// ═══ INKWELL PANEL ═══
function tcUpdateInkwell(snap) {
  const inkwell = snap.inkwell || {our:[], opp:[]};
  const ink = snap.ink || {our:0, opp:0};

  for (const side of ['our', 'opp']) {
    const el = document.getElementById('tc-ink-' + side);
    const nEl = document.getElementById('tc-ink-' + side + '-n');
    if (!el) continue;

    const cards = inkwell[side] || [];
    const available = cards.filter(c => !c.exerted).length;
    const total = cards.length || ink[side] || 0;
    if (nEl) nEl.textContent = `(${available}/${total})`;

    el.innerHTML = cards.map(c => {
      const name = c.name;
      const cls = c.exerted ? 'tc-ink-card tc-ink-exerted' : 'tc-ink-card';
      if (!name) {
        // Opponent hidden card
        return `<div class="${cls}" title="Hidden ink"><div class="tc-ink-hidden">?</div></div>`;
      }
      const db = (tcCardsDB || {})[name] || {};
      const img = tcCardImg(db);
      const short = name.split(' - ')[0];
      return `<div class="${cls}" title="${name}${c.exerted?' (used)':' (available)'}">
        ${img ? `<img src="${img}" alt="${short}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
        <div class="tc-ink-name" ${img?'style="display:none"':''}>${short}</div>
      </div>`;
    }).join('');
  }
}

// ═══ HAND PANEL ═══
function tcUpdateHand(hand, prevHand) {
  const el = document.getElementById('tc-hand-cards');
  const n = document.getElementById('tc-hand-n');
  if (!el) return;
  if (n) n.textContent = `(${hand.length})`;

  const prevCopy = [...prevHand];
  el.innerHTML = hand.map(name => {
    const pi = prevCopy.indexOf(name);
    const isNew = pi < 0;
    if (pi >= 0) prevCopy.splice(pi, 1);
    const db = (tcCardsDB || {})[name] || {};
    const img = tcCardImg(db);
    const short = name.split(' - ')[0];
    return `<div class="tc-hc${isNew?' tc-hc-new':''}" data-name="${name}" title="${name}">
      ${img ? `<img src="${img}" alt="${short}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
      <div class="tc-hc-name" ${img?'style="display:none"':''}>${short}</div>
    </div>`;
  }).join('');
}

// ═══ NAVIGATION ═══
function tcGoTo(idx) { tcAbort = true; tcAnimating = false; clearTimeout(tcPlayTimer); setTimeout(() => { tcAbort = false; tcApplySnap(idx, true); }, 60); }
function tcNext() { if (tcAnimating) return; tcAbort = true; clearTimeout(tcPlayTimer); setTimeout(() => { tcAbort = false; tcApplySnap(tcSnapIdx + 1, false); }, 60); }
function tcPrev() { if (tcAnimating) return; tcAbort = true; clearTimeout(tcPlayTimer); setTimeout(() => { tcAbort = false; tcApplySnap(tcSnapIdx - 1, true); }, 60); }
function tcStop() { tcPlaying = false; tcAbort = true; clearTimeout(tcPlayTimer); const b = document.getElementById('tc-btn-play'); if(b) b.textContent = '\u25b6'; }

function tcTogglePlay() {
  if (tcPlaying) { tcStop(); return; }
  tcPlaying = true;
  const btn = document.getElementById('tc-btn-play');
  if (btn) btn.textContent = '\u23f8';
  tcPlayTick();
}

async function tcPlayTick() {
  if (!tcPlaying || !tcReplayData) return;
  const snaps = tcReplayData.snapshots || [];
  if (tcSnapIdx >= snaps.length - 1) { tcStop(); return; }
  tcAbort = false;
  tcAnimating = true;
  await tcApplySnap(tcSnapIdx + 1, false);
  tcAnimating = false;
  if (!tcPlaying) return;
  // Post-animation pause: gives user time to read the board state.
  // Longer on meaningful actions so the eye can follow the sub-sequence
  // (hand out → card appear → draw in), shorter on End turn / mulligan.
  const snap = snaps[tcSnapIdx];
  const quiet = ['END_TURN', 'MULLIGAN', 'CHOOSE_STARTING_PLAYER', 'INITIAL'].includes(snap?.action_type);
  const base = quiet ? 400 : 850;
  const pause = Math.max(200, base / tcSpeed);
  tcPlayTimer = setTimeout(tcPlayTick, pause);
}

function tcCycleSpeed() {
  const speeds = [0.5, 1, 2, 4];
  const labels = ['0.5x', '1x', '2x', '4x'];
  const i = speeds.indexOf(tcSpeed);
  tcSpeed = speeds[(i + 1) % speeds.length];
  const btn = document.getElementById('tc-btn-speed');
  if (btn) btn.textContent = labels[(i + 1) % labels.length];
}

// ═══ WHITEBOARD (COACHING SANDBOX) ═══
let wbOpen = false;
let wbMode = 'snapshot';
let wbDeckState = { our: [], opp: [] }; // {name, qty, remaining}
let wbDeckPile = { our: [], opp: [] };  // ordered list of card names for draw simulation
let wbState = null;
let wbSelectedUid = null;
let wbUidCounter = 1;
let wbTurn = 1;

const WB_CANVAS_WIDTH = 760;
const WB_CANVAS_HEIGHT = 210;
const WB_ZONE_ORDER = [
  'opp-board', 'opp-hand', 'opp-ink', 'opp-discard',
  'our-board', 'our-hand', 'our-ink', 'our-discard',
];

function tcToggleWhiteboard() {
  wbOpen = !wbOpen;
  const btn = document.getElementById('tc-btn-wb');
  if (btn) btn.classList.toggle('tc-btn-active', wbOpen);

  let panel = document.getElementById('tc-whiteboard');
  if (!wbOpen) {
    if (panel) panel.remove();
    wbSelectedUid = null;
    wbArrowSvgs = [];
    wbMode = 'snapshot';
    return;
  }

  // Pause replay
  tcStop();

  // Clone current board state
  const snaps = tcReplayData?.snapshots || [];
  const snap = snaps[tcSnapIdx] || {};
  wbState = wbBuildStateFromSnapshot(snap);
  wbTurn = Number(snap.turn || 1);
  wbSelectedUid = null;
  wbMode = 'snapshot';
  wbDeckState = { our: [], opp: [] };
  wbDeckPile = { our: [], opp: [] };
  wbArrowSvgs = [];

  // Create whiteboard overlay
  const wrap = document.querySelector('.tc-wrap');
  if (!wrap) return;

  panel = document.createElement('div');
  panel.id = 'tc-whiteboard';
  panel.className = 'wb-panel';

  const p = tcReplayData.player_names || {};
  const persp = tcReplayData.perspective || 1;
  const ourName = p[String(persp)] || 'You';
  const oppName = p[String(persp===1?2:1)] || 'Opponent';

  panel.innerHTML = `
    <div class="wb-header">
      <div class="wb-header-main">
        <div class="wb-title-row">
          <span class="wb-title">&#9998; Coaching Sandbox</span>
          <span class="wb-turn-pill" id="wb-turn-pill">Turn ${snap.turn || '?'}</span>
        </div>
        <span class="wb-tip">Drag cards freely. Double click to ready or exert. Right-drag to trace combat lines.</span>
      </div>
      <div class="wb-header-controls">
        <button class="tc-btn wb-mode-btn" onclick="wbResetToSnapshot()" title="Load current replay snapshot">Snapshot</button>
        <button class="tc-btn wb-mode-btn" onclick="wbStartSandbox()" title="Start empty sandbox">New Sim</button>
        <select id="wb-deck-select-our" onchange="wbLoadDeck('our', this.value)">
          <option value="">Your deck</option>
        </select>
        <select id="wb-deck-select-opp" onchange="wbLoadDeck('opp', this.value)">
          <option value="">Opponent deck</option>
        </select>
        <button class="tc-btn wb-ctrl-btn" onclick="wbClearArrows()" title="Clear arrows">&#x2215;</button>
        <button class="tc-btn wb-ctrl-btn" onclick="wbReset()" title="Reset to snapshot">&#x21ba;</button>
        <button class="tc-btn wb-ctrl-btn" onclick="tcToggleWhiteboard()" title="Close">&#x2715;</button>
      </div>
    </div>
    <div class="wb-toolbar" id="wb-toolbar"></div>
    <div class="wb-simbar" id="wb-simbar"></div>
    <div class="wb-stage" id="wb-stage">
      <div class="wb-side wb-side-opp">
        <div class="wb-side-header">
          <div class="wb-side-ident">
            <span class="wb-side-tag opp">Opponent</span>
            <div class="wb-player-name">${oppName}</div>
          </div>
          <div class="wb-side-counters">
            <span class="tc-cnt">&#x2b50; <input type="number" class="wb-counter" id="wb-lore-opp" value="${(snap.lore||{}).opp||0}" min="0" max="20" title="Opp lore"></span>
            <span class="tc-cnt">&#x1f4a7; <input type="number" class="wb-counter" id="wb-ink-opp" value="${(snap.ink||{}).opp||0}" min="0" max="15" title="Opp ink"></span>
          </div>
        </div>
        <div class="wb-zone-row wb-zone-row-top">
          <div class="wb-zone wb-zone-tray">
            <div class="wb-zone-label">Opponent Hand <span id="wb-opp-hand-n"></span></div>
            <div class="wb-zone-cards wb-zone-tray-cards" id="wb-opp-hand"></div>
          </div>
          <div class="wb-zone wb-zone-tray wb-zone-mini">
            <div class="wb-zone-label">Opponent Ink <span id="wb-opp-ink-n"></span></div>
            <div class="wb-zone-cards wb-zone-small" id="wb-opp-ink"></div>
          </div>
          <div class="wb-zone wb-zone-tray wb-zone-mini">
            <div class="wb-zone-label">Opponent Discard <span id="wb-opp-discard-n"></span></div>
            <div class="wb-zone-cards wb-zone-small" id="wb-opp-discard"></div>
          </div>
        </div>
        <div class="wb-zone wb-zone-board">
          <div class="wb-zone-label">Opponent Board</div>
          <div class="wb-canvas" id="wb-opp-board"></div>
        </div>
      </div>
      <div class="wb-stage-divider"><span>Battlefield</span></div>
      <div class="wb-side wb-side-our">
        <div class="wb-side-header wb-side-header-our">
          <div class="wb-side-ident">
            <span class="wb-side-tag our">You</span>
            <div class="wb-player-name">${ourName}</div>
          </div>
          <div class="wb-side-counters">
            <span class="tc-cnt">&#x1f4a7; <input type="number" class="wb-counter" id="wb-ink-our" value="${(snap.ink||{}).our||0}" min="0" max="15" title="Our ink"></span>
            <span class="tc-cnt">&#x2b50; <input type="number" class="wb-counter" id="wb-lore-our" value="${(snap.lore||{}).our||0}" min="0" max="20" title="Our lore"></span>
          </div>
        </div>
        <div class="wb-zone wb-zone-board">
          <div class="wb-zone-label">${ourName} Board</div>
          <div class="wb-canvas" id="wb-our-board"></div>
        </div>
        <div class="wb-zone-row">
          <div class="wb-zone wb-zone-tray">
            <div class="wb-zone-label">${ourName} Hand <span id="wb-our-hand-n"></span></div>
            <div class="wb-zone-cards wb-zone-tray-cards" id="wb-our-hand"></div>
          </div>
          <div class="wb-zone wb-zone-tray wb-zone-mini">
            <div class="wb-zone-label">${ourName} Ink <span id="wb-our-ink-n"></span></div>
            <div class="wb-zone-cards wb-zone-small" id="wb-our-ink"></div>
          </div>
          <div class="wb-zone wb-zone-tray wb-zone-mini">
            <div class="wb-zone-label">${ourName} Discard <span id="wb-our-discard-n"></span></div>
            <div class="wb-zone-cards wb-zone-small" id="wb-our-discard"></div>
          </div>
        </div>
      </div>
    </div>
    <div class="wb-decks">
      <div class="wb-deck" id="wb-deck-opp" style="display:none">
        <div class="wb-deck-head">
          <div class="wb-deck-label">Opponent Deck <span id="wb-deck-count-opp"></span></div>
          <div class="wb-deck-actions">
            <button class="tc-btn wb-mini-btn" onclick="wbShuffleDeck('opp')">Shuffle</button>
            <button class="tc-btn wb-mini-btn" onclick="wbDraw('opp')">Draw</button>
            <button class="tc-btn wb-mini-btn" onclick="wbDraw('opp', true)">+Hidden</button>
            <button class="tc-btn wb-mini-btn" onclick="wbDrawOpening('opp')">Start 7</button>
          </div>
        </div>
        <div class="wb-deck-cards" id="wb-deck-cards-opp"></div>
      </div>
      <div class="wb-deck" id="wb-deck-our" style="display:none">
        <div class="wb-deck-head">
          <div class="wb-deck-label">Your Deck <span id="wb-deck-count-our"></span></div>
          <div class="wb-deck-actions">
            <button class="tc-btn wb-mini-btn" onclick="wbShuffleDeck('our')">Shuffle</button>
            <button class="tc-btn wb-mini-btn" onclick="wbDraw('our')">Draw</button>
            <button class="tc-btn wb-mini-btn" onclick="wbDrawOpening('our')">Start 7</button>
          </div>
        </div>
        <div class="wb-deck-cards" id="wb-deck-cards-our"></div>
      </div>
    </div>`;
  wrap.appendChild(panel);

  wbLoadDeckList();
  wbRenderAll();
  wbInitArrows();
}

function wbBuildEmptyState() {
  return {
    our: { board: [], hand: [], ink: [], discard: [] },
    opp: { board: [], hand: [], ink: [], discard: [] },
  };
}

function wbResetToSnapshot() {
  const snaps = tcReplayData?.snapshots || [];
  const snap = snaps[tcSnapIdx] || {};
  wbState = wbBuildStateFromSnapshot(snap);
  wbTurn = Number(snap.turn || 1);
  wbMode = 'snapshot';
  wbSelectedUid = null;
  wbClearArrows();
  for (const side of ['our', 'opp']) {
    if ((wbDeckState[side] || []).length) wbSyncPileWithState(side);
  }
  wbRecountDecks();
  wbRenderAll();
}

function wbStartSandbox() {
  wbMode = 'sandbox';
  wbState = wbBuildEmptyState();
  wbTurn = 1;
  wbSelectedUid = null;
  wbClearArrows();
  wbRecountDecks();
  wbRenderAll();
}

function wbReset() {
  if (wbMode === 'sandbox') {
    wbStartSandbox();
    return;
  }
  wbResetToSnapshot();
}

function wbRenderAll() {
  if (!wbState) return;
  const turnPill = document.getElementById('wb-turn-pill');
  if (turnPill) turnPill.textContent = `Turn ${wbTurn}`;
  wbRenderToolbar();
  wbRenderSimbar();
  wbRenderCanvas('opp');
  wbRenderCanvas('our');
  wbRenderTray('opp-hand', 'wb-opp-hand', 'wb-opp-hand-n');
  wbRenderTray('opp-ink', 'wb-opp-ink', 'wb-opp-ink-n');
  wbRenderTray('opp-discard', 'wb-opp-discard', 'wb-opp-discard-n');
  wbRenderTray('our-hand', 'wb-our-hand', 'wb-our-hand-n');
  wbRenderTray('our-ink', 'wb-our-ink', 'wb-our-ink-n');
  wbRenderTray('our-discard', 'wb-our-discard', 'wb-our-discard-n');
  wbRenderDeck('opp');
  wbRenderDeck('our');

  const zoneMap = {
    'wb-our-board':'our-board',
    'wb-opp-board':'opp-board',
    'wb-our-hand':'our-hand',
    'wb-opp-hand':'opp-hand',
    'wb-our-ink':'our-ink',
    'wb-opp-ink':'opp-ink',
    'wb-our-discard':'our-discard',
    'wb-opp-discard':'opp-discard',
  };
  for (const [id, zone] of Object.entries(zoneMap)) {
    const el = document.getElementById(id);
    if (el) el.dataset.wbZone = zone;
  }
}

let _wbLastClickTime = 0;
let _wbLastClickUid = '';

function wbRenderSimbar() {
  const el = document.getElementById('wb-simbar');
  if (!el) return;
  const modeLabel = wbMode === 'sandbox' ? 'Sandbox' : 'Snapshot';
  const ourDeck = wbDeckPile.our.length;
  const oppDeck = wbDeckPile.opp.length;
  el.innerHTML = `
    <div class="wb-simbar-main">
      <span class="wb-sim-mode ${wbMode}">${modeLabel}</span>
      <span class="wb-sim-meta">Our deck ${ourDeck} · Opp deck ${oppDeck}</span>
      <div class="wb-sim-actions">
        <button class="tc-btn wb-mini-btn" onclick="wbDraw('our')">Draw us</button>
        <button class="tc-btn wb-mini-btn" onclick="wbDraw('opp')">Draw opp</button>
        <button class="tc-btn wb-mini-btn" onclick="wbDraw('opp', true)">Hidden opp</button>
        <button class="tc-btn wb-mini-btn" onclick="wbAdvanceTurn()">+ Turn</button>
      </div>
    </div>`;
}

function wbCardMouseDown(e, uid) {
  if (e.button !== 0) return;
  e.preventDefault();

  const found = wbFindCard(uid);
  if (!found) return;
  const { zone, card } = found;
  const el = document.querySelector(`[data-wb-uid="${uid}"]`);
  if (!el) return;

  // Double click: second mousedown within 350ms on same card
  const now = Date.now();
  if (now - _wbLastClickTime < 350 && _wbLastClickUid === uid) {
    _wbLastClickTime = 0;
    wbToggleExert(uid);
    return;
  }
  _wbLastClickTime = now;
  _wbLastClickUid = uid;
  wbSelectedUid = uid;
  wbRenderToolbar();

  // Drag: hold button + move 12px
  const startX = e.clientX, startY = e.clientY;
  const startRect = el.getBoundingClientRect();
  let dragging = false;
  let ghost = null;
  let lastDropZone = null;

  const cleanupZones = () => {
    document.querySelectorAll('[data-wb-zone]').forEach(z => z.classList.remove('wb-drop-hover'));
  };

  const setGhostPosition = (ev) => {
    if (!ghost) return;
    ghost.style.left = `${ev.clientX - startRect.width / 2}px`;
    ghost.style.top = `${ev.clientY - startRect.height / 2}px`;
  };

  const onMove = ev => {
    if (!dragging && Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) > 12) {
      dragging = true;
      _wbLastClickTime = 0; // cancel double-click
      ghost = el.cloneNode(true);
      ghost.classList.add('wb-drag-ghost');
      document.body.appendChild(ghost);
      setGhostPosition(ev);
      el.classList.add('wb-dragging');
    }
    if (dragging) {
      setGhostPosition(ev);
      cleanupZones();
      const under = document.elementFromPoint(ev.clientX, ev.clientY);
      const dropZone = under?.closest('[data-wb-zone]');
      lastDropZone = dropZone || null;
      if (dropZone) {
        dropZone.classList.add('wb-drop-hover');
      }
    }
  };

  const onUp = ev => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    el.classList.remove('wb-dragging');
    cleanupZones();
    if (ghost) ghost.remove();
    if (dragging) {
      const under = document.elementFromPoint(ev.clientX, ev.clientY);
      const dropZone = under?.closest('[data-wb-zone]') || lastDropZone;
      if (dropZone && dropZone.dataset.wbZone) {
        const point = wbDropPoint(dropZone, ev);
        wbMoveCard(uid, dropZone.dataset.wbZone, point);
      } else if (zone.endsWith('-board')) {
        const boardZone = document.getElementById(zone === 'our-board' ? 'wb-our-board' : 'wb-opp-board');
        if (boardZone) {
          const point = wbDropPoint(boardZone, ev);
          wbMoveCard(uid, zone, point);
        }
      }
    } else {
      wbSelectedUid = uid;
      wbRenderToolbar();
    }
  };

  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

// ── Right-click drag → draw arrow ──
let wbArrowSvgs = [];
let wbArrowDragging = false;
let wbArrowStartX = 0, wbArrowStartY = 0;
let wbArrowPreview = null;

function wbInitArrows() {
  const board = document.getElementById('wb-stage');
  if (!board) return;
  board.style.position = 'relative';

  board.addEventListener('contextmenu', e => e.preventDefault());

  board.addEventListener('mousedown', e => {
    if (e.button !== 2) return; // right button only
    const bR = board.getBoundingClientRect();
    wbArrowStartX = e.clientX - bR.left;
    wbArrowStartY = e.clientY - bR.top;
    wbArrowDragging = true;

    // Create preview SVG
    wbArrowPreview = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    wbArrowPreview.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:45;width:100%;height:100%;overflow:visible';
    wbArrowPreview.innerHTML = `<defs><marker id="wb-ah-preview" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#ef4444" fill-opacity="0.5"/></marker></defs><line id="wb-arrow-line" x1="${wbArrowStartX}" y1="${wbArrowStartY}" x2="${wbArrowStartX}" y2="${wbArrowStartY}" stroke="#ef4444" stroke-width="3" stroke-opacity="0.4" stroke-dasharray="6 4" marker-end="url(#wb-ah-preview)"/>`;
    board.appendChild(wbArrowPreview);
  });

  board.addEventListener('mousemove', e => {
    if (!wbArrowDragging || !wbArrowPreview) return;
    const bR = board.getBoundingClientRect();
    const line = wbArrowPreview.getElementById('wb-arrow-line');
    if (line) {
      line.setAttribute('x2', e.clientX - bR.left);
      line.setAttribute('y2', e.clientY - bR.top);
    }
  });

  board.addEventListener('mouseup', e => {
    if (e.button !== 2 || !wbArrowDragging) return;
    wbArrowDragging = false;

    const bR = board.getBoundingClientRect();
    const endX = e.clientX - bR.left;
    const endY = e.clientY - bR.top;
    const dist = Math.sqrt((endX - wbArrowStartX)**2 + (endY - wbArrowStartY)**2);

    // Remove preview
    if (wbArrowPreview) { wbArrowPreview.remove(); wbArrowPreview = null; }

    // Only draw if dragged a minimum distance
    if (dist < 20) return;

    // Draw persistent arrow
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.classList.add('wb-arrow-svg');
    svg.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:40;width:100%;height:100%;overflow:visible';
    const markerId = 'wb-ah-' + Date.now();
    svg.innerHTML = `<defs><marker id="${markerId}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#ef4444"/></marker></defs><line x1="${wbArrowStartX}" y1="${wbArrowStartY}" x2="${endX}" y2="${endY}" stroke="#ef4444" stroke-width="3" stroke-opacity="0.8" marker-end="url(#${markerId})"/>`;
    board.appendChild(svg);
    wbArrowSvgs.push(svg);
  });
}

function wbClearArrows() {
  for (const svg of wbArrowSvgs) svg.remove();
  wbArrowSvgs = [];
}

function wbBuildStateFromSnapshot(snap) {
  const board = snap.board || { our: [], opp: [] };
  const items = snap.items || { our: [], opp: [] };
  const inkwell = snap.inkwell || { our: [], opp: [] };
  return {
    our: {
      board: wbLayoutBoardCards([...board.our, ...items.our], 'our'),
      hand: (snap.hand || []).map(name => wbMakeCard({ name }, 'our', 'our-hand')),
      ink: (inkwell.our || []).map(card => wbMakeCard(card, 'our', 'our-ink')),
      discard: [],
    },
    opp: {
      board: wbLayoutBoardCards([...board.opp, ...items.opp], 'opp'),
      hand: Array.from({ length: snap.hand_count_opp || 0 }, () => wbMakeCard({ name: 'Unknown card', hidden: true }, 'opp', 'opp-hand')),
      ink: (inkwell.opp || []).map(card => wbMakeCard(card, 'opp', 'opp-ink')),
      discard: [],
    },
  };
}

function wbMakeCard(raw, side, zone) {
  return {
    uid: `wb-${wbUidCounter++}`,
    side,
    zone,
    name: raw?.name || '',
    hidden: !!raw?.hidden || !raw?.name,
    id: raw?.id || '',
    iid: raw?.iid || '',
    damage: Number(raw?.damage || 0),
    exerted: !!raw?.exerted,
    x: Number(raw?.x || 24),
    y: Number(raw?.y || 24),
  };
}

function wbLayoutBoardCards(cards, side) {
  return cards.map((card, idx) => {
    const col = idx % 7;
    const row = Math.floor(idx / 7);
    return wbMakeCard({ ...card, x: 18 + col * 98, y: 18 + row * 24 }, side, `${side}-board`);
  });
}

function wbGetZone(zone) {
  if (!wbState) return null;
  const [side, area] = zone.split('-');
  if (!side || !area || !wbState[side]) return null;
  return wbState[side][area];
}

function wbFindCard(uid) {
  if (!wbState) return null;
  for (const zone of WB_ZONE_ORDER) {
    const cards = wbGetZone(zone) || [];
    const idx = cards.findIndex(card => card.uid === uid);
    if (idx >= 0) {
      return { zone, idx, card: cards[idx], cards };
    }
  }
  return null;
}

function wbCardShortName(card) {
  if (!card) return '';
  if (card.hidden) return 'Hidden';
  return (card.name || '?').split(' - ')[0];
}

function wbDropPoint(zoneEl, ev) {
  const rect = zoneEl.getBoundingClientRect();
  return {
    x: Math.max(8, Math.min(WB_CANVAS_WIDTH - 96, ev.clientX - rect.left - 36)),
    y: Math.max(8, Math.min(WB_CANVAS_HEIGHT - 116, ev.clientY - rect.top - 52)),
  };
}

function wbClampBoardCard(card) {
  card.x = Math.max(8, Math.min(WB_CANVAS_WIDTH - 96, Number(card.x || 0)));
  card.y = Math.max(8, Math.min(WB_CANVAS_HEIGHT - 116, Number(card.y || 0)));
}

function wbRenderToolbar() {
  const el = document.getElementById('wb-toolbar');
  if (!el) return;
  const found = wbSelectedUid ? wbFindCard(wbSelectedUid) : null;
  if (!found) {
    el.innerHTML = `<div class="wb-toolbar-empty">
      <span class="wb-toolbar-kicker">Quick Actions</span>
      <span>Select a card to move it between board, hand, ink, discard, or to track damage during review.</span>
    </div>`;
    return;
  }
  const { card, zone } = found;
  const sideLabel = card.side === 'our' ? 'Our side' : 'Opponent side';
  const sameSide = card.side;
  const boardZone = `${sameSide}-board`;
  const handZone = `${sameSide}-hand`;
  const inkZone = `${sameSide}-ink`;
  const discardZone = `${sameSide}-discard`;
  el.innerHTML = `
    <div class="wb-toolbar-main">
      <div class="wb-selection-pill">${sideLabel} • ${wbCardShortName(card)} • ${zone.replace('-', ' / ')}</div>
      <div class="wb-toolbar-groups">
        <div class="wb-toolbar-group">
          <span class="wb-toolbar-group-label">Move</span>
          <div class="wb-toolbar-actions">
            <button class="tc-btn wb-act-btn" onclick="wbMoveSelected('${boardZone}')">Board</button>
            <button class="tc-btn wb-act-btn" onclick="wbMoveSelected('${handZone}')">Hand</button>
            <button class="tc-btn wb-act-btn" onclick="wbMoveSelected('${inkZone}')">Ink</button>
            <button class="tc-btn wb-act-btn" onclick="wbMoveSelected('${discardZone}')">Discard</button>
          </div>
        </div>
        <div class="wb-toolbar-group">
          <span class="wb-toolbar-group-label">Damage</span>
          <div class="wb-toolbar-actions">
            <button class="tc-btn wb-act-btn danger" onclick="wbAdjustDamage('${card.uid}',1)">+1</button>
            <button class="tc-btn wb-act-btn" onclick="wbAdjustDamage('${card.uid}',-1)">-1</button>
          </div>
        </div>
      </div>
    </div>`;
}

function wbRenderCanvas(side) {
  const zone = `${side}-board`;
  const el = document.getElementById(side === 'our' ? 'wb-our-board' : 'wb-opp-board');
  if (!el) return;
  const cards = wbGetZone(zone) || [];
  el.dataset.wbZone = zone;
  el.innerHTML = cards.map(card => wbRenderBoardCard(card)).join('') || '<div class="wb-canvas-empty">Drop cards here</div>';
}

function wbRenderBoardCard(card) {
  const db = (tcCardsDB || {})[card.name] || {};
  const img = card.hidden ? '' : tcCardImg(db);
  const isCh = (db.type || '').toLowerCase().includes('character');
  const inkC = TC_INK_CLASS[(db.ink || '').trim()] || '';
  const { b, s } = card.hidden ? { b: 'Hidden', s: '' } : tcShortName(card.name);
  const dmg = card.damage || 0;
  const will = parseInt(db.will) || 0;
  const style = card.hidden
    ? `left:${card.x}px;top:${card.y}px`
    : `left:${card.x}px;top:${card.y}px;background-image:url(${img});background-size:cover;background-position:center 15%`;
  let cls = 'rv-mc wb-board-card wb-canvas-card';
  if (inkC) cls += ' rv-ink-' + inkC;
  if (card.exerted) cls += ' rv-exerted';
  if (card.uid === wbSelectedUid) cls += ' wb-selected';
  if (card.hidden) cls += ' wb-hidden-card';
  return `<div class="${cls}" style="${style}" title="${card.hidden ? 'Hidden card' : card.name}" data-wb-uid="${card.uid}" onmousedown="wbCardMouseDown(event,'${card.uid}')">
    ${card.hidden ? '<div class="wb-card-back">?</div>' : `<div class="rv-cost">${db.cost || '?'}</div>`}
    ${isCh && dmg > 0 ? `<div class="rv-dmg">-${dmg}</div>` : ''}
    <div class="rv-ovl"><div class="rv-cn2">${b}</div>${s ? `<div style="font-size:0.45rem;color:rgba(255,255,255,0.6)">${s}</div>` : ''}
    ${!card.hidden && isCh ? `<div class="rv-stats">${db.str ? '<span>&#x2694;'+db.str+'</span>' : ''}${db.will ? `<span>&#x1f6e1;${dmg>0?(will-dmg)+'/'+will:will}</span>` : ''}${db.lore ? '<span>&#x2b50;'+db.lore+'</span>' : ''}</div>` : ''}</div></div>`;
}

function wbRenderTray(zone, containerId, countId) {
  const el = document.getElementById(containerId);
  const n = document.getElementById(countId);
  if (!el) return;
  const cards = wbGetZone(zone) || [];
  el.dataset.wbZone = zone;
  if (n) n.textContent = `(${cards.length})`;
  el.innerHTML = cards.map(card => wbRenderTrayCard(card)).join('') || '<div class="wb-empty-zone"></div>';
}

function wbRenderTrayCard(card) {
  const db = (tcCardsDB || {})[card.name || ''] || {};
  const img = card.hidden ? '' : tcCardImg(db);
  const short = wbCardShortName(card);
  const exertedCls = card.exerted ? ' tc-ink-exerted' : '';
  const selectedCls = card.uid === wbSelectedUid ? ' wb-selected' : '';
  const hiddenCls = card.hidden ? ' wb-hidden-card' : '';
  return `<div class="tc-ink-card wb-small-card${exertedCls}${selectedCls}${hiddenCls}" title="${card.hidden ? 'Hidden card' : (card.name || 'hidden')}" data-wb-uid="${card.uid}" onmousedown="wbCardMouseDown(event,'${card.uid}')">
    ${img ? `<img src="${img}" alt="${short}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
    <div class="tc-ink-name" ${img ? 'style="display:none"' : ''}>${short}</div>
  </div>`;
}

function wbMoveSelected(targetZone) {
  if (!wbSelectedUid) return;
  wbMoveCard(wbSelectedUid, targetZone);
}

function wbToggleExert(uid) {
  const found = wbFindCard(uid);
  if (!found || found.card.exerted === undefined) return;
  found.card.exerted = !found.card.exerted;
  wbRenderAll();
}

function wbAdjustDamage(uid, delta) {
  const found = wbFindCard(uid);
  if (!found) return;
  found.card.damage = Math.max(0, Number(found.card.damage || 0) + delta);
  wbRenderAll();
}

function wbMoveCard(uid, toZone, point) {
  const found = wbFindCard(uid);
  if (!found) return;
  const { zone: fromZone, idx } = found;
  const src = wbGetZone(fromZone);
  const dst = wbGetZone(toZone);
  if (!src || !dst || idx < 0 || idx >= src.length) return;
  const card = src.splice(idx, 1)[0];
  const [side] = toZone.split('-');
  card.side = side;
  card.zone = toZone;
  if (toZone.endsWith('-board')) {
    if (card.exerted === undefined) card.exerted = false;
    card.damage = Number(card.damage || 0);
    if (point) {
      card.x = point.x;
      card.y = point.y;
    } else {
      const fallback = { x: 28 + (dst.length % 6) * 96, y: 26 + Math.floor(dst.length / 6) * 24 };
      card.x = fallback.x;
      card.y = fallback.y;
    }
    wbClampBoardCard(card);
  } else {
    delete card.x;
    delete card.y;
  }
  dst.push(card);
  wbSelectedUid = card.uid;
  wbRecountDecks();
  wbRenderAll();
}

async function wbLoadDeckList() {
  const selects = [
    document.getElementById('wb-deck-select-our'),
    document.getElementById('wb-deck-select-opp'),
  ].filter(Boolean);
  if (!selects.length) return;
  try {
    const user = tcDeckUser();
    let decks = [];
    if (user) {
      const resp = await fetch(`/api/decks?user=${encodeURIComponent(user)}`);
      const data = await resp.json();
      decks = data.decks || [];
    }
    if (!decks.length) {
      const resp = await fetch('/api/decks?user=cloud');
      const data = await resp.json();
      decks = data.decks || [];
    }
    selects.forEach(select => {
      for (const d of decks) {
        const opt = document.createElement('option');
        opt.value = JSON.stringify(d.cards || {});
        opt.textContent = `${d.name} (${d.deckCode}) — ${d.total || 0} cards`;
        select.appendChild(opt);
      }
    });
  } catch (e) { console.warn('Failed to load decks:', e); }
}

function wbDeckListFromCards(cards) {
  return Object.entries(cards).map(([name, qty]) => ({
    name, qty: parseInt(qty), remaining: parseInt(qty)
  })).sort((a, b) => {
    const da = (tcCardsDB || {})[a.name] || {};
    const dbb = (tcCardsDB || {})[b.name] || {};
    return (parseInt(da.cost) || 0) - (parseInt(dbb.cost) || 0) || a.name.localeCompare(b.name);
  });
}

function wbBuildPile(side) {
  const pile = [];
  (wbDeckState[side] || []).forEach(card => {
    for (let i = 0; i < card.qty; i++) pile.push(card.name);
  });
  wbDeckPile[side] = pile;
  wbShuffleDeck(side, false);
}

function wbSyncPileWithState(side) {
  wbBuildPile(side);
  const pile = wbDeckPile[side] || [];
  for (const zone of WB_ZONE_ORDER.filter(z => z.startsWith(side))) {
    for (const card of (wbGetZone(zone) || [])) {
      if (!card.name) continue;
      const idx = pile.indexOf(card.name);
      if (idx >= 0) pile.splice(idx, 1);
    }
  }
  wbDeckPile[side] = pile;
}

function wbRecountDecks() {
  for (const side of ['our', 'opp']) {
    const used = {};
    for (const zone of WB_ZONE_ORDER.filter(z => z.startsWith(side))) {
      for (const c of (wbGetZone(zone) || [])) {
        if (c.name) used[c.name] = (used[c.name] || 0) + 1;
      }
    }
    const pileNames = {};
    for (const name of (wbDeckPile[side] || [])) {
      pileNames[name] = (pileNames[name] || 0) + 1;
    }
    for (const dc of (wbDeckState[side] || [])) {
      dc.remaining = pileNames[dc.name] || Math.max(0, dc.qty - (used[dc.name] || 0));
    }
  }
}

function wbLoadDeck(side, cardsJson) {
  const deckEl = document.getElementById(`wb-deck-${side}`);
  if (!cardsJson) {
    wbDeckState[side] = [];
    wbDeckPile[side] = [];
    if (deckEl) deckEl.style.display = 'none';
    wbRenderAll();
    return;
  }

  let cards;
  try { cards = JSON.parse(cardsJson); } catch (e) { return; }

  wbDeckState[side] = wbDeckListFromCards(cards);
  wbBuildPile(side);
  wbRecountDecks();
  if (wbMode !== 'sandbox') wbStartSandbox();
  if (deckEl) deckEl.style.display = '';
  wbRenderAll();
}

function wbShuffleDeck(side, rerender = true) {
  const pile = wbDeckPile[side] || [];
  for (let i = pile.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pile[i], pile[j]] = [pile[j], pile[i]];
  }
  wbDeckPile[side] = pile;
  wbRecountDecks();
  if (rerender) wbRenderAll();
}

function wbDraw(side, hidden = false) {
  const pile = wbDeckPile[side] || [];
  if (!pile.length) return;
  const name = pile.shift();
  const payload = hidden ? { name, hidden: true } : { name };
  wbGetZone(`${side}-hand`).push(wbMakeCard(payload, side, `${side}-hand`));
  wbRecountDecks();
  wbRenderAll();
}

function wbDrawOpening(side) {
  for (let i = 0; i < 7; i++) wbDraw(side, side === 'opp');
}

function wbAdvanceTurn() {
  wbTurn += 1;
  const pill = document.getElementById('wb-turn-pill');
  if (pill) pill.textContent = `Turn ${wbTurn}`;
}

function wbRenderDeck(side) {
  const el = document.getElementById(`wb-deck-cards-${side}`);
  const countEl = document.getElementById(`wb-deck-count-${side}`);
  const wrap = document.getElementById(`wb-deck-${side}`);
  if (!el || !countEl || !wrap) return;
  const state = wbDeckState[side] || [];
  if (!state.length) {
    wrap.style.display = 'none';
    return;
  }
  wrap.style.display = '';
  const totalRemaining = state.reduce((s, c) => s + c.remaining, 0);
  countEl.textContent = `(${totalRemaining} remaining)`;
  el.innerHTML = state.map((c, i) => {
    const db = (tcCardsDB || {})[c.name] || {};
    const img = tcCardImg(db);
    const short = c.name.split(' - ')[0];
    const dimmed = c.remaining <= 0;
    const cls = 'wb-card' + (dimmed ? ' wb-card-empty' : '');
    return `<div class="${cls}" onclick="${dimmed ? '' : `wbAddFromDeck('${side}', ${i})`}" title="${c.name} (${c.remaining}/${c.qty})">
      ${img ? `<img src="${img}" alt="${short}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
      <div class="wb-card-name" ${img ? 'style="display:none"' : ''}>${short}</div>
      <div class="wb-card-qty">${c.remaining}</div>
    </div>`;
  }).join('');
}

function wbAddFromDeck(side, deckIdx) {
  const card = (wbDeckState[side] || [])[deckIdx];
  if (!card || card.remaining <= 0) return;
  const pile = wbDeckPile[side] || [];
  const idx = pile.indexOf(card.name);
  if (idx >= 0) pile.splice(idx, 1);
  wbGetZone(`${side}-hand`).push(wbMakeCard({ name: card.name, hidden: side === 'opp' }, side, `${side}-hand`));
  wbRecountDecks();
  wbRenderAll();
}

// ═══ CSS ═══
(function() {
  if (document.getElementById('tc-css')) return;
  const s = document.createElement('style');
  s.id = 'tc-css';
  s.textContent = `
    .tc-upload-inner{border:2px dashed var(--border);border-radius:12px;padding:28px;text-align:center;transition:border-color .2s,background .2s;cursor:pointer}
    .tc-upload-inner.tc-drag-over{border-color:var(--gold);background:rgba(212,160,58,.08)}
    .tc-replay-row{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;font-size:.85em;cursor:pointer;transition:background .15s}
    .tc-replay-row:hover{background:var(--bg3)}

    .tc-wrap{background:var(--bg2);border-radius:12px;overflow:hidden}
    .tc-top-bar{display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg3);border-bottom:1px solid var(--border)}
    .tc-close{background:none;border:none;color:var(--text2);font-size:1.3em;cursor:pointer;padding:0 4px}
    .tc-title{font-weight:600;font-size:.9em;flex:1}
    .tc-badge-wr{font-weight:700;font-size:.85em}
    .tc-badge-hand{font-size:.68em;padding:2px 8px;border-radius:10px;background:rgba(76,175,80,.15);color:#4caf50;font-weight:600}

    .tc-turn-strip{display:flex;gap:4px;padding:8px 14px;overflow-x:auto;scrollbar-width:none;border-bottom:1px solid var(--border);-webkit-overflow-scrolling:touch}
    .tc-turn-strip::-webkit-scrollbar{display:none}
    .tc-turn-pill{padding:4px 10px;border-radius:12px;font-size:.72em;font-weight:600;color:var(--text2);background:var(--bg3);cursor:pointer;white-space:nowrap;transition:all .3s;flex-shrink:0}
    .tc-turn-pill.active{background:var(--gold);color:var(--bg);box-shadow:0 0 12px rgba(212,160,58,.4)}
    .tc-turn-pill.past{color:var(--text);background:var(--bg)}

    .tc-controls{display:flex;align-items:center;gap:6px;padding:8px 14px;border-bottom:1px solid var(--border);flex-wrap:wrap}
    .tc-btn{background:var(--bg3);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:4px 10px;cursor:pointer;font-size:.82em;min-width:32px;text-align:center;transition:background .15s}
    .tc-btn:hover{background:var(--bg)}
    .tc-slider{flex:1;min-width:80px;accent-color:var(--gold)}
    .tc-step-num{font-size:.65em;color:var(--text2)}
    .tc-action-bar{padding:6px 14px;font-size:.8em;color:var(--gold);font-weight:600;background:rgba(212,160,58,.06);border-bottom:1px solid var(--border);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:color .3s}

    .tc-body{display:grid;grid-template-columns:1fr 200px;min-height:280px}
    .tc-side-panel{background:var(--bg3);border-left:1px solid var(--border);display:flex;flex-direction:column;overflow-y:auto;max-height:500px}
    .tc-events{padding:8px;display:flex;flex-direction:column;gap:2px;flex:1}
    .tc-events h4{font-size:.7rem;color:var(--text2);text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px}

    .tc-ink-panel{padding:8px;border-bottom:1px solid var(--border)}
    .tc-ink-section{margin-bottom:6px}
    .tc-ink-section:last-child{margin-bottom:0}
    .tc-ink-label{font-size:.68em;color:var(--text2);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
    .tc-ink-label span{color:var(--gold);font-weight:700}
    .tc-ink-cards{display:flex;gap:3px;flex-wrap:wrap}
    .tc-ink-card{width:32px;height:44px;border-radius:4px;overflow:hidden;background:var(--bg);border:1px solid rgba(212,160,58,.4);flex-shrink:0;position:relative;transition:opacity .2s}
    .tc-ink-card img{width:100%;height:100%;object-fit:cover}
    .tc-ink-name{display:flex;align-items:center;justify-content:center;text-align:center;font-size:.38em;padding:2px;height:100%;color:var(--text2);word-break:break-word}
    .tc-ink-exerted{opacity:.35;border-color:var(--border)}
    .tc-ink-hidden{display:flex;align-items:center;justify-content:center;height:100%;font-size:.7em;color:var(--text2);font-weight:600}

    @media(max-width:900px){.tc-body{grid-template-columns:1fr}.tc-side-panel{max-height:250px;border-left:none;border-top:1px solid var(--border)}}
    .tc-board-wrap{padding:12px 14px}
    .tc-field{display:flex;gap:6px;flex-wrap:wrap;min-height:80px;align-items:flex-start;padding:8px 0;transition:opacity .2s}
    .tc-field-label{font-size:.68em;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;font-weight:600}
    .tc-midline{display:flex;align-items:center;gap:12px;justify-content:center;padding:4px 0;margin:2px 0}
    .tc-mid-sep{flex:1;height:1px;background:var(--border);max-width:60px}
    .tc-cnt{font-size:.72em;color:var(--text2);font-weight:600}

    .tc-field .rv-mc{transition:none !important}
    .tc-anim-play{animation:tcPlay .5s cubic-bezier(.22,1,.36,1) both !important}
    .tc-dying{animation:tcDie .5s ease both !important;pointer-events:none}
    .tc-dmg-flash{animation:tcDmgFlash .5s ease both !important}
    @keyframes tcPlay{0%{opacity:0;transform:translateY(30px) scale(.6);filter:brightness(1.5)}60%{opacity:1;transform:translateY(-4px) scale(1.05);filter:brightness(1.1)}100%{opacity:1;transform:translateY(0) scale(1);filter:brightness(1)}}
    @keyframes tcDie{0%{opacity:1;transform:scale(1) rotate(0deg)}20%{opacity:.9;transform:scale(1.08);filter:brightness(1.4) saturate(2)}100%{opacity:0;transform:scale(.4) rotate(8deg);filter:grayscale(1) brightness(.5)}}
    @keyframes tcDmgFlash{0%{transform:scale(1);box-shadow:none}30%{transform:scale(1.6);background:#ef4444;box-shadow:0 0 16px 4px #ef4444;color:#fff}100%{transform:scale(1);box-shadow:none}}
    .tc-new-glow{box-shadow:0 0 12px 3px var(--gold) !important;border-color:var(--gold) !important}
    .tc-ability-hit{animation:tcAbilityHit .5s ease both !important}
    @keyframes tcAbilityHit{0%{box-shadow:none;filter:brightness(1)}30%{box-shadow:0 0 20px 6px #a855f7;filter:brightness(1.4)}100%{box-shadow:none;filter:brightness(1)}}

    .tc-btn-wb{font-size:1em !important;padding:4px 8px !important}
    .tc-btn-active{background:var(--gold) !important;color:var(--bg) !important}

    .wb-panel{margin-top:12px;border:1px solid rgba(255,255,255,.08);border-radius:16px;overflow:hidden;background:
      radial-gradient(circle at top, rgba(36,113,163,.08), transparent 35%),
      linear-gradient(180deg, rgba(16,21,28,.98), rgba(11,15,20,.98));box-shadow:0 22px 60px rgba(0,0,0,.38);animation:tcFadeIn .25s ease}
    .wb-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;background:
      linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01)),
      rgba(9,13,19,.92);border-bottom:1px solid rgba(255,255,255,.07);flex-wrap:wrap}
    .wb-header-main{display:flex;flex-direction:column;gap:4px;min-width:220px;flex:1}
    .wb-title-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .wb-title{font-weight:700;font-size:.9em;color:#eaf1fb;letter-spacing:.02em}
    .wb-turn-pill{display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;background:rgba(36,113,163,.16);border:1px solid rgba(100,165,255,.28);color:#9ed0ff;font-size:.68em;font-weight:800;text-transform:uppercase;letter-spacing:.08em}
    .wb-tip{font-size:.72em;color:#90a1b6}
    .wb-header-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .wb-header select{min-width:210px;flex:0 1 280px;background:#0f1722;color:var(--text);border:1px solid rgba(255,255,255,.09);border-radius:10px;padding:7px 10px;font-size:.78em}
    .wb-ctrl-btn{min-width:34px;padding:6px 10px !important;border-radius:10px !important}
    .wb-mode-btn{border-radius:10px !important}
    .wb-toolbar{padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.07);background:
      linear-gradient(180deg, rgba(17,24,34,.9), rgba(14,19,27,.92))}
    .wb-toolbar-empty{display:flex;flex-direction:column;gap:4px;font-size:.76em;color:#8fa0b5}
    .wb-toolbar-kicker{font-size:.64em;text-transform:uppercase;letter-spacing:.12em;color:#7ea7d1;font-weight:800}
    .wb-toolbar-main{display:flex;gap:14px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
    .wb-selection-pill{font-size:.74em;font-weight:700;color:#f0f6ff;padding:8px 12px;border-radius:12px;background:rgba(100,165,255,.1);border:1px solid rgba(100,165,255,.22)}
    .wb-toolbar-groups{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}
    .wb-toolbar-group{display:flex;flex-direction:column;gap:6px}
    .wb-toolbar-group-label{font-size:.64em;color:#7f93aa;font-weight:800;text-transform:uppercase;letter-spacing:.12em}
    .wb-toolbar-actions{display:flex;gap:6px;flex-wrap:wrap}
    .wb-act-btn{border-radius:10px !important;background:rgba(255,255,255,.04) !important;border:1px solid rgba(255,255,255,.1) !important}
    .wb-act-btn:hover{border-color:rgba(100,165,255,.35) !important;color:#cfe7ff !important}
    .wb-act-btn.danger:hover{border-color:rgba(248,81,73,.35) !important;color:#ffb4ae !important}
    .wb-simbar{padding:8px 16px;border-bottom:1px solid rgba(255,255,255,.06);background:rgba(100,165,255,.04)}
    .wb-simbar-main{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .wb-sim-mode{display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;font-size:.64em;font-weight:800;text-transform:uppercase;letter-spacing:.12em}
    .wb-sim-mode.snapshot{background:rgba(212,160,58,.12);color:var(--gold);border:1px solid rgba(212,160,58,.24)}
    .wb-sim-mode.sandbox{background:rgba(63,185,80,.12);color:#7ce38c;border:1px solid rgba(63,185,80,.24)}
    .wb-sim-meta{font-size:.74em;color:#8ea0b4}
    .wb-sim-actions{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto}
    .wb-mini-btn{padding:5px 9px !important;border-radius:9px !important;font-size:.72em !important}
    .wb-stage{padding:16px;display:grid;gap:14px;background:
      radial-gradient(circle at center, rgba(36,113,163,.08), transparent 42%),
      linear-gradient(180deg, rgba(255,255,255,.015), rgba(255,255,255,0)),
      #0b1118}
    .wb-stage-divider{display:flex;align-items:center;justify-content:center}
    .wb-stage-divider span{display:inline-flex;align-items:center;justify-content:center;padding:4px 12px;border-radius:999px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);font-size:.64em;text-transform:uppercase;letter-spacing:.16em;color:#7f93aa;font-weight:800}
    .wb-side{display:grid;gap:10px;padding:12px;border:1px solid rgba(255,255,255,.06);border-radius:14px;background:rgba(255,255,255,.02)}
    .wb-side-header,.wb-side-footer{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
    .wb-side-ident{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .wb-side-tag{display:inline-flex;align-items:center;padding:3px 9px;border-radius:999px;font-size:.62em;font-weight:800;text-transform:uppercase;letter-spacing:.12em;border:1px solid rgba(255,255,255,.12)}
    .wb-side-tag.opp{background:rgba(248,81,73,.12);border-color:rgba(248,81,73,.24);color:#ff9387}
    .wb-side-tag.our{background:rgba(63,185,80,.12);border-color:rgba(63,185,80,.24);color:#74d883}
    .wb-player-name{font-size:.82em;font-weight:700;color:#edf4ff}
    .wb-side-counters{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
    .wb-zone{display:grid;gap:6px}
    .wb-zone-row{display:grid;grid-template-columns:minmax(0,1fr) 156px 156px;gap:10px}
    .wb-zone-label{font-size:.64em;color:#7f93aa;font-weight:800;text-transform:uppercase;letter-spacing:.12em}
    .wb-zone-cards{display:flex;gap:6px;flex-wrap:wrap;min-height:70px;align-items:flex-start;padding:10px;border-radius:12px;background:
      linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.012));border:1px solid rgba(255,255,255,.08);box-shadow:inset 0 1px 0 rgba(255,255,255,.03)}
    .wb-zone-tray-cards{min-height:72px}
    .wb-zone-small{min-height:54px;gap:4px}
    .wb-zone-board .wb-zone-label{margin-bottom:0}
    .wb-canvas{position:relative;min-height:${WB_CANVAS_HEIGHT}px;border-radius:16px;border:1px solid rgba(255,255,255,.08);background:
      radial-gradient(circle at 50% 0%, rgba(63,185,80,.09), transparent 38%),
      linear-gradient(180deg, rgba(18,38,28,.72), rgba(13,25,21,.82)),
      repeating-linear-gradient(90deg, rgba(255,255,255,.018) 0, rgba(255,255,255,.018) 1px, transparent 1px, transparent 84px),
      repeating-linear-gradient(180deg, rgba(255,255,255,.012) 0, rgba(255,255,255,.012) 1px, transparent 1px, transparent 116px);overflow:hidden;box-shadow:inset 0 1px 0 rgba(255,255,255,.04), inset 0 -24px 60px rgba(0,0,0,.18)}
    .wb-canvas::before{content:'';position:absolute;inset:14px;border:1px dashed rgba(255,255,255,.08);border-radius:12px;pointer-events:none}
    .wb-canvas::after{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent);pointer-events:none}
    .wb-canvas-empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#8ea0b4;font-size:.76em}
    .wb-board-card{cursor:pointer;transition:transform .15s, box-shadow .15s}
    .wb-canvas-card{position:absolute;transform-origin:center center}
    .wb-board-card:hover{transform:translateY(-3px);box-shadow:0 0 14px rgba(100,165,255,.28)}
    .wb-small-card{cursor:pointer !important}
    .wb-empty-zone{min-height:30px}
    .wb-hidden-card{background:linear-gradient(160deg, #2c3440, #141a22) !important;border-color:rgba(255,255,255,.12) !important}
    .wb-card-back{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:1.2em;font-weight:800;color:rgba(255,255,255,.7);background:
      radial-gradient(circle at 30% 20%, rgba(212,160,58,.25), transparent 40%),
      linear-gradient(160deg, #2a3342, #11161d)}
    .wb-selected{box-shadow:0 0 0 2px var(--gold), 0 0 18px rgba(212,160,58,.4) !important;border-color:var(--gold) !important}
    .wb-dragging{opacity:.28;transform:scale(.95)}
    .wb-drag-ghost{position:fixed;z-index:999;pointer-events:none;opacity:.92;transform:rotate(3deg);filter:drop-shadow(0 8px 18px rgba(0,0,0,.55))}
    .wb-drop-hover{background:rgba(100,165,255,.12) !important;border-color:#64a5ff !important;border-style:solid !important;box-shadow:inset 0 0 0 1px rgba(100,165,255,.22)}
    .wb-arrow-svg{pointer-events:none}
    .wb-counter{width:36px;background:#0f1722;color:#eaf1fb;border:1px solid rgba(255,255,255,.1);border-radius:8px;text-align:center;font-size:.75em;font-weight:700;padding:3px 2px;-moz-appearance:textfield}
    .wb-counter::-webkit-inner-spin-button,.wb-counter::-webkit-outer-spin-button{-webkit-appearance:none;margin:0}
    .wb-decks{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px 16px;border-top:1px solid rgba(255,255,255,.07);background:rgba(255,255,255,.02)}
    .wb-deck{padding:10px 12px;border:1px solid rgba(255,255,255,.07);border-radius:12px;background:rgba(15,23,34,.55)}
    .wb-deck-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:8px}
    .wb-deck-label{font-size:.64em;color:#7f93aa;font-weight:800;text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px}
    .wb-deck-label span{color:#9ed0ff}
    .wb-deck-head .wb-deck-label{margin-bottom:0}
    .wb-deck-actions{display:flex;gap:6px;flex-wrap:wrap}
    .wb-deck-cards{display:flex;gap:3px;flex-wrap:nowrap;overflow-x:auto;padding-bottom:6px;-webkit-overflow-scrolling:touch}
    .wb-deck-cards::-webkit-scrollbar{height:4px}
    .wb-deck-cards::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
    .wb-card{width:52px;height:72px;border-radius:6px;overflow:hidden;background:var(--bg3);border:1px solid rgba(255,255,255,.1);flex-shrink:0;position:relative;cursor:pointer;transition:transform .15s,opacity .2s,border-color .15s,box-shadow .15s}
    .wb-card:hover{transform:translateY(-3px);border-color:#64a5ff;box-shadow:0 0 0 1px rgba(100,165,255,.18)}
    .wb-card img{width:100%;height:100%;object-fit:cover}
    .wb-card-name{display:flex;align-items:center;justify-content:center;text-align:center;font-size:.42em;padding:2px;height:100%;color:var(--text2);word-break:break-word}
    .wb-card-qty{position:absolute;top:2px;right:2px;background:rgba(0,0,0,.75);color:#fff;font-size:.55em;font-weight:700;min-width:14px;height:14px;border-radius:7px;display:flex;align-items:center;justify-content:center;padding:0 3px}
    .wb-card-empty{opacity:.25;cursor:default;pointer-events:none}
    @keyframes tcDrawArrow{from{stroke-dashoffset:1000}to{stroke-dashoffset:0}}
    @keyframes tcCombatPulse{0%{transform:scale(0);opacity:0}50%{transform:scale(1.2)}100%{transform:scale(1);opacity:1}}

    .tc-hand-panel{border-top:2px solid var(--gold);padding:10px 14px;background:rgba(212,160,58,.04)}
    .tc-hand-label{font-size:.72em;color:var(--gold);font-weight:600;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
    .tc-hand-cards{display:flex;gap:5px;flex-wrap:wrap}
    .tc-hc{width:50px;height:70px;border-radius:5px;overflow:hidden;background:var(--bg3);border:1px solid var(--gold);flex-shrink:0;transition:transform .2s;position:relative}
    .tc-hc:hover{transform:translateY(-3px)}
    .tc-hc img{width:100%;height:100%;object-fit:cover}
    .tc-hc-name{display:flex;align-items:center;justify-content:center;text-align:center;font-size:.45em;padding:3px;height:100%;color:var(--text2);word-break:break-word}
    .tc-hc-new{animation:tcDrawIn .45s cubic-bezier(.22,1,.36,1) both}
    .tc-hc-leaving{animation:tcHandLeave .28s ease-in forwards !important;pointer-events:none}
    @keyframes tcDrawIn{0%{opacity:0;transform:translateY(-24px) scale(.7);filter:brightness(1.4)}60%{opacity:1;transform:translateY(2px) scale(1.05)}100%{opacity:1;transform:translateY(0) scale(1);filter:brightness(1)}}
    @keyframes tcHandLeave{0%{opacity:1;transform:translateY(0) scale(1)}100%{opacity:0;transform:translateY(-40px) scale(.55);filter:brightness(1.2)}}

    .tc-spell-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.55);z-index:50;animation:tcFadeIn .25s ease;transition:opacity .3s ease;border-radius:8px;backdrop-filter:blur(2px)}
    .tc-spell-card{text-align:center;animation:tcSpellPop .3s cubic-bezier(.34,1.56,.64,1) both}
    .tc-spell-card img{width:140px;border-radius:10px;box-shadow:0 0 30px rgba(168,85,247,.6);border:2px solid rgba(168,85,247,.7)}
    .tc-spell-song img{box-shadow:0 0 30px rgba(59,130,246,.6);border-color:rgba(59,130,246,.7)}
    .tc-spell-name{margin-top:8px;font-size:.75em;font-weight:600;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.8)}
    @keyframes tcSpellPop{0%{opacity:0;transform:scale(.5) translateY(20px)}100%{opacity:1;transform:scale(1) translateY(0)}}
    @keyframes tcFadeIn{from{opacity:0}to{opacity:1}}

    /* Card hero overlay (used for PLAY_CARD character/item, ACTIVATE_ABILITY, SHIFT) */
    .tc-hero-card{position:relative;text-align:center;animation:tcHeroPop .35s cubic-bezier(.34,1.56,.64,1) both}
    .tc-hero-card img{width:200px;border-radius:14px;border:3px solid rgba(255,255,255,.25);display:block;margin:0 auto}
    .tc-hero-name{margin-top:10px;font-size:.95em;font-weight:700;color:#fff;text-shadow:0 2px 6px rgba(0,0,0,.9);letter-spacing:.3px}
    .tc-hero-sub{margin-top:4px;font-size:.72em;font-weight:600;color:rgba(255,255,255,.85);padding:3px 10px;display:inline-block;border-radius:10px;background:rgba(0,0,0,.45);backdrop-filter:blur(3px);letter-spacing:.4px;text-transform:uppercase}
    .tc-hero-cost{position:absolute;top:-12px;left:-12px;width:34px;height:34px;border-radius:50%;background:radial-gradient(circle at 30% 30%, #5b9bd5, #1e3a5f);color:#fff;font-weight:800;font-size:1.1em;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(0,0,0,.6);border:2px solid rgba(255,255,255,.4);z-index:2}
    /* Color variants */
    .tc-hero-play-card img{box-shadow:0 0 36px rgba(212,160,58,.65),0 8px 30px rgba(0,0,0,.5);border-color:rgba(212,160,58,.85)}
    .tc-hero-item-card img{box-shadow:0 0 36px rgba(245,158,11,.65),0 8px 30px rgba(0,0,0,.5);border-color:rgba(245,158,11,.85)}
    .tc-hero-shift-card img{box-shadow:0 0 36px rgba(34,211,238,.65),0 8px 30px rgba(0,0,0,.5);border-color:rgba(34,211,238,.85);animation:tcHeroShift 1s ease infinite alternate}
    .tc-hero-ability-card img{box-shadow:0 0 44px rgba(168,85,247,.8),0 8px 30px rgba(0,0,0,.5);border-color:rgba(168,85,247,.95);animation:tcHeroAbilityPulse 1.4s ease-in-out infinite}
    .tc-hero-ability .tc-hero-sub{background:linear-gradient(90deg, rgba(168,85,247,.85), rgba(139,92,246,.85));border:1px solid rgba(168,85,247,.7);box-shadow:0 0 18px rgba(168,85,247,.5);animation:tcHeroUnderline 1.2s ease-in-out infinite}
    @keyframes tcHeroPop{0%{opacity:0;transform:scale(.55) translateY(26px) rotateY(-18deg)}60%{opacity:1;transform:scale(1.04) translateY(-4px) rotateY(0)}100%{opacity:1;transform:scale(1) translateY(0) rotateY(0)}}
    @keyframes tcHeroAbilityPulse{0%,100%{box-shadow:0 0 30px rgba(168,85,247,.55),0 8px 30px rgba(0,0,0,.5)}50%{box-shadow:0 0 56px rgba(168,85,247,1),0 0 90px rgba(168,85,247,.35),0 8px 30px rgba(0,0,0,.5)}}
    @keyframes tcHeroShift{0%{box-shadow:0 0 28px rgba(34,211,238,.5),0 8px 30px rgba(0,0,0,.5)}100%{box-shadow:0 0 48px rgba(34,211,238,.95),0 0 80px rgba(34,211,238,.35),0 8px 30px rgba(0,0,0,.5)}}
    @keyframes tcHeroUnderline{0%,100%{filter:brightness(1)}50%{filter:brightness(1.35)}}

    @media(max-width:767px){
      .tc-hc{width:42px;height:60px}
      .tc-controls{gap:4px;padding:6px 10px}
      .tc-spell-card img{width:100px}
      .wb-zone-row{grid-template-columns:1fr}
      .wb-header{align-items:flex-start}
      .wb-header-controls{width:100%}
      .wb-header select{min-width:0;flex:1 1 100%}
      .wb-toolbar-main{align-items:flex-start}
      .wb-toolbar-groups{width:100%}
      .wb-sim-actions{margin-left:0}
      .wb-decks{grid-template-columns:1fr;padding:12px}
      .wb-side{padding:10px}
      .wb-stage{padding:12px}
    }
  `;
  document.head.appendChild(s);
})();
