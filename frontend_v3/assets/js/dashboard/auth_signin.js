/**
 * V3 auth UI — sign-in modal + header slot rendering.
 *
 * Companion to ``auth_bootstrap.js`` (which handles JWT storage, fetch wrap
 * and profile load). This file owns the user-facing flow:
 *
 * - ``lmRenderAuthSlot()`` populates ``#lm-auth-slot`` in the header. If
 *   ``window.LM_USER`` is null → "Sign in" / "Sign up" CTA buttons.
 *   Otherwise → "Hi, {display_name}" + tier badge + "Logout" button.
 * - ``lmShowSignIn()`` opens the sign-in modal. Submit → POST /auth/login →
 *   stores tokens via ``lmAuthWriteTokens`` → reloads page so all tier-aware
 *   modules pick up the fresh session.
 * - ``lmShowSignUp()`` opens the sign-up modal (registers + signs in).
 *
 * Anti-monolith: standalone module, never touches monolith.js. CSS lives in
 * ``frontend_v3/assets/css/dashboard/auth.css``. Sign-up is bundled here
 * (small surface, shares form helpers); future password reset → separate file.
 */
(function () {
  'use strict';

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function tierBadgeHtml(tier) {
    const t = (tier || 'free').toLowerCase();
    if (t === 'free') return '';
    return '<span class="lm-auth-tier-badge">' + escHtml(t) + '</span>';
  }

  // ── Header slot ─────────────────────────────────────────────────────────
  function renderAuthSlot() {
    const slot = document.getElementById('lm-auth-slot');
    if (!slot) return;
    const user = window.LM_USER;
    if (user) {
      const name = user.display_name || user.email || 'User';
      slot.innerHTML =
        '<span class="lm-auth-logged">' +
          'Hi, <span class="lm-auth-logged-name">' + escHtml(name) + '</span>' +
          tierBadgeHtml(user.tier) +
        '</span>' +
        '<button type="button" class="lm-auth-cta lm-auth-cta--ghost" onclick="lmDoLogout()">Logout</button>';
      return;
    }
    slot.innerHTML =
      '<button type="button" class="lm-auth-cta lm-auth-cta--ghost" onclick="lmShowSignIn()">Sign in</button>' +
      '<button type="button" class="lm-auth-cta" onclick="lmShowSignUp()">Sign up</button>';
  }
  window.lmRenderAuthSlot = renderAuthSlot;

  // Re-render slot whenever a render() pass fires elsewhere. Cheap, idempotent.
  document.addEventListener('DOMContentLoaded', renderAuthSlot);
  // auth_bootstrap calls render() after profile loads; re-run our slot then.
  // We rely on the global render() to delegate; if not, fall back to a 250ms
  // delayed retry in case LM_USER lands a tick later.
  setTimeout(renderAuthSlot, 250);
  setTimeout(renderAuthSlot, 800);

  // ── Modal shell ─────────────────────────────────────────────────────────
  function closeModal() {
    const ov = document.getElementById('lm-auth-modal-overlay');
    if (ov) ov.remove();
  }
  window.lmCloseAuthModal = closeModal;

  function buildModalShell(title, subtitle, bodyHtml) {
    closeModal();
    const overlay = document.createElement('div');
    overlay.id = 'lm-auth-modal-overlay';
    overlay.className = 'lm-modal-overlay';
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });
    overlay.innerHTML =
      '<div class="lm-modal" role="dialog" aria-modal="true">' +
        '<div class="lm-modal-body">' +
          '<button type="button" class="lm-modal-close" onclick="lmCloseAuthModal()" aria-label="Close">×</button>' +
          '<h2 class="lm-modal-title">' + escHtml(title) + '</h2>' +
          (subtitle ? '<p class="lm-modal-sub">' + escHtml(subtitle) + '</p>' : '') +
          bodyHtml +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    document.addEventListener('keydown', escListener);
    // Focus first input
    setTimeout(function () {
      const f = overlay.querySelector('input');
      if (f) f.focus();
    }, 50);
  }

  function escListener(e) {
    if (e.key === 'Escape') {
      closeModal();
      document.removeEventListener('keydown', escListener);
    }
  }

  function showError(formEl, msg) {
    const err = formEl.querySelector('.lm-form-error');
    if (err) {
      err.textContent = msg;
      err.classList.add('lm-show');
    }
    const info = formEl.querySelector('.lm-form-info');
    if (info) info.classList.remove('lm-show');
  }
  function showInfo(formEl, msg) {
    const info = formEl.querySelector('.lm-form-info');
    if (info) {
      info.textContent = msg;
      info.classList.add('lm-show');
    }
    const err = formEl.querySelector('.lm-form-error');
    if (err) err.classList.remove('lm-show');
  }

  // ── Sign-in modal ───────────────────────────────────────────────────────
  function showSignIn() {
    buildModalShell(
      'Sign in',
      'Welcome back. Sign in to access your saved decks and tier-locked features.',
      '<form id="lm-signin-form" autocomplete="on">' +
        '<div class="lm-form-error" role="alert"></div>' +
        '<div class="lm-form-info" role="status"></div>' +
        '<div class="lm-form-group">' +
          '<label class="lm-form-label" for="lm-signin-email">Email</label>' +
          '<input class="lm-form-input" id="lm-signin-email" type="email" name="email" placeholder="you@example.com" autocomplete="email" required>' +
        '</div>' +
        '<div class="lm-form-group">' +
          '<label class="lm-form-label" for="lm-signin-password">Password</label>' +
          '<input class="lm-form-input" id="lm-signin-password" type="password" name="password" placeholder="••••••••" autocomplete="current-password" required>' +
        '</div>' +
        '<button type="submit" class="lm-form-submit">Sign in</button>' +
        '<div class="lm-form-footer">' +
          'New here? <button type="button" class="lm-form-link" onclick="lmShowSignUp()">Create an account</button>' +
        '</div>' +
      '</form>'
    );
    const form = document.getElementById('lm-signin-form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      submitSignIn(form);
    });
  }
  window.lmShowSignIn = showSignIn;

  async function submitSignIn(form) {
    const email = form.querySelector('#lm-signin-email').value.trim();
    const password = form.querySelector('#lm-signin-password').value;
    const submit = form.querySelector('button[type="submit"]');
    if (!email || !password) {
      showError(form, 'Email and password are required.');
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Signing in…';
    try {
      const resp = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, password: password }),
      });
      if (!resp.ok) {
        const detail = (await resp.json().catch(() => ({}))).detail || resp.statusText;
        showError(form, 'Sign in failed: ' + (detail || 'check email and password.'));
        submit.disabled = false;
        submit.textContent = 'Sign in';
        return;
      }
      const body = await resp.json();
      if (typeof window.lmAuthWriteTokens === 'function') {
        window.lmAuthWriteTokens(body.access_token, body.refresh_token);
      }
      showInfo(form, 'Signed in. Reloading…');
      // Full reload so every module re-runs with LM_USER set.
      setTimeout(function () { window.location.reload(); }, 400);
    } catch (err) {
      showError(form, 'Network error. Check your connection and try again.');
      submit.disabled = false;
      submit.textContent = 'Sign in';
    }
  }

  // ── Sign-up modal ───────────────────────────────────────────────────────
  function showSignUp() {
    buildModalShell(
      'Create account',
      'Free tier covers Play, Meta, Deck and Improve baseline. Pro and Coach tiers unlock advanced analytics.',
      '<form id="lm-signup-form" autocomplete="on">' +
        '<div class="lm-form-error" role="alert"></div>' +
        '<div class="lm-form-info" role="status"></div>' +
        '<div class="lm-form-group">' +
          '<label class="lm-form-label" for="lm-signup-name">Display name</label>' +
          '<input class="lm-form-input" id="lm-signup-name" type="text" name="display_name" placeholder="Your handle" autocomplete="name" required>' +
        '</div>' +
        '<div class="lm-form-group">' +
          '<label class="lm-form-label" for="lm-signup-email">Email</label>' +
          '<input class="lm-form-input" id="lm-signup-email" type="email" name="email" placeholder="you@example.com" autocomplete="email" required>' +
        '</div>' +
        '<div class="lm-form-group">' +
          '<label class="lm-form-label" for="lm-signup-password">Password</label>' +
          '<input class="lm-form-input" id="lm-signup-password" type="password" name="password" placeholder="At least 8 characters" autocomplete="new-password" minlength="8" required>' +
        '</div>' +
        '<div class="lm-form-group">' +
          '<label style="font-size:0.82em;color:var(--text2);display:flex;align-items:flex-start;gap:8px;line-height:1.4">' +
            '<input type="checkbox" id="lm-signup-tos" required style="margin-top:3px">' +
            '<span>I agree to the Terms of Service and Privacy Policy.</span>' +
          '</label>' +
        '</div>' +
        '<button type="submit" class="lm-form-submit">Create account</button>' +
        '<div class="lm-form-footer">' +
          'Already have an account? <button type="button" class="lm-form-link" onclick="lmShowSignIn()">Sign in</button>' +
        '</div>' +
      '</form>'
    );
    const form = document.getElementById('lm-signup-form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      submitSignUp(form);
    });
  }
  window.lmShowSignUp = showSignUp;

  async function submitSignUp(form) {
    const name = form.querySelector('#lm-signup-name').value.trim();
    const email = form.querySelector('#lm-signup-email').value.trim();
    const password = form.querySelector('#lm-signup-password').value;
    const tos = form.querySelector('#lm-signup-tos').checked;
    const submit = form.querySelector('button[type="submit"]');
    if (!name || !email || !password) {
      showError(form, 'All fields are required.');
      return;
    }
    if (password.length < 8) {
      showError(form, 'Password must be at least 8 characters.');
      return;
    }
    if (!tos) {
      showError(form, 'You must agree to the Terms of Service.');
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Creating account…';
    try {
      const resp = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, password: password, display_name: name }),
      });
      if (!resp.ok) {
        const detail = (await resp.json().catch(() => ({}))).detail || resp.statusText;
        showError(form, 'Sign up failed: ' + (detail || 'try a different email.'));
        submit.disabled = false;
        submit.textContent = 'Create account';
        return;
      }
      const body = await resp.json();
      if (typeof window.lmAuthWriteTokens === 'function') {
        window.lmAuthWriteTokens(body.access_token, body.refresh_token);
      }
      showInfo(form, 'Account created. Reloading…');
      setTimeout(function () { window.location.reload(); }, 400);
    } catch (err) {
      showError(form, 'Network error. Check your connection and try again.');
      submit.disabled = false;
      submit.textContent = 'Create account';
    }
  }

  // ── Logout ──────────────────────────────────────────────────────────────
  async function doLogout() {
    const refresh = (function () {
      try { return window.localStorage.getItem('lm_refresh_token'); }
      catch (_) { return null; }
    })();
    if (refresh) {
      try {
        await fetch('/api/v1/auth/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
      } catch (_) { /* server-side revoke best-effort */ }
    }
    if (typeof window.lmAuthClearTokens === 'function') {
      window.lmAuthClearTokens();
    }
    window.location.reload();
  }
  window.lmDoLogout = doLogout;
})();
