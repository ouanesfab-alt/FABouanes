// FABOuanes — Gestionnaire de synchronisation hors-ligne
// Tourne dans la page (pas dans le Service Worker)

import {
  getOperationsByStatus,
  updateOperationStatus,
  countPending,
  cacheRefData,
} from './offline-db.js';

const SYNC_ENDPOINT = '/api/mobile/v1/offline/sync';

/** Met à jour le badge dans la navbar (desktop et mobile) */
async function updatePendingBadge() {
  const count = await countPending();
  const badges = document.querySelectorAll('#offline-pending-badge, .offline-pending-badge, #mobile-offline-pending-badge');
  badges.forEach(badge => {
    badge.textContent = count > 0 ? String(count) : '';
    badge.hidden = count === 0;
  });
  await updateNetworkPillUI();
}

/** Met à jour la pilule réseau interactive dans la navbar */
export async function updateNetworkPillUI() {
  const pill = document.getElementById('navNetworkStatus');
  if (!pill) return;
  const dot = document.getElementById('networkPillDot');
  const icon = document.getElementById('networkPillIcon');
  const label = document.getElementById('networkPillLabel');

  const online = navigator.onLine;
  let count = 0;
  try {
    count = await countPending();
  } catch (e) {}

  // Ne pas écraser l'affichage si une synchronisation manuelle est active
  if (pill.classList.contains('is-syncing')) return;

  pill.classList.remove('is-offline', 'is-pending', 'is-online', 'is-success');

  if (!online) {
    pill.classList.add('is-offline');
    if (dot) dot.classList.add('d-none');
    if (icon) {
      icon.className = 'bi bi-wifi-off network-pill-icon';
      icon.classList.remove('d-none', 'spinning');
    }
    if (label) label.textContent = count > 0 ? `${count} (Hors-ligne)` : 'Hors-ligne';
    pill.setAttribute('title', `Mode hors-ligne${count > 0 ? ` — ${count} opération(s) en attente locale` : ''}`);
    return;
  }

  if (count > 0) {
    pill.classList.add('is-pending');
    if (dot) dot.classList.add('d-none');
    if (icon) {
      icon.className = 'bi bi-arrow-repeat network-pill-icon';
      icon.classList.remove('d-none', 'spinning');
    }
    if (label) label.textContent = `${count} en attente`;
    pill.setAttribute('title', `${count} opération(s) en attente — Cliquer pour synchroniser`);
    return;
  }

  // En ligne et synchronisé
  pill.classList.add('is-online');
  if (dot) dot.classList.remove('d-none');
  if (icon) icon.classList.add('d-none');
  if (label) label.textContent = 'En ligne';
  pill.setAttribute('title', 'Connecté au réseau — Données synchronisées');
}

/** Synchronise toutes les opérations en attente */
export async function syncPendingOperations() {
  if (!navigator.onLine) return { synced: 0, failed: 0 };

  const pending = await getOperationsByStatus('pending');
  if (pending.length === 0) return { synced: 0, failed: 0 };

  let synced = 0;
  let failed = 0;

  for (const op of pending) {
    try {
      // Clé d'idempotence unique et reproductible pour éviter les doublons sur retry
      const idempotencyKey = `fab-${op.uuid || (op.id + '-' + Date.parse(op.created_at || new Date().toISOString()))}`;
      // Récupère le token CSRF depuis la meta tag
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const res = await fetch(SYNC_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
          'X-Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify({ type: op.type, payload: op.payload }),
      });

      if (res.ok) {
        await updateOperationStatus(op.id, 'synced');
        synced++;
      } else {
        const err = await res.text();
        await updateOperationStatus(op.id, op.retry_count >= 3 ? 'failed' : 'pending', err);
        failed++;
      }
    } catch (e) {
      await updateOperationStatus(op.id, 'pending', e.message);
      failed++;
    }
  }

  await updatePendingBadge();

  if (synced > 0) showSyncToast(`${synced} opération(s) synchronisée(s) ✓`);
  if (failed > 0) showSyncToast(`${failed} opération(s) en erreur`, 'warning');

  return { synced, failed };
}

/** Met en cache les données de référence (clients, catalogue) */
export async function cacheReferenceData() {
  if (!navigator.onLine) return;
  // Ne pas tenter de mettre en cache si l'utilisateur n'est pas connecté (évite les erreurs 401 dans la console)
  if (document.body && document.body.classList.contains('auth-page')) return;
  try {
    const opts = { credentials: 'include' };
    const [clientsRes, catalogRes, suppliersRes, rawMaterialsRes] = await Promise.all([
      fetch('/api/v1/clients?limit=500', opts),
      fetch('/api/v1/sellable-items', opts),
      fetch('/api/v1/suppliers?limit=500', opts),
      fetch('/api/v1/raw-materials?limit=500', opts),
    ]);
    // Silently abort if not authenticated (user not logged in yet)
    if ([clientsRes, catalogRes, suppliersRes, rawMaterialsRes]
        .some(r => r.status === 401 || r.status === 403)) return;

    if (clientsRes.ok) {
      const data = await clientsRes.json();
      await cacheRefData('clients', data.data || data);
    }
    if (catalogRes.ok) {
      const data = await catalogRes.json();
      await cacheRefData('catalog', data.data || data);
    }
    if (suppliersRes.ok) {
      const data = await suppliersRes.json();
      await cacheRefData('suppliers', data.data || data);
    }
    if (rawMaterialsRes.ok) {
      const data = await rawMaterialsRes.json();
      await cacheRefData('raw_materials', data.data || data);
    }
  } catch (e) {
    console.warn('[FAB offline] Impossible de mettre en cache les données de référence :', e);
  }
}

function showSyncToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `alert alert-${type} position-fixed bottom-0 end-0 m-3`;
  toast.style.cssText = 'z-index:9999;font-size:13px;max-width:320px;pointer-events:none';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

/** Initialise la synchronisation et les listeners réseau */
export function initOfflineSync() {
  updatePendingBadge();
  updateNetworkPillUI();
  cacheReferenceData();

  window.syncPendingOperations = syncPendingOperations;
  window.updateNetworkPillUI = updateNetworkPillUI;

  // Clic interactif sur la pilule de statut
  const pill = document.getElementById('navNetworkStatus');
  if (pill && !pill.dataset.bound) {
    pill.dataset.bound = '1';
    pill.addEventListener('click', async (e) => {
      e.preventDefault();
      if (pill.classList.contains('is-syncing')) return;

      if (!navigator.onLine) {
        showSyncToast('Connexion internet requise pour synchroniser.', 'warning');
        if (navigator.vibrate) navigator.vibrate(30);
        return;
      }

      const dot = document.getElementById('networkPillDot');
      const icon = document.getElementById('networkPillIcon');
      const label = document.getElementById('networkPillLabel');

      pill.classList.add('is-syncing');
      if (dot) dot.classList.add('d-none');
      if (icon) {
        icon.className = 'bi bi-arrow-repeat network-pill-icon spinning';
        icon.classList.remove('d-none');
      }
      if (label) label.textContent = 'Synchronisation…';
      pill.setAttribute('title', 'Synchronisation en cours…');

      const res = await syncPendingOperations();

      pill.classList.remove('is-syncing');
      if (res.failed === 0) {
        pill.classList.add('is-success');
        if (icon) {
          icon.className = 'bi bi-check2 network-pill-icon';
          icon.classList.remove('d-none', 'spinning');
        }
        if (label) label.textContent = res.synced > 0 ? 'Synchronisé !' : 'À jour ✓';
        pill.setAttribute('title', 'Toutes les données sont synchronisées');
        setTimeout(() => {
          updateNetworkPillUI();
        }, 2200);
      } else {
        await updateNetworkPillUI();
      }
    });
  }

  window.addEventListener('online', async () => {
    updateNetworkPillUI();
    showSyncToast('Connexion rétablie — synchronisation en cours…', 'info');
    await syncPendingOperations();
    await cacheReferenceData();
    updateNetworkPillUI();
  });

  window.addEventListener('offline', () => {
    updateNetworkPillUI();
  });

  // Sync périodique toutes les 2 minutes si en ligne
  setInterval(async () => {
    if (navigator.onLine) {
      await syncPendingOperations();
      updateNetworkPillUI();
    }
  }, 120_000);
}

