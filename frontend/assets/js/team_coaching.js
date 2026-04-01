/**
 * Team Coaching — Animated Replay Viewer + Hand Panel
 *
 * Reuses rv* card rendering from dashboard.html (rvRenderCard, rvCardImg, rvCardsDB)
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
async function tcHandleDrop(e) { if (e.dataTransfer.files.length) await tcUpload(e.dataTransfer.files); }
async function tcHandleFiles(files) { if (files.length) await tcUpload(files); }
async function tcUpload(files) {
  const status = document.getElementById('tc-upload-status');
  if (!status) return;
  status.innerHTML = '';
  for (const file of files) {
    const form = new FormData();
    form.append('file', file);
    try {
      const resp = await fetch('/api/v1/team/replay/upload', { method: 'POST', body: form });
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
    const list = await (await fetch(url)).json();
    if (!list.length) { el.innerHTML = '<div style="color:var(--text2);font-size:0.85em;padding:8px">No replays uploaded yet</div>'; return; }
    el.innerHTML = '<div style="font-weight:600;margin-bottom:8px;font-size:0.9em">Uploaded Replays</div>' +
      list.map(r => `<div class="tc-replay-row" onclick="tcLoadReplay('${r.game_id}')">
        <span style="color:${r.winner===1?'var(--green)':'var(--red)'};font-weight:700">${r.winner===1?'W':'L'}</span>
        <strong>${r.player||'?'}</strong> vs ${r.opponent} \u2014 T${r.turns}
        <span style="color:var(--text2);font-size:0.8em;margin-left:auto">${(r.created_at||'').split('T')[0]}</span>
      </div>`).join('');
  } catch (err) { el.innerHTML = `<div style="color:var(--red);font-size:0.85em">Error: ${err.message}</div>`; }
}

// ═══ LOAD REPLAY ═══
async function tcLoadReplay(gameId) {
  const area = document.getElementById('tc-viewer-area'); if (!area) return;
  area.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text2)">Loading...</div>';
  tcAbort = true; tcPlaying = false; clearTimeout(tcPlayTimer);

  try { tcReplayData = await (await fetch(`/api/v1/team/replay/${gameId}`)).json(); }
  catch (err) { area.innerHTML = `<div style="color:var(--red);padding:20px">${err.message}</div>`; return; }

  const snaps = tcReplayData.snapshots;
  if (!snaps || !snaps.length) { area.innerHTML = '<div style="color:var(--red);padding:20px">No data</div>'; return; }

  if (!rvCardsDB) { try { rvCardsDB = await (await fetch('/api/replay/cards_db')).json(); } catch(_){} }

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
      <div class="tc-events" id="tc-events"><h4>Events</h4></div>
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

  // Spell overlay for actions/songs (old DOM has targets for arrows)
  if (!skipAnim && prev) {
    await tcShowSpellOverlay(snap, prev);
  }

  // Combat arrows — ONLY for ATTACK actions (old DOM has attacker + defender)
  if (!skipAnim && prev && snap.action_type === 'ATTACK' && !tcAbort) {
    let atkName = null, atkFieldId = null, defFieldId = null, defSideCurr = null, defSidePrev = null;
    for (const [fid, curr, prevC] of [['tc-field-our', allOur, allPrevOur], ['tc-field-opp', allOpp, allPrevOpp]]) {
      const newlyExerted = curr.find(c => {
        const pc = prevC.find(p => p.name === c.name);
        return c.exerted && pc && !pc.exerted;
      });
      if (newlyExerted) {
        atkName = newlyExerted.name;
        atkFieldId = fid;
        defFieldId = fid === 'tc-field-our' ? 'tc-field-opp' : 'tc-field-our';
        defSideCurr = fid === 'tc-field-our' ? allOpp : allOur;
        defSidePrev = fid === 'tc-field-our' ? allPrevOpp : allPrevOur;
        break;
      }
    }
    if (atkName && defFieldId) {
      // Attacker is on old DOM (not yet exerted visually, but positioned correctly)
      const srcEl = document.querySelector(`#${atkFieldId} [data-name="${atkName}"]`);
      // Defender: card that took damage or died on opposite side
      let defName = null, dmgAmount = 0;
      for (const c of defSideCurr) {
        const pc = defSidePrev.find(p => p.name === c.name);
        if (pc && c.damage > pc.damage) { defName = c.name; dmgAmount = c.damage - pc.damage; break; }
      }
      if (!defName) {
        const currNames = defSideCurr.map(c => c.name);
        const died = defSidePrev.find(c => !currNames.includes(c.name));
        if (died) defName = died.name;
      }
      // Target is on old DOM (still exists, even if it will die after board update)
      const tgtEl = defName ? document.querySelector(`#${defFieldId} [data-name="${defName}"]`) : null;
      if (srcEl && tgtEl && !tcAbort) {
        await tcDrawArrow(srcEl, tgtEl, '#ef4444', dmgAmount ? '-' + dmgAmount : '\u2694');
      }
    }
  }

  // Damage transfer (boost/ability): card heals AND another card takes damage or dies in same snapshot
  if (!skipAnim && prev && snap.action_type !== 'ATTACK' && !tcAbort) {
    // Find card that lost damage (healed)
    for (const [srcFid, srcCurr, srcPrev] of [['tc-field-our', allOur, allPrevOur], ['tc-field-opp', allOpp, allPrevOpp]]) {
      const healed = srcCurr.find(c => {
        const pc = srcPrev.find(p => p.name === c.name);
        return pc && c.damage < pc.damage;
      });
      if (!healed) continue;
      const healPc = srcPrev.find(p => p.name === healed.name);
      const dmgMoved = healPc.damage - healed.damage;
      // Find target that took damage or died (either side)
      for (const [tgtFid, tgtCurr, tgtPrev] of [['tc-field-our', allOur, allPrevOur], ['tc-field-opp', allOpp, allPrevOpp]]) {
        let tgtName = null;
        for (const c of tgtCurr) {
          if (c.name === healed.name) continue;
          const pc = tgtPrev.find(p => p.name === c.name);
          if (pc && c.damage > pc.damage) { tgtName = c.name; break; }
        }
        if (!tgtName) {
          const currNames = tgtCurr.map(c => c.name);
          const died = tgtPrev.find(c => c.name !== healed.name && !currNames.includes(c.name));
          if (died) tgtName = died.name;
        }
        if (tgtName) {
          const srcEl = document.querySelector(`#${srcFid} [data-name="${healed.name}"]`);
          const tgtEl = document.querySelector(`#${tgtFid} [data-name="${tgtName}"]`);
          if (srcEl && tgtEl) await tcDrawArrow(srcEl, tgtEl, '#f59e0b', '-' + dmgMoved);
          break;
        }
      }
      break;
    }
  }

  // ── NOW update board (death animations + innerHTML swap) ── parallel both sides
  await Promise.all([
    tcUpdateField('tc-field-our', allOur, allPrevOur, skipAnim),
    tcUpdateField('tc-field-opp', allOpp, allPrevOpp, skipAnim)
  ]);

  // Events log
  tcUpdateEvents(snap, prev);

  // Hand
  tcUpdateHand(snap.hand || [], prev ? (prev.hand || []) : []);
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

  // Detect plays (new cards on board)
  for (const side of ['our','opp']) {
    const prevNames = prevBoard[side].map(c=>c.name);
    const prevCopy = [...prevNames];
    for (const c of board[side]) {
      const pi = prevCopy.indexOf(c.name);
      if (pi >= 0) { prevCopy.splice(pi, 1); }
      else { events.push({icon:'\u25b6', cls:'rv-ep-play', txt:`<b>${tcSn(c.name)}</b> played (${c.cost||'?'})`}); }
    }
    // Deaths
    const currNames = board[side].map(c=>c.name);
    const currCopy = [...currNames];
    for (const c of prevBoard[side]) {
      const ci = currCopy.indexOf(c.name);
      if (ci >= 0) { currCopy.splice(ci, 1); }
      else { events.push({icon:'\u2620', cls:'rv-ep-dead', txt:`<b>${tcSn(c.name)}</b> destroyed`}); }
    }
    // Damage changes
    for (const c of board[side]) {
      const pc = prevBoard[side].find(p=>p.name===c.name);
      if (pc && c.damage > pc.damage) {
        events.push({icon:'\ud83d\udca5', cls:'rv-ep-dead', txt:`<b>${tcSn(c.name)}</b> -${c.damage-pc.damage} (${c.damage} total)`});
      }
    }
    // Exert (quest)
    for (const c of board[side]) {
      const pc = prevBoard[side].find(p=>p.name===c.name && !p.exerted);
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

  // 1. Animate deaths BEFORE replacing DOM
  if (!skipAnim) {
    const currNames = cards.map(c => c.name);
    const currCopy = [...currNames];
    for (const pc of prevCards) {
      const ci = currCopy.indexOf(pc.name);
      if (ci >= 0) { currCopy.splice(ci, 1); }
      else {
        const deadEl = el.querySelector(`[data-name="${pc.name}"]`);
        if (deadEl) deadEl.classList.add('tc-dying');
      }
    }
    // Also flash damage changes on existing DOM before swap
    for (const c of cards) {
      const pc = prevCards.find(p => p.name === c.name);
      if (pc && c.damage > pc.damage) {
        const dmgEl = el.querySelector(`[data-name="${c.name}"] .rv-dmg`);
        if (dmgEl) dmgEl.classList.add('tc-dmg-flash');
      }
    }
    // Wait for death animation (fixed, clearly visible)
    if (el.querySelector('.tc-dying')) {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  // 2. Build card HTML
  const prevNames = prevCards.map(c => c.name);
  const newHtml = cards.map(c => {
    const isNew = !prevNames.includes(c.name) || cards.filter(x=>x.name===c.name).length > prevNames.filter(x=>x===c.name).length;
    const db = (rvCardsDB||{})[c.name] || {};
    const imgUrl = rvCardImg ? rvCardImg(db) : '';
    const isCh = (db.type||'').toLowerCase().includes('character');
    const ink = (typeof RV_IC !== 'undefined' ? RV_IC : {})[(db.ink||'').trim()] || '';
    const {b,s} = (typeof rvSn === 'function') ? rvSn(c.name) : {b:c.name.split(' - ')[0], s:''};
    const dmg = c.damage || 0;
    const will = parseInt(db.will) || 0;
    const pc = prevCards.find(p => p.name === c.name);
    const dmgChanged = !skipAnim && pc && c.damage > pc.damage;

    let cls = 'rv-mc';
    if (ink) cls += ' rv-ink-' + ink;
    if (c.exerted) cls += ' rv-exerted';
    if (!skipAnim && isNew) cls += ' tc-anim-play tc-new-glow';
    const dmgCls = dmgChanged ? ' tc-dmg-flash' : '';
    const dmgHtml = isCh && dmg > 0 ? `<div class="rv-dmg${dmgCls}">-${dmg}</div>` : '';
    const style = imgUrl ? `background-image:url(${imgUrl});background-size:cover;background-position:center 15%` : '';

    return `<div class="${cls}" style="${style}" data-name="${c.name}" title="${c.name}">
      <div class="rv-cost">${db.cost||'?'}</div>${dmgHtml}
      <div class="rv-ovl"><div class="rv-cn2">${b}</div>${s?`<div style="font-size:0.45rem;color:rgba(255,255,255,0.6)">${s}</div>`:''}
      ${isCh?`<div class="rv-stats">${db.str?'<span>\u2694'+db.str+'</span>':''}${db.will?`<span>\ud83d\udee1${dmg>0?(will-dmg)+'/'+will:will}</span>`:''}${db.lore?'<span>\u2b50'+db.lore+'</span>':''}</div>`:''}</div></div>`;
  }).join('');

  el.innerHTML = newHtml;
}

// ═══ SPELL OVERLAY ═══
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
  const db = (rvCardsDB || {})[spellName] || {};
  const tp = (db.type || '').toLowerCase();
  if (!tp.includes('action') && !tp.includes('song')) return;

  const img = (typeof rvCardImg === 'function') ? rvCardImg(db) : '';
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
        const pc = prevBoard[side].find(p => p.name === c.name);
        if (pc && c.damage > pc.damage) {
          const tgtEl = document.querySelector(`#${fieldId} [data-name="${c.name}"]`);
          if (spellEl && tgtEl) await tcDrawArrow(spellEl, tgtEl, '#a855f7', '-' + (c.damage - pc.damage));
        }
      }
      // Removal targets (card was in prev but not in curr)
      const currNames = currBoard[side].map(c => c.name);
      for (const pc of prevBoard[side]) {
        if (!currNames.includes(pc.name)) {
          const tgtEl = document.querySelector(`#${fieldId} [data-name="${pc.name}"]`);
          if (spellEl && tgtEl) await tcDrawArrow(spellEl, tgtEl, '#a855f7', '💀');
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
    const db = (rvCardsDB||{})[name] || {};
    const img = (typeof rvCardImg === 'function') ? rvCardImg(db) : '';
    const short = name.split(' - ')[0];
    return `<div class="tc-hc${isNew?' tc-hc-new':''}" title="${name}">
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
  // Post-animation pause: gives user time to read the board state
  const pause = Math.max(200, 600 / tcSpeed);
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
    .tc-events{background:var(--bg3);border-left:1px solid var(--border);padding:8px;overflow-y:auto;max-height:400px;display:flex;flex-direction:column;gap:2px}
    .tc-events h4{font-size:.7rem;color:var(--text2);text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px}
    @media(max-width:900px){.tc-body{grid-template-columns:1fr}.tc-events{max-height:150px;border-left:none;border-top:1px solid var(--border)}}
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
    @keyframes tcDrawArrow{from{stroke-dashoffset:1000}to{stroke-dashoffset:0}}
    @keyframes tcCombatPulse{0%{transform:scale(0);opacity:0}50%{transform:scale(1.2)}100%{transform:scale(1);opacity:1}}

    .tc-hand-panel{border-top:2px solid var(--gold);padding:10px 14px;background:rgba(212,160,58,.04)}
    .tc-hand-label{font-size:.72em;color:var(--gold);font-weight:600;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
    .tc-hand-cards{display:flex;gap:5px;flex-wrap:wrap}
    .tc-hc{width:50px;height:70px;border-radius:5px;overflow:hidden;background:var(--bg3);border:1px solid var(--gold);flex-shrink:0;transition:transform .2s;position:relative}
    .tc-hc:hover{transform:translateY(-3px)}
    .tc-hc img{width:100%;height:100%;object-fit:cover}
    .tc-hc-name{display:flex;align-items:center;justify-content:center;text-align:center;font-size:.45em;padding:3px;height:100%;color:var(--text2);word-break:break-word}
    .tc-hc-new{animation:tcPlay .4s ease both}

    .tc-spell-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.55);z-index:50;animation:tcFadeIn .25s ease;transition:opacity .3s ease;border-radius:8px}
    .tc-spell-card{text-align:center;animation:tcSpellPop .3s cubic-bezier(.34,1.56,.64,1) both}
    .tc-spell-card img{width:140px;border-radius:10px;box-shadow:0 0 30px rgba(168,85,247,.6);border:2px solid rgba(168,85,247,.7)}
    .tc-spell-song img{box-shadow:0 0 30px rgba(59,130,246,.6);border-color:rgba(59,130,246,.7)}
    .tc-spell-name{margin-top:8px;font-size:.75em;font-weight:600;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.8)}
    @keyframes tcSpellPop{0%{opacity:0;transform:scale(.5) translateY(20px)}100%{opacity:1;transform:scale(1) translateY(0)}}
    @keyframes tcFadeIn{from{opacity:0}to{opacity:1}}

    @media(max-width:767px){
      .tc-hc{width:42px;height:60px}
      .tc-controls{gap:4px;padding:6px 10px}
      .tc-spell-card img{width:100px}
    }
  `;
  document.head.appendChild(s);
})();
