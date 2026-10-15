// FABOuanes ERP — Shortcuts Module (Windows Desktop & Web Keybindings)

export function initShortcutsModule() {
  document.addEventListener('keydown', (e) => {
    // Only handle if Ctrl or Cmd key is pressed or F-keys
    const isCmdOrCtrl = e.ctrlKey || e.metaKey;
    const activeElement = document.activeElement;
    const isInput = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.isContentEditable);

    // Ctrl + K: Open Global Quick Search
    if (isCmdOrCtrl && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (typeof window.openSearch === 'function') {
        window.openSearch();
      } else {
        const searchBtn = document.getElementById('globalSearchBtn') || document.querySelector('[data-search-trigger]');
        if (searchBtn) searchBtn.click();
      }
      return;
    }

    // Ctrl + J: Focus Sabrina Assistant input
    if (isCmdOrCtrl && e.key.toLowerCase() === 'j') {
      e.preventDefault();
      const chatInput = document.getElementById('fabChatInput');
      if (chatInput) {
        chatInput.focus();
        chatInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    // Ctrl + Shift + F: Open Global Search input
    if (isCmdOrCtrl && (e.key.toLowerCase() === 'f' && e.shiftKey)) {
      e.preventDefault();
      const searchBtn = document.getElementById('navSearchBtn') || document.querySelector('[data-bs-target="#globalSearchModal"]');
      if (searchBtn) {
        searchBtn.click();
      }
      return;
    }

    // F1 or Shift+?: Open Shortcuts Help Modal
    if (e.key === 'F1' || (e.key === '?' && !isInput)) {
      e.preventDefault();
      const modalEl = document.getElementById('shortcutsModal');
      if (modalEl && window.bootstrap) {
        const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      }
      return;
    }

    // Ctrl + N: Shortcut to New Sale
    if (isCmdOrCtrl && e.key.toLowerCase() === 'n') {
      e.preventDefault();
      window.location.href = '/operations/sales/new';
      return;
    }

    // F2: Focus Client Selector in active form
    if (e.key === 'F2') {
      e.preventDefault();
      const clientSelector = document.getElementById('clientSelect') 
        || document.getElementById('saleEditClientSelect')
        || document.getElementById('paymentClientSelect')
        || document.getElementById('inputName')
        || document.querySelector('select[name="client_id"]');
      if (clientSelector) {
        clientSelector.focus();
        if (typeof clientSelector.scrollIntoView === 'function') {
          clientSelector.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
      return;
    }

    // Ctrl + S or Ctrl + Enter: Submit the active form directly
    if (isCmdOrCtrl && (e.key === 'Enter' || e.key.toLowerCase() === 's')) {
      const activeForm = document.activeElement?.closest('form') 
        || document.querySelector('form:not([style*="display: none"]):not([hidden])');
      if (activeForm) {
        e.preventDefault();
        const submitBtn = activeForm.querySelector('button[type="submit"], input[type="submit"], .btn-success, .btn-primary');
        if (submitBtn && !submitBtn.disabled) {
          submitBtn.click();
        } else if (typeof activeForm.requestSubmit === 'function') {
          activeForm.requestSubmit();
        }
      }
      return;
    }

    // Number keys 1, 2, 3 on quick_add page to switch category cards
    if (!isInput && ['1', '2', '3'].includes(e.key)) {
      const qaCards = document.querySelectorAll('.qa-card');
      const idx = parseInt(e.key, 10) - 1;
      if (qaCards[idx]) {
        e.preventDefault();
        qaCards[idx].click();
      }
      return;
    }

    // Ctrl + B: Shortcut to Bons Space
    if (isCmdOrCtrl && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      window.location.href = '/bons';
      return;
    }
  });
}
