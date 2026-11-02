/**
 * Potion Paste — main application logic
 */
(function () {
  'use strict';

  const API = '/api';
  let currentUser = null;
  let currentSnippet = null;
  let csrfToken = null;
  let socket = null;
  let saveTimer = null;
  let isDirty = false;
  let shareToken = null;
  let sharePermissions = { can_comment: false, can_edit: false };

  // ---------- Helpers ----------
  function toast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    document.getElementById('toasts').appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  async function api(path, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };
    if (shareToken) headers['X-Share-Token'] = shareToken;
    if (csrfToken && options.method && options.method !== 'GET') {
      headers['X-CSRFToken'] = csrfToken;
    }
    const res = await fetch(API + path, {
      credentials: 'include',
      ...options,
      headers,
    });
    if (res.status === 401) {
      showAuth();
      throw new Error('Unauthorized');
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.message || data.error || 'Request failed');
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  async function fetchCsrf() {
    try {
      const data = await api('/csrf-token');
      csrfToken = data.csrf_token;
    } catch (_) {}
  }

  // ---------- Auth ----------
  function showAuth() {
    document.getElementById('authScreen').classList.remove('hidden');
    document.getElementById('appShell').classList.add('hidden');
  }

  function hideAuth() {
    document.getElementById('authScreen').classList.add('hidden');
    document.getElementById('appShell').classList.remove('hidden');
  }

  async function checkAuth() {
    const shareMatch = location.pathname.match(/^\/share\/([^/]+)\/?$/);
    if (shareMatch) {
      shareToken = new URLSearchParams(location.hash.slice(1)).get('token')
        || new URLSearchParams(location.search).get('token');
      try {
        await fetchCsrf();
        try {
          currentUser = (await api('/auth/me')).user;
        } catch (_) {
          currentUser = null;
        }
        const data = await api(`/share/${encodeURIComponent(shareMatch[1])}`);
        currentSnippet = data.snippet;
        sharePermissions = data.permissions || sharePermissions;
        hideAuth();
        document.getElementById('sidebar').classList.add('hidden');
        document.querySelector('.app-header .search').classList.add('hidden');
        document.querySelector('.app-header .header-actions').classList.add('hidden');
        document.getElementById('commentsPanel').classList.add('open');
        document.getElementById('commentForm').classList.add('hidden');
        PotionEditor.setup(document.getElementById('codeInput'), document.getElementById('lineNumbers'));
        showEditor(currentSnippet);
        document.getElementById('snippetTitle').readOnly = true;
        document.getElementById('languageSelect').disabled = true;
        document.getElementById('codeInput').readOnly = true;
        ['visibilityToggle', 'shareBtn', 'saveBtn', 'deleteBtn'].forEach((id) => {
          document.getElementById(id).classList.add('hidden');
        });
        loadComments(currentSnippet.id);
      } catch (err) {
        showAuth();
        const loginError = document.getElementById('loginError');
        loginError.textContent = err.data?.message || 'This share link is invalid or expired';
        loginError.classList.remove('hidden');
      }
      return;
    }
    try {
      await fetchCsrf();
      const data = await api('/auth/me');
      currentUser = data.user;
      hideAuth();
      initApp();
    } catch {
      showAuth();
    }
  }

  document.getElementById('showRegister').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('loginCard').classList.add('hidden');
    document.getElementById('registerCard').classList.remove('hidden');
  });
  document.getElementById('showLogin').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('registerCard').classList.add('hidden');
    document.getElementById('loginCard').classList.remove('hidden');
  });

  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('loginError');
    errEl.classList.add('hidden');
    try {
      const data = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: document.getElementById('loginEmail').value.trim(),
          password: document.getElementById('loginPassword').value,
        }),
      });
      currentUser = data.user;
      await fetchCsrf();
      hideAuth();
      initApp();
      toast('Welcome back!');
    } catch (err) {
      errEl.textContent = err.data?.message || 'Login failed';
      errEl.classList.remove('hidden');
    }
  });

  document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('regError');
    errEl.classList.add('hidden');
    try {
      const data = await api('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username: document.getElementById('regUsername').value.trim(),
          email: document.getElementById('regEmail').value.trim(),
          password: document.getElementById('regPassword').value,
        }),
      });
      currentUser = data.user;
      await fetchCsrf();
      hideAuth();
      initApp();
      toast('Account created!');
    } catch (err) {
      errEl.textContent = err.data?.message || 'Registration failed';
      errEl.classList.remove('hidden');
    }
  });

  // ---------- Snippets ----------
  async function loadSnippets(q = '') {
    const list = document.getElementById('snippetList');
    try {
      if (!navigator.onLine) {
        const cached = await PotionOffline.getAllCached(currentUser?.id);
        renderSnippetList(cached);
        return;
      }
      const data = await api(`/snippets?q=${encodeURIComponent(q)}&per_page=50`);
      renderSnippetList(data.snippets);
      // Cache
      for (const s of data.snippets) {
        PotionOffline.cacheSnippet(s, currentUser?.id);
      }
    } catch (err) {
      // Fallback to cache
      const cached = await PotionOffline.getAllCached(currentUser?.id);
      if (cached.length) {
        renderSnippetList(cached);
        toast('Showing offline cache', 'error');
      } else {
        list.innerHTML = `<div class="empty-state"><p>Could not load snippets</p></div>`;
      }
    }
  }

  function renderSnippetList(snippets) {
    const list = document.getElementById('snippetList');
    if (!snippets.length) {
      list.innerHTML = `
        <div class="empty-state" style="padding:32px 16px">
          <div class="icon">📄</div>
          <h3 style="font-size:14px">No snippets yet</h3>
          <p style="font-size:12px">Create your first one</p>
        </div>`;
      return;
    }
    list.innerHTML = snippets.map(s => `
      <div class="snippet-item ${currentSnippet?.id === s.id ? 'active' : ''}" data-id="${s.id}">
        <div class="title">${escapeHtml(s.title || 'Untitled')}</div>
        <div class="meta">
          <span class="lang-tag">${escapeHtml(s.language)}</span>
          ${s.is_private ? '<span class="lock-icon">🔒</span>' : '<span>🔗</span>'}
          <span>${formatRelative(s.updated_at)}</span>
        </div>
      </div>
    `).join('');
    list.querySelectorAll('.snippet-item').forEach(el => {
      el.addEventListener('click', () => openSnippet(el.dataset.id));
    });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatRelative(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h';
    return d.toLocaleDateString();
  }

  async function openSnippet(id) {
    if (isDirty && !confirm('Discard your unsaved changes?')) return;
    try {
      let data;
      if (!navigator.onLine) {
        const cached = await PotionOffline.getCachedSnippet(id, currentUser?.id);
        if (!cached) throw new Error('Not available offline');
        data = { snippet: cached };
      } else {
        data = await api(`/snippets/${id}`);
        PotionOffline.cacheSnippet(data.snippet, currentUser?.id);
      }
      currentSnippet = data.snippet;
      isDirty = false;
      showEditor(currentSnippet);
      loadComments(id);
      // Join socket room
      if (socket) socket.emit('join_snippet', { snippet_id: id });
      // Update list active state
      document.querySelectorAll('.snippet-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === id);
      });
    } catch (err) {
      toast(err.message || 'Failed to load snippet', 'error');
    }
  }

  function showEditor(s) {
    document.getElementById('emptyEditor').classList.add('hidden');
    const view = document.getElementById('editorView');
    view.classList.remove('hidden');
    view.style.display = 'flex';

    document.getElementById('snippetTitle').value = s.title || '';
    document.getElementById('languageSelect').value = s.language || 'plaintext';
    document.getElementById('codeInput').value = s.code || '';
    document.getElementById('versionText').textContent = `v${s.version || 1}`;
    document.getElementById('updatedText').textContent = s.updated_at
      ? `Updated ${formatRelative(s.updated_at)}`
      : '';
    document.getElementById('statusText').textContent = 'Ready';

    const vis = document.getElementById('visibilityToggle');
    const label = document.getElementById('visibilityLabel');
    if (s.is_private) {
      vis.classList.add('private');
      label.textContent = 'Private';
    } else {
      vis.classList.remove('private');
      label.textContent = 'Shared';
    }

    PotionEditor.updateLineNumbers(
      document.getElementById('codeInput'),
      document.getElementById('lineNumbers')
    );
  }

  async function saveSnippet() {
    if (!currentSnippet || shareToken) return;
    const payload = {
      title: document.getElementById('snippetTitle').value.trim() || 'Untitled',
      language: document.getElementById('languageSelect').value,
      code: document.getElementById('codeInput').value,
      is_private: document.getElementById('visibilityToggle').classList.contains('private'),
    };

    document.getElementById('statusText').textContent = 'Saving…';
    document.getElementById('saveBtn').disabled = true;

    try {
      if (!navigator.onLine) {
        // Queue offline
        await PotionOffline.queueOp({
          entity_type: 'snippet',
          entity_id: currentSnippet.id,
          operation: 'update',
          client_version: currentSnippet.version,
          payload,
          owner_id: currentUser?.id,
        });
        // Optimistic local update
        Object.assign(currentSnippet, payload);
        currentSnippet.updated_at = new Date().toISOString();
        await PotionOffline.cacheSnippet(currentSnippet);
        isDirty = false;
        document.getElementById('statusText').textContent = 'Saved offline';
        toast('Saved offline — will sync later');
        loadSnippets();
        return;
      }

      const data = await api(`/snippets/${currentSnippet.id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      currentSnippet = data.snippet;
      isDirty = false;
      document.getElementById('statusText').textContent = 'Saved';
      document.getElementById('versionText').textContent = `v${currentSnippet.version}`;
      document.getElementById('updatedText').textContent = `Updated ${formatRelative(currentSnippet.updated_at)}`;
      PotionOffline.cacheSnippet(currentSnippet, currentUser?.id);
      toast('Saved');
      loadSnippets();
    } catch (err) {
      document.getElementById('statusText').textContent = 'Error';
      toast(err.data?.message || 'Save failed', 'error');
    } finally {
      document.getElementById('saveBtn').disabled = false;
    }
  }

  async function createSnippet() {
    if (isDirty && !confirm('Discard your unsaved changes?')) return;
    try {
      if (!navigator.onLine) {
        const id = 'local_' + Date.now().toString(36);
        const sn = {
          id,
          title: 'Untitled',
          language: 'plaintext',
          code: '',
          is_private: true,
          version: 1,
          updated_at: new Date().toISOString(),
        };
        await PotionOffline.queueOp({
          entity_type: 'snippet',
          entity_id: id,
          operation: 'create',
          payload: sn,
          owner_id: currentUser?.id,
        });
        await PotionOffline.cacheSnippet({ ...sn, _owner_id: currentUser?.id });
        currentSnippet = sn;
        showEditor(sn);
        loadSnippets();
        toast('Created offline');
        return;
      }
      const data = await api('/snippets', {
        method: 'POST',
        body: JSON.stringify({
          title: 'Untitled',
          language: 'plaintext',
          code: '',
          is_private: true,
        }),
      });
      currentSnippet = data.snippet;
      showEditor(currentSnippet);
      loadSnippets();
      toast('Snippet created');
    } catch (err) {
      toast(err.data?.message || 'Create failed', 'error');
    }
  }

  async function deleteSnippet() {
    if (!currentSnippet || shareToken) return;
    if (!confirm('Delete this snippet permanently?')) return;
    try {
      if (!navigator.onLine) {
        await PotionOffline.queueOp({
          entity_type: 'snippet',
          entity_id: currentSnippet.id,
          operation: 'delete',
          client_version: currentSnippet.version,
          owner_id: currentUser?.id,
        });
        await PotionOffline.deleteCachedSnippet(currentSnippet.id);
        toast('Queued for deletion');
      } else {
        await api(`/snippets/${currentSnippet.id}`, { method: 'DELETE' });
        await PotionOffline.deleteCachedSnippet(currentSnippet.id);
        toast('Deleted');
      }
      currentSnippet = null;
      document.getElementById('editorView').classList.add('hidden');
      document.getElementById('emptyEditor').classList.remove('hidden');
      loadSnippets();
    } catch (err) {
      toast('Delete failed', 'error');
    }
  }

  // ---------- Comments ----------
  async function loadComments(snippetId) {
    const list = document.getElementById('commentsList');
    const form = document.getElementById('commentForm');
    if (currentUser && (!shareToken || sharePermissions.can_comment)) form.classList.remove('hidden');
    else form.classList.add('hidden');
    try {
      const data = await api(`/snippets/${snippetId}/comments`);
      if (!data.comments.length) {
        list.innerHTML = `<p style="font-size:13px;color:var(--text-muted);text-align:center;padding:24px">No comments yet</p>`;
        return;
      }
      list.innerHTML = data.comments.map(c => `
        <div class="comment" data-id="${c.id}">
          <div class="comment-author">
            <span>${escapeHtml(c.author?.display_name || c.author?.username || 'User')}</span>
            <span class="comment-time">${formatRelative(c.created_at)}</span>
          </div>
          <div class="comment-body">${escapeHtml(c.body)}</div>
        </div>
      `).join('');
    } catch {
      list.innerHTML = `<p style="font-size:13px;color:var(--text-muted);text-align:center;padding:24px">Comments unavailable offline</p>`;
    }
  }

  async function postComment() {
    if (!currentSnippet) return;
    const body = document.getElementById('commentBody').value.trim();
    if (!body) return;
    try {
      await api(`/snippets/${currentSnippet.id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body }),
      });
      document.getElementById('commentBody').value = '';
      loadComments(currentSnippet.id);
      toast('Comment posted');
    } catch (err) {
      toast(err.data?.message || 'Failed to post', 'error');
    }
  }

  // ---------- Share ----------
  document.getElementById('shareBtn').addEventListener('click', () => {
    if (!currentSnippet) return;
    const modal = document.getElementById('shareModal');
    document.getElementById('shareLinkInput').value = '';
    modal.classList.add('open');
  });

  document.getElementById('generateShareBtn').addEventListener('click', async () => {
    if (!currentSnippet) return;
    try {
      const data = await api(`/snippets/${currentSnippet.id}/share`, {
        method: 'POST',
        body: JSON.stringify({
          can_comment: document.getElementById('shareCanComment').checked,
        }),
      });
      const url = location.origin + (data.url || `/share/${data.share_id}`);
      document.getElementById('shareLinkInput').value = url;
      toast('Share link ready');
    } catch (err) {
      toast('Could not create share link', 'error');
    }
  });

  document.getElementById('copyShareLink').addEventListener('click', async () => {
    const input = document.getElementById('shareLinkInput');
    await PotionEditor.copyToClipboard(input.value);
    toast('Link copied');
  });

  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.remove('open'));
    });
  });

  // ---------- Events ----------
  document.getElementById('newSnippetBtn').addEventListener('click', createSnippet);
  document.getElementById('emptyNewBtn').addEventListener('click', createSnippet);
  document.getElementById('saveBtn').addEventListener('click', saveSnippet);
  document.getElementById('deleteBtn').addEventListener('click', deleteSnippet);
  document.getElementById('postCommentBtn').addEventListener('click', postComment);
  document.getElementById('refreshList').addEventListener('click', () => loadSnippets());
  document.getElementById('logoutBtn').addEventListener('click', async () => {
    try {
      await api('/auth/logout', { method: 'POST' });
      currentUser = null;
      location.assign('/app');
    } catch (err) {
      toast('Could not sign out', 'error');
    }
  });
  document.getElementById('copyBtn').addEventListener('click', async () => {
    const code = document.getElementById('codeInput').value;
    await PotionEditor.copyToClipboard(code);
    toast('Code copied');
  });

  document.getElementById('visibilityToggle').addEventListener('click', () => {
    const el = document.getElementById('visibilityToggle');
    el.classList.toggle('private');
    document.getElementById('visibilityLabel').textContent =
      el.classList.contains('private') ? 'Private' : 'Shared';
    isDirty = true;
  });

  document.getElementById('codeInput').addEventListener('input', () => {
    isDirty = true;
    document.getElementById('statusText').textContent = 'Unsaved changes';
    clearTimeout(saveTimer);
    // Optional auto-save debounce
    // saveTimer = setTimeout(saveSnippet, 2500);
  });
  document.getElementById('snippetTitle').addEventListener('input', () => {
    isDirty = true;
  });
  document.getElementById('languageSelect').addEventListener('change', () => {
    isDirty = true;
    document.getElementById('statusText').textContent = 'Unsaved changes';
  });

  document.getElementById('searchInput').addEventListener('input', (e) => {
    clearTimeout(window._searchT);
    window._searchT = setTimeout(() => loadSnippets(e.target.value), 300);
  });

  document.getElementById('toggleComments').addEventListener('click', () => {
    document.getElementById('commentsPanel').classList.toggle('open');
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      saveSnippet();
    }
  });

  // Offline / online
  function updateOnlineStatus() {
    const banner = document.getElementById('offlineBanner');
    if (navigator.onLine) {
      banner.classList.remove('show');
      // Attempt sync
      PotionOffline.syncPending(
        (body) => api('/sync/push', { method: 'POST', body: JSON.stringify(body) }),
        currentUser?.id
      ).then((res) => {
        if (res.results?.length) {
          toast(`Synced ${res.results.filter(r => r.status === 'applied').length} changes`);
          loadSnippets();
        }
      });
    } else {
      banner.classList.add('show');
    }
  }
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);

  // Socket
  function initSocket() {
    if (typeof io === 'undefined') return;
    socket = io({ withCredentials: true });
    socket.on('connect', () => console.log('WS connected'));
    socket.on('snippet:updated', (payload) => {
      if (currentSnippet && payload.id === currentSnippet.id) {
        // Don't overwrite local dirty state
        if (!isDirty) {
          currentSnippet = payload;
          showEditor(payload);
          toast('Snippet updated by another session');
        }
      }
      loadSnippets();
    });
    socket.on('comment:created', (payload) => {
      if (currentSnippet && document.getElementById('commentsList')) {
        loadComments(currentSnippet.id);
      }
    });
  }

  function initApp() {
    if (currentUser) {
      document.getElementById('userName').textContent = currentUser.display_name || currentUser.username;
      document.getElementById('userAvatar').textContent = (currentUser.display_name || currentUser.username || '?')[0].toUpperCase();
    }
    PotionEditor.setup(
      document.getElementById('codeInput'),
      document.getElementById('lineNumbers')
    );
    loadSnippets();
    initSocket();
    updateOnlineStatus();

    // PWA install prompt handling can go here
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  }

  // Boot
  checkAuth();
})();
