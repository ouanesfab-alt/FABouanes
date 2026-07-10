/**
 * Ripple Effect Module — 200ms
 * Injecte un effet ripple sur TOUS les boutons de toutes les pages
 * via un seul event listener global (mousedown + touchstart)
 */

const RIPPLE_SELECTOR = [
  '.btn',
  'button',
  '[type="submit"]',
  '[type="button"]',
  '[type="reset"]',
  '.dropdown-item',
  '.nav-link',
  '.nav-btn',
  '.nav-btn-primary',
  '.nav-link-menu',
  '.nav-hamburger',
  '.side-nav-toggle',
  '.bot-tab-add',
  '.sidebar-link',
  '.list-group-item-action',
  '.fab-action-btn',
  '.icon-btn',
  '.quick-action-btn',
  '.action-btn',
  '.page-link'
].join(',');

const DURATION = 500; // ms

function createRipple(element, event) {
  const rect = element.getBoundingClientRect();

  const clientX = (event.clientX !== undefined) ? event.clientX
    : (event.touches && event.touches[0]) ? event.touches[0].clientX
    : rect.left + rect.width / 2;
  const clientY = (event.clientY !== undefined) ? event.clientY
    : (event.touches && event.touches[0]) ? event.touches[0].clientY
    : rect.top + rect.height / 2;

  const x    = clientX - rect.left;
  const y    = clientY - rect.top;
  const size = Math.max(rect.width, rect.height) * 2;

  const ripple = document.createElement('span');
  ripple.className   = 'ripple-wave';
  ripple.style.width  = size + 'px';
  ripple.style.height = size + 'px';
  ripple.style.left   = (x - size / 2) + 'px';
  ripple.style.top    = (y - size / 2) + 'px';

  element.appendChild(ripple);

  setTimeout(() => {
    if (ripple.parentNode) ripple.parentNode.removeChild(ripple);
  }, DURATION + 50);
}

function handleRipple(event) {
  const el  = event.target;
  const btn = el.closest ? el.closest(RIPPLE_SELECTOR) : null;
  if (!btn) return;
  createRipple(btn, event);
}

export function initRippleModule() {
  document.addEventListener('mousedown', handleRipple, true);
  document.addEventListener('touchstart', handleRipple, { passive: true, capture: true });
}
