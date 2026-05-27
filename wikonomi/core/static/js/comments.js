(function () {
  const root = document.getElementById('wk-comment-section');
  if (!root) return;

  const state = { comments: [], cursor: null, sort: 'top', openReplyFormId: null, isLoading: false, isSubmitting: false };
  const ct = root.dataset.contentType;
  const oid = root.dataset.objectId;
  const isAuthenticated = root.dataset.isAuthenticated === 'true';
  const currentUserId = Number(root.dataset.currentUserId || 0);

  const csrfToken = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  const headers = { 'Content-Type': 'application/json' };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  const esc = (s) => (s || '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m]));
  const api = (path, options = {}) => fetch(`/api/comments/${path}`, { headers, ...options });

  function render() {
    const items = state.comments.map(renderComment).join('') || '<p class="wk-comments__empty">No comments yet.</p>';
    root.classList.add('wk-comments');
    root.innerHTML = `
      <div class="wk-comments__header"><h3>Comments (${state.comments.length})</h3>
      <select data-action="sort"><option value="top" ${state.sort==='top'?'selected':''}>Top</option><option value="newest" ${state.sort==='newest'?'selected':''}>Newest</option><option value="oldest" ${state.sort==='oldest'?'selected':''}>Oldest</option></select></div>
      ${isAuthenticated ? `<div class="wk-comments__compose"><textarea data-input="compose" placeholder="Add a comment..."></textarea><button data-action="compose">Post</button></div>` : ''}
      <div class="wk-comments__list">${items}</div>
      ${state.cursor ? '<button class="wk-comments__load-more" data-action="load-more">Load more</button>' : ''}`;
  }

  function renderComment(c) {
    const showReply = state.openReplyFormId === c.id && isAuthenticated;
    const canEdit = currentUserId && c.author && c.author.id === currentUserId;
    return `<article class="wk-comments__item" data-id="${c.id}">
      <div class="wk-comments__meta"><strong>${esc(c.author?.username || 'user')}</strong> <span>${esc(c.time_ago || '')}</span> ${c.is_pinned?'<span>📌</span>':''}</div>
      <p>${esc(c.body)}</p>
      <div class="wk-comments__actions">
        ${isAuthenticated?`<button data-action="reply" data-id="${c.id}" data-username="${esc(c.author?.username || '')}">Reply</button>
        <button data-action="like" data-id="${c.id}" data-liked="${c.user_has_liked}">${c.user_has_liked ? 'Unlike' : 'Like'} (${c.like_count || 0})</button>
        <button data-action="flag" data-id="${c.id}">Flag</button>`:''}
        <button data-action="copy-link" data-id="${c.id}">Copy link</button>
        ${canEdit?`<button data-action="edit" data-id="${c.id}">Edit</button><button data-action="delete" data-id="${c.id}">Delete</button>`:''}
        ${isAuthenticated?`<button data-action="pin" data-id="${c.id}">${c.is_pinned?'Unpin':'Pin'}</button>`:''}
      </div>
      ${showReply ? `<div class="wk-comments__reply"><textarea data-input="reply" data-id="${c.id}">@${esc(c.author?.username || '')} </textarea><button data-action="send-reply" data-id="${c.id}">Send</button></div>`:''}
    </article>`;
  }

  async function loadComments(append = false) {
    if (state.isLoading) return;
    state.isLoading = true;
    try {
      const q = new URLSearchParams({ ct, oid, sort: state.sort });
      if (append && state.cursor) q.set('cursor', state.cursor);
      const res = await api(`?${q.toString()}`);
      const data = await res.json();
      state.cursor = data.next ? new URL(data.next).searchParams.get('cursor') : null;
      state.comments = append ? state.comments.concat(data.results || []) : (data.results || []);
    } finally { state.isLoading = false; render(); }
  }

  root.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]'); if (!btn) return;
    const action = btn.dataset.action; const id = Number(btn.dataset.id);
    if (action === 'load-more') return loadComments(true);
    if (action === 'reply') { state.openReplyFormId = state.openReplyFormId === id ? null : id; return render(); }
    if (action === 'compose') {
      const body = (root.querySelector('[data-input="compose"]')?.value || '').trim(); if (!body) return;
      const res = await api('', { method: 'POST', body: JSON.stringify({ content_type: Number(ct), object_id: Number(oid), body }) });
      if (res.ok) loadComments();
    }
    if (action === 'send-reply') {
      const body = (root.querySelector(`[data-input="reply"][data-id="${id}"]`)?.value || '').trim(); if (!body) return;
      const res = await api(`${id}/reply/`, { method: 'POST', body: JSON.stringify({ body }) });
      if (res.ok) { state.openReplyFormId = null; loadComments(); }
    }
    if (action === 'delete') { const res = await api(`${id}/`, { method: 'DELETE' }); if (res.ok) loadComments(); }
    if (action === 'edit') {
      const cur = state.comments.find((c) => c.id === id); const body = window.prompt('Edit comment', cur?.body || ''); if (!body) return;
      const res = await api(`${id}/`, { method: 'PATCH', body: JSON.stringify({ body }) }); if (res.ok) loadComments();
    }
    if (action === 'pin') { const res = await api(`${id}/pin/`, { method: 'POST' }); if (res.ok) loadComments(); }
    if (action === 'flag') { await api(`${id}/flag/`, { method: 'POST', body: JSON.stringify({ reason: 'other' }) }); }
    if (action === 'copy-link') { navigator.clipboard?.writeText(`${window.location.href.split('#')[0]}#comment-${id}`); }
    if (action === 'like') {
      const idx = state.comments.findIndex((c) => c.id === id); if (idx < 0) return;
      const prev = JSON.parse(JSON.stringify(state.comments[idx]));
      const c = state.comments[idx];
      c.user_has_liked = !c.user_has_liked; c.like_count += c.user_has_liked ? 1 : -1; render();
      const res = await api(`${id}/like/`, { method: 'POST' });
      if (!res.ok) { state.comments[idx] = prev; render(); }
    }
  });

  root.addEventListener('change', (e) => {
    if (e.target.matches('[data-action="sort"]')) { state.sort = e.target.value; state.cursor = null; loadComments(); }
  });

  loadComments();
})();
