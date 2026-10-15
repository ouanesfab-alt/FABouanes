// FABOuanes — Gestionnaire de synchronisation hors-ligne
// Tourne dans la page (pas dans le Service Worker)

import {
  getOperationsByStatus,
  getConflictOperations,
  updateOperationStatus,
  countPending,
  countConflicts,
  cacheRefData,
} from './offline-db.js';

const SYNC_ENDPOINT = '/api/mobile/v1/offline/sync';
const BULK_SYNC_ENDPOINT = '/api/mobile/v1/offline/sync/bulk';

/** Met à jour le badge dans la navbar (desktop et mobile) */
async function updatePendingBadge() {
  const count = await countPending();
  const conflictCount = await countConflicts();
  const badges = document.querySelectorAll('#offline-pending-badge, .offline-pending-badge, #mobile-offline-pending-badge');
  badges.forEach(badge => {
    const total = count + conflictCount;
    badge.textContent = total > 0 ? String(total) : '';
    badge.hidden = total === 0;
    if (conflictCount > 0) {
      badge.classList.remove('bg-warning');
      badge.classList.add('bg-danger');
      badge.setAttribute('title', `${count} en attente, ${conflictCount} en conflit`);
    } else {
      badge.classList.remove('bg-danger');
      badge.classList.add('bg-warning');
      badge.removeAttribute('title');
    }
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
  let conflicts = 0;
  try {
    count = await countPending();
    conflicts = await countConflicts();
  } catch (e) {}

  // Ne pas écraser l'affichage si une synchronisation manuelle est active
  if (pill.classList.contains('is-syncing')) return;

  pill.classList.remove('is-offline', 'is-pending', 'is-online', 'is-success', 'is-conflict');

  if (!online) {
    pill.classList.add('is-offline');
    if (dot) dot.classList.add('d-none');
    if (icon) {
      icon.className = 'bi bi-wifi-off network-pill-icon';
      icon.classList.remove('d-none', 'spinning');
    }
    const total = count + conflicts;
    if (label) label.textContent = total > 0 ? `${total} (Hors-ligne)` : 'Hors-ligne';
    pill.setAttribute('title', `Mode hors-ligne${total > 0 ? ` — ${total} opération(s) locale(s)` : ''}`);
    return;
  }

  if (conflicts > 0) {
    pill.classList.add('is-conflict');
    if (dot) dot.classList.add('d-none');
    if (icon) {
      icon.className = 'bi bi-exclamation-triangle-fill network-pill-icon text-danger';
      icon.classList.remove('d-none', 'spinning');
    }
    if (label) label.textContent = `${conflicts} conflit(s)`;
    pill.setAttribute('title', `${conflicts} conflit(s) hors-ligne requérant votre attention — Cliquer pour examiner`);
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

/** Synchronise toutes les opérations en attente avec isolation Dead-Letter Queue */
export async function syncPendingOperations() {
  if (!navigator.onLine) return { synced: 0, failed: 0, conflicts: 0 };

  const pending = await getOperationsByStatus('pending');
  if (pending.length === 0) return { synced: 0, failed: 0, conflicts: 0 };

  let synced = 0;
  let failed = 0;
  let conflicts = 0;

  for (const op of pending) {
    try {
      const mutationId = op.mutation_id || op.uuid || `fab-${op.id}-${Date.now()}`;
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const payloadWithId = {
        ...(op.payload || {}),
        mutation_id: mutationId,
      };

      const res = await fetch(SYNC_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
          'X-Idempotency-Key': mutationId,
        },
        body: JSON.stringify({
          mutation_id: mutationId,
          type: op.type,
          payload: payloadWithId,
        }),
      });

      if (res.ok) {
        await updateOperationStatus(op.id, 'synced');
        synced++;
      } else {
        const rawText = await res.text();
        let reason = rawText;
        let isConflict = res.status === 409 || res.status === 422;

        try {
          const json = JSON.parse(rawText);
          if (json.status === 'conflict') isConflict = true;
          reason = json.reason || json.error || json.detail || rawText;
        } catch (_) {}

        if (isConflict) {
          // Dead-Letter Queue : marque en 'conflict' dans IndexedDB sans bloquer les suivantes
          await updateOperationStatus(op.id, 'conflict', reason);
          conflicts++;
        } else {
          await updateOperationStatus(op.id, op.retry_count >= 3 ? 'failed' : 'pending', reason);
          failed++;
        }
      }
    } catch (e) {
      await updateOperationStatus(op.id, 'pending', e.message);
      failed++;
    }
  }

  await updatePendingBadge();

  if (synced > 0) showSyncToast(`${synced} opération(s) synchronisée(s) ✓`);
  if (conflicts > 0) showSyncToast(`${conflicts} opération(s) en conflit (à vérifier)`, 'danger');
  if (failed > 0) showSyncToast(`${failed} opération(s) en échec réseau`, 'warning');

  return { synced, failed, conflicts };
}

/** Synchronise un lot d'opérations via le endpoint bulk avec isolation DLQ */
export async function syncOperationsBulk(operations) {
  if (!navigator.onLine || !operations || operations.length === 0) {
    return { results: [] };
  }

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const opsPayload = operations.map(op => ({
    mutation_id: op.mutation_id || op.uuid,
    idempotency_key: op.mutation_id || op.uuid,
    type: op.type,
    payload: {
      ...(op.payload || {}),
      mutation_id: op.mutation_id || op.uuid,
    },
  }));

  try {
    const res = await fetch(BULK_SYNC_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
      },
      body: JSON.stringify({ operations: opsPayload }),
    });

    if (!res.ok) {
      return { error: await res.text() };
    }

    const data = await res.json();
    const results = data.results || [];

    for (let i = 0; i < operations.length; i++) {
      const op = operations[i];
      const match = results.find(r => r.mutation_id === (op.mutation_id || op.uuid)) || results[i];
      if (!match) continue;

      if (match.status === 'conflict' || match.status_code === 422 || match.status_code === 409) {
        const reason = match.error || match.response?.reason || 'Conflit de validation';
        await updateOperationStatus(op.id, 'conflict', reason);
      } else if (match.status === 'synced' || match.status_code === 200) {
        await updateOperationStatus(op.id, 'synced');
      } else if (match.status_code >= 500) {
        await updateOperationStatus(op.id, op.retry_count >= 3 ? 'failed' : 'pending', match.error);
      }
    }

    await updatePendingBadge();
    return data;
  } catch (err) {
    console.error('Erreur lors du bulk sync :', err);
    throw err;
  }
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

