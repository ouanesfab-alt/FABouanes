// FABOuanes — IndexedDB offline store
// Stores pending operations and reference data cache

const DB_NAME = 'fabouanes-offline';
const DB_VERSION = 1;

let _db = null;

function openDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (e) => {
      const db = e.target.result;

      // File d'attente des opérations à synchroniser
      if (!db.objectStoreNames.contains('pending_ops')) {
        const store = db.createObjectStore('pending_ops', {
          keyPath: 'id',
          autoIncrement: true,
        });
        store.createIndex('by_status', 'status');
        store.createIndex('by_created', 'created_at');
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

/** Ajouter une opération en attente */
export async function queueOperation(type, payload) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('pending_ops', 'readwrite');
    const store = tx.objectStore('pending_ops');
    const uuid = (self.crypto && self.crypto.randomUUID) 
      ? self.crypto.randomUUID() 
      : (Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15));
    const op = {
      uuid,
      type,
      payload,
      status: 'pending',
      created_at: (new Date(Date.now() - new Date().getTimezoneOffset() * 60000)).toISOString(),
      retry_count: 0,
      error: null,
    };
    const req = store.add(op);
    req.onsuccess = () => resolve(req.result);
    req.onerror   = () => reject(req.error);
  });
}

/** Lire toutes les opérations par statut */
export async function getOperationsByStatus(status) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('pending_ops', 'readonly');
    const store = tx.objectStore('pending_ops');
    const index = store.index('by_status');
    const req   = index.getAll(status);
    req.onsuccess = () => resolve(req.result);
    req.onerror   = () => reject(req.error);
  });
}

/** Mettre à jour le statut d'une opération */
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

/** Compter les opérations en attente */
export async function countPending() {
  const ops = await getOperationsByStatus('pending');
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
