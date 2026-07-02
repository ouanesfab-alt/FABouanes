(function () {
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
      if (buttons.length > 0) {
        buttons[0].click();
      } else {
        reset(true);
      }
    }
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
  
  // Swipe-to-close gesture on mobile drawer
  let touchStartX = 0;
  let touchStartY = 0;
  drawer.addEventListener('touchstart', function(e) {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
  }, {passive: true});
  drawer.addEventListener('touchend', function(e) {
    const touchEndX = e.changedTouches[0].screenX;
    const touchEndY = e.changedTouches[0].screenY;
    const diffX = touchStartX - touchEndX;
    const diffY = Math.abs(touchStartY - touchEndY);
    if (diffX > 50 && diffY < 80) {
      shut();
    }
  }, {passive: true});

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

  // 🎛️ Inline Editing Controller (Finder style)
  document.addEventListener('click', function (event) {
    const editable = event.target.closest('[data-inline-edit]');
    if (!editable || event.target.closest('input, button')) return;

    // Trigger editing state
    if (editable.classList.contains('is-editing')) return;
    
    event.preventDefault();
    event.stopPropagation();

    const fieldName = editable.getAttribute('data-inline-edit');
    const currentValue = editable.getAttribute('data-value') || '';
    const label = editable.getAttribute('data-label') || 'Valeur';
    const container = document.getElementById('clientDetailContainer');
    if (!container) return;

    editable.classList.add('is-editing');
    const originalHTML = editable.innerHTML;

    // Build edit form inside the editable element
    editable.innerHTML = `
      <form class="inline-edit-form" onsubmit="return false;">
        <input type="text" class="inline-edit-input" value="${currentValue.replace(/"/g, '&quot;')}" placeholder="${label}...">
        <div class="inline-edit-actions">
          <button type="button" class="inline-edit-btn inline-edit-save" title="Enregistrer"><i class="bi bi-check-lg"></i></button>
          <button type="button" class="inline-edit-btn inline-edit-cancel" title="Annuler"><i class="bi bi-x-lg"></i></button>
        </div>
      </form>
    `;

    const input = editable.querySelector('.inline-edit-input');
    input.focus();
    input.select();

    function restore() {
      editable.classList.remove('is-editing');
      editable.innerHTML = originalHTML;
    }

    async function save() {
      const newValue = input.value.trim();
      if (newValue === currentValue) {
        restore();
        return;
      }
      if (fieldName === 'name' && !newValue) {
        alert('Le nom est obligatoire.');
        input.focus();
        return;
      }

      // Collect values from client details container
      const clientId = container.getAttribute('data-client-id');
      const payload = {
        name: container.getAttribute('data-client-name'),
        phone: container.getAttribute('data-client-phone'),
        address: container.getAttribute('data-client-address'),
        notes: container.getAttribute('data-client-notes'),
        opening_credit: container.getAttribute('data-client-opening-credit') || '0.0',
        csrf_token: window.fabCsrfToken || ''
      };

      // Update the edited field
      payload[fieldName] = newValue;

      // Submit POST via fetch
      const saveBtn = editable.querySelector('.inline-edit-save');
      saveBtn.innerHTML = '<span class="mac-spinner" style="margin-right:0;"></span>';
      saveBtn.disabled = true;

      try {
        const bodyParams = new URLSearchParams(payload);
        const response = await fetch(`/contacts/clients/${clientId}/edit`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: bodyParams.toString()
        });

        if (response.ok) {
          window.location.reload();
        } else {
          alert("Erreur lors de la modification du client.");
          restore();
        }
      } catch (err) {
        alert("Erreur réseau.");
        restore();
      }
    }

    // Bind actions
    editable.querySelector('.inline-edit-cancel').addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      restore();
    });

    editable.querySelector('.inline-edit-save').addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      save();
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        save();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        restore();
      }
    });
  });
})();

window.openInvoice = window.openInvoice || function (event, url) {
  if (event) event.preventDefault();
  let dest = url || (event && event.currentTarget && event.currentTarget.href);
  if (!dest || dest === '#' || dest === window.location.href + '#') return;
  if (dest.indexOf('/') === 0) dest = window.location.protocol + '//' + window.location.host + dest;
  window.location.href = dest;
};
