(function () {
  'use strict';

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char];
    });
  }

  function renderBadge(status) {
    const label = {
      ready: 'ready',
      active: 'active',
      next: 'next',
      locked: 'locked',
    }[status] || 'note';
    return '<span class="v3-badge v3-badge--' + escapeHtml(status || 'note') + '">' + label + '</span>';
  }

  function renderHero(view) {
    return [
      '<section class="v3-hero">',
      '<div>',
      '<p class="v3-overline">Lorcana Intelligence V3</p>',
      '<h1 class="v3-title">' + escapeHtml(view.title) + '</h1>',
      '<p class="v3-copy">' + escapeHtml(view.summary) + '</p>',
      '</div>',
      '<div class="v3-hero__meta">',
      '<div class="v3-kpi"><span class="v3-kpi__value">' + escapeHtml(view.legacyCount) + '</span><span class="v3-kpi__label">surface legacy</span></div>',
      '<div class="v3-kpi"><span class="v3-kpi__value">' + escapeHtml(view.focus) + '</span><span class="v3-kpi__label">focus</span></div>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderRailCard(title, items) {
    const body = items.map(function (item) {
      return [
        '<article class="v3-rail-card__item">',
        '<div class="v3-rail-card__head">',
        '<strong>' + escapeHtml(item.title) + '</strong>',
        renderBadge(item.status),
        '</div>',
        '<p>' + escapeHtml(item.copy) + '</p>',
        '</article>',
      ].join('');
    }).join('');

    return [
      '<section class="v3-rail-card">',
      '<div class="v3-section-head">',
      '<h2>' + escapeHtml(title) + '</h2>',
      '</div>',
      body,
      '</section>',
    ].join('');
  }

  function renderBlueprint(items) {
    const body = items.map(function (item) {
      return [
        '<article class="v3-blueprint-card">',
        '<div class="v3-blueprint-card__top">',
        '<span class="v3-blueprint-card__label">' + escapeHtml(item.label) + '</span>',
        '<span class="v3-blueprint-card__ownership">' + escapeHtml(item.ownership) + '</span>',
        '</div>',
        '<p>' + escapeHtml(item.summary) + '</p>',
        '<div class="v3-chip-row">',
        item.legacy.map(function (entry) {
          return '<span class="v3-chip">' + escapeHtml(entry) + '</span>';
        }).join(''),
        '</div>',
        '</article>',
      ].join('');
    }).join('');

    return [
      '<section class="v3-panel">',
      '<div class="v3-section-head">',
      '<h2>Mappa IA target</h2>',
      '<p>La shell espone gia la struttura finale, senza ancora spostare gli oggetti reali.</p>',
      '</div>',
      '<div class="v3-blueprint-grid">',
      body,
      '</div>',
      '</section>',
    ].join('');
  }

  function renderStageList(items) {
    return items.map(function (item) {
      return [
        '<article class="v3-stage v3-stage--' + escapeHtml(item.status) + '">',
        '<div class="v3-stage__meta">',
        '<span class="v3-stage__phase">' + escapeHtml(item.phase) + '</span>',
        renderBadge(item.status),
        '</div>',
        '<h3>' + escapeHtml(item.title) + '</h3>',
        '<p>' + escapeHtml(item.outcome) + '</p>',
        '</article>',
      ].join('');
    }).join('');
  }

  function renderPlaceholder(view) {
    return [
      '<section class="v3-panel">',
      '<div class="v3-section-head">',
      '<h2>' + escapeHtml(view.title) + '</h2>',
      '<p>' + escapeHtml(view.summary) + '</p>',
      '</div>',
      '<div class="v3-placeholder">',
      '<p>Base V3 pronta. Questa superficie e gia definita nella IA ma non e ancora collegata agli oggetti live.</p>',
      '<div class="v3-chip-row">',
      view.legacy.map(function (entry) {
        return '<span class="v3-chip">' + escapeHtml(entry) + '</span>';
      }).join(''),
      '</div>',
      '</div>',
      '</section>',
    ].join('');
  }

  window.V3 = window.V3 || {};
  window.V3.UI = {
    escapeHtml,
    renderHero,
    renderRailCard,
    renderBlueprint,
    renderStageList,
    renderPlaceholder,
  };
})();
