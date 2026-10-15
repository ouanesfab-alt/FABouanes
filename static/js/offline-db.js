// FABOuanes — IndexedDB offline store
// Stores pending operations, conflict queue, and reference data cache

const DB_NAME = 'fabouanes-offline';
const DB_VERSION = 2;

let _db = null;

/** Génère un UUIDv4 conforme */
export function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function openDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (e) => {
      const db = e.target.result;

      // File d'attente des opérations à synchroniser
      let store;
      if (!db.objectStoreNames.contains('pending_ops')) {
        store = db.createObjectStore('pending_ops', {
          keyPath: 'id',
          autoIncrement: true,
        });
      } else {
        store = e.target.transaction.objectStore('pending_ops');
      }

      if (!store.indexNames.contains('by_status')) {
        store.createIndex('by_status', 'status');
      }
      if (!store.indexNames.contains('by_created')) {
        store.createIndex('by_created', 'created_at');
      }
      if (!store.indexNames.contains('by_mutation_id')) {
        store.createIndex('by_mutation_id', 'mutation_id', { unique: false });
      }

      // Cache des données de référence (clients, catalogue)
      if (!db.objectStoreNames.contains('ref_cache')) {
        db.createObjectStore('ref_cache', { keyPath: 'key' });
      }
    };

    req.onsuccess = (e) => { _db = e.target.result; resolve(_db); };
    req.onerror  = () => reject(req.error);
  });
}

/** Ajouter une opération en attente avec mutation_id UUIDv4 */
export async function queueOperation(type, payload) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending_ops', 'readwrite');
    const store = tx.objectStore('pending_ops');
    const mutationId = generateUUID();
    const cleanPayload = payload && typeof payload === 'object' ? { ...payload } : (payload || {});
    cleanPayload.mutation_id = mutationId;

    const op = {
      mutation_id: mutationId,
      uuid: mutationId,
      type,
      payload: cleanPayload,
      status: 'pending',
      created_at: (new Date(Date.now() - new Date().getTimezoneOffset() * 60000)).toISOString(),
      retry_count: 0,
      error: null,
    };
    const req = store.add(op);
    req.onsuccess = () => resolve({ id: req.result, mutation_id: mutationId });
    req.onerror   = () => reject(req.error);
  });
}

/** Lire toutes les opérations par statut ('pending', 'conflict', 'synced', 'failed') */
export async function getOperationsByStatus(status) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('pending_ops', 'readonly');
    const store = tx.objectStore('pending_ops');
    const index = store.index('by_status');
    const req   = index.getAll(status);
    req.onsuccess = () => resolve(req.result || []);
    req.onerror   = () => reject(req.error);
  });
}

/** Lire toutes les opérations en conflit (Dead-Letter Queue pour inspection/résolution) */
export async function getConflictOperations() {
  return await getOperationsByStatus('conflict');
}

/** Mettre à jour le statut et l'erreur éventuelle d'une opération */
export async function updateOperationStatus(id, status, error = null) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('pending_ops', 'readwrite');
    const store = tx.objectStore('pending_ops');
    const get   = store.get(id);
    get.onsuccess = () => {
      const op = get.result;
      if (!op) return resolve();
      op.status      = status;
      op.error       = error;
      op.retry_count = (op.retry_count || 0) + (status === 'failed' ? 1 : 0);
      const put = store.put(op);
      put.onsuccess = () => resolve();
      put.onerror   = () => reject(put.error);
    };
    get.onerror = () => reject(get.error);
  });
}

/** Résoudre un conflit en mettant à jour le payload et en remettant l'opération en attente */
export async function resolveConflict(id, newPayload) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('pending_ops', 'readwrite');
    const store = tx.objectStore('pending_ops');
    const get   = store.get(id);
    get.onsuccess = () => {
      const op = get.result;
      if (!op) return resolve(false);
      op.payload     = newPayload;
      op.status      = 'pending';
      op.error       = null;
      op.retry_count = 0;
      const put = store.put(op);
      put.onsuccess = () => resolve(true);
      put.onerror   = () => reject(put.error);
    };
    get.onerror = () => reject(get.error);
  });
}

/** Supprimer une opération (ex: après abandon volontaire d'un conflit) */
export async function deleteOperation(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('pending_ops', 'readwrite');
    const store = tx.objectStore('pending_ops');
    const req   = store.delete(id);
    req.onsuccess = () => resolve(true);
    req.onerror   = () => reject(req.error);
  });
}

/** Compter les opérations en attente */
export async function countPending() {
  const ops = await getOperationsByStatus('pending');
  return ops.length;
}

/** Compter les opérations en conflit */
export async function countConflicts() {
  const ops = await getConflictOperations();
  return ops.length;
}

/** Sauvegarder des données de référence */
export async function cacheRefData(key, data) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('ref_cache', 'readwrite');
    const store = tx.objectStore('ref_cache');
    const req   = store.put({ key, data, cached_at: (new Date(Date.now() - new Date().getTimezoneOffset() * 60000)).toISOString() });
    req.onsuccess = () => resolve();
    req.onerror   = () => reject(req.error);
  });
}

/** Lire des données de référence */
export async function getRefData(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('ref_cache', 'readonly');
    const store = tx.objectStore('ref_cache');
    const req   = store.get(key);
    req.onsuccess = () => resolve(req.result ? req.result.data : null);
    req.onerror   = () => reject(req.error);
  });
}
