/**
 * Ripple Effect Module — 500ms
 * Sélecteur exhaustif couvrant TOUS les boutons de TOUTES les pages
 */

const RIPPLE_SELECTOR = [
  'button',
  '.btn',
  '[type="button"]',
  '[type="submit"]',
  '[type="reset"]',
  'a.nav-link',
  'a.dropdown-item',
  'a.list-group-item-action',
  'a.page-link',
  '.nav-btn',
  '.bot-tab',
  '.bot-tab-add',
  '.sidebar-link',
  '.drawer-link',
  '[role="button"]',
  '.clickable',
  '.nav-brand',
  '.nav-hamburger',
  '.side-nav-toggle'
].join(',');

const DURATION = 700; // ms

function getElementBgBrightness(element) {
  let el = element;
  let bg = 'rgba(0, 0, 0, 0)';
  while (el) {
    bg = window.getComputedStyle(el).backgroundColor;
    if (bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
      const parts = bg.match(/[\d\.]+/g);
      if (parts) {
        const alpha = parts[3] !== undefined ? parseFloat(parts[3]) : 1;
        if (alpha > 0.3) {
          break;
        }
      }
    }
    el = el.parentElement;
  }
  if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') {
    const theme = document.documentElement.getAttribute('data-theme') || 'light';
    return theme.includes('dark') ? 'dark' : 'light';
  }
  const parts = bg.match(/[\d\.]+/g);
  if (parts) {
    const r = parseInt(parts[0], 10);
    const g = parseInt(parts[1], 10);
    const b = parseInt(parts[2], 10);
    const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
    return yiq >= 128 ? 'light' : 'dark';
  }
  const theme = document.documentElement.getAttribute('data-theme') || 'light';
  return theme.includes('dark') ? 'dark' : 'light';
}

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

  const brightness = getElementBgBrightness(element);
  const ripple = document.createElement('span');
  ripple.className = `ripple-wave ${brightness === 'light' ? 'ripple-dark' : 'ripple-light'}`;
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
