(function () {
  const root = document.getElementById('wk-comment-section');
  if (!root) return;

  const state = {
    comments: [], cursor: null, sort: 'top', openReplyFormId: null, isLoading: false,
    isInitialLoading: true, isLoadingMore: false, openMenuId: null, editingCommentId: null, editBody: '',
    deleteTargetId: null, flagTargetId: null, flagReason: 'other', isSubmittingFlag: false,
    toast: '', errors: {}, focusTarget: null
  };
  const ct = root.dataset.contentType;
  const oid = root.dataset.objectId;
  const isAuthenticated = root.dataset.isAuthenticated === 'true';
  const currentUserId = Number(root.dataset.currentUserId || 0);
  const canPinComments = root.dataset.canPinComments === 'true';
  const isInfiniteScroll = root.dataset.infiniteScroll === 'true';

  const csrfToken = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  const headers = { 'Content-Type': 'application/json' };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;
  const esc = (s) => (s || '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m]));
  const api = (path, options = {}) => fetch(`/api/comments/${path}`, { headers, ...options });
  let infiniteObserver = null;
  const repliesCache = new Map();

  function canEdit(c) { return currentUserId && c.author && c.author.id === currentUserId && !c.is_deleted; }
  function canDelete(c) { return currentUserId && c.author && (c.author.id === currentUserId || root.dataset.isStaff === 'true') && !c.is_deleted; }
  function canPin(c) { return canPinComments && !c.is_deleted; }
  function setError(key, msg) { state.errors[key] = msg; }
  function clearError(key) { delete state.errors[key]; }

  function formatRelativeTime(dateStr) {
    const secs = Math.max(0, Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000));
    if (secs < 60) return 'just now';
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
    if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
    return `${Math.floor(secs / 86400)}d ago`;
  }

  function errHtml(key, inputId) {
    const msg = state.errors[key];
    if (!msg) return { inputAttrs: '', html: '' };
    return { inputAttrs: `aria-invalid="true" aria-describedby="${inputId}-err"`, html: `<p id="${inputId}-err">${esc(msg)}</p>` };
  }

  function renderSkeletonRows(n = 3) {
    return Array.from({ length: n }).map(() => `
      <article class="wk-comments__item wk-comments__item--skeleton" aria-hidden="true">
        <div class="wk-comments__meta"><span class="wk-skeleton wk-skeleton--avatar"></span><span class="wk-skeleton wk-skeleton--line"></span></div>
        <p class="wk-skeleton wk-skeleton--block"></p>
      </article>
    `).join('');
  }

  function render() {
    const sortedComments = [...state.comments].sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned));
    const items = state.isInitialLoading ? renderSkeletonRows(4) : (sortedComments.map(renderComment).join('') || '<p class="wk-comments__empty">No comments yet.</p>');
    const composeErr = errHtml('compose', 'compose-input');
    root.classList.add('wk-comments');
    root.innerHTML = `
      <div class="wk-comments__header"><h3>Comments (${state.comments.length})</h3>
      <select data-action="sort"><option value="top" ${state.sort==='top'?'selected':''}>Top</option><option value="newest" ${state.sort==='newest'?'selected':''}>Newest</option><option value="oldest" ${state.sort==='oldest'?'selected':''}>Oldest</option></select></div>
      ${state.toast ? `<div class="wk-comments__toast">${esc(state.toast)}</div>` : ''}
      ${isAuthenticated ? `<div class="wk-comments__compose"><textarea id="compose-input" data-input="compose" ${composeErr.inputAttrs} placeholder="Add a comment..."></textarea>${composeErr.html}<button data-action="compose">Post</button></div>` : ''}
      <div class="wk-comments__list" role="list">${items}</div>
      <div aria-live="polite" aria-atomic="true">${state.toast ? esc(state.toast) : ''}</div>
      ${state.isLoadingMore ? `<div class="wk-comments__pagination-skeleton">${renderSkeletonRows(2)}</div>` : ''}
      ${(state.cursor && !isInfiniteScroll) ? '<button class="wk-comments__load-more" data-action="load-more">Load more</button>' : ''}
      ${(state.cursor && isInfiniteScroll) ? '<div class="wk-comments__sentinel" data-role="scroll-sentinel"></div>' : ''}
      ${renderDeleteModal()}
      ${renderFlagModal()}`;
    if (state.focusTarget) {
      const el = root.querySelector(state.focusTarget);
      if (el) el.focus();
      state.focusTarget = null;
    }
    attachInfiniteObserver();
  }

  function renderComment(c) {
    const showReply = state.openReplyFormId === c.id && isAuthenticated;
    const showMenu = state.openMenuId === c.id;
    const isEditing = state.editingCommentId === c.id;
    const replyErr = errHtml(`reply-${c.id}`, `reply-${c.id}`);
    const editErr = errHtml(`edit-${c.id}`, `edit-${c.id}`);
    const replies = repliesCache.get(c.id) || { expanded: false, items: [], cursor: null, isLoading: false, isLoadingMore: false };
    return `<article class="wk-comments__item" role="listitem" id="comment-${c.id}" data-id="${c.id}">
      <div class="wk-comments__meta"><img class="wk-comments__avatar" src="${esc(c.author?.profile_picture || '/static/img/default_avatar.png')}" alt="" loading="lazy"/><strong>${esc(c.author?.username || 'user')}</strong> <span data-created-at="${esc(c.created_at || '')}">${esc(formatRelativeTime(c.created_at || new Date().toISOString()))}</span> ${c.is_pinned?'<span>📌 Pinned</span>':''}</div>
      ${isEditing ? `<div class="wk-comments__edit"><textarea id="edit-${c.id}" data-input="edit" data-id="${c.id}" ${editErr.inputAttrs}>${esc(state.editBody)}</textarea>${editErr.html}<div><button data-action="save-edit" data-id="${c.id}">Save</button><button data-action="cancel-edit">Cancel</button></div></div>` : `<p class="wk-comments__item-body">${esc(c.body)}</p>`}
      <div class="wk-comments__actions">
        ${isAuthenticated?`<button data-action="reply" data-id="${c.id}">Reply</button>
        <button data-action="like" data-id="${c.id}" data-liked="${c.user_has_liked}" aria-pressed="${c.user_has_liked ? 'true' : 'false'}">${c.user_has_liked ? 'Unlike' : 'Like'} (${c.like_count || 0})</button>`:''}
        ${c.reply_count ? `<button data-action="toggle-replies" data-id="${c.id}">${replies.expanded ? 'Hide replies' : `View replies (${c.reply_count})`}</button>` : ''}
        <button data-action="more" data-id="${c.id}" aria-haspopup="menu" aria-expanded="${showMenu ? 'true' : 'false'}">More</button>
      </div>
      ${replies.expanded ? renderReplies(c.id, replies) : ''}
      ${showMenu ? `<div class="wk-comments__menu" role="menu">
        <button data-action="copy-link" data-id="${c.id}">Copy link</button>
        ${isAuthenticated ? `<button data-action="flag" data-id="${c.id}">Flag</button>` : ''}
        ${canEdit(c) ? `<button data-action="edit" data-id="${c.id}">Edit</button>` : ''}
        ${canDelete(c) ? `<button data-action="delete" data-id="${c.id}">Delete</button>` : ''}
        ${canPin(c) ? `<button data-action="pin" data-id="${c.id}">${c.is_pinned ? 'Unpin' : 'Pin'}</button>` : ''}
      </div>` : ''}
      ${showReply ? `<div class="wk-comments__reply"><textarea id="reply-${c.id}" data-input="reply" data-id="${c.id}" ${replyErr.inputAttrs}>@${esc(c.author?.username || '')} </textarea>${replyErr.html}<button data-action="send-reply" data-id="${c.id}">Send</button></div>`:''}
    </article>`;
  }

  function renderReplies(parentId, replies) {
    const rows = replies.isLoading ? renderSkeletonRows(1) : replies.items.map((r) => `<div class="wk-comments__reply-item"><img class="wk-comments__avatar wk-comments__avatar--sm" src="${esc(r.author?.profile_picture || '/static/img/default_avatar.png')}" alt="" loading="lazy"/><strong>${esc(r.author?.username || 'user')}</strong> <span data-created-at="${esc(r.created_at || '')}">${esc(formatRelativeTime(r.created_at || new Date().toISOString()))}</span><p>${esc(r.body)}</p></div>`).join('');
    return `<div class="wk-comments__replies">${rows}${replies.isLoadingMore ? '<div class="wk-comments__mini-skeleton wk-skeleton wk-skeleton--line"></div>' : ''}${replies.cursor ? `<button data-action="load-more-replies" data-id="${parentId}">Load more replies</button>` : ''}</div>`;
  }

  async function loadComments(append = false) {
    if (state.isLoading) return;
    state.isLoading = true;
    state.isInitialLoading = !append && state.comments.length === 0;
    state.isLoadingMore = append;
    render();
    try {
      const q = new URLSearchParams({ ct, oid, sort: state.sort });
      if (append && state.cursor) q.set('cursor', state.cursor);
      const res = await api(`?${q.toString()}`); const data = await res.json();
      state.cursor = data.next ? new URL(data.next).searchParams.get('cursor') : null;
      state.comments = append ? state.comments.concat(data.results || []) : (data.results || []);
    } finally { state.isLoading = false; state.isInitialLoading = false; state.isLoadingMore = false; render(); }
  }

  async function loadReplies(parentId, append = false) {
    const current = repliesCache.get(parentId) || { expanded: true, items: [], cursor: null, isLoading: false, isLoadingMore: false };
    if ((append && !current.cursor) || current.isLoading || current.isLoadingMore) return;
    current.isLoading = !append;
    current.isLoadingMore = append;
    repliesCache.set(parentId, current);
    render();
    const url = append && current.cursor ? `${parentId}/replies/?cursor=${encodeURIComponent(current.cursor)}` : `${parentId}/replies/`;
    const res = await api(url);
    const data = await res.json();
    current.cursor = data.next ? new URL(data.next).searchParams.get('cursor') : null;
    current.items = append ? current.items.concat(data.results || []) : (data.results || []);
    current.isLoading = false;
    current.isLoadingMore = false;
    repliesCache.set(parentId, current);
    render();
  }

  function attachInfiniteObserver() {
    if (!isInfiniteScroll) return;
    if (infiniteObserver) infiniteObserver.disconnect();
    const sentinel = root.querySelector('[data-role="scroll-sentinel"]');
    if (!sentinel) return;
    infiniteObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && state.cursor && !state.isLoading) loadComments(true);
      });
    }, { rootMargin: '200px' });
    infiniteObserver.observe(sentinel);
  }

  function flashToast(msg) { state.toast = msg; render(); setTimeout(() => { state.toast = ''; render(); }, 2500); }

  root.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]'); if (!btn) return;
    const action = btn.dataset.action; const id = Number(btn.dataset.id);
    if (action === 'load-more') return loadComments(true);
    if (action === 'toggle-replies') {
      const current = repliesCache.get(id) || { expanded: false, items: [], cursor: null, isLoading: false, isLoadingMore: false };
      current.expanded = !current.expanded;
      repliesCache.set(id, current);
      render();
      if (current.expanded && current.items.length === 0) loadReplies(id, false);
      return;
    }
    if (action === 'load-more-replies') return loadReplies(id, true);
    if (action === 'more') { state.openMenuId = state.openMenuId === id ? null : id; return render(); }
    if (action === 'reply') { state.openReplyFormId = state.openReplyFormId === id ? null : id; if (state.openReplyFormId) state.focusTarget = `[data-input="reply"][data-id="${id}"]`; return render(); }
    if (action === 'compose') { const body = (root.querySelector('[data-input="compose"]')?.value || '').trim(); if (!body) { setError('compose', 'Comment is required.'); return render(); } clearError('compose'); const res = await api('', { method: 'POST', body: JSON.stringify({ content_type: Number(ct), object_id: Number(oid), body }) }); if (res.ok) { root.querySelector('[data-input="compose"]').value = ''; loadComments(); } else { flashToast('Failed to save comment.'); } }
    if (action === 'send-reply') { const body = (root.querySelector(`[data-input="reply"][data-id="${id}"]`)?.value || '').trim(); if (!body) { setError(`reply-${id}`, 'Reply is required.'); return render(); } clearError(`reply-${id}`); const res = await api(`${id}/reply/`, { method: 'POST', body: JSON.stringify({ body }) }); if (res.ok) { state.openReplyFormId = null; loadComments(); } else { flashToast('Failed to save reply.'); } }
  });

  root.addEventListener('change', (e) => {
    if (e.target.matches('[data-action="sort"]')) { state.sort = e.target.value; state.cursor = null; loadComments(); }
  });

  setInterval(() => {
    root.querySelectorAll('[data-created-at]').forEach((el) => {
      const createdAt = el.getAttribute('data-created-at');
      if (createdAt) el.textContent = formatRelativeTime(createdAt);
    });
  }, 60000);

  loadComments();
})();
