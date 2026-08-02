import { absoluteUrl } from './api.js';

export function openInvoice(event, url) {
  if (event) event.preventDefault();
  let dest = url || (event && event.currentTarget && event.currentTarget.href);
  if (!dest || dest === '#' || dest === window.location.href + '#') return;
  if (dest.indexOf('/') === 0) dest = window.location.protocol + '//' + window.location.host + dest;
  window.location.href = dest;
}

export function initLayoutModule() {
  document.querySelectorAll('[data-fab-switch-root]').forEach(function (root) {
    const buttons = Array.from(root.querySelectorAll('[data-fab-switch-target]'));
    const panels = buttons.map(function (btn) { return document.getElementById(btn.getAttribute('data-fab-switch-target')); }).filter(Boolean);
    const placeholder = document.getElementById(root.getAttribute('data-fab-switch-placeholder') || '');
    const storageKey = root.id === 'dashboardSwitchButtons' ? 'fab_dash_tab' : (root.id ? 'fab_switch_' + root.id : null);

    function reset(showPlaceholder) {
      buttons.forEach(function (btn) { btn.classList.remove('is-active'); btn.setAttribute('aria-pressed', 'false'); });
      panels.forEach(function (panel) { panel.hidden = true; });
      if (placeholder) placeholder.hidden = !showPlaceholder;
    }

    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const target = btn.getAttribute('data-fab-switch-target');
        const panel = document.getElementById(target);
        const active = btn.classList.contains('is-active');
        
        reset(active);
        
        if (active) {
          if (storageKey) {
            try { localStorage.removeItem(storageKey); } catch (e) {}
          }
          return;
        }
        
        if (!panel) return;
        btn.classList.add('is-active');
        btn.setAttribute('aria-pressed', 'true');
        panel.hidden = false;
        if (placeholder) placeholder.hidden = true;
        
        if (storageKey) {
          try { localStorage.setItem(storageKey, target); } catch (e) {}
        }
        
        requestAnimationFrame(function () {
          document.dispatchEvent(new CustomEvent('fab:panel-open', { detail: { panel: panel } }));
          window.dispatchEvent(new Event('resize'));
        });
      });
    });

    let restored = false;
    if (storageKey) {
      try {
        const savedTarget = localStorage.getItem(storageKey);
        if (savedTarget) {
          const targetBtn = buttons.find(function (b) { return b.getAttribute('data-fab-switch-target') === savedTarget; });
          if (targetBtn) {
            const panel = document.getElementById(savedTarget);
            if (panel) {
              reset(false);
              targetBtn.classList.add('is-active');
              targetBtn.setAttribute('aria-pressed', 'true');
              panel.hidden = false;
              if (placeholder) placeholder.hidden = true;
              restored = true;
              requestAnimationFrame(function () {
                document.dispatchEvent(new CustomEvent('fab:panel-open', { detail: { panel: panel } }));
                window.dispatchEvent(new Event('resize'));
              });
            }
          }
        }
      } catch (e) {}
    }

    if (!restored) {
      reset(true);
    }
  });

  const btn = document.getElementById('drawerBtn');
  const close = document.getElementById('drawerClose');
  const drawer = document.getElementById('navDrawer');
  const overlay = document.getElementById('navOverlay');

  if (btn && drawer && overlay) {
    let previousOverflow = '';
    const open = function () { previousOverflow = document.body.style.overflow; drawer.classList.add('open'); overlay.classList.add('open'); document.body.style.overflow = 'hidden'; };
    const shut = function () { drawer.classList.remove('open'); overlay.classList.remove('open'); document.body.style.overflow = previousOverflow; };
    btn.addEventListener('click', open);
    close?.addEventListener('click', shut);
    overlay.addEventListener('click', shut);
    document.addEventListener('keydown', function (event) { if (event.key === 'Escape' && drawer.classList.contains('open')) shut(); });
    drawer.querySelectorAll('a').forEach(function (link) { link.addEventListener('click', shut); });
  }

  // ── 0. Drawer Submenu Accordions (Mobile & Sidebar Outils Toggle) ──
  document.addEventListener('click', function (e) {
    const toggle = e.target.closest('[data-drawer-toggle]');
    if (!toggle) return;
    const group = toggle.closest('.drawer-group');
    if (!group) return;
    const nextOpen = !group.classList.contains('open');
    group.classList.toggle('open', nextOpen);
    toggle.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
  });

  // ── 0b. Robust Navbar Dropdown Click Handler (Conflict-free Bootstrap 5 & Fallback) ──
  document.addEventListener('click', function (e) {
    const trigger = e.target.closest('[data-bs-toggle="dropdown"], .nav-link-menu');
    if (!trigger) {
      if (!e.target.closest('.dropdown')) {
        document.querySelectorAll('.dropdown.show, .dropdown-menu.show').forEach(function (el) {
          el.classList.remove('show');
        });
      }
      return;
    }

    // If Bootstrap 5 is active, let Bootstrap manage the dropdown natively to prevent double-toggling (open/close conflict)
    if (window.bootstrap && window.bootstrap.Dropdown) {
      try {
        const instance = window.bootstrap.Dropdown.getOrCreateInstance(trigger);
        if (instance) return;
      } catch (err) {}
    }

    // Fallback if Bootstrap JS is not loaded or fails
    const parent = trigger.closest('.dropdown') || trigger.parentElement;
    if (!parent) return;
    const menu = parent.querySelector('.dropdown-menu');
    if (!menu) return;

    const isShown = menu.classList.contains('show') || parent.classList.contains('show');

    document.querySelectorAll('.dropdown.show, .dropdown-menu.show').forEach(function (el) {
      if (el !== parent && el !== menu) {
        el.classList.remove('show');
      }
    });

    const nextShow = !isShown;
    parent.classList.toggle('show', nextShow);
    menu.classList.toggle('show', nextShow);
    trigger.setAttribute('aria-expanded', nextShow ? 'true' : 'false');
  });





  // ── 1. Global Keyboard Shortcuts (Ctrl+K / Cmd+K -> Search, Alt+N -> New Operation) ──
  document.addEventListener('keydown', function (e) {
    // Ctrl+K or Cmd+K: Open Quick Search
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      const searchTrigger = document.querySelector('[data-search-trigger]') || document.getElementById('globalSearchBtn');
      if (searchTrigger) {
        searchTrigger.click();
      } else {
        const searchModal = document.getElementById('searchOverlay') || document.querySelector('.search-overlay');
        if (searchModal) searchModal.hidden = !searchModal.hidden;
      }
    }
    // Alt+N: Quick New Sale / Operation
    if (e.altKey && e.key.toLowerCase() === 'n') {
      e.preventDefault();
      const newOpBtn = document.querySelector('a[href*="/operations/new"], a[href*="/sales/new"]');
      if (newOpBtn) newOpBtn.click();
    }
  });

  // ── 2. Form Auto-Draft UX Protection (Anti-Data Loss) ──
  document.querySelectorAll('form[data-auto-save-draft]').forEach(function(form) {
    const formId = form.id || form.action || window.location.pathname;
    const storageKey = 'fab_draft_' + formId;

    // Restore draft on load
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const data = JSON.parse(saved);
        Object.keys(data).forEach(function(name) {
          const input = form.querySelector(`[name="${name}"]`);
          if (input && !input.value) {
            input.value = data[name];
          }
        });
      }
    } catch(e) {}

    // Auto-save inputs to draft
    form.addEventListener('input', function() {
      try {
        const formData = new FormData(form);
        const draft = {};
        formData.forEach((val, key) => {
          if (key && !key.includes('password') && !key.includes('csrf') && typeof val === 'string') {
            draft[key] = val;
          }
        });
        sessionStorage.setItem(storageKey, JSON.stringify(draft));
      } catch(e) {}
    });

    // Clear draft on successful submit
    form.addEventListener('submit', function() {
      try { sessionStorage.removeItem(storageKey); } catch(e) {}
    });
  });

  window.openInvoice = window.openInvoice || openInvoice;
}
