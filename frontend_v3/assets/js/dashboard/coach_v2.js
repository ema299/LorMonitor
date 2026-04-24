let rvCardsDB = null; // cached cards DB
let rvGameList = null; // cached game list for current matchup
let rvDeck = null, rvOpp = null; // current matchup
let rvGame = null; // current loaded game
let rvSteps = []; // computed steps
let rvTurnGroups = [];
let rvStepIdx = 0;
let rvFilter = 'all';
let rvPublicLog = null; // PG-derived normalized public log
let rvHandData = null; // hand_at_turn from .gz replay (null = not available)
let rvHandMode = 'none'; // 'full' (from .gz) | 'partial' (from log INITIAL_HAND) | 'none'

const RV_SET_MAP = {TFC:1,ROTF:2,ITI:3,URR:4,SHS:5,AZS:6,ARI:7,ROJ:8,FAB:9,WITW:10,WIS:11,WUN:12,'1':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'11':11,'12':12};
const RV_IC = {Amber:'amber',Amethyst:'amethyst',Emerald:'emerald',Ruby:'ruby',Sapphire:'sapphire',Steel:'steel'};

function rvCardImg(card) {
  if (!card||!card.set||!card.number) return '';
  const sets=card.set.split('\n').map(s=>s.trim()), nums=card.number.split('\n').map(n=>n.trim());
  for (let i=0;i<sets.length;i++) {
    const sn=RV_SET_MAP[sets[i]], cn=(nums[i]||nums[0]).replace(/^0+/,'')||'0';
    if (sn&&cn!=='-'&&cn!=='0') return `https://cards.duels.ink/lorcana/en/thumbnail/${sn}-${cn}.webp`;
  }
  return '';
}

function rvIsPersistent(name) {
  if (!rvCardsDB) return true;
  const c = rvCardsDB[name]; if (!c) return true;
  const t = (c.type||'').toLowerCase();
  return !t.includes('action') && !t.includes('song');
}
function rvIsItem(name) {
  if (!rvCardsDB) return false;
  const c = rvCardsDB[name]; if (!c) return false;
  const t = (c.type||'').toLowerCase();
  return t.includes('item') || t.includes('location');
}

// ── Mini step builder (port of Python build_game_steps) ──
function rvBuildSteps(game) {
  const rawTurns = game.turns || [];
  const turns = {};
  if (Array.isArray(rawTurns)) rawTurns.forEach(td => { if (td.t) turns[td.t] = td; });
  else Object.assign(turns, rawTurns);
  const length = game.length || Math.max(...Object.keys(turns).map(Number), 0);
  const board = {our:[], opp:[]};
  const discard = {our:[], opp:[]};
  const hand = {our:7, opp:7};
  const lore = {our:0, opp:0};
  const inkwell = {our:0, opp:0};
  const steps = [];

  for (let tNum = 1; tNum <= length; tNum++) {
    const td = turns[tNum]; if (!td) continue;
    const first = td.first_player || 'our';
    const second = first === 'our' ? 'opp' : 'our';

    for (const activeSide of [first, second]) {
      const passiveSide = activeSide === 'our' ? 'opp' : 'our';
      // Ready phase
      board[activeSide].forEach(e => { e.exerted = false; e.drying = false; });
      // Draw
      if (tNum === 1) { if (activeSide === second) hand[activeSide]++; }
      else hand[activeSide]++;

      const boardStart = rvSnap(board);
      const halfLabel = activeSide === first ? 'first' : 'second';
      const rawEvents = (td.event_log || []).filter(ev => ev.half === halfLabel);
      const events = [];
      const inkSpent = {our:0, opp:0};

      for (const ev of rawEvents) {
        const etype = ev.type;
        const evSide = ev.side || activeSide;

        if (etype === 'ink' || etype === 'ramp') {
          inkwell[evSide]++;
          events.push({type: etype, side: evSide, card: ev.card||''});
        }
        else if (etype === 'play') {
          const cardName = ev.card;
          const isSpell = !rvIsPersistent(cardName);
          let isShift = false, cost = ev.cost || 0;
          for (const pd of (td[evSide+'_play_detail']||[])) {
            if (pd.name === cardName && pd.is_shift) { isShift = true; cost = pd.ink_paid || cost; break; }
            if (pd.name === cardName) { cost = pd.ink_paid || cost; break; }
          }
          inkSpent[evSide] += cost;
          // Singer exerts
          if (ev.is_sung && ev.singer) {
            const se = rvFindEntry(board[evSide], ev.singer, true);
            if (se) se.exerted = true;
          }
          if (isSpell) { discard[evSide].push(cardName); }
          else {
            if (isShift) {
              const base = cardName.includes(' - ') ? cardName.split(' - ')[0] : cardName;
              const idx = board[evSide].findIndex(e => e.name.split(' - ')[0] === base && e.name !== cardName);
              if (idx >= 0) board[evSide].splice(idx, 1);
              board[evSide].push({name:cardName, damage:0, exerted:false, shifted:true, drying:false});
            } else {
              board[evSide].push({name:cardName, damage:0, exerted:false, shifted:false, drying:true});
            }
          }
          hand[evSide] = Math.max(0, hand[evSide] - 1);
          events.push({type:'play', side:evSide, card:cardName, cost, spell:isSpell, shift:isShift, sung:!!ev.is_sung, singer:ev.singer||null});
        }
        else if (etype === 'ability') {
          events.push({type:'ability', side:evSide, card:ev.card||'', effect:ev.effect||'', ability_name:ev.ability||''});
        }
        else if (etype === 'damage') {
          const entry = rvFindEntry(board[ev.side || evSide], ev.receiver);
          let total = ev.amount || 0;
          if (entry) { entry.damage += (ev.amount||0); total = entry.damage; }
          events.push({type:'damage', side:ev.side||evSide, card:ev.receiver, dealer:ev.dealer||'', amount:ev.amount||0, total});
        }
        else if (etype === 'destroyed') {
          const dSide = ev.side || evSide;
          const idx = board[dSide].findIndex(e => e.name === ev.card);
          if (idx >= 0) { discard[dSide].push(ev.card); board[dSide].splice(idx, 1); }
          events.push({type:'destroyed', side:dSide, card:ev.card});
        }
        else if (etype === 'quest') {
          const qe = rvFindEntry(board[evSide], ev.card, true);
          if (qe) qe.exerted = true;
          lore[evSide] += (ev.lore || 0);
          events.push({type:'quest', side:evSide, card:ev.card, lore:ev.lore||0});
        }
        else if (etype === 'challenge') {
          const ae = rvFindEntry(board[evSide], ev.attacker, true);
          if (ae) ae.exerted = true;
          let defKilled = false, atkKilled = false;
          for (const ch of (td[evSide+'_challenges']||[])) {
            if (ch.attacker === ev.attacker && ch.defender === ev.defender) {
              defKilled = ch.def_killed || false; atkKilled = ch.atk_killed || false; break;
            }
          }
          events.push({type:'challenge', side:evSide, attacker:ev.attacker, defender:ev.defender, def_killed:defKilled, atk_killed:atkKilled});
        }
        else if (etype === 'bounce') {
          const bSide = ev.side || evSide;
          const idx = board[bSide].findIndex(e => e.name === ev.card);
          if (idx >= 0) { board[bSide].splice(idx, 1); hand[bSide]++; }
          events.push({type:'bounce', side:bSide, card:ev.card});
        }
        else if (etype === 'draw') {
          hand[evSide]++;
          events.push({type:'draw', side:evSide, card:ev.card||''});
        }
        else if (etype === 'discard') {
          hand[evSide] = Math.max(0, hand[evSide] - 1);
          events.push({type:'discard', side:evSide, card:ev.card||''});
        }
        else if (etype === 'support') {
          events.push({type:'support', side:evSide, supporter:ev.supporter||'', supported:ev.supported||''});
        }
      }
      steps.push({
        turn: tNum, who: activeSide,
        label: `T${tNum} ${activeSide === 'our' ? 'Us' : 'Opp'}`,
        board_start: boardStart, board_after: rvSnap(board),
        inkwell: {our:{total:inkwell.our, spent:inkSpent.our}, opp:{total:inkwell.opp, spent:inkSpent.opp}},
        lore: {our:lore.our, opp:lore.opp},
        hand: {our:Math.max(0,hand.our), opp:Math.max(0,hand.opp)},
        events
      });
    }
  }
  return steps;
}

function rvVirtualizeTimelineStep(baseStep) {
  const ev = baseStep.timeline_event || {};
  const fx = ev.fx || {};
  const steps = [];
  const pushVirtual = (subkind, phase, summary, extra) => {
    steps.push({
      ...baseStep,
      label: `T${baseStep.turn} ${baseStep.who === 'our' ? 'Us' : 'Opp'} • ${phase}${summary ? ` • ${summary}` : ''}`,
      phase,
      summary,
      substep_kind: subkind,
      ...(extra || {}),
    });
  };

  if (ev.type === 'CARD_ATTACK') {
    pushVirtual('attack_declare', 'Attack', baseStep.summary || 'declare attack');
    const targetDamage = Number(fx.damage_to_target || 0);
    const sourceDamage = Number(fx.damage_to_source || 0);
    if (targetDamage > 0 || sourceDamage > 0) {
      pushVirtual('attack_damage', 'Damage', `exchange ${targetDamage || 0}/${sourceDamage || 0}`);
    }
    if (fx.target_destroyed || fx.source_destroyed) {
      const pieces = [];
      if (fx.target_destroyed) pieces.push('target banished');
      if (fx.source_destroyed) pieces.push('source banished');
      pushVirtual('attack_banish', 'Banish', pieces.join(' • '));
    }
    return steps;
  }

  if (ev.type === 'CARD_QUEST' && Number(fx.lore_gained || 0) > 0) {
    pushVirtual('quest_declare', 'Quest', baseStep.summary || 'declare quest');
    pushVirtual('quest_lore', 'Lore', `+${fx.lore_gained} lore`);
    return steps;
  }

  if (ev.type === 'CARD_PLAYED' && baseStep.events && baseStep.events[0] && baseStep.events[0].spell && (ev.effect_text || '').trim()) {
    pushVirtual('spell_play', 'Play', baseStep.summary || 'cast spell');
    pushVirtual('spell_effect', 'Effect', ev.effect_text);
    return steps;
  }

  if ((ev.type === 'ABILITY_TRIGGERED' || ev.type === 'ABILITY_ACTIVATED') && (ev.effect_text || '').trim()) {
    pushVirtual('ability_trigger', 'Effect', baseStep.summary || 'ability triggered');
    pushVirtual('ability_resolve', 'Resolve', ev.effect_text);
    return steps;
  }

  return [baseStep];
}

function rvDeduplicateVirtualSteps(steps) {
  const deduped = [];
  for (const step of (steps || [])) {
    const prev = deduped[deduped.length - 1];
    const ev = step && step.timeline_event;
    const prevEv = prev && prev.timeline_event;
    const effectText = ((ev && ev.effect_text) || '').trim();
    const prevEffectText = ((prevEv && prevEv.effect_text) || '').trim();
    const sourceCard = ((ev && ev.source) || {}).card || '';
    const prevSourceCard = ((prevEv && prevEv.source) || {}).card || '';
    const sameAdjacentEffect =
      prev &&
      ev &&
      prevEv &&
      step.turn === prev.turn &&
      step.who === prev.who &&
      sourceCard &&
      sourceCard === prevSourceCard &&
      effectText &&
      effectText === prevEffectText &&
      step.substep_kind &&
      prev.substep_kind &&
      (
        (step.substep_kind === 'ability_resolve' && prev.substep_kind === 'ability_trigger') ||
        (step.substep_kind === 'spell_effect' && prev.substep_kind === 'spell_play')
      );
    if (sameAdjacentEffect) continue;
    deduped.push(step);
  }
  return deduped;
}

function rvBuildStepsFromPublicLog(publicLog) {
  const timeline = (publicLog && publicLog.viewer_timeline) || [];
  const discard = {our: 0, opp: 0};
  const built = timeline.flatMap(ev => {
    const who = ev.side === 'our' ? 'our' : 'opp';
    const res = ev.resources || {};
    const fx = ev.fx || {};
    const data = (ev.raw && ev.raw.data) || {};
    const source = ev.source || {};
    const firstTarget = (ev.targets && ev.targets[0]) || {};
    const card = source.card || firstTarget.card || '';
    const renderEvent = {
      type: 'ability',
      side: who,
      card,
      effect: ev.effect_text || ev.label || '',
      ability_name: ev.type || '',
      source_card: source.card || '',
      target_cards: (ev.targets || []).map(t => t.card).filter(Boolean),
      fx,
    };

    if (ev.type === 'CARD_PLAYED') {
      renderEvent.type = 'play';
      renderEvent.card = source.card || '';
      renderEvent.cost = data.cardCost || 0;
      renderEvent.spell = !rvIsPersistent(renderEvent.card || '');
      renderEvent.shift = false;
      renderEvent.sung = false;
      renderEvent.singer = null;
    } else if (ev.type === 'CARD_INKED' || ev.type === 'CARD_PUT_INTO_INKWELL') {
      renderEvent.type = 'ink';
      renderEvent.card = source.card || '';
    } else if (ev.type === 'CARD_DRAWN' || ev.type === 'TURN_DRAW') {
      renderEvent.type = 'draw';
      renderEvent.card = source.card || '';
    } else if (ev.type === 'CARD_QUEST') {
      renderEvent.type = 'quest';
      renderEvent.card = source.card || '';
      renderEvent.lore = data.loreGained || (fx && fx.lore_gained) || 0;
    } else if (ev.type === 'CARD_ATTACK') {
      renderEvent.type = 'challenge';
      renderEvent.attacker = source.card || '';
      renderEvent.defender = firstTarget.card || '';
      renderEvent.def_killed = !!(fx && fx.target_destroyed);
      renderEvent.atk_killed = !!(fx && fx.source_destroyed);
      renderEvent.damage_to_target = fx.damage_to_target;
      renderEvent.damage_to_source = fx.damage_to_source;
    } else if (ev.type === 'CARD_DESTROYED') {
      renderEvent.type = 'destroyed';
      renderEvent.card = source.card || '';
    } else if (ev.type === 'CARD_DISCARDED') {
      renderEvent.type = 'discard';
      renderEvent.card = source.card || '';
    } else if (ev.type === 'CARD_RETURNED') {
      renderEvent.type = 'bounce';
      renderEvent.card = source.card || '';
    }

    if (ev.type === 'CARD_DESTROYED' || ev.type === 'CARD_DISCARDED') {
      discard[who] += 1;
    } else if (ev.type === 'CARD_PLAYED' && renderEvent.spell) {
      discard[who] += 1;
    }

    const phase = rvTimelinePhase(ev);
    const summary = rvTimelineSummary(ev);
    const boardAfter = ev.board_after || {our: [], opp: []};
    const boardCounts = {
      our: ((boardAfter.our || []).length),
      opp: ((boardAfter.opp || []).length),
    };
    const zones = {
      discard: {our: discard.our, opp: discard.opp},
      deck: {
        our: Math.max(0, 60 - ((res.hand || {}).our || 0) - ((res.inkwell || {}).our || 0) - boardCounts.our - discard.our),
        opp: Math.max(0, 60 - ((res.hand || {}).opp || 0) - ((res.inkwell || {}).opp || 0) - boardCounts.opp - discard.opp),
      },
    };
    const baseStep = {
      turn: ev.turn,
      who,
      label: `T${ev.turn} ${who === 'our' ? 'Us' : 'Opp'} • ${phase}${summary ? ` • ${summary}` : ''}`,
      board_start: ev.board_before || {our: [], opp: []},
      board_after: boardAfter,
      inkwell: {
        our: {total: ((res.inkwell||{}).our)||0, spent: who === 'our' ? (renderEvent.cost || 0) : 0},
        opp: {total: ((res.inkwell||{}).opp)||0, spent: who === 'opp' ? (renderEvent.cost || 0) : 0},
      },
      lore: (res.lore || {our:0, opp:0}),
      hand: (res.hand || {our:0, opp:0}),
      zones,
      events: [renderEvent],
      timeline_event: ev,
      phase,
      summary,
    };
    return rvVirtualizeTimelineStep(baseStep);
  });
  return rvDeduplicateVirtualSteps(built);
}

function rvTimelinePhase(ev) {
  const t = (ev && ev.type) || '';
  if (t === 'TURN_READY') return 'Ready';
  if (t === 'TURN_DRAW' || t === 'CARD_DRAWN') return 'Draw';
  if (t === 'CARD_INKED' || t === 'CARD_PUT_INTO_INKWELL') return 'Ink';
  if (t === 'CARD_PLAYED') return 'Play';
  if (t === 'CARD_QUEST' || t === 'LORE_GAINED') return 'Quest';
  if (t === 'CARD_ATTACK') return 'Attack';
  if (t === 'ABILITY_TRIGGERED' || t === 'ABILITY_ACTIVATED') return 'Effect';
  if (t === 'CARD_DESTROYED') return 'Banish';
  if (t === 'CARD_DISCARDED') return 'Discard';
  if (t === 'CARD_RETURNED') return 'Bounce';
  return t.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

function rvTimelineSummary(ev) {
  if (!ev) return '';
  const source = (ev.source && ev.source.card) || '';
  const target = ((ev.targets || [])[0] || {}).card || '';
  const sn = n => rvSn(n || '').b;
  switch (ev.type) {
    case 'TURN_READY':
      return 'untap / ready board';
    case 'TURN_DRAW':
      return 'automatic draw';
    case 'CARD_DRAWN':
      return source ? sn(source) : 'named draw';
    case 'CARD_INKED':
    case 'CARD_PUT_INTO_INKWELL':
      return source ? sn(source) : 'ink';
    case 'CARD_PLAYED':
      return source ? sn(source) : 'card enters play';
    case 'CARD_QUEST':
      return source ? sn(source) : 'quest';
    case 'CARD_ATTACK':
      return source && target ? `${sn(source)} -> ${sn(target)}` : (source || target ? sn(source || target) : 'challenge');
    case 'ABILITY_TRIGGERED':
    case 'ABILITY_ACTIVATED':
      return source ? sn(source) : 'ability';
    case 'CARD_DESTROYED':
      return source ? sn(source) : 'banish';
    case 'CARD_DISCARDED':
      return source ? sn(source) : 'discard';
    case 'CARD_RETURNED':
      return source ? sn(source) : 'bounce';
    default:
      return ev.label || '';
  }
}

function rvStepButtonLabel(step) {
  if (!step) return 'T?';
  return `T${rvEscapeHtml(step.turn)}`;
}

function rvBuildTurnGroups(steps) {
  const groups = [];
  let current = null;
  (steps || []).forEach((step, idx) => {
    const key = `${step.turn}|${step.who}`;
    if (!current || current.key !== key) {
      current = {
        key,
        turn: step.turn,
        who: step.who,
        start: idx,
        end: idx,
      };
      groups.push(current);
    } else {
      current.end = idx;
    }
  });
  return groups;
}

function rvPhaseClassName(phase) {
  return String(phase || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-');
}
function rvSnap(board) {
  const r = {};
  for (const s of ['our','opp']) r[s] = board[s].map(e => ({...e}));
  return r;
}
function rvFindEntry(list, name, preferReady) {
  let first = null;
  for (const e of list) {
    if (e.name === name) {
      if (!first) first = e;
      if (preferReady && !e.exerted) return e;
    }
  }
  return first;
}

// ── Replay viewer render ──
function rvSn(n) {
  if (n.includes(' - ')) { const [b,s]=n.split(' - ',2); return {b, s:s.length>12?s.slice(0,12)+'..':s}; }
  return {b: n.length>18?n.slice(0,18)+'..':n, s:''};
}

function rvRenderCard(entry, isNew, opts) {
  opts = opts || {};
  const c = (rvCardsDB||{})[entry.name] || {};
  const ink = RV_IC[(c.ink||'').trim()] || '';
  const {b,s} = rvSn(entry.name);
  const isCh = (c.type||'').toLowerCase().includes('character');
  const imgUrl = rvCardImg(c);
  const dmg = entry.damage || 0;
  const will = parseInt(c.will) || 0;
  let cls = 'rv-mc';
  if (ink) cls += ' rv-ink-' + ink;
  if (entry.exerted) cls += ' rv-exerted';
  if (entry.drying && !entry.exerted) cls += ' rv-drying';
  if (isNew) cls += ' rv-mc-new';
  if (opts.isSource) cls += ' rv-focus-source';
  if (opts.isTarget) cls += ' rv-focus-target';
  const dmgHtml = isCh && dmg > 0 ? `<div class="rv-dmg">-${dmg}</div>` : '';
  const style = imgUrl ? `background-image:url(${imgUrl});background-size:cover;background-position:center 15%` : '';
  let fxTag = '';
  if (opts.isSource && opts.isTarget) fxTag = '<div class="rv-fx-tag src">SRC/TGT</div>';
  else if (opts.isSource) fxTag = '<div class="rv-fx-tag src">SRC</div>';
  else if (opts.isTarget) fxTag = '<div class="rv-fx-tag tgt">TGT</div>';
  let hitPop = '';
  if (opts.hitText) {
    hitPop = `<div class="rv-hit-pop ${opts.hitKind || 'effect'}">${opts.hitText}</div>`;
  }
  const keyAttr = opts.cardKey ? ` data-card-key="${rvEscapeHtml(opts.cardKey)}"` : '';
  return `<div class="${cls}"${keyAttr} style="${style}" title="${entry.name}${c.ability?'\n'+c.ability.slice(0,100):''}">
    <div class="rv-cost">${c.cost||'?'}</div>${fxTag}${dmgHtml}${hitPop}
    <div class="rv-ovl"><div class="rv-cn2">${b}</div>${s?`<div style="font-size:0.45rem;color:rgba(255,255,255,0.6)">${s}</div>`:''}
    ${isCh?`<div class="rv-stats">${c.str?'<span>⚔'+c.str+'</span>':''}${c.will?`<span>🛡${dmg>0?(will-dmg)+'/'+will:will}</span>`:''}${c.lore?'<span>⭐'+c.lore+'</span>':''}</div>`:''}</div></div>`;
}

// Diff previous vs current board by (side, name) multiset — returns {our: Set, opp: Set}
function rvDiffBoard(prevBoard, currBoard) {
  const result = {our: new Set(), opp: new Set()};
  for (const side of ['our','opp']) {
    const prevCount = {};
    ((prevBoard && prevBoard[side]) || []).forEach(c => { prevCount[c.name] = (prevCount[c.name]||0) + 1; });
    const currCount = {};
    ((currBoard && currBoard[side]) || []).forEach(c => { currCount[c.name] = (currCount[c.name]||0) + 1; });
    for (const name in currCount) {
      if ((currCount[name]||0) > (prevCount[name]||0)) result[side].add(name);
    }
  }
  return result;
}

function rvBoardOverlay(step) {
  const ev = step && step.timeline_event;
  if (!ev) return '';
  const phase = step.phase || rvTimelinePhase(ev);
  const summary = step.summary || rvTimelineSummary(ev);
  const effectText = (ev.effect_text || '').trim();
  const phaseClass = rvPhaseClassName(phase);
  return `<div class="rv-board-overlay ${phaseClass}">
    <div class="rv-board-banner">
      <div>
        <div class="rv-board-phase">${rvEscapeHtml(phase)}</div>
        <div class="rv-board-summary">${rvEscapeHtml(summary || ev.label || ev.type || 'Event')}</div>
        ${effectText ? `<div class="rv-board-summary" style="margin-top:4px;color:var(--text2);font-size:0.66rem">${rvEscapeHtml(effectText)}</div>` : ''}
      </div>
      <div class="rv-board-seq">Turn ${rvEscapeHtml(step.turn)} • Seq ${rvEscapeHtml(ev.seq)}</div>
    </div>
  </div>`;
}

function rvRenderBoardAction(step) {
  const ev = step && step.timeline_event;
  if (!ev) return '';
  const source = ev.source || {};
  const target = ((ev.targets || [])[0]) || {};
  const sourceCard = source.card || '';
  const targetCard = target.card || '';
  const arrow = ((ev.fx || {}).arrow || targetCard)
    ? '<svg viewBox="0 0 40 14" aria-hidden="true"><defs><marker id="rv-arrow-head-center" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><polygon points="0 0, 6 3.5, 0 7" fill="currentColor"></polygon></marker></defs><line x1="2" y1="7" x2="34" y2="7" marker-end="url(#rv-arrow-head-center)"></line></svg>'
    : '•';
  const note = step.summary || ev.label || ev.type || '';
  if (!sourceCard && !targetCard && !note) return '';
  return `<div class="rv-action-ribbon">
    <div class="rv-action-part">
      <span class="rv-action-side">${rvEscapeHtml(rvEventSideLabel(source.side || step.who))}</span>
      <strong>${rvEscapeHtml(sourceCard || 'System')}</strong>
    </div>
    <div class="rv-action-arrow">${arrow}</div>
    <div class="rv-action-part">
      <span class="rv-action-side">${rvEscapeHtml(targetCard ? rvEventSideLabel(target.side || '') : 'Action')}</span>
      <strong>${rvEscapeHtml(targetCard || note)}</strong>
    </div>
    ${ev.effect_text ? `<div class="rv-action-note">${rvEscapeHtml(ev.effect_text)}</div>` : ''}
  </div>`;
}

function rvRenderInkwell(side, total, spent, active) {
  const label = side === 'our' ? 'Our Ink' : 'Opp Ink';
  const safeTotal = Math.max(0, Number(total || 0));
  const safeSpent = Math.max(0, Math.min(safeTotal, Number(spent || 0)));
  const cards = [];
  for (let i = 0; i < safeTotal; i++) {
    cards.push(`<div class="rv-ink-card${i < safeSpent ? ' spent' : ''}" title="${label}${i < safeSpent ? ' (used)' : ' (ready)'}"></div>`);
  }
  return `<div class="rv-ink-zone"${active ? ' style="border-color:rgba(212,160,58,0.24)"' : ''}>
    <div class="rv-ink-meta">
      <span class="rv-ink-count">${safeTotal}</span>
      <span>${label}</span>
      <span class="rv-ink-spent">${safeSpent} spent</span>
    </div>
    <div class="rv-ink-fan">${cards.join('')}</div>
  </div>`;
}

function rvRenderPileMeta(label, count, subtitle) {
  return `<div class="rv-pile">
    <div class="rv-pile-label">${rvEscapeHtml(label)}</div>
    <div class="rv-pile-count">${rvEscapeHtml(count)}</div>
    <div class="rv-pile-sub">${rvEscapeHtml(subtitle || '')}</div>
  </div>`;
}

function rvBoardFocusFlags(step, side, cardName, counts) {
  const ev = step && step.timeline_event;
  if (!ev) return {isSource:false, isTarget:false};
  const source = ev.source || {};
  const targets = Array.isArray(ev.targets) ? ev.targets : [];
  let isSource = false;
  let isTarget = false;
  if (source.card === cardName && (source.side || step.who) === side) {
    counts.source[cardName] = (counts.source[cardName] || 0) + 1;
    isSource = counts.source[cardName] === 1;
  }
  const matchingTargets = targets.filter(t => t.card === cardName && t.side === side);
  if (matchingTargets.length) {
    counts.target[cardName] = (counts.target[cardName] || 0) + 1;
    isTarget = counts.target[cardName] <= matchingTargets.length;
  }
  let hitText = '';
  let hitKind = '';
  const fx = (ev && ev.fx) || {};
  const sub = (step && step.substep_kind) || '';
  if (isTarget && fx.damage_to_target != null && Number(fx.damage_to_target) > 0) {
    hitText = `-${fx.damage_to_target}`;
    hitKind = 'damage';
  } else if (isSource && fx.damage_to_source != null && Number(fx.damage_to_source) > 0) {
    hitText = `-${fx.damage_to_source}`;
    hitKind = 'damage';
  } else if (isSource && fx.lore_gained != null && Number(fx.lore_gained) > 0) {
    hitText = `+${fx.lore_gained} lore`;
    hitKind = 'lore';
  } else if (isSource && (sub === 'ability_trigger' || sub === 'spell_effect')) {
    hitText = 'effect';
    hitKind = 'effect';
  } else if (isSource && (ev.type === 'CARD_DRAWN' || ev.type === 'TURN_DRAW')) {
    hitText = 'draw';
    hitKind = 'draw';
  }
  return {isSource, isTarget, hitText, hitKind};
}

function rvCaptureBoardPositions(root) {
  const out = {};
  if (!root) return out;
  root.querySelectorAll('[data-card-key]').forEach(node => {
    out[node.dataset.cardKey] = node.getBoundingClientRect();
  });
  return out;
}

function rvAnimateBoardFlip(root, prevRects) {
  if (!root || !prevRects) return;
  root.querySelectorAll('[data-card-key]').forEach(node => {
    const key = node.dataset.cardKey;
    const prev = prevRects[key];
    if (!prev) return;
    const next = node.getBoundingClientRect();
    const dx = prev.left - next.left;
    const dy = prev.top - next.top;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
    node.classList.add('rv-flip-move');
    node.style.transform = `translate(${dx}px, ${dy}px)`;
    requestAnimationFrame(() => {
      node.style.transform = '';
    });
    setTimeout(() => node.classList.remove('rv-flip-move'), 520);
  });
}

function rvRenderBoard(boardState, step, newNames) {
  const el = document.getElementById('rv-board'); if (!el) return;
  const prevRects = rvCaptureBoardPositions(el);
  const g = rvFilteredGames()[rvGameIdx];
  const nOur = (newNames && newNames.our) || new Set();
  const nOpp = (newNames && newNames.opp) || new Set();
  // Only mark the first K duplicates as "new" (K = how many extra appeared this step)
  const mkRenderer = (side) => {
    const nameSet = side === 'our' ? nOur : nOpp;
    const used = {};
    const focusCounts = {source:{}, target:{}};
    const cardCounts = {};
    return (card) => {
      let isNew = false;
      if (nameSet.has(card.name)) {
        used[card.name] = (used[card.name]||0) + 1;
        isNew = used[card.name] === 1; // first occurrence gets the glow
      }
      cardCounts[card.name] = (cardCounts[card.name] || 0) + 1;
      const cardKey = `${side}:${card.name}:${cardCounts[card.name]}`;
      const focus = rvBoardFocusFlags(step, side, card.name, focusCounts);
      return rvRenderCard(card, isNew, {...focus, cardKey});
    };
  };
  let html = '<div class="rv-arena">';
  // Opponent field
  const renderOpp = mkRenderer('opp');
  html += `<div class="rv-side opp">
    <div class="rv-side-meta">
      <div class="rv-zone-meta">
        ${rvRenderPileMeta('Opp Deck', step.zones?.deck?.opp ?? '?', 'cards left')}
        ${rvRenderPileMeta('Opp Discard', step.zones?.discard?.opp ?? 0, 'discard pile')}
      </div>
      <div class="rv-blbl"><span>${g?.en||'Opp'}</span> ${step.who==='opp'?'<span class="rv-ap">◀ turn</span>':''}</div>
    </div>`;
  html += `<div class="rv-field ${step.who==='opp'?'rv-field-active':'rv-field-inactive'}">`;
  const oppCards = boardState.opp || [];
  const oppEx = oppCards.filter(c=>c.exerted), oppRd = oppCards.filter(c=>!c.exerted&&!rvIsItem(c.name)), oppIt = oppCards.filter(c=>rvIsItem(c.name));
  if (oppEx.length) html += `<div class="rv-zone exerted"><div class="rv-zone-label">Exerted Characters (${oppEx.length})</div><div class="rv-card-row">${oppEx.map(renderOpp).join('')}</div></div>`;
  html += `<div class="rv-battle-mid">
    <div class="rv-zone ready"><div class="rv-zone-label">Ready Characters (${oppRd.length})</div><div class="rv-card-row">${oppRd.map(renderOpp).join('')}</div></div>
    <div class="rv-utility-col">
      <div class="rv-zone items"><div class="rv-zone-label">Items / Locations (${oppIt.length})</div><div class="rv-card-row">${oppIt.map(renderOpp).join('')}</div></div>
    </div>
  </div>`;
  html += rvRenderInkwell('opp', step.inkwell?.opp?.total || 0, step.inkwell?.opp?.spent || 0, step.who === 'opp');
  html += `</div></div>`;
  html += `<div class="rv-centerline">Battlefield</div>`;
  // Our field
  const renderOur = mkRenderer('our');
  const ourCards = boardState.our || [];
  const ourEx = ourCards.filter(c=>c.exerted), ourRd = ourCards.filter(c=>!c.exerted&&!rvIsItem(c.name)), ourIt = ourCards.filter(c=>rvIsItem(c.name));
  html += `<div class="rv-side ours">`;
  html += `<div class="rv-field ${step.who==='our'?'rv-field-active':'rv-field-inactive'}">`;
  if (ourEx.length) html += `<div class="rv-zone exerted"><div class="rv-zone-label">Exerted Characters (${ourEx.length})</div><div class="rv-card-row">${ourEx.map(renderOur).join('')}</div></div>`;
  html += `<div class="rv-battle-mid">
    <div class="rv-zone ready"><div class="rv-zone-label">Ready Characters (${ourRd.length})</div><div class="rv-card-row">${ourRd.map(renderOur).join('')}</div></div>
    <div class="rv-utility-col">
      <div class="rv-zone items"><div class="rv-zone-label">Items / Locations (${ourIt.length})</div><div class="rv-card-row">${ourIt.map(renderOur).join('')}</div></div>
    </div>
  </div>`;
  html += rvRenderInkwell('our', step.inkwell?.our?.total || 0, step.inkwell?.our?.spent || 0, step.who === 'our');
  html += `</div>`;
  html += `<div class="rv-side-meta">
    <div class="rv-zone-meta">
      ${rvRenderPileMeta('Our Deck', step.zones?.deck?.our ?? '?', 'cards left')}
      ${rvRenderPileMeta('Our Discard', step.zones?.discard?.our ?? 0, 'discard pile')}
    </div>
    <div class="rv-blbl"><span>${g?.on||'Us'}</span> ${step.who==='our'?'<span class="rv-ap">◀ turn</span>':''}</div>
  </div>`;
  html += `</div></div>`;
  el.innerHTML = html;
  rvAnimateBoardFlip(el, prevRects);
}

function rvRenderEvents(events, step) {
  const el = document.getElementById('rv-events'); if (!el) return;
  if (step && step.timeline_event) {
    el.innerHTML = rvRenderTimelineEvent(step);
    return;
  }
  const iconMap = {play:'▶',ability:'✨',damage:'💥',destroyed:'☠',quest:'⭐',challenge:'⚔',bounce:'↩',draw:'🃏',ink:'●',ramp:'●',discard:'✖',support:'❤'};
  const clsMap = {play:'rv-ep-play',ability:'rv-ep-ab',damage:'rv-ep-dead',destroyed:'rv-ep-dead',quest:'rv-ep-quest',challenge:'rv-ep-chal',draw:'rv-ep-draw'};
  let html = '<h4 id="rv-step-label"></h4>';
  const sn = n => rvSn(n||'').b;
  const preview = (name) => {
    if (!name) return '';
    const img = rvCardImgByName(name);
    if (!img) return `<div style="min-width:54px;height:72px;border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:6px;font-size:.58rem;line-height:1.1;color:var(--text2);display:flex;align-items:center;justify-content:center;text-align:center">${sn(name)}</div>`;
    return `<div style="min-width:54px;height:72px;border:1px solid rgba(255,255,255,.16);border-radius:8px;background-image:url(${img});background-size:cover;background-position:center 20%;box-shadow:0 4px 18px rgba(0,0,0,.25)"></div>`;
  };
  for (const ev of events) {
    const icon = iconMap[ev.type]||'•';
    const cls = clsMap[ev.type]||'';
    let txt = '';
    let cardPreview = preview(ev.card || ev.source_card || '');
    if (ev.type==='play') txt=`<b>${sn(ev.card)}</b> (${ev.cost})${ev.spell?' [SPELL]':''}${ev.sung?' [SONG]':''}${ev.shift?' [SHIFT]':''}`;
    else if (ev.type==='ability') {
      const targets = (ev.target_cards || []).map(sn).join(' → ');
      txt=`<b>${sn(ev.card||ev.source_card)}</b>: ${ev.effect||ev.ability_name||''}${targets?`<div style="margin-top:4px;color:var(--text2)">→ ${targets}</div>`:''}`;
    }
    else if (ev.type==='damage') txt=`<b>${sn(ev.card)}</b> -${ev.amount} (${ev.total})`;
    else if (ev.type==='destroyed') txt=`<b>${sn(ev.card)}</b> dies`;
    else if (ev.type==='quest') txt=`<b>${sn(ev.card)}</b> +${ev.lore} lore`;
    else if (ev.type==='challenge') {
      txt=`<b>${sn(ev.attacker)}</b> → <b>${sn(ev.defender)}</b>${ev.def_killed?' ☠':''}`;
      if (ev.damage_to_target != null || ev.damage_to_source != null) {
        txt += `<div style="margin-top:4px;color:var(--text2)">DMG ${ev.damage_to_target ?? '?'} / ${ev.damage_to_source ?? '?'}</div>`;
      }
      cardPreview = `<div style="display:flex;gap:8px;align-items:center">${preview(ev.attacker)}${ev.defender?`<div style="color:var(--text2);font-size:1rem">→</div>${preview(ev.defender)}`:''}</div>`;
    }
    else if (ev.type==='bounce') txt=`<b>${sn(ev.card)}</b> bounced`;
    else if (ev.type==='draw') txt=`Draw: <b>${sn(ev.card)}</b>`;
    else if (ev.type==='ink'||ev.type==='ramp') txt=`Ink: ${sn(ev.card)}`;
    else txt = ev.type;
    html += `<div class="rv-ev" style="display:flex;align-items:flex-start;gap:10px;justify-content:space-between">
      <div style="display:flex;gap:10px;min-width:0;flex:1 1 auto">
        <span class="rv-ei ${cls}">${icon}</span>
        <span style="min-width:0">${txt}</span>
      </div>
      <div style="flex:0 0 auto">${cardPreview}</div>
    </div>`;
  }
  if (!events.length) html += '<div style="color:var(--text2);font-size:0.72rem">No events</div>';
  el.innerHTML = html;
}

function rvUpdateCounters(step, animate) {
  const ids = ['rv-cOL','rv-cEL','rv-cOI','rv-cEI','rv-cOH','rv-cEH'];
  const vals = [step.lore.our, step.lore.opp, `${step.inkwell.our.spent}/${step.inkwell.our.total}`, `${step.inkwell.opp.spent}/${step.inkwell.opp.total}`, step.hand.our, step.hand.opp];
  ids.forEach((id,i) => {
    const el = document.getElementById(id); if (!el) return;
    const box = el.closest('.rv-ct');
    const newVal = String(vals[i]);
    const changed = el.textContent !== newVal;
    el.textContent = newVal;
    if (box && animate) {
      box.classList.remove('rv-ct-step');
      void box.offsetWidth;
      box.classList.add('rv-ct-step');
      setTimeout(() => box.classList.remove('rv-ct-step'), 520);
    }
    if (animate && changed) {
      el.classList.remove('rv-cv-flash');
      // force reflow to restart transition
      void el.offsetWidth;
      el.classList.add('rv-cv-flash');
      setTimeout(() => el.classList.remove('rv-cv-flash'), 260);
    }
  });
  const lbl = document.getElementById('rv-step-label');
  if (lbl) lbl.textContent = step.label;
}

function rvAnimateStepContainers() {
  ['rv-board', 'rv-events', 'rv-hand-cards'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('rv-step-enter');
    void el.offsetWidth;
    el.classList.add('rv-step-enter');
    setTimeout(() => el.classList.remove('rv-step-enter'), 460);
  });
}

let rvPlaying = false;
let rvPlayTimer = null;
let rvPlayToIdx = null;
let rvSpeed = 3200; // ms base step
const RV_SPEEDS = [5200, 3200, 1800, 950];
const RV_SPEED_LABELS = ['0.35x', '0.6x', '1x', '2x'];
let rvSpeedIdx = 1; // default slow

function rvPlay() {
  if (rvPlaying) { rvStop(); return; }
  rvPlaying = true;
  rvPlayToIdx = null;
  const btn = document.getElementById('rv-play');
  if (btn) { btn.textContent = '⏸'; btn.title = 'Pause'; }
  rvTick();
}
function rvStop() {
  rvPlaying = false;
  rvPlayToIdx = null;
  if (rvPlayTimer) { clearTimeout(rvPlayTimer); rvPlayTimer = null; }
  const btn = document.getElementById('rv-play');
  if (btn) { btn.textContent = '▶'; btn.title = 'Play'; }
}
function rvTick() {
  if (!rvPlaying) return;
  if (rvPlayToIdx != null && rvStepIdx >= rvPlayToIdx) {
    rvStop();
    return;
  }
  if (rvStepIdx < rvSteps.length - 1) {
    rvGoToStep(rvStepIdx + 1, true);
    const step = rvSteps[rvStepIdx];
    const pause = rvAutoplayDelay(step);
    rvPlayTimer = setTimeout(rvTick, pause);
  } else {
    rvStop(); // end of game
  }
}
function rvCycleSpeed() {
  rvSpeedIdx = (rvSpeedIdx + 1) % RV_SPEEDS.length;
  rvSpeed = RV_SPEEDS[rvSpeedIdx];
  const btn = document.getElementById('rv-speed');
  if (btn) btn.textContent = RV_SPEED_LABELS[rvSpeedIdx];
}

function rvAutoplayDelay(step) {
  if (!step || !step.timeline_event) return rvSpeed;
  const sub = step.substep_kind || '';
  if (sub === 'attack_declare') return Math.round(rvSpeed * 1.45);
  if (sub === 'attack_damage') return Math.round(rvSpeed * 1.55);
  if (sub === 'attack_banish') return Math.round(rvSpeed * 1.3);
  if (sub === 'quest_declare') return Math.round(rvSpeed * 1.15);
  if (sub === 'quest_lore') return Math.round(rvSpeed * 1.2);
  if (sub === 'spell_play') return Math.round(rvSpeed * 1.2);
  if (sub === 'spell_effect') return Math.round(rvSpeed * 1.45);
  if (sub === 'ability_trigger') return Math.round(rvSpeed * 1.2);
  if (sub === 'ability_resolve') return Math.round(rvSpeed * 1.45);
  const type = step.timeline_event.type || '';
  if (type === 'TURN_READY') return Math.round(rvSpeed * 0.95);
  if (type === 'TURN_DRAW' || type === 'CARD_DRAWN') return Math.round(rvSpeed * 0.9);
  if (type === 'CARD_INKED' || type === 'CARD_PUT_INTO_INKWELL') return Math.round(rvSpeed * 1.05);
  if (type === 'CARD_PLAYED') return Math.round(rvSpeed * 1.35);
  if (type === 'ABILITY_TRIGGERED' || type === 'ABILITY_ACTIVATED') return Math.round(rvSpeed * 1.55);
  if (type === 'CARD_ATTACK') return Math.round(rvSpeed * 1.7);
  if (type === 'CARD_DESTROYED') return Math.round(rvSpeed * 1.25);
  if (type === 'CARD_QUEST' || type === 'LORE_GAINED') return Math.round(rvSpeed * 1.2);
  return rvSpeed;
}

function rvPlayTurnGroup(groupIdx) {
  const group = rvTurnGroups[groupIdx];
  if (!group) return;
  rvStop();
  rvGoToStep(group.start, false);
  if (group.start >= group.end) return;
  rvPlaying = true;
  rvPlayToIdx = group.end;
  const btn = document.getElementById('rv-play');
  if (btn) { btn.textContent = '⏸'; btn.title = 'Pause'; }
  rvTick();
}

let rvGameIdx = 0;
function rvFilteredGames() {
  if (!rvGameList) return [];
  if (rvFilter === 'all') return rvGameList;
  if (rvFilter === 'W') return rvGameList.filter(g=>g.r==='W');
  if (rvFilter === 'L') return rvGameList.filter(g=>g.r==='L');
  if (rvFilter === 'otp') return rvGameList.filter(g=>g.otp);
  if (rvFilter === 'otd') return rvGameList.filter(g=>!g.otp);
  return rvGameList;
}

function rvGoToStep(idx, fromAutoplay) {
  if (!rvSteps.length || idx < 0 || idx >= rvSteps.length) return;
  if (!fromAutoplay) rvStop(); // manual navigation stops autoplay
  const prevIdx = rvStepIdx;
  const prevStep = (prevIdx !== idx) ? rvSteps[prevIdx] : null;
  // Animate only on forward-by-one moves (autoplay or "next"), not on jumps/rewind
  const animate = (idx === prevIdx + 1);
  rvStepIdx = idx;
  const step = rvSteps[idx];
  // Update step buttons + scroll active into view
  const activeGroupIdx = rvTurnGroups.findIndex(g => idx >= g.start && idx <= g.end);
  document.querySelectorAll('.rv-sb').forEach((b,i)=>{
    b.classList.toggle('active',i===activeGroupIdx);
    if (i===activeGroupIdx) b.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});
  });
  const sn = document.getElementById('rv-step-num');
  if (sn) sn.textContent = `${idx+1}/${rvSteps.length}`;
  const newNames = animate ? rvDiffBoard(prevStep && prevStep.board_after, step.board_after) : null;
  rvRenderBoard(step.board_after, step, newNames);
  rvRenderEvents(step.events, step);
  rvUpdateCounters(step, animate);
  rvRenderHand(step, animate);
  if (animate) rvAnimateStepContainers();
}

function rvRenderHand(step, animate) {
  const panel = document.getElementById('rv-hand-panel');
  if (!panel) return;

  if (rvHandMode === 'none') { panel.style.display = 'none'; return; }
  panel.style.display = 'block';

  const badge = document.getElementById('rv-hand-badge');
  const countEl = document.getElementById('rv-hand-count');
  const cardsEl = document.getElementById('rv-hand-cards');
  if (!cardsEl) return;

  const turnKey = String(step.turn || 1);

  if (rvHandMode === 'full' && rvHandData && rvHandData.hand_at_turn) {
    // Full hand from .gz replay
    if (badge) { badge.textContent = '🔓 Full'; badge.className = 'rv-hand-badge full'; }
    const hand = rvHandData.hand_at_turn[turnKey] || [];
    if (countEl) countEl.textContent = `${hand.length} cards`;

    const prevTurnKey = String(Math.max(1, (step.turn || 1) - 1));
    const prevHand = rvHandData.hand_at_turn[prevTurnKey] || [];
    const prevSet = new Set(prevHand);

    cardsEl.innerHTML = hand.map(name => {
      const isNew = animate && !prevSet.has(name);
      const img = rvCardImgByName(name);
      return `<div class="rv-hc${isNew ? ' rv-hc-new' : ''}" title="${name}">
        ${img ? `<img src="${img}" alt="${name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
        <div class="rv-hc-name" ${img ? 'style="display:none"' : ''}>${name.split(' - ')[0]}</div>
      </div>`;
    }).join('');
    // Stagger draw-in: each new card picks up an 80ms-per-index delay
    if (animate) {
      cardsEl.querySelectorAll('.rv-hc-new').forEach((el, i) => {
        el.style.animationDelay = (i * 80) + 'ms';
      });
    }

  } else if (rvHandMode === 'partial') {
    // Partial hand from log (initial hand known, draws unknown)
    if (badge) { badge.textContent = '🔒 Partial'; badge.className = 'rv-hand-badge partial'; }
    const handSize = step.hand ? step.hand.our : 7;
    if (countEl) countEl.textContent = `${handSize} cards`;

    // Show initial hand cards that haven't been played yet (rough tracking)
    let html = '';
    if (rvHandData && rvHandData.initial_hand) {
      // known cards still in hand
      const known = rvHandData.known_at_turn ? (rvHandData.known_at_turn[turnKey] || []) : rvHandData.initial_hand;
      known.forEach(name => {
        const img = rvCardImgByName(name);
        html += `<div class="rv-hc" title="${name}">
          ${img ? `<img src="${img}" alt="${name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
          <div class="rv-hc-name" ${img ? 'style="display:none"' : ''}>${name.split(' - ')[0]}</div>
        </div>`;
      });
      // unknown draws
      const unknownCount = Math.max(0, handSize - known.length);
      for (let i = 0; i < unknownCount; i++) {
        html += '<div class="rv-hc rv-hc-unknown"></div>';
      }
    } else {
      for (let i = 0; i < handSize; i++) {
        html += '<div class="rv-hc rv-hc-unknown"></div>';
      }
    }
    cardsEl.innerHTML = html;
  }
}

function rvBuildPartialHand(game, initialHand) {
  // Build known hand cards per turn from log data (initial hand - played - inked + ability draws)
  const hand = [...initialHand];
  const result = {};
  let currentTurn = 1;
  result['1'] = [...hand];

  if (!game.turns) return result;
  const turns = Array.isArray(game.turns) ? game.turns : Object.values(game.turns);

  for (const t of turns) {
    const tn = t.t || t.turn || 0;
    if (tn > currentTurn) {
      currentTurn = tn;
      result[String(currentTurn)] = [...hand];
    }
    // Remove played cards from hand
    const plays = [...(t.our_plays || []), ...(t.our_play_detail || []).map(p => p.name || p.card)].filter(Boolean);
    plays.forEach(c => { const i = hand.indexOf(c); if (i >= 0) hand.splice(i, 1); });
    // Remove inked cards
    const inked = t.our_inkwell || [];
    if (Array.isArray(inked)) inked.forEach(c => { const i = hand.indexOf(c); if (i >= 0) hand.splice(i, 1); });
    // Add ability draws (named)
    const drawn = t.our_drawn || [];
    if (Array.isArray(drawn)) drawn.forEach(c => { if (typeof c === 'string') hand.push(c); else if (c && c.name) hand.push(c.name); });
  }
  return result;
}

function rvCardImgByName(name) {
  if (!rvCardsDB || !rvCardsDB[name]) return '';
  return rvCardImg(rvCardsDB[name]);
}

function rvCardDetailsByName(name) {
  if (!rvCardsDB || !name || !rvCardsDB[name]) return null;
  const c = rvCardsDB[name];
  return {
    name,
    image: rvCardImg(c),
    cost: c.cost || '?',
    type: c.type || '',
    ink: (c.ink || '').trim(),
    strength: c.str || '',
    willpower: c.will || '',
    lore: c.lore || '',
    ability: c.ability || c.text || '',
  };
}

function rvEscapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function kcResponseSections(resp) {
  const sections = [];
  if (!resp || typeof resp !== 'object') return sections;
  if (resp.headline) sections.push({ title: 'Threat', body: resp.headline });
  if (resp.core_rule) sections.push({ title: 'How to Respond', body: resp.core_rule });
  if (Array.isArray(resp.priority_actions) && resp.priority_actions.length) {
    sections.push({ title: 'Priority Actions', items: resp.priority_actions });
  }
  if (Array.isArray(resp.what_to_avoid) && resp.what_to_avoid.length) {
    sections.push({ title: 'What to Avoid', items: resp.what_to_avoid });
  }
  if (resp.stock_build_note) sections.push({ title: 'If You Play the Stock Build', body: resp.stock_build_note });
  if (resp.off_meta_note) sections.push({ title: 'If Your Build Is Different', body: resp.off_meta_note });
  if (resp.play_draw_note) sections.push({ title: 'Play / Draw Note', body: resp.play_draw_note });
  if (resp.failure_state) sections.push({ title: 'Failure State', body: resp.failure_state });
  return sections;
}

function kcResponseSummary(resp) {
  if (!resp || typeof resp !== 'object') return '';
  return resp.headline || resp.core_rule || resp.strategy || '';
}

function kcRenderResponse(resp, opts) {
  opts = opts || {};
  if (!resp || typeof resp !== 'object') return '';
  const sections = kcResponseSections(resp);
  let html = '';
  if (sections.length) {
    sections.forEach(section => {
      html += `<div style="margin-top:${opts.compact ? '6px' : '8px'}">`;
      html += `<div style="font-size:${opts.compact ? '0.8em' : '0.84em'};font-weight:700;color:var(--green);margin-bottom:4px">${section.title}</div>`;
      if (section.body) html += `<div style="font-size:${opts.compact ? '0.82em' : '0.85em'}">${section.body}</div>`;
      if (section.items && section.items.length) {
        html += `<div class="cv2-resp-chips">`;
        section.items.forEach(item => { html += `<span class="cv2-resp-chip">${item}</span>`; });
        html += `</div>`;
      }
      html += `</div>`;
    });
  } else if (resp.strategy) {
    html += `<div style="font-size:${opts.compact ? '0.82em' : '0.85em'}">${resp.strategy}</div>`;
  }
  if (resp.cards && resp.cards.length) {
    html += `<div style="margin-top:6px;font-size:${opts.compact ? '0.8em' : '0.82em'}"><strong>Key cards:</strong> ${resp.cards.join(', ')}</div>`;
  }
  if (resp.turn_needed) {
    html += `<div style="font-size:${opts.compact ? '0.78em' : '0.8em'};color:var(--text2);margin-top:4px">Needed by: T${resp.turn_needed}</div>`;
  }
  return html;
}

function rvEventSideLabel(side) {
  if (side === 'our') return 'Us';
  if (side === 'opp') return 'Opp';
  return side || 'Unknown';
}

function rvRenderFocusCard(name, subtitle, effectText, extraChips) {
  if (!name) return '';
  const meta = rvCardDetailsByName(name);
  const safeSubtitle = rvEscapeHtml(subtitle || '');
  const chips = [];
  if (meta) {
    if (meta.cost) chips.push(`Cost ${rvEscapeHtml(meta.cost)}`);
    if (meta.type) chips.push(rvEscapeHtml(meta.type));
    if (meta.ink) chips.push(rvEscapeHtml(meta.ink));
    if (meta.strength || meta.willpower) chips.push(`Stats ${rvEscapeHtml(meta.strength || '?')}/${rvEscapeHtml(meta.willpower || '?')}`);
    if (meta.lore) chips.push(`Lore ${rvEscapeHtml(meta.lore)}`);
  }
  (extraChips || []).forEach(chip => { if (chip) chips.push(rvEscapeHtml(chip)); });
  const focusText = effectText || (meta && meta.ability) || '';
  const art = meta && meta.image
    ? `<div class="rv-ev-focus-art" style="background-image:url(${meta.image})"></div>`
    : `<div class="rv-ev-focus-art rv-ev-focus-fallback">${rvEscapeHtml(rvSn(name).b)}</div>`;
  return `<div class="rv-ev-focus">
    ${art}
    <div class="rv-ev-focus-copy">
      <div class="rv-ev-focus-title">${rvEscapeHtml(name)}</div>
      <div class="rv-ev-focus-sub">${safeSubtitle}</div>
      ${chips.length ? `<div class="rv-ev-focus-lines">${chips.map(chip => `<span class="rv-ev-focus-line">${chip}</span>`).join('')}</div>` : ''}
      ${focusText ? `<div class="rv-ev-focus-text">${rvEscapeHtml(focusText)}</div>` : ''}
    </div>
  </div>`;
}

function rvRenderTimelineEvent(step) {
  const ev = step && step.timeline_event;
  if (!ev) return '';

  const iconMap = {CARD_PLAYED:'▶',CARD_INKED:'●',CARD_PUT_INTO_INKWELL:'●',CARD_DRAWN:'🃏',TURN_DRAW:'🃏',CARD_QUEST:'⭐',CARD_ATTACK:'⚔',ABILITY_TRIGGERED:'✨',ABILITY_ACTIVATED:'✨',CARD_DESTROYED:'☠',CARD_DISCARDED:'✖',CARD_RETURNED:'↩',LORE_GAINED:'⭐'};
  const source = ev.source || {};
  const targets = Array.isArray(ev.targets) ? ev.targets : [];
  const firstTarget = targets[0] || {};
  const fx = ev.fx || {};
  const raw = ev.raw || {};
  const data = raw.data || {};
  const sourceName = source.card || '';
  const sourceSide = source.side || step.who;
  const targetName = firstTarget.card || '';
  const targetSide = firstTarget.side || (step.who === 'our' ? 'opp' : 'our');
  const chips = [];
  if (fx.kind) chips.push(fx.kind);
  if (fx.damage_to_target != null) chips.push(`to target ${fx.damage_to_target}`);
  if (fx.damage_to_source != null) chips.push(`to source ${fx.damage_to_source}`);
  if (fx.lore_gained) chips.push(`lore +${fx.lore_gained}`);
  if (data.cardCost != null && ev.type === 'CARD_PLAYED') chips.push(`cost ${data.cardCost}`);
  if (fx.target_destroyed) chips.push('target banished');
  if (fx.source_destroyed) chips.push('source banished');

  const arrow = fx.arrow || targetName;
  const flowTarget = targetName
    ? `<div class="rv-ev-node">
        <div class="rv-ev-role">Target</div>
        <div class="rv-ev-name">${rvEscapeHtml(targetName)}</div>
        <div class="rv-ev-side">${rvEscapeHtml(rvEventSideLabel(targetSide))}</div>
      </div>`
    : `<div class="rv-ev-node ghost">
        <div class="rv-ev-role">Target</div>
        <div class="rv-ev-name">No explicit target</div>
        <div class="rv-ev-side">Global / self / unresolved</div>
      </div>`;

  let summary = ev.label || ev.type || 'Event';
  if (ev.type === 'CARD_ATTACK' && sourceName) {
    summary = `${sourceName}${targetName ? ` attacks ${targetName}` : ' attacks'}`;
  } else if (ev.type === 'CARD_QUEST' && sourceName) {
    summary = `${sourceName} quests`;
  } else if (ev.type === 'CARD_PLAYED' && sourceName) {
    summary = `${sourceName} enters play`;
  } else if (ev.type === 'CARD_INKED' && sourceName) {
    summary = `${sourceName} goes to ink`;
  } else if (ev.type === 'CARD_DRAWN' && sourceName) {
    summary = `${sourceName} drawn`;
  } else if (ev.type === 'CARD_DESTROYED' && sourceName) {
    summary = `${sourceName} is banished`;
  }

  const focusName = sourceName || targetName;
  const focusSubtitle = `${rvEventSideLabel(sourceSide)} • ${ev.type || 'event'}`;
  const focusText = ev.effect_text || summary;
  const targetFocus = targetName && targetName !== focusName
    ? rvRenderFocusCard(targetName, `${rvEventSideLabel(targetSide)} • target`, `Target involved in ${summary}`, [])
    : '';

  return `<div class="rv-ev-shell">
    <div class="rv-ev-head">
      <h4 id="rv-step-label">${rvEscapeHtml(step.label || summary)}</h4>
      <span class="rv-ev-type">${rvEscapeHtml(ev.type || 'EVENT')}</span>
    </div>
    <div class="rv-ev-turn">Turn ${rvEscapeHtml(ev.turn)} • Seq ${rvEscapeHtml(ev.seq)} • ${rvEscapeHtml(rvEventSideLabel(step.who))} • ${rvEscapeHtml(step.phase || rvTimelinePhase(ev))}</div>
    <div class="rv-ev-main">
      <div class="rv-ev-flow">
        <div class="rv-ev-node">
          <div class="rv-ev-role">Source</div>
          <div class="rv-ev-name">${rvEscapeHtml(sourceName || 'System')}</div>
          <div class="rv-ev-side">${rvEscapeHtml(rvEventSideLabel(sourceSide))}</div>
        </div>
        <div class="rv-ev-arrow">${arrow ? '→' : '•'}</div>
        ${flowTarget}
      </div>
      ${chips.length ? `<div class="rv-ev-meta">${chips.map(chip => `<span class="rv-ev-chip">${rvEscapeHtml(chip)}</span>`).join('')}</div>` : ''}
      <div class="rv-ev-text"><strong>${rvEscapeHtml(summary)}</strong>${ev.effect_text ? `<div style="margin-top:6px">${rvEscapeHtml(ev.effect_text)}</div>` : ''}</div>
      <div class="rv-ev-list">
        <div class="rv-ev">
          <span class="rv-ei">${iconMap[ev.type] || '•'}</span>
          <span>${rvEscapeHtml(ev.label || ev.type || 'Event')}</span>
        </div>
      </div>
    </div>
    ${focusName ? rvRenderFocusCard(focusName, focusSubtitle, focusText, chips) : '<div class="rv-ev-empty">No card focus available for this event.</div>'}
    ${targetFocus}
  </div>`;
}

async function rvLoadGame(gameInfo) {
  const wrap = document.getElementById('rv-board');
  if (wrap) wrap.innerHTML = '<div class="rv-loading">Loading game...</div>';
  try {
    const resp = await fetch(`/api/replay/game?deck=${rvDeck}&opp=${rvOpp}&idx=${gameInfo.i}`);
    const data = await resp.json();
    if (data.error) { if(wrap) wrap.innerHTML = `<div class="rv-empty">${data.error}</div>`; return; }
    rvGame = data;
    rvPublicLog = null;
    if (gameInfo && gameInfo.match_id) {
      try {
        const plResp = await fetch(`/api/replay/public-log?match_id=${gameInfo.match_id}`);
        if (plResp.ok) rvPublicLog = await plResp.json();
      } catch(_) {}
    }
    rvSteps = rvPublicLog ? rvBuildStepsFromPublicLog(rvPublicLog.viewer_public_log) : rvBuildSteps(rvGame);
    rvTurnGroups = rvBuildTurnGroups(rvSteps);
    rvStepIdx = 0;

    // Try to load hand data from coaching .gz upload or from log INITIAL_HAND
    rvHandData = null;
    rvHandMode = 'none';
    if (rvGame && rvGame.game_id) {
      try {
        const hResp = await fetch(`/api/v1/team/replay/${rvGame.game_id}`);
        if (hResp.ok) {
          rvHandData = await hResp.json();
          rvHandMode = 'full';
        }
      } catch(_) {}
    }
    if (rvHandMode === 'none' && rvGame) {
      // Check if log has INITIAL_HAND (our_hand field from loader)
      const ih = rvGame.our_hand || rvGame.initial_hand;
      if (ih && ih.length) {
        rvHandData = { initial_hand: ih, known_at_turn: rvBuildPartialHand(rvGame, ih) };
        rvHandMode = 'partial';
      }
    }
    // Render step navigation
    const sbs = document.getElementById('rv-sbs');
    if (sbs) {
      let lastT = -1;
      sbs.innerHTML = rvTurnGroups.map((g,i) => {
        const sep = (g.turn !== lastT && lastT !== -1) ? '<span class="rv-ssep"></span>' : '';
        lastT = g.turn;
        const label = `T${g.turn} ${g.who === 'our' ? 'Us' : 'Opp'}`;
        return `${sep}<button class="rv-sb${g.who==='opp'?' rv-opp':''}" onclick="rvPlayTurnGroup(${i})">${label}</button>`;
      }).join('');
    }
    rvGoToStep(0);
  } catch(e) {
    if(wrap) wrap.innerHTML = `<div class="rv-empty">Error: ${e.message}</div>`;
  }
}

function rvSelectGame(idx) {
  rvStop();
  rvGameIdx = idx;
  const fg = rvFilteredGames();
  if (idx >= 0 && idx < fg.length) rvLoadGame(fg[idx]);
  // Update select
  const sel = document.getElementById('rv-gs');
  if (sel) sel.value = idx;
  // Update result badge
  const g = fg[idx];
  const rb = document.getElementById('rv-gr');
  if (rb && g) { rb.textContent = g.r==='W'?'WIN':'LOSS'; rb.className = 'rv-fb ' + (g.r==='W'?'rv-ep-play':'rv-ep-chal'); rb.style.fontWeight='700'; }
}

function rvApplyFilter(f) {
  rvFilter = f;
  document.querySelectorAll('.rv-fb[data-f]').forEach(b=>b.classList.toggle('active',b.dataset.f===f));
  rvPopulateSelect();
  const fg = rvFilteredGames();
  if (fg.length) rvSelectGame(0);
  else { const b=document.getElementById('rv-board'); if(b) b.innerHTML='<div class="rv-empty">No games match filter</div>'; }
}

function rvPopulateSelect() {
  const sel = document.getElementById('rv-gs'); if (!sel) return;
  const fg = rvFilteredGames();
  sel.innerHTML = fg.map((g,i) => `<option value="${i}">#${g.i+1} ${g.r==='W'?'✅':'❌'} ${g.otp?'OTP':'OTD'} T${g.l} vs ${g.en||'?'}${g.em?' MMR:'+g.em:''}</option>`).join('');
  sel.onchange = () => rvSelectGame(+sel.value);
  const info = document.getElementById('rv-info');
  if (info) info.textContent = `${fg.length} games`;
}

async function rvInit(deck, opp) {
  rvDeck = deck; rvOpp = opp;
  rvFilter = 'all'; rvGameIdx = 0;
  const wrap = document.getElementById('rv-board');
  if (wrap) wrap.innerHTML = '<div class="rv-loading">Loading replay data...</div>';
  try {
    // Load cards DB (cached)
    if (!rvCardsDB) {
      const dbResp = await fetch('/api/replay/cards_db');
      rvCardsDB = await dbResp.json();
    }
    // Load game list
    const resp = await fetch(`/api/replay/list?deck=${deck}&opp=${opp}`);
    const data = await resp.json();
    if (data.error) { if(wrap) wrap.innerHTML = `<div class="rv-empty">${data.error}</div>`; return; }
    rvGameList = data.games;
    rvPopulateSelect();
    if (rvGameList.length) rvSelectGame(0);
    else { if(wrap) wrap.innerHTML = '<div class="rv-empty">No games in archive</div>'; }
  } catch(e) {
    if(wrap) wrap.innerHTML = `<div class="rv-empty">Replay unavailable (${e.message})</div>`;
  }
}

function buildReplayViewer(deck, opp) {
  return `<div class="rv-wrap">
    <div class="rv-header">
      <h3>🎬 Replay</h3>
      <select id="rv-gs"></select>
      <div class="rv-filters">
        <button class="rv-fb active" data-f="all" onclick="rvApplyFilter('all')">All</button>
        <button class="rv-fb" data-f="W" onclick="rvApplyFilter('W')">Win</button>
        <button class="rv-fb" data-f="L" onclick="rvApplyFilter('L')">Loss</button>
        <button class="rv-fb" data-f="otp" onclick="rvApplyFilter('otp')">OTP</button>
        <button class="rv-fb" data-f="otd" onclick="rvApplyFilter('otd')">OTD</button>
      </div>
      <span class="rv-fb" id="rv-gr" style="font-weight:700"></span>
      <span class="rv-info" id="rv-info"></span>
    </div>
    <div class="rv-steps">
      <div class="rv-controls">
        <button class="rv-sa" onclick="rvGoToStep(rvStepIdx-1)" title="Previous step">◀</button>
        <button class="rv-sa" id="rv-play" onclick="rvPlay()" title="Play" style="font-size:0.9rem">▶</button>
        <button class="rv-sa" id="rv-speed" onclick="rvCycleSpeed()" title="Speed" style="font-size:0.6rem;width:32px">1x</button>
        <button class="rv-sa" onclick="rvGoToStep(rvStepIdx+1)" title="Next step">▶</button>
        <span style="font-size:0.65rem;color:var(--text2);margin-left:4px" id="rv-step-num"></span>
      </div>
      <div class="rv-step-scroll" id="rv-sbs"></div>
    </div>
    <div class="rv-counters">
      <div class="rv-cs rv-ours">
        <span class="rv-cn" id="rv-on">Us</span>
        <div class="rv-ct"><span class="rv-cv" id="rv-cOL">0</span><span class="rv-cl">Lore</span></div>
        <div class="rv-ct"><span class="rv-cv" id="rv-cOI">0/0</span><span class="rv-cl">Ink</span></div>
        <div class="rv-ct"><span class="rv-cv" id="rv-cOH">7</span><span class="rv-cl">Hand</span></div>
      </div>
      <div class="rv-cdiv"></div>
      <div class="rv-cs rv-opps">
        <div class="rv-ct"><span class="rv-cv" id="rv-cEH">7</span><span class="rv-cl">Hand</span></div>
        <div class="rv-ct"><span class="rv-cv" id="rv-cEI">0/0</span><span class="rv-cl">Ink</span></div>
        <div class="rv-ct"><span class="rv-cv" id="rv-cEL">0</span><span class="rv-cl">Lore</span></div>
        <span class="rv-cn" id="rv-en">Opp</span>
      </div>
    </div>
    <div class="rv-body">
      <div class="rv-board" id="rv-board"><div class="rv-loading">Select a matchup to view replays</div></div>
      <div class="rv-events" id="rv-events"><h4>Events</h4></div>
    </div>
    <div class="rv-hand-panel" id="rv-hand-panel" style="display:none">
      <div class="rv-hand-header">
        <span class="rv-hand-title">Hand</span>
        <span class="rv-hand-badge" id="rv-hand-badge"></span>
        <span class="rv-hand-count" id="rv-hand-count"></span>
      </div>
      <div class="rv-hand-cards" id="rv-hand-cards"></div>
    </div>
  </div>`;
}


// === COACH V2 TAB — Threat-Centered ===
function renderCoachV2Tab(main) {
  const az = getAnalyzerData();
  const availDecks = az.available_decks || [];
  const matchups = (az[coachDeck]||{}).available_matchups || [];
  if (!coachOpp || !matchups.includes(coachOpp)) {
    coachOpp = matchups[0] || null;
    syncOppInksFromDeck(coachOpp);
  }

  const selectorHtml = buildMatchupSelector('coach');

  const deckData = az[coachDeck];
  if (!deckData || !coachOpp) {
    main.innerHTML = selectorHtml + `<div class="coming-soon-card"><div class="lock-emoji">🔒</div><h3>Select Matchup</h3><p>Pick your deck and opponent using the ink icons above.</p></div>`;
    return;
  }

  const mu = getMatchupData(coachOpp);
  if (!mu) {
    main.innerHTML = selectorHtml + `<div class="coming-soon-card"><div class="lock-emoji">📊</div><h3>Data not available</h3><p>No report for this matchup.</p></div>`;
    return;
  }

  const ov = mu.overview || {};
  const pb = mu.playbook || [];
  const kc = mu.killer_curves || [];
  const tl = mu.threats_llm || {};
  const ac = mu.ability_cards || [];
  const la = mu.loss_analysis || {};
  const threats = tl.threats || [];

  // A.3 Play soft gate — register this matchup view (deduped by day).
  if (typeof playRegisterMatchupView === 'function') {
    playRegisterMatchupView(coachDeck, coachOpp);
  }

  let content = selectorHtml;

  // 1. Compact KPI strip
  const wrCl = (ov.wr||0) >= 50 ? 'wr-good' : 'wr-bad';
  content += `<div class="cv2-strip">
    <div class="cv2-stat"><div class="cv2-val ${wrCl}">${ov.wr||'?'}%</div><div class="cv2-lbl">Win Rate</div></div>
    <div class="cv2-sep"></div>
    <div class="cv2-stat"><div class="cv2-val">${ov.otp_wr||'?'}%</div><div class="cv2-lbl">OTP (${ov.otp_games||'?'}g)</div></div>
    <div class="cv2-stat"><div class="cv2-val">${ov.otd_wr||'?'}%</div><div class="cv2-lbl">OTD (${ov.otd_games||'?'}g)</div></div>
    <div class="cv2-sep"></div>
    <div class="cv2-stat"><div class="cv2-val">${ov.gap||'?'}pp</div><div class="cv2-lbl">Gap</div></div>
    <div class="cv2-stat"><div class="cv2-val">${(ov.wins||0)+(ov.losses||0)}</div><div class="cv2-lbl">Match</div></div>
    ${tl.type_summary ? `<div class="cv2-sep"></div><div style="flex:1;font-size:0.82em;color:var(--gold);font-style:italic">${tl.type_summary}</div>` : ''}
    <div class="cv2-sep"></div>
    <button onclick="openCheatsheet()" style="background:linear-gradient(135deg,var(--gold),#E8C97A);color:var(--bg);border:none;border-radius:8px;padding:8px 14px;font-weight:700;font-size:0.8em;cursor:pointer;white-space:nowrap;transition:transform 0.15s" onmousedown="this.style.transform='scale(0.96)'" onmouseup="this.style.transform=''">Pre-Match</button>
  </div>`;

  // A.3 Conversion header — single-line insight above curves/responses.
  const _topCurve = kc[0];
  const _critTurn = _topCurve?.critical_turn?.turn || null;
  const _topCurveName = _topCurve?.name || (threats[0]?.name) || '';
  if (_topCurveName) {
    content += `<div class="cv2-conv-hdr" style="margin:10px 0 16px;padding:12px 14px;background:linear-gradient(135deg,rgba(212,160,58,0.10),rgba(212,160,58,0.04));border-left:3px solid var(--gold);border-radius:6px;font-size:0.95em;line-height:1.45">
      <div style="color:var(--gold);font-weight:700;font-size:0.78em;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:4px">The threat</div>
      <div style="color:var(--text)"><strong>${_topCurveName}</strong>${_critTurn ? ` closes this matchup around turn <strong>${_critTurn}</strong>.` : '.'} Scroll for how to respond &rarr;</div>
    </div>`;
  }

  // 2. Build unified threat list from killer_curves + threats_llm
  // Group curves by name similarity to threats
  const threatBriefs = [];
  // Start with killer curves as primary threats (they have sequences)
  kc.forEach((curve, i) => {
    // Find matching LLM threat by name overlap
    const matchingThreat = threats.find(t => {
      const tName = (t.name || '').toLowerCase();
      const cName = (curve.name || '').toLowerCase();
      // Match if they share key card names
      const cCards = (curve.key_cards || []).map(c => c.toLowerCase());
      return cCards.some(c => tName.includes(c.split(' - ')[0])) || tName.includes(cName.split(' ')[0]);
    });

    // Find matching playbook turns
    const critTurn = curve.critical_turn?.turn || 4;

    threatBriefs.push({
      id: i + 1,
      name: curve.name,
      pct: curve.frequency?.pct || 0,
      losses: curve.frequency?.loss_count || 0,
      totalLosses: curve.frequency?.total_loss || 0,
      type: curve.type || '?',
      criticalTurn: `T${critTurn}`,
      criticalComponent: curve.critical_turn?.component || '',
      swing: curve.critical_turn?.swing || '',
      sequence: curve.sequence || {},
      response: curve.response || {},
      validation: curve.validation || {},
      keyCards: curve.key_cards || [],
      // From matching LLM threat
      description: matchingThreat?.description || '',
      sections: matchingThreat?.sections || [],
      notes: matchingThreat?.notes || '',
      mitigation: matchingThreat?.mitigation || '',
      // Playbook context for relevant turns
      playbook: pb.filter(t => {
        const tNum = parseInt(t.turn?.replace(/\D/g, '') || '0');
        return tNum >= 1 && tNum <= critTurn + 1;
      }),
    });
  });

  // Add LLM threats not covered by curves
  threats.forEach(t => {
    const alreadyCovered = threatBriefs.some(tb => {
      const tName = (t.name || '').toLowerCase();
      const tbName = (tb.name || '').toLowerCase();
      return tName === tbName || tbName.includes(tName.split(' - ')[0].toLowerCase());
    });
    if (!alreadyCovered && t.pct >= 5) {
      threatBriefs.push({
        id: threatBriefs.length + 1,
        name: t.name,
        pct: t.pct || 0,
        losses: t.losses || 0,
        totalLosses: t.total_losses || 0,
        type: '',
        criticalTurn: t.critical_turn || '?',
        criticalComponent: '',
        swing: '',
        sequence: {},
        response: {},
        validation: {},
        description: t.description || '',
        sections: t.sections || [],
        notes: t.notes || '',
        mitigation: t.mitigation || '',
        playbook: pb,
      });
    }
  });

  // Sort by pct descending
  threatBriefs.sort((a, b) => b.pct - a.pct);

  // 3. Render threat briefs — section header first
  content += `<div class="tab-section-hdr">
    <span class="tab-section-hdr__eyebrow">Threat Analysis</span>
    <span class="tab-section-hdr__title">Key threats &amp; how to respond</span>
  </div>`;
  if (threatBriefs.length === 0) {
    content += `<div class="card" style="text-align:center;padding:24px;color:var(--text2)">No threats identified for this matchup.</div>`;
  }

  threatBriefs.forEach((tb, idx) => {
    const sevColor = tb.pct >= 25 ? 'var(--red)' : tb.pct >= 15 ? 'var(--yellow)' : 'var(--text2)';
    const pctBg = tb.pct >= 25 ? 'rgba(248,81,73,0.2)' : tb.pct >= 15 ? 'rgba(210,153,34,0.15)' : 'rgba(255,255,255,0.06)';
    const pctColor = tb.pct >= 25 ? 'var(--red)' : tb.pct >= 15 ? 'var(--yellow)' : 'var(--text2)';
    // Preview strip — card thumbnails per turn, always visible even when collapsed.
    // Uses tb.sequence when available; falls back to keyCards ungrouped.
    const prevSeq = Object.entries(tb.sequence || {});
    let previewHtml = '';
    if (prevSeq.length > 0) {
      const groups = prevSeq.map(([turn, s]) => {
        const plays = s.plays || (s.card ? [{ card: s.card }] : []);
        if (!plays.length) return '';
        const thumbs = plays.map(p => {
          const img = cardImgUrlFuzzy(p.card);
          const full = img ? img.replace('/thumbnail/', '/full/') : '';
          const short = (p.card || '').split(' - ')[0];
          if (img) {
            return `<img src="${img}" class="cv2-prev-card" data-zoom="${full}" onclick="event.stopPropagation();pfZoomCard(this)" title="${p.card}" loading="lazy" alt="${short}">`;
          }
          return `<span class="cv2-prev-stub" title="${p.card}">${short}</span>`;
        }).join('');
        return `<div class="cv2-prev-turn"><span class="cv2-prev-t">${turn}</span>${thumbs}</div>`;
      }).filter(Boolean).join('');
      if (groups) previewHtml = `<div class="cv2-threat-preview" onclick="event.stopPropagation()">${groups}</div>`;
    } else if (tb.keyCards.length > 0) {
      const thumbs = tb.keyCards.slice(0, 6).map(c => {
        const img = cardImgUrlFuzzy(c);
        const full = img ? img.replace('/thumbnail/', '/full/') : '';
        const short = (c || '').split(' - ')[0];
        return img
          ? `<img src="${img}" class="cv2-prev-card" data-zoom="${full}" onclick="event.stopPropagation();pfZoomCard(this)" title="${c}" loading="lazy" alt="${short}">`
          : `<span class="cv2-prev-stub" title="${c}">${short}</span>`;
      }).join('');
      previewHtml = `<div class="cv2-threat-preview" onclick="event.stopPropagation()"><div class="cv2-prev-turn"><span class="cv2-prev-t">Key</span>${thumbs}</div></div>`;
    }

    content += `<div class="cv2-threat" onclick="this.classList.toggle('open')">
      <div class="cv2-threat-hdr">
        <div class="cv2-sev" style="background:${sevColor}"></div>
        <span class="cv2-name">${tb.name}</span>
        <span class="cv2-turn-badge">${tb.criticalTurn}${tb.criticalComponent ? ' · ' + tb.criticalComponent : ''}</span>
        <span class="cv2-pct" style="background:${pctBg};color:${pctColor}">${tb.pct}% (${tb.losses})</span>
        <span class="cv2-arrow">▼</span>
      </div>
      ${previewHtml}
      <div class="cv2-threat-body">`;

    // Description
    if (tb.description) {
      content += `<div style="font-size:0.85em;color:var(--text2);margin-top:8px;margin-bottom:8px">${tb.description}</div>`;
    }
    if (tb.type) {
      content += `<div style="font-size:0.78em;color:var(--text2);margin-bottom:8px">Type: <strong style="color:var(--gold)">${tb.type}</strong>${tb.swing ? ` · Swing: ${tb.swing}` : ''}</div>`;
    }

    // Two columns: Opponent plan + Our response
    const seqEntries = Object.entries(tb.sequence);
    const hasSeq = seqEntries.length > 0;
    const hasSections = tb.sections.length > 0;
    const hasResponse = tb.response.strategy || kcResponseSections(tb.response).length;

    if (hasSeq || hasSections || hasResponse) {
      content += `<div class="cv2-stack">`;

      // LEFT: Opponent's plan (from sequence + playbook)
      if (hasSeq) {
        content += `<div class="cv2-col"><h4 class="opp-title">Opponent's Plan</h4>`;
        seqEntries.forEach(([turn, s]) => {
          const plays = s.plays || (s.card ? [{card: s.card, ink_cost: s.ink_cost, is_shift: s.is_shift, is_sung: s.is_sung}] : []);
          const totalInk = s.total_ink != null ? s.total_ink : plays.reduce((a, p) => a + (p.ink_cost||0), 0);
          const playsHtml = plays.map(p => {
            let tag = '';
            if (p.is_shift) tag = ' <span style="color:var(--amethyst);font-weight:700">[SHIFT]</span>';
            if (p.is_sung) tag = ' <span style="color:var(--sapphire);font-weight:700">[SONG]</span>';
            return `<strong>${p.card}</strong>${tag}`;
          }).join(' + ');
          content += `<div class="cv2-turn-row">
            <span class="cv2-t">${turn}</span>
            <span class="cv2-play">${playsHtml} <span style="color:var(--text2);font-size:0.85em">(${totalInk} ink)</span></span>
          </div>`;
        });
        content += `</div>`;
      } else if (tb.playbook.length > 0) {
        content += `<div class="cv2-col"><h4 class="opp-title">Opponent's Plan</h4>`;
        tb.playbook.slice(0, 5).forEach(t => {
          const topPlay = (t.plays || []).slice(0, 2).map(p => p.card).join(', ');
          content += `<div class="cv2-turn-row">
            <span class="cv2-t">${t.turn}</span>
            <span class="cv2-play">${topPlay || '—'}</span>
          </div>`;
        });
        content += `</div>`;
      } else {
        // No sequence or playbook — show key cards as threat indicators
        content += `<div class="cv2-col"><h4 class="opp-title">Threat Pattern</h4>`;
        content += `<div style="font-size:0.85em;color:var(--text2);margin-bottom:6px">${tb.name}</div>`;
        if (tb.criticalTurn && tb.criticalTurn !== 'Tundefined') {
          content += `<div style="font-size:0.82em;margin-bottom:6px">Critical turn: <strong style="color:var(--gold)">${tb.criticalTurn}</strong></div>`;
        }
        if (tb.keyCards.length > 0) {
          const cardsHtml = tb.keyCards.map(c => {
            const img = cardImgUrlFuzzy(c);
            const short = c.split(' - ')[0];
            return img ? `<div style="display:inline-flex;align-items:center;gap:4px;margin:2px 8px 2px 0"><img src="${img}" style="width:24px;height:33px;border-radius:3px;object-fit:cover" loading="lazy" onerror="this.style.display='none'"><span style="font-size:0.82em">${short}</span></div>` : `<span style="font-size:0.82em;margin-right:8px">${short}</span>`;
          }).join('');
          content += `<div style="margin-top:4px">${cardsHtml}</div>`;
        }
        content += `</div>`;
      }

      // RIGHT: Our response
      content += `<div class="cv2-col"${!hasSeq && tb.playbook.length === 0 ? ' style="flex:1"' : ''}><h4 class="our-title">How to Respond</h4>`;
      if (hasSections) {
        tb.sections.forEach(s => {
          const typeIcon = s.type === 'Prevention' ? '🛡' : s.type === 'Response' ? '⚔' : '🔄';
          content += `<div style="margin-bottom:8px">
            <div style="font-size:0.8em;font-weight:600;color:var(--green);margin-bottom:4px">${typeIcon} ${s.type}${s.label ? ' — ' + s.label : ''}</div>`;
          if (s.plans && s.plans.length) {
            s.plans.forEach(p => {
              const planText = p.plan_a && p.plan_a !== '—' ? p.plan_a : (p.plan_b && p.plan_b !== '—' ? p.plan_b : '—');
              if (planText !== '—') {
                content += `<div class="cv2-turn-row">
                  <span class="cv2-t">${p.turn}</span>
                  <span class="cv2-play">${planText}</span>
                  ${p.plan_b && p.plan_b !== '—' && p.plan_a !== '—' ? `<span style="color:var(--text2);font-size:0.8em">alt: ${p.plan_b}</span>` : ''}
                </div>`;
              }
            });
          }
          content += `</div>`;
        });
      } else if (hasResponse) {
        content += kcRenderResponse(tb.response, { compact: true });
      } else {
        content += `<div style="color:var(--text2);font-size:0.85em">Response not yet analyzed.</div>`;
      }
      content += `</div>`;

      content += `</div>`; // cv2-columns
    }

    // Killer curve card timeline (if sequence exists)
    if (hasSeq) {
      content += `<div class="cv2-curve-timeline">`;
      seqEntries.forEach(([turn, s]) => {
        const plays = s.plays || (s.card ? [{card: s.card, ink_cost: s.ink_cost, is_shift: s.is_shift, is_sung: s.is_sung}] : []);
        const imgsHtml = plays.map(p => {
          const url = cardImgUrlFuzzy(p.card);
          return url ? `<img src="${url}" alt="${p.card}" style="width:60px;height:auto;border-radius:4px;opacity:0.9" loading="lazy" onerror="this.style.display='none'">` : '';
        }).filter(Boolean).join('');
        const totalInk = s.total_ink != null ? s.total_ink : plays.reduce((a, p) => a + (p.ink_cost||0), 0);
        const cardsLabel = plays.map(p => p.card.split(' - ')[0]).join(' + ');
        const tags = plays.some(p => p.is_shift) ? ' · shift' : '';
        const lore = s.lore_this_turn ? ` · ${s.lore_this_turn}L` : '';

        content += `<div class="cv2-curve-step">
          <div class="cv2-cs-turn">${turn}</div>
          ${imgsHtml ? `<div style="display:flex;gap:2px;justify-content:center;flex-wrap:wrap;margin:3px 0">${imgsHtml}</div>` : ''}
          <div class="cv2-cs-card">${cardsLabel}</div>
          <div class="cv2-cs-cost">${totalInk} ink${tags}${lore}</div>
        </div>`;
      });
      content += `</div>`;

      // Response is shown in the right column only
    }

    // Notes / mitigation
    if (tb.notes) {
      content += `<div class="cv2-mitigation"><strong>Note:</strong> ${tb.notes}</div>`;
    }
    if (tb.mitigation) {
      content += `<div class="cv2-mitigation"><strong>Mitigation:</strong> ${tb.mitigation}</div>`;
    }

    content += `</div></div>`; // cv2-threat-body + cv2-threat
  });

  // A.3 How to Respond — dedicated block, soft-gated after 3rd daily matchup.
  const _responses = mu.killer_responses || [];
  const _responseFromThreats = threats.filter(t => t.response || t.response_otp || t.response_otd).map(t => ({
    title: t.name || 'Threat',
    otp: t.response_otp || t.response,
    otd: t.response_otd || t.response,
  }));
  const _respItems = _responses.length ? _responses : _responseFromThreats;
  if (_respItems.length) {
    const _gated = (typeof playShouldGateResponse === 'function') && playShouldGateResponse(coachDeck, coachOpp);
    const _inner = _respItems.slice(0, 3).map(r => `
      <div style="padding:10px 12px;background:var(--bg1);border-radius:6px;margin-bottom:8px">
        <div style="font-weight:700;color:var(--gold);margin-bottom:6px">${r.title || 'Response'}</div>
        ${r.otp ? `<div style="font-size:0.88em;margin-bottom:4px"><span style="color:var(--green);font-weight:600">OTP:</span> ${r.otp}</div>` : ''}
        ${r.otd && r.otd !== r.otp ? `<div style="font-size:0.88em"><span style="color:var(--sapphire);font-weight:600">OTD:</span> ${r.otd}</div>` : ''}
      </div>`).join('');
    content += `<div class="tab-section-hdr" style="margin-top:var(--sp-5)">
      <span class="tab-section-hdr__eyebrow">How to Respond</span>
      <span class="tab-section-hdr__title">Play this, avoid that</span>
    </div>`;
    if (_gated) {
      const _count = (typeof playMatchupsViewedCount === 'function') ? playMatchupsViewedCount() : 4;
      content += `<div class="cv2-respond-block premium-wall" style="margin:12px 0">
        <div class="premium-content" style="filter:blur(4px);pointer-events:none">${_inner}</div>
        <div class="paywall-overlay">
          <div class="lock-big">🔒</div>
          <h3>You've scouted ${_count} matchups today</h3>
          <p>Unlock unlimited matchup responses and full killer curve analysis &rarr; Pro &euro;9/m</p>
          <button class="unlock-btn" onclick="playSoftUnlock()">Unlock Play — 9&euro;/month</button>
        </div>
      </div>`;
    } else {
      content += `<div class="cv2-respond-block" style="margin:12px 0">${_inner}</div>`;
    }
  }

  // 4. Secondary data: tabs at bottom — with section header
  content += `<div class="tab-section-hdr" style="margin-top:var(--sp-5)">
    <span class="tab-section-hdr__eyebrow">Match Tools</span>
    <span class="tab-section-hdr__title">Killer Cards · Playbook</span>
  </div>`;
  content += `<div class="cv2-secondary" id="cv2-sec-tabs">
    <button class="cv2-sec-tab${cv2SecTab==='killer_cards'?' active':''}" onclick="event.stopPropagation();cv2SecTab='killer_cards';renderCV2Secondary()">Killer Cards</button>
    <button class="cv2-sec-tab${cv2SecTab==='playbook'?' active':''}" onclick="event.stopPropagation();cv2SecTab='playbook';renderCV2Secondary()">Full Playbook</button>
  </div>
  <div class="cv2-sec-body" id="cv2-sec-body"></div>`;

  // Best Plays — sequence reali devastanti del deck in matchup
  if (typeof buildBestPlaysCard === 'function') {
    const bpHtml = buildBestPlaysCard(coachDeck);
    if (bpHtml) content += bpHtml;
  }

  main.innerHTML = content;

  // Render secondary content
  renderCV2Secondary();
}

function renderCV2Secondary() {
  const body = document.getElementById('cv2-sec-body');
  const tabs = document.getElementById('cv2-sec-tabs');
  if (!body || !tabs) return;

  // Update active tab
  tabs.querySelectorAll('.cv2-sec-tab').forEach(t => {
    t.classList.toggle('active', t.textContent.toLowerCase().includes(
      cv2SecTab === 'killer_cards' ? 'cards' : 'playbook'
    ));
  });

  const mu = getMatchupData(coachOpp);
  if (!mu) { body.innerHTML = ''; return; }

  const pb = mu.playbook || [];
  const ac = mu.ability_cards || [];

  if (cv2SecTab === 'killer_cards') {
    if (ac.length === 0) { body.innerHTML = '<div class="card" style="padding:16px;color:var(--text2)">No killer cards identified.</div>'; return; }

    // Group by cost (like playbook groups by turn)
    const byCost = {};
    ac.forEach(c => { const k = c.cost || 0; (byCost[k] = byCost[k] || []).push(c); });
    Object.values(byCost).forEach(arr => arr.sort((a,b) => b.loss_pct - a.loss_pct));
    const costs = Object.keys(byCost).map(Number).sort((a,b) => a - b);

    let html = `<div class="card" style="padding:20px 20px 12px 20px;margin-top:12px"><div class="playbook">`;

    costs.forEach(cost => {
      const cards = byCost[cost];
      const maxPct = Math.max(...cards.map(c => c.loss_pct));
      const danger = maxPct >= 55 ? 'high' : maxPct >= 40 ? 'mid' : 'low';
      const cardsPreview = cards.slice(0,3).map(c => {
        const imgUrl = cardImgUrlFuzzy(c.card);
        const shortN = c.card.split(' - ')[0];
        const thumb = imgUrl ? `<img src="${imgUrl}" style="width:18px;height:25px;border-radius:2px;vertical-align:middle;object-fit:cover;margin-right:3px">` : '';
        return `${thumb}<strong>${shortN}</strong> <span class="pct">${c.loss_pct}%</span>`;
      }).join(' &middot; ');

      html += `<div class="pb-turn" onclick="event.stopPropagation();this.classList.toggle('open')">
        <div class="pb-dot ${danger}"></div>
        <div class="pb-header">
          <span class="pb-turn-num">C${cost}</span>
          <div class="pb-cards">${cardsPreview}</div>
        </div>
        <div class="pb-expand">
          <table class="deck-table" style="margin-bottom:6px"><tr><th></th><th>Carta</th><th>Loss%</th><th>Ability</th></tr>`;

      cards.forEach(c => {
        const pct = c.loss_pct;
        const cls = pct >= 50 ? 'wr-bad' : '';
        const imgUrl = cardImgUrlFuzzy(c.card);
        const fullUrl = imgUrl ? imgUrl.replace('/thumbnail/', '/full/') : '';
        const thumb = imgUrl
          ? `<img src="${imgUrl}" style="width:28px;height:39px;border-radius:3px;object-fit:cover;vertical-align:middle;border:1px solid var(--border)">`
          : '<span style="font-size:1.3em;vertical-align:middle">&#127183;</span>';
        const rowZoom = fullUrl ? `data-zoom="${fullUrl}" onclick="event.stopPropagation();pfZoomCard(this)" style="cursor:pointer"` : '';

        html += `<tr ${rowZoom}>
          <td style="width:36px;padding:4px">${thumb}</td>
          <td><strong>${c.card}</strong></td>
          <td class="${cls}">${pct}%</td>
          <td style="font-size:0.8em;color:var(--text2)">${(c.ability||'').length > 80 ? c.ability.substring(0,77)+'...' : (c.ability||'')}</td>
        </tr>`;

      });

      html += `</table></div></div>`;
    });

    html += `</div></div>`;
    body.innerHTML = html;

  } else if (cv2SecTab === 'playbook') {
    if (pb.length === 0) { body.innerHTML = '<div class="card" style="padding:16px;color:var(--text2)">No playbook available.</div>'; return; }
    let html = `<div class="card" style="padding:20px 20px 12px 20px;margin-top:12px"><div class="playbook">`;
    pb.forEach(t => {
      const plays = t.plays || [];
      const kills = t.impact?.killed_per_game || 0;
      const lore = t.impact?.lore_quested || 0;
      const danger = kills >= 0.8 || lore >= 2.0 ? 'high' : kills >= 0.3 || lore >= 1.0 ? 'mid' : 'low';
      const cardsStr = plays.slice(0,3).map(p => `<strong>${p.card}</strong> <span class="pct">${p.pct}%</span>`).join(' · ');
      const statsHtml = (kills > 0 || lore > 0) ? `<div class="pb-stats">${kills > 0 ? `<span class="kill">${kills} kill/g</span>` : ''}${lore > 0 ? `<span class="lore">${lore} lore</span>` : ''}</div>` : '';

      html += `<div class="pb-turn" onclick="event.stopPropagation();this.classList.toggle('open')">
        <div class="pb-dot ${danger}"></div>
        <div class="pb-header">
          <span class="pb-turn-num">${t.turn}</span>
          <div class="pb-cards">${cardsStr}</div>
          ${statsHtml}
        </div>
        <div class="pb-expand">`;
      if (plays.length > 0) {
        html += `<table class="deck-table" style="margin-bottom:6px"><tr><th>Carta</th><th>Costo</th><th>Freq</th><th>Effetto</th></tr>`;
        plays.forEach(p => { html += `<tr><td><strong>${p.card}</strong></td><td>${p.cost}</td><td>${p.pct}%</td><td style="color:var(--text2)">${p.effect}</td></tr>`; });
        html += `</table>`;
      }
      if (t.combos && t.combos.length) {
        html += `<div class="pb-combo"><strong>Combo:</strong> ${t.combos.map(c => `${c.cards} (${c.freq}x)`).join(' · ')}</div>`;
      }
      html += `</div></div>`;
    });
    html += `</div></div>`;
    body.innerHTML = html;

  }
}

