// FABOuanes — Gestionnaire de synchronisation hors-ligne
// Tourne dans la page (pas dans le Service Worker)

import {
  getOperationsByStatus,
  updateOperationStatus,
  countPending,
  cacheRefData,
} from './offline-db.js';

const SYNC_ENDPOINT = '/api/mobile/v1/offline/sync';

/** Met à jour le badge dans la navbar */
async function updatePendingBadge() {
  const count = await countPending();
  const badge = document.getElementById('offline-pending-badge');
  if (!badge) return;
  badge.textContent = count > 0 ? String(count) : '';
  badge.hidden      = count === 0;
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
  cacheReferenceData();

  window.addEventListener('online', async () => {
    showSyncToast('Connexion rétablie — synchronisation en cours…', 'info');
    await syncPendingOperations();
    await cacheReferenceData();
  });

  // Sync périodique toutes les 2 minutes si en ligne
  setInterval(async () => {
    if (navigator.onLine) await syncPendingOperations();
  }, 120_000);
}
