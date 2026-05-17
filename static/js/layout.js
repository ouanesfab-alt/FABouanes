(function () {
  document.querySelectorAll('[data-fab-switch-root]').forEach(function (root) {
    const buttons = Array.from(root.querySelectorAll('[data-fab-switch-target]'));
    const panels = buttons.map(function (btn) { return document.getElementById(btn.getAttribute('data-fab-switch-target')); }).filter(Boolean);
    const placeholder = document.getElementById(root.getAttribute('data-fab-switch-placeholder') || '');
    function reset(showPlaceholder) {
      buttons.forEach(function (btn) { btn.classList.remove('is-active'); btn.setAttribute('aria-pressed', 'false'); });
      panels.forEach(function (panel) { panel.hidden = true; });
      if (placeholder) placeholder.hidden = !showPlaceholder;
    }
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const panel = document.getElementById(btn.getAttribute('data-fab-switch-target'));
        const active = btn.classList.contains('is-active');
        reset(active);
        if (!panel || active) return;
        btn.classList.add('is-active');
        btn.setAttribute('aria-pressed', 'true');
        panel.hidden = false;
        if (placeholder) placeholder.hidden = true;
        requestAnimationFrame(function () {
          document.dispatchEvent(new CustomEvent('fab:panel-open', { detail: { panel: panel } }));
          window.dispatchEvent(new Event('resize'));
        });
      });
    });
    reset(true);
  });

  const btn = document.getElementById('drawerBtn');
  const close = document.getElementById('drawerClose');
  const drawer = document.getElementById('navDrawer');
  const overlay = document.getElementById('navOverlay');
  if (!btn || !drawer || !overlay) return;
  let previousOverflow = '';
  function open() { previousOverflow = document.body.style.overflow; drawer.classList.add('open'); overlay.classList.add('open'); document.body.style.overflow = 'hidden'; }
  function shut() { drawer.classList.remove('open'); overlay.classList.remove('open'); document.body.style.overflow = previousOverflow; }
  btn.addEventListener('click', open);
  close?.addEventListener('click', shut);
  overlay.addEventListener('click', shut);
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape' && drawer.classList.contains('open')) shut(); });
  drawer.querySelectorAll('[data-drawer-toggle]').forEach(function (toggle) {
    const group = toggle.closest('.drawer-group');
    if (!group) return;
    toggle.addEventListener('click', function (event) {
      event.preventDefault();
      const nextOpen = !group.classList.contains('open');
      group.classList.toggle('open', nextOpen);
      toggle.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
    });
  });
  drawer.querySelectorAll('a').forEach(function (link) { link.addEventListener('click', shut); });
})();

window.openInvoice = window.openInvoice || function (event, url) {
  if (event) event.preventDefault();
  let dest = url || (event && event.currentTarget && event.currentTarget.href);
  if (!dest || dest === '#' || dest === window.location.href + '#') return;
  if (dest.indexOf('/') === 0) dest = window.location.protocol + '//' + window.location.host + dest;
  window.location.href = dest;
};
