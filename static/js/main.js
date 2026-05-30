import { initThemeModule } from './modules/theme.js';
import { initApiModule } from './modules/api.js';
import { initLayoutModule, openInvoice } from './modules/layout.js';
import { initFormsModule } from './modules/forms.js';
import { initTablesModule } from './modules/tables.js';
import { initNotificationsModule } from './modules/notifications.js';
import { initContextMenuModule } from './modules/contextMenu.js';
import { initMobileShellModule } from './modules/mobileShell.js';

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
