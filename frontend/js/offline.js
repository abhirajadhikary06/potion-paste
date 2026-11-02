/**
 * Offline layer: IndexedDB storage + pending operation queue
 */
const DB_NAME = 'potion-paste';const DB_VERSION = 1;
const STORES = {
  snippets: 'snippets',
  pending: 'pending_ops',
  meta: 'meta',
};

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORES.snippets)) {
        const s = db.createObjectStore(STORES.snippets, { keyPath: 'id' });
        s.createIndex('updated_at', 'updated_at');
      }
      if (!db.objectStoreNames.contains(STORES.pending)) {
        db.createObjectStore(STORES.pending, { keyPath: 'op_id' });
      }
      if (!db.objectStoreNames.contains(STORES.meta)) {
        db.createObjectStore(STORES.meta, { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(store, key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const req = tx.objectStore(store).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbPut(store, value) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    tx.objectStore(store).put(value);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbGetAll(store) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const req = tx.objectStore(store).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function idbDelete(store, key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    tx.objectStore(store).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

function generateOpId() {
  return 'op_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 10);
}

window.PotionOffline = {
  async cacheSnippet(snippet, ownerId) {
    if (!snippet || !snippet.id) return;
    const snippetOwnerId = ownerId || snippet._owner_id || snippet.owner?.id || null;
    const previous = await idbGet(STORES.snippets, snippet.id);
    await idbPut(STORES.snippets, {
      ...previous,
      ...snippet,
      _owner_id: snippetOwnerId,
      _cached_at: new Date().toISOString(),
    });
  },

  async getCachedSnippet(id, ownerId) {
    const snippet = await idbGet(STORES.snippets, id);
    return snippet?._owner_id === ownerId ? snippet : null;
  },

  async getAllCached(ownerId) {
    const snippets = await idbGetAll(STORES.snippets);
    return snippets.filter((snippet) => snippet._owner_id === ownerId);
  },

  async queueOp(op) {
    const ownerId = op.owner_id || null;
    const pending = await idbGetAll(STORES.pending);
    const sameEntity = pending.filter((item) =>
      item._owner_id === ownerId && item.entity_id === op.entity_id && item.entity_type === op.entity_type
    );

    if (op.operation === 'update') {
      const create = sameEntity.find((item) => item.operation === 'create');
      const update = sameEntity.find((item) => item.operation === 'update');
      const existing = create || update;
      if (existing) {
        existing.payload = { ...existing.payload, ...op.payload };
        await idbPut(STORES.pending, existing);
        return existing;
      }
    }

    if (op.operation === 'delete') {
      const create = sameEntity.find((item) => item.operation === 'create');
      if (create) {
        await idbDelete(STORES.pending, create.op_id);
        for (const item of sameEntity) {
          if (item.operation === 'update') await idbDelete(STORES.pending, item.op_id);
        }
        return null;
      }
      for (const item of sameEntity) {
        if (item.operation === 'update') await idbDelete(STORES.pending, item.op_id);
      }
    }

    const record = {
      op_id: op.op_id || generateOpId(),
      entity_type: op.entity_type,
      entity_id: op.entity_id,
      operation: op.operation,
      client_version: op.client_version,
      payload: op.payload,
      _owner_id: ownerId,
      created_at: new Date().toISOString(),
    };
    await idbPut(STORES.pending, record);
    return record;
  },

  async getPendingOps(ownerId) {
    const ops = await idbGetAll(STORES.pending);
    return ops
      .filter((op) => op._owner_id === ownerId)
      .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.op_id.localeCompare(b.op_id));
  },

  async clearOp(opId) {
    await idbDelete(STORES.pending, opId);
  },

  async deleteCachedSnippet(id) {
    await idbDelete(STORES.snippets, id);
  },

  async syncPending(apiPush, ownerId) {
    const ops = await this.getPendingOps(ownerId);
    if (!ops.length) return { results: [] };
    try {
      const res = await apiPush({ operations: ops });
      for (const r of res.results || []) {
        if (r.status === 'applied' || r.status === 'rejected') {
          await this.clearOp(r.op_id);
        }
        if (r.status === 'applied' && r.operation === 'delete') {
          await this.deleteCachedSnippet(r.entity_id);
        }
        if (r.status === 'applied' && r.operation === 'update' && r.server_version) {
          const cached = await idbGet(STORES.snippets, r.entity_id);
          if (cached && cached._owner_id === ownerId) {
            cached.version = r.server_version;
            await idbPut(STORES.snippets, cached);
          }
        }
        // Conflicts stay for user resolution
      }
      return res;
    } catch (e) {
      console.warn('Sync failed, will retry later', e);
      return { results: [], error: e };
    }
  },

  isOnline() {
    return navigator.onLine;
  },
};
