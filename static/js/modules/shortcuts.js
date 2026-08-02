// FABOuanes ERP — Shortcuts Module (Windows Desktop & Web Keybindings)

export function initShortcutsModule() {
  document.addEventListener('keydown', (e) => {
    // Only handle if Ctrl or Cmd key is pressed or F-keys
    const isCmdOrCtrl = e.ctrlKey || e.metaKey;
    const activeElement = document.activeElement;
    const isInput = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.isContentEditable);

    // Ctrl + K: Focus Sabrina Assistant input
    if (isCmdOrCtrl && e.key.toLowerCase() === 'k') {
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
      window.location.href = '/sales/new';
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
