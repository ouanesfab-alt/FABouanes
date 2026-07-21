/**
 * Ripple Effect Module — 500ms
 * Sélecteur exhaustif couvrant TOUS les boutons de TOUTES les pages
 */

const RIPPLE_SELECTOR = [
  /* Natifs */
  '.btn', 'button', '[type="submit"]', '[type="button"]', '[type="reset"]',
  /* Bootstrap variants */
  '.btn-primary', '.btn-secondary', '.btn-danger', '.btn-success',
  '.btn-warning', '.btn-dark', '.btn-link', '.btn-lg', '.btn-sm',
  '.btn-outline-primary', '.btn-outline-secondary', '.btn-outline-danger',
  '.btn-outline-success', '.btn-outline-dark',
  /* App-specific */
  '.btn-premium', '.btn-brown', '.btn-login',
  '.btn-cancel-write', '.btn-confirm-write',
  '.btn-copy', '.btn-send', '.btn-speak', '.btn-stop',
  '.btn-page-action', '.btn-page-action-secondary',
  '.btn-achat-submit', '.btn-vente-submit', '.btn-payment-submit',
  /* Navbar & layout */
  '.nav-brand', '.nav-links a',
  '.nav-btn', '.nav-btn-primary', '.nav-link-menu',
  '.nav-hamburger', '.side-nav-toggle', '.bot-tab-add', '.bot-tab',
  '.nav-link', '.nav-drawer-close',
  '.drawer-link', '.drawer-link-btn', '.drawer-sublink',
  /* Dropdowns */
  '.dropdown-item', '.dropdown-toggle',
  /* Lists & tabs */
  '.list-group-item-action', '.page-link',
  '.search-tab', '.view-tab', '.category-tab',
  '.sidebar-link',
  /* Misc interactive */
  '.fab-bar-btn', '.fab-bubble-btn', '.fab-sheet-close', '.fab-switch-btn',
  '.kpi-quick-btn', '.kpi-sheet-close',
  '.mac-btn', '.mac-modal-close',
  '.toolbar-btn', '.pin-toggle', '.toggle-pass',
  '.bubble-action-btn', '.chat-send-btn',
  '.flash-toast-close', '.btn-close',
  '.doc-line-remove', '.remove-row',
  '.js-theme', '.js-font', '.js-nav-layout',
  '.search-result-item',
  '.cm-print', '.thread-delete-btn',
  '.contacts-link',
  '.fab-action-btn', '.icon-btn', '.quick-action-btn', '.action-btn'
].join(',');

const DURATION = 700; // ms

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

  // Apply custom colored tint overlay for colored buttons
  try {
    const style = window.getComputedStyle(element);
    const bg = style.backgroundColor;
    const color = style.color;
    
    // Check if the element has a solid non-transparent background
    if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)' && !bg.startsWith('rgba(0,0,0,0)')) {
      ripple.style.backgroundColor = bg;
      ripple.style.mixBlendMode = 'screen';
      ripple.style.opacity = '0.6';
    } else if (color) {
      ripple.style.backgroundColor = color;
      ripple.style.mixBlendMode = 'normal';
      ripple.style.opacity = '0.25';
    }
  } catch (e) {
    // Graceful fallback to CSS default if computed styles fail
  }

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
