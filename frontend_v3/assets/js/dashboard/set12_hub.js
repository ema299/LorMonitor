/**
 * Set 12 Hub — Home tab hero per lancio espansione Set 12 (drop: 12 Maggio 2026).
 *
 * API esposta:
 *   window.renderSet12Hub()  -> stringa HTML (senza <style>/<script>)
 *   window.initSet12Hub()    -> inject styles + wire countdown + wire form submit
 *
 * Integration:
 *   In profile.js renderProfileTab(), prima di main.innerHTML:
 *     const set12 = (typeof renderSet12Hub === 'function') ? renderSet12Hub() : '';
 *   Poi inline in cima al template:
 *     main.innerHTML = `${set12}<div class="pf-dash">...</div>`;
 *   Dopo l'innerHTML:
 *     if (typeof initSet12Hub === 'function') initSet12Hub();
 *
 * Cosa e' TODO (placeholder attualmente visibili):
 *   FORM_ACTION  -> URL Google Form quando creato
 *   DISCORD_INVITE -> invite permanente Discord quando creato
 */

(function (global) {
  'use strict';

  // Drop date Set 12 — confermato 22/04
  const RELEASE_DATE = '2026-05-12T00:00:00Z';

  // TODO: sostituire quando Google Form e' creato
  // Pattern per Google Form: https://docs.google.com/forms/d/e/FORM_ID/formResponse
  // con campo email come entry.NUMERIC_ID (ispeziona via DevTools)
  const FORM_ACTION = 'https://docs.google.com/forms/d/e/REPLACE-WITH-FORM-ID/formResponse';
  const FORM_EMAIL_FIELD = 'entry.REPLACE-WITH-ENTRY-ID';

  // TODO: sostituire quando Discord server e' creato
  const DISCORD_INVITE = 'https://discord.gg/REPLACE-WITH-INVITE';

  // ============================================================
  // STYLES — injected once in <head>
  // ============================================================
  const STYLES = `
    .set12-hub {
      background: linear-gradient(135deg, #1a0f2e 0%, #2d1a4a 100%);
      color: #fff;
      border-radius: 12px;
      padding: 28px 20px;
      margin: 0 0 20px;
      border: 1px solid rgba(255, 215, 0, 0.25);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
      position: relative;
      overflow: hidden;
    }
    .set12-hub::before {
      content: '';
      position: absolute;
      top: -50%; right: -20%;
      width: 400px; height: 400px;
      background: radial-gradient(circle, rgba(255, 215, 0, 0.08) 0%, transparent 60%);
      pointer-events: none;
    }
    .set12-hub__inner { position: relative; max-width: 720px; margin: 0 auto; }
    .set12-hub__eyebrow {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.18em;
      color: #ffd700;
      text-transform: uppercase;
      margin-bottom: 10px;
      padding: 4px 10px;
      background: rgba(255, 215, 0, 0.1);
      border-radius: 4px;
      border: 1px solid rgba(255, 215, 0, 0.25);
    }
    .set12-hub__title {
      font-size: 1.55rem;
      line-height: 1.22;
      font-weight: 700;
      margin: 0 0 12px;
      letter-spacing: -0.01em;
    }
    @media (min-width: 768px) {
      .set12-hub__title { font-size: 2rem; }
    }
    .set12-hub__title-accent { color: #ffd700; }
    .set12-hub__lede {
      font-size: 0.95rem;
      line-height: 1.55;
      margin: 0 0 20px;
      opacity: 0.92;
    }
    .set12-hub__countdown {
      display: flex;
      gap: 18px;
      justify-content: center;
      margin: 0 0 20px;
      padding: 14px 0;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 8px;
      border: 1px solid rgba(255, 215, 0, 0.1);
    }
    .set12-hub__cd-item { text-align: center; min-width: 60px; }
    .set12-hub__cd-value {
      display: block;
      font-size: 1.9rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      color: #ffd700;
      line-height: 1;
    }
    .set12-hub__cd-label {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      opacity: 0.72;
      margin-top: 4px;
      display: block;
    }
    .set12-hub__form {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 215, 0, 0.18);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 16px;
    }
    .set12-hub__label {
      display: block;
      font-size: 0.88rem;
      font-weight: 600;
      margin-bottom: 10px;
    }
    .set12-hub__form-row {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    @media (min-width: 640px) {
      .set12-hub__form-row { flex-direction: row; }
    }
    .set12-hub__input {
      flex: 1;
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #fff;
      padding: 11px 14px;
      border-radius: 6px;
      font-size: 0.95rem;
      outline: none;
      font-family: inherit;
    }
    .set12-hub__input::placeholder { color: rgba(255, 255, 255, 0.4); }
    .set12-hub__input:focus { border-color: #ffd700; }
    .set12-hub__submit {
      background: #ffd700;
      color: #1a0f2e;
      font-weight: 700;
      border: 0;
      padding: 11px 20px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.95rem;
      white-space: nowrap;
      transition: transform 0.15s ease, background 0.15s ease;
      font-family: inherit;
    }
    .set12-hub__submit:hover { transform: translateY(-1px); background: #ffed4e; }
    .set12-hub__submit:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    .set12-hub__disclaimer {
      font-size: 0.72rem;
      opacity: 0.55;
      margin: 8px 0 0;
    }
    .set12-hub__form-feedback {
      margin-top: 8px;
      font-size: 0.85rem;
      min-height: 1.2em;
    }
    .set12-hub__form-feedback.is-success { color: #7ae27a; }
    .set12-hub__form-feedback.is-error { color: #ff8a8a; }
    .set12-hub__ctas {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 20px;
    }
    .set12-hub__cta {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 16px;
      border-radius: 6px;
      text-decoration: none;
      font-weight: 600;
      font-size: 0.85rem;
      transition: transform 0.15s ease;
    }
    .set12-hub__cta:hover { transform: translateY(-1px); }
    .set12-hub__cta--discord { background: #5865F2; color: #fff; }
    .set12-hub__cta--discord:hover { background: #6876ff; }
    .set12-hub__cta--preview {
      background: transparent;
      color: #ffd700;
      border: 1px solid rgba(255, 215, 0, 0.4);
    }
    .set12-hub__cta--preview:hover { background: rgba(255, 215, 0, 0.08); }
    .set12-hub__teaser {
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      padding-top: 16px;
      margin-top: 4px;
    }
    .set12-hub__teaser-title {
      font-size: 1rem;
      font-weight: 600;
      margin: 0 0 10px;
      color: #ffd700;
      letter-spacing: 0.01em;
    }
    .set12-hub__teaser-list {
      margin: 0;
      padding-left: 18px;
      line-height: 1.75;
      font-size: 0.88rem;
      opacity: 0.95;
    }
    .set12-hub__teaser-list strong { color: #ffd700; font-weight: 600; }
    .set12-hub--dropped .set12-hub__eyebrow { background: rgba(126, 226, 122, 0.15); border-color: rgba(126, 226, 122, 0.4); color: #7ae27a; }
  `;

  // ============================================================
  // HTML — pure fragment (safe per innerHTML)
  // ============================================================
  function html() {
    return '<section class="v3-panel set12-hub" id="set12Hub" data-release-date="' + RELEASE_DATE + '">' +
      '<div class="set12-hub__inner">' +
        '<span class="set12-hub__eyebrow">SET 12 — Coming May 12</span>' +
        '<h1 class="set12-hub__title">' +
          '100,000 matches simulated with Set 12 cards.<br>' +
          '<span class="set12-hub__title-accent">See the meta before it arrives.</span>' +
        '</h1>' +
        '<p class="set12-hub__lede">' +
          "Set 12 is about to drop. While everyone else waits to test, we’ve already simulated " +
          "the meta with the new cards. Data-driven tier list, broken killer curves, day-one combos. " +
          "Subscribe — you get it free the moment it’s out." +
        '</p>' +
        '<div class="set12-hub__countdown" id="set12Countdown" aria-live="polite">' +
          '<div class="set12-hub__cd-item"><span class="set12-hub__cd-value" data-cd="days">--</span><span class="set12-hub__cd-label">days</span></div>' +
          '<div class="set12-hub__cd-item"><span class="set12-hub__cd-value" data-cd="hours">--</span><span class="set12-hub__cd-label">hours</span></div>' +
          '<div class="set12-hub__cd-item"><span class="set12-hub__cd-value" data-cd="mins">--</span><span class="set12-hub__cd-label">min</span></div>' +
        '</div>' +
        '<form class="set12-hub__form" id="set12LeadForm" novalidate>' +
          '<label class="set12-hub__label" for="set12Email">' +
            'Get the Set 12 Meta Preview PDF the day it drops' +
          '</label>' +
          '<div class="set12-hub__form-row">' +
            '<input type="email" id="set12Email" name="email" required autocomplete="email" ' +
                   'placeholder="you@example.com" class="set12-hub__input">' +
            '<button type="submit" class="set12-hub__submit">Reserve my copy</button>' +
          '</div>' +
          '<p class="set12-hub__disclaimer">' +
            'Free. No spam. Unsubscribe anytime. Powered by 50K+ real match data.' +
          '</p>' +
          '<div class="set12-hub__form-feedback" id="set12FormFeedback" role="status" aria-live="polite"></div>' +
        '</form>' +
        '<div class="set12-hub__ctas">' +
          '<a class="set12-hub__cta set12-hub__cta--discord" href="' + DISCORD_INVITE + '" target="_blank" rel="noopener">' +
            '<span aria-hidden="true">#</span> Join the Discord' +
          '</a>' +
          '<a class="set12-hub__cta set12-hub__cta--preview" href="#set12Preview">See the sneak peek</a>' +
        '</div>' +
        '<div class="set12-hub__teaser" id="set12Preview">' +
          '<h2 class="set12-hub__teaser-title">What you get in the Meta Preview</h2>' +
          '<ul class="set12-hub__teaser-list">' +
            '<li><strong>Data-driven tier list</strong> from 100K matches simulated with Set 12 cards</li>' +
            '<li><strong>Top 5 shock cards</strong> that reshape the meta</li>' +
            '<li><strong>3 broken combos</strong> with killer curves and tactical response</li>' +
            '<li><strong>Matchup matrix</strong> post-Set 12 vs Set 11</li>' +
            '<li><strong>Rising / falling decks</strong> with projected WR</li>' +
          '</ul>' +
        '</div>' +
      '</div>' +
    '</section>';
  }

  // ============================================================
  // STYLES injection (once)
  // ============================================================
  function injectStyles() {
    if (document.getElementById('set12HubStyles')) return;
    const style = document.createElement('style');
    style.id = 'set12HubStyles';
    style.textContent = STYLES;
    document.head.appendChild(style);
  }

  // ============================================================
  // COUNTDOWN tick
  // ============================================================
  let countdownInterval = null;

  function initCountdown() {
    const root = document.getElementById('set12Hub');
    if (!root) return;
    if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }

    const release = new Date(root.getAttribute('data-release-date')).getTime();
    const fields = {
      days: root.querySelector('[data-cd="days"]'),
      hours: root.querySelector('[data-cd="hours"]'),
      mins: root.querySelector('[data-cd="mins"]'),
    };

    function pad(n) { return String(n).padStart(2, '0'); }

    function tick() {
      const now = Date.now();
      const diff = Math.max(0, release - now);
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      const mins = Math.floor((diff % 3600000) / 60000);
      if (fields.days) fields.days.textContent = pad(days);
      if (fields.hours) fields.hours.textContent = pad(hours);
      if (fields.mins) fields.mins.textContent = pad(mins);
      if (diff === 0) {
        root.classList.add('set12-hub--dropped');
        const eyebrow = root.querySelector('.set12-hub__eyebrow');
        if (eyebrow) eyebrow.textContent = 'SET 12 — Live Now';
      }
    }
    tick();
    countdownInterval = setInterval(tick, 30000);
  }

  // ============================================================
  // LEAD FORM submit
  // ============================================================
  function initForm() {
    const form = document.getElementById('set12LeadForm');
    const feedback = document.getElementById('set12FormFeedback');
    if (!form || !feedback) return;

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      feedback.className = 'set12-hub__form-feedback';
      feedback.textContent = '';

      const email = (form.email.value || '').trim();
      if (!email || email.indexOf('@') < 1 || email.length < 6) {
        feedback.className = 'set12-hub__form-feedback is-error';
        feedback.textContent = 'Please enter a valid email.';
        return;
      }

      const submitBtn = form.querySelector('.set12-hub__submit');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Submitting...';

      // MVP: se FORM_ACTION non e' ancora configurato (placeholder),
      // salva localmente + mostra success. Quando Google Form e' pronto, rimuovi questo branch.
      const isPlaceholder = FORM_ACTION.indexOf('REPLACE') >= 0;

      try {
        if (isPlaceholder) {
          // Fallback locale finche' Google Form non e' configurato
          const stored = JSON.parse(localStorage.getItem('set12_local_signups') || '[]');
          if (stored.indexOf(email) < 0) stored.push(email);
          localStorage.setItem('set12_local_signups', JSON.stringify(stored));
          console.info('[Set 12 Hub] email salvata localmente (Google Form non ancora configurato):', email);
          feedback.className = 'set12-hub__form-feedback is-success';
          feedback.textContent = 'You are in. Watch your inbox on drop day (May 12).';
          form.reset();
        } else {
          // Submit a Google Form (no-cors perche' Google non restituisce CORS headers)
          const body = new URLSearchParams();
          body.set(FORM_EMAIL_FIELD, email);
          await fetch(FORM_ACTION, {
            method: 'POST',
            mode: 'no-cors',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString(),
          });
          feedback.className = 'set12-hub__form-feedback is-success';
          feedback.textContent = 'You are in. Watch your inbox on drop day (May 12).';
          form.reset();
        }
      } catch (err) {
        feedback.className = 'set12-hub__form-feedback is-error';
        feedback.textContent = 'Something broke. Try again in a moment.';
        console.error('[Set 12 Hub] submit error:', err);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Reserve my copy';
      }
    });
  }

  // ============================================================
  // Public API
  // ============================================================
  function init() {
    injectStyles();
    initCountdown();
    initForm();
  }

  global.renderSet12Hub = html;
  global.initSet12Hub = init;

})(window);
