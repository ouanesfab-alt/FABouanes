import { initThemeModule } from './modules/theme.js';
import { initApiModule } from './modules/api.js';
import { initLayoutModule, openInvoice } from './modules/layout.js';
import { initFormsModule } from './modules/forms.js';
import { initTablesModule } from './modules/tables.js';
import { initNotificationsModule } from './modules/notifications.js';
import { initContextMenuModule } from './modules/contextMenu.js';
import { initMobileShellModule } from './modules/mobileShell.js';
import { initOfflineSync } from './offline-sync.js';
import { initRippleModule } from './modules/ripple.js';
import { initAudioModule } from './modules/audio.js';
import { initShortcutsModule } from './modules/shortcuts.js';
import { initInstantNavModule } from './modules/instantNav.js';

// Bind functions to window for backward compatibility with inline HTML events
window.openInvoice = openInvoice;

// Initialize all modules in correct dependency order
initThemeModule();
initApiModule();
initLayoutModule();
initFormsModule();
initTablesModule();
initNotificationsModule();
initContextMenuModule();
initMobileShellModule();
// Active la synchronisation hors-ligne (IndexedDB → /api/mobile/v1/offline/sync)
initOfflineSync();
// Ripple effect sur tous les boutons
initRippleModule();
// Sons de clics et retours sonores PWA
initAudioModule();
// Raccourcis clavier optimisés pour Windows Desktop (Ctrl+K, Ctrl+N, Ctrl+B, etc.)
initShortcutsModule();
// Navigation SPA Turbo Instantanée (Zéro rechargement complet de page, basculement ultra-rapide)
initInstantNavModule();

// Auto-reinitialization on SPA PJAX page transitions
document.addEventListener('fab:page-loaded', () => {
  initLayoutModule();
  initFormsModule();
  initTablesModule();
  initContextMenuModule();
  initRippleModule();
});



