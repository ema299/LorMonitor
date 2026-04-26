/**
 * V3 feedback button — sticky floating button + modal.
 *
 * Lives in the bottom-right corner of the viewport (NOT in any tab),
 * so it respects the hardblock add-only window on Deck/Team/Play.
 *
 * Posts to ``POST /api/v1/feedback`` (anonymous-tolerant). On success
 * the button briefly flips to a "thanks" state then resets. Form auto-
 * captures location.href + navigator.userAgent for triage context.
 *
 * Reuses the .lm-modal-* / .lm-form-* CSS already shipped in
 * ``auth.css`` so we don't add a third style sheet.
 */
(function () {
  'use strict';

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function injectStyles() {
    if (document.getElementById('lm-feedback-styles')) return;
    const css = [
      '.lm-feedback-btn {',
      '  position: fixed; right: 16px; bottom: 16px; z-index: 9000;',
      '  background: var(--gold); color: var(--bg);',
      '  border: 0; border-radius: 999px;',
      '  padding: 10px 16px; font-weight: 700; font-size: 0.85em;',
      '  cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,0.35);',
      '  display: inline-flex; align-items: center; gap: 6px;',
      '  letter-spacing: 0.3px;',
      '}',
      '.lm-feedback-btn:hover { transform: translateY(-1px); }',
      '.lm-feedback-btn--success { background: var(--green); color: var(--bg); }',
      '@media (max-width: 640px) {',
      '  .lm-feedback-btn { right: 12px; bottom: 12px; padding: 9px 14px; font-size: 0.82em; }',
      '}',
    ].join('\n');
    const style = document.createElement('style');
    style.id = 'lm-feedback-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }

  function renderButton() {
    if (document.getElementById('lm-feedback-btn')) return;
    injectStyles();
    const btn = document.createElement('button');
    btn.id = 'lm-feedback-btn';
    btn.type = 'button';
    btn.className = 'lm-feedback-btn';
    btn.innerHTML = '<span aria-hidden="true">💬</span> Feedback';
    btn.setAttribute('aria-label', 'Send feedback');
    btn.addEventListener('click', showModal);
    document.body.appendChild(btn);
  }

  function flashSuccess() {
    const btn = document.getElementById('lm-feedback-btn');
    if (!btn) return;
    btn.classList.add('lm-feedback-btn--success');
    btn.innerHTML = '<span aria-hidden="true">✓</span> Thanks!';
    setTimeout(function () {
      btn.classList.remove('lm-feedback-btn--success');
      btn.innerHTML = '<span aria-hidden="true">💬</span> Feedback';
    }, 2500);
  }

  function closeModal() {
    const ov = document.getElementById('lm-feedback-modal-overlay');
    if (ov) ov.remove();
  }

  function showModal() {
    closeModal();
    const overlay = document.createElement('div');
    overlay.id = 'lm-feedback-modal-overlay';
    overlay.className = 'lm-modal-overlay';
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });
    overlay.innerHTML =
      '<div class="lm-modal" role="dialog" aria-modal="true">' +
        '<div class="lm-modal-body">' +
          '<button type="button" class="lm-modal-close" onclick="(function(){var o=document.getElementById(\'lm-feedback-modal-overlay\'); if(o) o.remove();})()" aria-label="Close">×</button>' +
          '<h2 class="lm-modal-title">Send feedback</h2>' +
          '<p class="lm-modal-sub">Found a bug, have a request or want to share something? We read everything.</p>' +
          '<form id="lm-feedback-form">' +
            '<div class="lm-form-error" role="alert"></div>' +
            '<div class="lm-form-info" role="status"></div>' +
            '<div class="lm-form-group">' +
              '<label class="lm-form-label" for="lm-feedback-kind">Type</label>' +
              '<select class="lm-form-input" id="lm-feedback-kind" name="kind">' +
                '<option value="general">General</option>' +
                '<option value="bug">Bug report</option>' +
                '<option value="request">Feature request</option>' +
                '<option value="coach_issue">Coach workspace issue</option>' +
              '</select>' +
            '</div>' +
            '<div class="lm-form-group">' +
              '<label class="lm-form-label" for="lm-feedback-msg">Message</label>' +
              '<textarea class="lm-form-input" id="lm-feedback-msg" name="message" rows="5" minlength="4" maxlength="4000" required placeholder="What happened? (max 4000 chars)"></textarea>' +
            '</div>' +
            '<button type="submit" class="lm-form-submit">Send</button>' +
            '<div class="lm-form-footer" style="font-size:0.78em">' +
              'We capture the page URL and browser info to help triage. Limit: ' +
              '5/day signed-in, 3/day anonymous.' +
            '</div>' +
          '</form>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    setTimeout(function () {
      const ta = overlay.querySelector('#lm-feedback-msg');
      if (ta) ta.focus();
    }, 50);

    const form = document.getElementById('lm-feedback-form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      submit(form);
    });
  }

  async function submit(form) {
    const kind = form.querySelector('#lm-feedback-kind').value;
    const message = form.querySelector('#lm-feedback-msg').value.trim();
    const submitBtn = form.querySelector('button[type="submit"]');
    const errEl = form.querySelector('.lm-form-error');
    const infoEl = form.querySelector('.lm-form-info');

    if (!message || message.length < 4) {
      errEl.textContent = 'Please tell us a bit more (4+ characters).';
      errEl.classList.add('lm-show');
      infoEl.classList.remove('lm-show');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending…';
    try {
      const resp = await fetch('/api/v1/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind: kind,
          message: message,
          page_url: window.location.href,
          user_agent: navigator.userAgent,
        }),
      });
      if (!resp.ok) {
        let detail = resp.statusText;
        try { detail = (await resp.json()).detail || detail; } catch (_) {}
        if (resp.status === 429) {
          errEl.textContent = String(detail || 'Daily feedback limit reached.');
        } else {
          errEl.textContent = 'Could not send: ' + detail;
        }
        errEl.classList.add('lm-show');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Send';
        return;
      }
      infoEl.textContent = "Thanks — we received your feedback.";
      infoEl.classList.add('lm-show');
      errEl.classList.remove('lm-show');
      submitBtn.textContent = 'Sent';
      flashSuccess();
      setTimeout(closeModal, 1200);
    } catch (err) {
      errEl.textContent = 'Network error. Please try again.';
      errEl.classList.add('lm-show');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderButton);
  } else {
    renderButton();
  }
})();
