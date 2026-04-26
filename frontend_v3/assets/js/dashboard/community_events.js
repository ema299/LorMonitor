function renderCommunityTab(main) {
  const cfg = COMMUNITY_CONFIG;
  const playSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none"/></svg>';

  // Live section
  let liveHtml = '';
  if (cfg.live.isLive && cfg.live.videoId) {
    const src = cfg.live.platform === 'twitch'
      ? `https://player.twitch.tv/?channel=${cfg.live.channelId}&parent=${location.hostname}`
      : `https://www.youtube.com/embed/${cfg.live.videoId}?autoplay=1`;
    liveHtml = `
      <div class="comm-live-embed-wrap"><iframe src="${src}" allow="autoplay; encrypted-media" allowfullscreen loading="lazy"></iframe></div>
      <div style="font-weight:600;font-size:0.95em;margin-bottom:4px">${cfg.live.title}</div>
      <div style="font-size:0.82em;color:var(--text2)">${cfg.live.channel}</div>`;
  } else {
    liveHtml = `<div class="comm-live-embed-wrap">
      <div class="comm-live-placeholder">
        ${playSvg}
        <div style="font-weight:600">No stream right now</div>
        <div style="font-size:0.82em">Check the schedule below</div>
      </div>
    </div>`;
  }

  // Schedule
  let schedHtml = '';
  cfg.schedule.forEach(s => {
    const d = new Date(s.date);
    const day = d.toLocaleDateString('en', {weekday:'short', day:'numeric', month:'short'});
    const time = d.toLocaleTimeString('en', {hour:'2-digit', minute:'2-digit', hour12:false});
    // Build .ics data URI for +cal button
    const dtStart = s.date.replace(/[-:]/g,'').replace('T','T') + '00Z';
    const dtEnd = new Date(d.getTime() + 2*3600000).toISOString().replace(/[-:]/g,'').split('.')[0] + 'Z';
    const icsData = `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nDTSTART:${dtStart}\r\nDTEND:${dtEnd}\r\nSUMMARY:${s.title}\r\nDESCRIPTION:${s.channel}\r\nEND:VEVENT\r\nEND:VCALENDAR`;
    const icsHref = 'data:text/calendar;charset=utf-8,' + encodeURIComponent(icsData);
    schedHtml += `<div class="comm-schedule-row">
      <div class="comm-sched-day">${day}</div>
      <div><div class="comm-sched-title">${s.title}</div><div class="comm-sched-channel">${s.channel}</div></div>
      <div style="display:flex;align-items:center;gap:8px">
        <div class="comm-sched-time">${time}</div>
        <a class="comm-cal-btn" href="${icsHref}" download="stream.ics" title="Add to calendar">+cal</a>
      </div>
    </div>`;
  });

  // Clip filter tags
  const allTags = new Set();
  cfg.clips.forEach(c => c.tags.forEach(t => allTags.add(t)));
  let chipHtml = `<button class="comm-chip${commActiveFilter==='all'?' active':''}" onclick="commActiveFilter='all';renderCommunityTab(document.getElementById('main-content'))">All</button>`;
  allTags.forEach(t => {
    chipHtml += `<button class="comm-chip${commActiveFilter===t?' active':''}" onclick="commActiveFilter='${t}';renderCommunityTab(document.getElementById('main-content'))">${t}</button>`;
  });

  // Clips
  const filtered = commActiveFilter === 'all' ? cfg.clips : cfg.clips.filter(c => c.tags.includes(commActiveFilter));
  let clipsHtml = '';
  filtered.forEach(c => {
    const tagHtml = c.tags.map(t => {
      const levelCls = ['beginner','intermediate','advanced'].includes(t) ? ` comm-tag-${t}` : ' comm-tag-deck';
      return `<span class="comm-tag${levelCls}">${t}</span>`;
    }).join('');
    const coachLink = c.coachLink
      ? `<a class="comm-clip-coach-link" href="#" onclick="event.stopPropagation();switchToTab('play',{deck:'${c.coachLink.deck}',opp:'${c.coachLink.opp}'});return false">Study in Play &rarr;</a>`
      : '';
    clipsHtml += `<div class="comm-clip-card" onclick="playCommClip(this,'${c.id}')">
      <div class="comm-clip-thumb">
        <img loading="lazy" src="https://img.youtube.com/vi/${c.id}/mqdefault.jpg" alt="${c.title}" onerror="this.style.display='none'">
        <div class="comm-clip-play-overlay">${playSvg}</div>
        <span class="comm-clip-duration">${c.duration}</span>
      </div>
      <div class="comm-clip-body">
        <div class="comm-clip-title">${c.title}</div>
        <div class="comm-clip-tags">${tagHtml}</div>
        <div class="comm-clip-meta">
          <span>${c.author}</span>
          ${coachLink}
        </div>
      </div>
    </div>`;
  });
  if (!clipsHtml) clipsHtml = '<div class="comm-empty">' + playSvg + '<div>No clips match this filter</div></div>';

  // Archive — with topic filter
  const archiveTopics = new Set();
  cfg.archive.forEach(v => v.topics.forEach(t => archiveTopics.add(t)));
  let archTopicOpts = '<option value="">All Topics</option>';
  archiveTopics.forEach(t => { archTopicOpts += `<option value="${t}">${t}</option>`; });

  const archFilter = window.commArchiveFilter || '';
  const filteredArch = archFilter ? cfg.archive.filter(v => v.topics.includes(archFilter)) : cfg.archive;
  let archHtml = '';
  filteredArch.forEach(v => {
    const topicTags = v.topics.map(t => `<span class="comm-tag comm-tag-deck">${t}</span>`).join(' ');
    archHtml += `<div class="comm-vod-row">
      <div class="comm-vod-thumb" onclick="playCommClip(this,'${v.id}')">
        <img loading="lazy" src="https://img.youtube.com/vi/${v.id}/mqdefault.jpg" alt="${v.title}" onerror="this.style.display='none'">
        <div class="comm-clip-play-overlay" style="opacity:0.6"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:24px;height:24px"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none"/></svg></div>
      </div>
      <div class="comm-vod-body">
        <div class="comm-vod-title">${v.title}</div>
        <div class="comm-vod-meta" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px">
          <span>${v.date}</span>
          <span style="opacity:0.4">&middot;</span>
          <span>${v.duration}</span>
          <span style="opacity:0.4">&middot;</span>
          ${topicTags}
        </div>
      </div>
    </div>`;
  });
  if (!archHtml) archHtml = '<div class="comm-empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg><div>No archived streams match this filter</div></div>';

  const badgeCls = cfg.live.isLive ? 'is-live' : 'is-offline';
  const badgeText = cfg.live.isLive ? 'LIVE' : 'OFFLINE';
  const svgIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px">`;

  // Events preview — top 3 eventi imminenti (sub-section di Community, V3-5 22/04)
  // Bottone "See all events" embedda renderEventsTab dentro un container locale (#comm-events-full)
  // invece di switchToTab('events'): il tab Events non e' piu' un primary, vive solo qui.
  const upcomingEvents = (typeof EVENTS_CONFIG !== 'undefined') ? EVENTS_CONFIG.slice(0, 3) : [];
  const eventsPreviewHtml = upcomingEvents.length && typeof buildEventCardsHtml === 'function'
    ? `<div class="comm-events-grid" id="comm-events-preview" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:12px">${buildEventCardsHtml(upcomingEvents)}</div>
       <div style="text-align:center;padding:14px 0 4px" id="comm-events-toggle-row">
         <button onclick="commToggleEventsFull()" id="comm-events-toggle-btn" style="background:transparent;border:1px solid rgba(255,215,0,0.4);color:var(--gold);padding:8px 18px;border-radius:6px;font-weight:600;cursor:pointer">See all events &middot; map &middot; submit &rarr;</button>
       </div>
       <div id="comm-events-full" style="margin-top:14px"></div>`
    : `<div class="comm-empty" style="padding:20px 0"><div style="font-size:0.85em">No upcoming events. Check back soon.</div></div>`;

  main.innerHTML = `
    <div class="tab-section-hdr">
      <span class="tab-section-hdr__eyebrow">Live Now</span>
      <span class="tab-section-hdr__title">Stream &middot; Schedule &middot; Events</span>
    </div>
    <div class="deck-intro deck-intro--above">
      <strong>What's happening today.</strong> The stream when it's live, the next
      scheduled shows, and the closest tournaments. The whole row is gone-quiet when
      there is no live content — no stale "stream offline" placeholder.
    </div>

    <div class="card card-hero">
      <div class="section-title">
        ${svgIcon}<circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none"/></svg>
        Live &amp; Content
        <span class="comm-live-badge ${badgeCls}">${badgeText}</span>
      </div>
      ${liveHtml}
      ${cfg.schedule.length ? `<div style="margin-top:16px"><div style="font-weight:600;font-size:0.9em;color:var(--text2);margin-bottom:8px">Upcoming Streams</div>${schedHtml}</div>` : '<div class="comm-empty" style="padding:20px 0"><div style="font-size:0.85em">No streams scheduled right now. Follow us for updates.</div></div>'}
    </div>

    <div class="card">
      <div class="section-title">
        ${svgIcon}<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
        Events &amp; Tournaments
      </div>
      <div style="font-size:0.85em;color:var(--text2);margin-bottom:8px">Upcoming Lorcana events in your region. Full map &amp; submit form in the Events sub-section.</div>
      ${eventsPreviewHtml}
    </div>

    <div class="tab-section-hdr" style="margin-top:var(--sp-5)">
      <span class="tab-section-hdr__eyebrow">Learn</span>
      <span class="tab-section-hdr__title">Teaching clips &middot; VOD archive</span>
    </div>
    <div class="deck-intro deck-intro--above">
      <strong>School of Lorcana.</strong> Curated short clips by judges and pro players
      grouped by skill level and archetype. The Archive below collects full-length VODs
      filtered by deck so you can study a specific matchup end-to-end.
    </div>

    <div class="card">
      <div class="section-title" style="flex-wrap:wrap">
        ${svgIcon}<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 1.66 2.69 3 6 3s6-1.34 6-3v-5"/></svg>
        School of Lorcana
        <div class="comm-filter-row">${chipHtml}</div>
      </div>
      <div style="font-size:0.85em;color:var(--text2);margin-bottom:10px">Rules, fundamentals, archetypes. Curated by judges and pro players.</div>
      <div class="comm-clip-grid">${clipsHtml}</div>
    </div>

    <div class="card">
      <div class="section-title">
        ${svgIcon}<rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>
        Archive
      </div>
      <div class="comm-archive-filter-row">
        <label>Filter by deck:</label>
        <select class="deck-select" style="min-width:120px" id="comm-arch-filter" onchange="window.commArchiveFilter=this.value;renderCommunityTab(document.getElementById('main-content'))">${archTopicOpts}</select>
      </div>
      ${archHtml}
    </div>`;
  // Restore archive filter select value
  const archSelEl = document.getElementById('comm-arch-filter');
  if (archSelEl && archFilter) archSelEl.value = archFilter;
}

// V3-5 22/04: Events embedded inside Community. Toggle expands the full Events
// surface (filter bar + Leaflet map + list + submit form) inline. No tab switch.
function commToggleEventsFull() {
  const container = document.getElementById('comm-events-full');
  const btn = document.getElementById('comm-events-toggle-btn');
  const preview = document.getElementById('comm-events-preview');
  if (!container || !btn) return;
  const isOpen = container.dataset.open === '1';
  if (isOpen) {
    container.innerHTML = '';
    container.dataset.open = '';
    btn.innerHTML = 'See all events &middot; map &middot; submit &rarr;';
    if (preview) preview.style.display = '';
  } else {
    if (typeof renderEventsTab === 'function') renderEventsTab(container);
    container.dataset.open = '1';
    btn.innerHTML = '&uarr; Hide events';
    if (preview) preview.style.display = 'none';
  }
}

function playCommClip(el, videoId) {
  const thumb = el.classList.contains('comm-clip-card') ? el.querySelector('.comm-clip-thumb') : el;
  thumb.innerHTML = `<div style="position:absolute;inset:0"><iframe src="https://www.youtube.com/embed/${videoId}?autoplay=1" allow="autoplay;encrypted-media" allowfullscreen style="width:100%;height:100%;border:none;position:absolute;top:0;left:0"></iframe></div>`;
  // Track progress
  const seen = JSON.parse(localStorage.getItem('comm_clips_seen') || '[]');
  if (!seen.includes(videoId)) { seen.push(videoId); localStorage.setItem('comm_clips_seen', JSON.stringify(seen)); }
}


// === EVENTS TAB ===
let evLeafletLoaded = false;
let evMap = null;
let evMarkers = [];
let evCurrentView = 'split';
let evShowSubmitForm = false;

const EVENTS_CONFIG = [
  { id: 'ev1', shop: 'Magic Corner', address: 'Via Orefici 2, Milano', region: 'nord', lat: 45.464, lng: 9.190, date: '2026-04-05T18:30', format: 'core', fee: '5\u20AC', title: 'Torneo Settimanale', website: '' },
  { id: 'ev2', shop: 'Otaku Store', address: 'Via Nazionale 45, Roma', region: 'centro', lat: 41.901, lng: 12.494, date: '2026-04-06T15:00', format: 'infinity', fee: 'Free', title: 'Infinity Saturday', website: '' },
  { id: 'ev3', shop: 'Jolly Troll', address: 'Via Roma 18, Torino', region: 'nord', lat: 45.070, lng: 7.686, date: '2026-04-12T17:00', format: 'core', fee: '8\u20AC', title: 'Monthly Championship', website: '' },
  { id: 'ev4', shop: 'Games Academy', address: 'Corso Italia 8, Firenze', region: 'centro', lat: 43.770, lng: 11.249, date: '2026-04-08T19:00', format: 'draft', fee: '12\u20AC', title: 'Draft Night', website: '' },
  { id: 'ev5', shop: 'Fantasia Store', address: 'Via Toledo 120, Napoli', region: 'sud', lat: 40.849, lng: 14.255, date: '2026-04-13T16:00', format: 'core', fee: '5\u20AC', title: 'Lorcana Sunday', website: '' },
];

function buildEventCardsHtml(events) {
  const days = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const storeSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px"><path d="M3 9l1-5h16l1 5"/><path d="M3 9h18v11a1 1 0 01-1 1H4a1 1 0 01-1-1V9z"/></svg>';
  if (!events.length) {
    return `<div class="ev-empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
      <p>No events match your filters</p>
      <button class="ev-submit-btn" onclick="evToggleSubmitForm(true)">Submit yours &rarr;</button>
    </div>`;
  }
  return events.map(ev => {
    const d = new Date(ev.date);
    const time = d.toLocaleTimeString('en', {hour:'2-digit', minute:'2-digit', hour12:false});
    const fmtLabel = { core: 'Core', infinity: 'Infinity', draft: 'Draft' }[ev.format] || ev.format;
    const metaTarget = ev.format === 'infinity' ? 'infinity' : 'core';
    return `<div class="event-card" data-event-id="${ev.id}" onclick="evHighlightOnMap('${ev.id}')">
      <div class="event-card-date-strip">
        <div class="ecd-day">${days[d.getDay()]}</div>
        <div class="ecd-num">${d.getDate()}</div>
        <div class="ecd-mon">${months[d.getMonth()]}</div>
      </div>
      <div class="event-card-body">
        <div class="event-card-top">
          <span class="event-format-badge event-format-${ev.format || 'core'}">${fmtLabel}</span>
          <span class="event-region-label">${ev.region}</span>
        </div>
        <div class="event-card-title">${ev.title}</div>
        <div class="event-card-shop">${storeSvg} ${ev.shop} &mdash; ${ev.address}</div>
        <div class="event-card-footer">
          <div class="event-card-meta">
            <span>${time}</span>
            <span class="event-card-sep">&middot;</span>
            <span>Entry: ${ev.fee}</span>
          </div>
          <a class="ev-meta-brief-link" href="#" onclick="event.stopPropagation();switchToTab('meta');return false">Meta Brief &rarr;</a>
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderEventsTab(main) {
  // View toggle SVGs
  const listSvg = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="1" y1="3" x2="15" y2="3"/><line x1="1" y1="8" x2="15" y2="8"/><line x1="1" y1="13" x2="15" y2="13"/></svg>';
  const mapSvg = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 1C5.24 1 3 3.24 3 6c0 3.75 5 9 5 9s5-5.25 5-9c0-2.76-2.24-5-5-5z"/><circle cx="8" cy="6" r="2"/></svg>';
  const splitSvg = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="1" width="14" height="14" rx="2"/><line x1="8" y1="1" x2="8" y2="15"/></svg>';

  const cardsHtml = buildEventCardsHtml(EVENTS_CONFIG);

  main.innerHTML = `
    <div class="tab-section-hdr">
      <span class="tab-section-hdr__eyebrow">Events</span>
      <span class="tab-section-hdr__title">Tournaments &middot; map &middot; submission</span>
    </div>
    <div class="deck-intro deck-intro--above">
      <strong>Lorcana events near you.</strong> Filter by region and format, browse on
      the map or as a list. Submit a missing tournament with the button on the right —
      we publish it after a quick check.
    </div>

    <div class="events-filter-bar">
      <div class="events-filter-group">
        <select class="deck-select" id="ev-filter-region" onchange="evApplyFilters()" style="min-width:100px">
          <option value="">All Regions</option>
          <option value="nord">Nord</option>
          <option value="centro">Centro</option>
          <option value="sud">Sud</option>
        </select>
        <select class="deck-select" id="ev-filter-format" onchange="evApplyFilters()" style="min-width:100px">
          <option value="">All Formats</option>
          <option value="core">Core</option>
          <option value="infinity">Infinity</option>
          <option value="draft">Draft</option>
        </select>
      </div>
      <div class="events-view-toggle">
        <button class="ev-view-btn${evCurrentView==='split'?' active':''}" data-view="split" onclick="evSetView('split')" aria-label="Split view">${splitSvg}</button>
        <button class="ev-view-btn${evCurrentView==='list'?' active':''}" data-view="list" onclick="evSetView('list')" aria-label="List view">${listSvg}</button>
        <button class="ev-view-btn${evCurrentView==='map'?' active':''}" data-view="map" onclick="evSetView('map')" aria-label="Map only">${mapSvg}</button>
      </div>
      <button class="ev-submit-btn" onclick="evToggleSubmitForm(true)">+ Submit Event</button>
    </div>

    <div class="events-split" id="events-split">
      <div class="events-map-pane${evCurrentView==='list'?' ':' ev-mobile-map-active'}" id="events-map-pane" style="${evCurrentView==='list'?'display:none':''}">
        <div id="ev-leaflet-map" class="ev-leaflet-map"></div>
        <div class="ev-map-legend">
          <span class="ev-legend-dot ev-legend-core"></span>Core
          <span class="ev-legend-dot ev-legend-infinity"></span>Infinity
          <span class="ev-legend-dot ev-legend-draft"></span>Draft
        </div>
      </div>
      <div class="events-list-pane" id="events-list-pane" style="${evCurrentView==='map'?'display:none':''}">
        <div class="events-list-header">
          <span id="ev-count-label">${EVENTS_CONFIG.length} event${EVENTS_CONFIG.length !== 1 ? 's' : ''}</span>
          <div class="ev-sort-bar">
            <button class="ev-sort-btn active" data-sort="date" onclick="evSetSort('date')">Date</button>
            <button class="ev-sort-btn" data-sort="nearest" onclick="evSetSort('nearest')">Nearest</button>
          </div>
        </div>
        <div class="events-list" id="events-list">${cardsHtml}</div>
      </div>
    </div>`;

  // Init Leaflet
  initEvLeaflet();
}

function initEvLeaflet() {
  if (!evLeafletLoaded) {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(css);
    const js = document.createElement('script');
    js.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    js.onload = () => { evLeafletLoaded = true; buildEvMap(); };
    document.head.appendChild(js);
  } else {
    setTimeout(buildEvMap, 50);
  }
}

function buildEvMap() {
  const el = document.getElementById('ev-leaflet-map');
  if (!el || !window.L) return;
  if (evMap) { evMap.remove(); evMap = null; }
  evMap = L.map('ev-leaflet-map', { center: [42.5, 12.5], zoom: 6, zoomControl: true });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap', maxZoom: 18
  }).addTo(evMap);
  evMarkers = [];
  const colors = { core: '#2471A3', infinity: '#7B3FA0', draft: '#2A8F4E' };
  EVENTS_CONFIG.forEach(ev => {
    const color = colors[ev.format] || '#6C7A89';
    const icon = L.divIcon({
      className: '',
      html: `<svg width="28" height="36" viewBox="0 0 28 36"><path d="M14 0C6.27 0 0 6.27 0 14c0 9.67 14 22 14 22S28 23.67 28 14C28 6.27 21.73 0 14 0z" fill="${color}" opacity="0.9"/><circle cx="14" cy="14" r="5" fill="white" opacity="0.9"/></svg>`,
      iconSize: [28, 36], iconAnchor: [14, 36], popupAnchor: [0, -36]
    });
    const marker = L.marker([ev.lat, ev.lng], { icon }).addTo(evMap);
    marker.bindPopup(`<strong>${ev.title}</strong><br>${ev.shop}<br><span class="event-format-badge event-format-${ev.format}" style="display:inline-block;margin-top:4px">${ev.format}</span>`);
    marker._evId = ev.id;
    marker.on('click', () => {
      const card = document.querySelector(`.event-card[data-event-id="${ev.id}"]`);
      if (card) { card.scrollIntoView({ behavior:'smooth', block:'center' }); card.classList.add('ev-highlighted'); setTimeout(()=>card.classList.remove('ev-highlighted'), 2000); }
    });
    evMarkers.push(marker);
  });
}

function evHighlightOnMap(evId) {
  if (!evMap) return;
  const ev = EVENTS_CONFIG.find(e => e.id === evId);
  if (!ev) return;
  evMap.setView([ev.lat, ev.lng], 10, { animate: true });
  const m = evMarkers.find(mk => mk._evId === evId);
  if (m) m.openPopup();
}

function evSetView(view) {
  evCurrentView = view;
  const mapPane = document.getElementById('events-map-pane');
  const listPane = document.getElementById('events-list-pane');
  if (!mapPane || !listPane) return;
  const split = document.getElementById('events-split');
  document.querySelectorAll('.ev-view-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  if (view === 'list') {
    mapPane.style.display = 'none';
    listPane.style.display = '';
    split.style.gridTemplateColumns = '1fr';
  } else if (view === 'map') {
    mapPane.style.display = '';
    listPane.style.display = 'none';
    split.style.gridTemplateColumns = '1fr';
    mapPane.classList.add('ev-mobile-map-active');
    if (evMap) setTimeout(() => evMap.invalidateSize(), 100);
  } else {
    mapPane.style.display = '';
    listPane.style.display = '';
    split.style.gridTemplateColumns = '1fr 380px';
    if (evMap) setTimeout(() => evMap.invalidateSize(), 100);
  }
}

let evCurrentSort = 'date';

function evSetSort(sort) {
  evCurrentSort = sort;
  document.querySelectorAll('.ev-sort-btn').forEach(b => b.classList.toggle('active', b.dataset.sort === sort));
  evApplyFilters();
}

function evApplyFilters() {
  const region = document.getElementById('ev-filter-region')?.value || '';
  const format = document.getElementById('ev-filter-format')?.value || '';
  let filtered = EVENTS_CONFIG.filter(ev => (!region || ev.region === region) && (!format || ev.format === format));
  // Sort
  if (evCurrentSort === 'date') {
    filtered.sort((a, b) => new Date(a.date) - new Date(b.date));
  }
  // Rebuild list
  const listEl = document.getElementById('events-list');
  if (listEl) listEl.innerHTML = buildEventCardsHtml(filtered);
  // Update count
  const countEl = document.getElementById('ev-count-label');
  if (countEl) countEl.textContent = `${filtered.length} event${filtered.length !== 1 ? 's' : ''}`;
  // Update markers
  if (evMap) {
    evMarkers.forEach(m => {
      const ev = EVENTS_CONFIG.find(e => e.id === m._evId);
      if (!ev) return;
      const show = (!region || ev.region === region) && (!format || ev.format === format);
      if (show) { if (!evMap.hasLayer(m)) m.addTo(evMap); } else { if (evMap.hasLayer(m)) evMap.removeLayer(m); }
    });
  }
}

function evToggleSubmitForm(show) {
  let overlay = document.getElementById('ev-submit-overlay');
  if (show && !overlay) {
    overlay = document.createElement('div');
    overlay.id = 'ev-submit-overlay';
    overlay.className = 'ev-submit-overlay';
    overlay.onclick = e => { if (e.target === overlay) evToggleSubmitForm(false); };
    overlay.innerHTML = `<div class="ev-submit-modal">
      <div class="ev-modal-hdr"><h3>Submit Your Tournament</h3><button class="cs-close" onclick="evToggleSubmitForm(false)">&times;</button></div>
      <form class="ev-submit-form" onsubmit="evSubmitEvent(event)">
        <div class="ev-form-group"><label>Shop Name *</label><input type="text" required class="ev-input" placeholder="Magic Store Roma"></div>
        <div class="ev-form-group"><label>Address *</label><input type="text" required class="ev-input" placeholder="Via Roma 12, Milano MI"></div>
        <div class="ev-form-row">
          <div class="ev-form-group"><label>Date *</label><input type="date" required class="ev-input"></div>
          <div class="ev-form-group"><label>Time *</label><input type="time" required class="ev-input"></div>
        </div>
        <div class="ev-form-group"><label>Format *</label><select required class="deck-select" style="width:100%"><option value="core">Core Constructed</option><option value="infinity">Infinity</option><option value="draft">Draft</option><option value="sealed">Sealed</option></select></div>
        <div class="ev-form-group"><label>Entry Fee</label><input type="text" class="ev-input" placeholder="5\u20AC or Free"></div>
        <div class="ev-form-group"><label>Contact Email *</label><input type="email" required class="ev-input" placeholder="store@example.com"></div>
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
          <button type="submit" class="ev-submit-confirm-btn">Submit for Review</button>
          <span class="ev-form-note">We review within 24h.</span>
        </div>
      </form>
    </div>`;
    document.body.appendChild(overlay);
  } else if (!show && overlay) {
    overlay.remove();
  }
}

function evSubmitEvent(e) {
  e.preventDefault();
  const overlay = document.getElementById('ev-submit-overlay');
  if (overlay) {
    const modal = overlay.querySelector('.ev-submit-modal');
    modal.innerHTML = `<div style="text-align:center;padding:40px">
      <div style="font-size:2em;margin-bottom:12px">\u2705</div>
      <h3 style="color:var(--gold)">Thanks!</h3>
      <p style="color:var(--text2)">We'll review your event within 24 hours.</p>
      <button class="pf-ghost-btn" onclick="evToggleSubmitForm(false)" style="margin-top:12px">Close</button>
    </div>`;
  }
}

