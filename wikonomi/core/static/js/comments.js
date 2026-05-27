(function () {
  const root = document.getElementById('wk-comment-section');
  if (!root) return;

  const state = {
    comments: [], cursor: null, sort: 'top', openReplyFormId: null, isLoading: false,
    openMenuId: null, editingCommentId: null, editBody: '', deleteTargetId: null,
    flagTargetId: null, flagReason: 'other', isSubmittingFlag: false, toast: '', errors: {}, focusTarget: null
  };
  const ct = root.dataset.contentType;
  const oid = root.dataset.objectId;
  const isAuthenticated = root.dataset.isAuthenticated === 'true';
  const currentUserId = Number(root.dataset.currentUserId || 0);
  const canPinComments = root.dataset.canPinComments === 'true';

  const csrfToken = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  const headers = { 'Content-Type': 'application/json' };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;
  const esc = (s) => (s || '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m]));
  const api = (path, options = {}) => fetch(`/api/comments/${path}`, { headers, ...options });

  function canEdit(c) { return currentUserId && c.author && c.author.id === currentUserId && !c.is_deleted; }
  function canDelete(c) { return currentUserId && c.author && (c.author.id === currentUserId || root.dataset.isStaff === 'true') && !c.is_deleted; }
  function canPin(c) { return canPinComments && !c.is_deleted; }
  function setError(key, msg) { state.errors[key] = msg; }
  function clearError(key) { delete state.errors[key]; }

  function errHtml(key, inputId) {
    const msg = state.errors[key];
    if (!msg) return { inputAttrs: '', html: '' };
    return { inputAttrs: `aria-invalid="true" aria-describedby="${inputId}-err"`, html: `<p id="${inputId}-err">${esc(msg)}</p>` };
  }

  function render() {
    const sortedComments = [...state.comments].sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned));
    const items = sortedComments.map(renderComment).join('') || '<p class="wk-comments__empty">No comments yet.</p>';
    const composeErr = errHtml('compose', 'compose-input');
    root.classList.add('wk-comments');
    root.innerHTML = `
      <div class="wk-comments__header"><h3>Comments (${state.comments.length})</h3>
      <select data-action="sort"><option value="top" ${state.sort==='top'?'selected':''}>Top</option><option value="newest" ${state.sort==='newest'?'selected':''}>Newest</option><option value="oldest" ${state.sort==='oldest'?'selected':''}>Oldest</option></select></div>
      ${state.toast ? `<div class="wk-comments__toast">${esc(state.toast)}</div>` : ''}
      ${isAuthenticated ? `<div class="wk-comments__compose"><textarea id="compose-input" data-input="compose" ${composeErr.inputAttrs} placeholder="Add a comment..."></textarea>${composeErr.html}<button data-action="compose">Post</button></div>` : ''}
      <div class="wk-comments__list" role="list">${items}</div>
      <div aria-live="polite" aria-atomic="true">${state.toast ? esc(state.toast) : ''}</div>
      ${state.cursor ? '<button class="wk-comments__load-more" data-action="load-more">Load more</button>' : ''}
      ${renderDeleteModal()}
      ${renderFlagModal()}`;
    root.querySelectorAll('.wk-comments__item-body').forEach((n) => { n.textContent = n.textContent || ''; });
    if (state.focusTarget) {
      const el = root.querySelector(state.focusTarget);
      if (el) el.focus();
      state.focusTarget = null;
    }
  }

  function renderComment(c) {
    const showReply = state.openReplyFormId === c.id && isAuthenticated;
    const showMenu = state.openMenuId === c.id;
    const isEditing = state.editingCommentId === c.id;
    const replyErr = errHtml(`reply-${c.id}`, `reply-${c.id}`);
    const editErr = errHtml(`edit-${c.id}`, `edit-${c.id}`);
    return `<article class="wk-comments__item" role="listitem" id="comment-${c.id}" data-id="${c.id}">
      <div class="wk-comments__meta"><strong>${esc(c.author?.username || 'user')}</strong> <span>${esc(c.time_ago || '')}</span> ${c.is_pinned?'<span>📌 Pinned</span>':''}</div>
      ${isEditing ? `<div class="wk-comments__edit"><textarea id="edit-${c.id}" data-input="edit" data-id="${c.id}" ${editErr.inputAttrs}>${esc(state.editBody)}</textarea>${editErr.html}<div><button data-action="save-edit" data-id="${c.id}">Save</button><button data-action="cancel-edit">Cancel</button></div></div>` : `<p class="wk-comments__item-body">${esc(c.body)}</p>`}
      <div class="wk-comments__actions">
        ${isAuthenticated?`<button data-action="reply" data-id="${c.id}">Reply</button>
        <button data-action="like" data-id="${c.id}" data-liked="${c.user_has_liked}" aria-pressed="${c.user_has_liked ? 'true' : 'false'}">${c.user_has_liked ? 'Unlike' : 'Like'} (${c.like_count || 0})</button>`:''}
        <button data-action="more" data-id="${c.id}" aria-haspopup="menu" aria-expanded="${showMenu ? 'true' : 'false'}">More</button>
      </div>
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

  const renderDeleteModal = () => state.deleteTargetId ? `<div class="wk-comments__modal" role="dialog" aria-modal="true"><div class="wk-comments__modal-content"><p>Delete this comment?</p><button data-action="confirm-delete" data-id="${state.deleteTargetId}">Delete</button><button data-action="cancel-delete">Cancel</button></div></div>` : '';
  const renderFlagModal = () => state.flagTargetId ? `<div class="wk-comments__modal" role="dialog" aria-modal="true"><div class="wk-comments__modal-content"><p>Flag comment</p>
    <label><input type="radio" name="flag-reason" value="spam" ${state.flagReason==='spam'?'checked':''}/> Spam</label>
    <label><input type="radio" name="flag-reason" value="harassment" ${state.flagReason==='harassment'?'checked':''}/> Harassment</label>
    <label><input type="radio" name="flag-reason" value="misinformation" ${state.flagReason==='misinformation'?'checked':''}/> Misinformation</label>
    <label><input type="radio" name="flag-reason" value="other" ${state.flagReason==='other'?'checked':''}/> Other</label>
    <button data-action="submit-flag" data-id="${state.flagTargetId}" ${state.isSubmittingFlag?'disabled':''}>${state.isSubmittingFlag?'Submitting...':'Submit'}</button><button data-action="cancel-flag">Cancel</button>
  </div></div>` : '';

  async function loadComments(append = false) {
    if (state.isLoading) return;
    state.isLoading = true;
    try {
      const q = new URLSearchParams({ ct, oid, sort: state.sort });
      if (append && state.cursor) q.set('cursor', state.cursor);
      const res = await api(`?${q.toString()}`); const data = await res.json();
      state.cursor = data.next ? new URL(data.next).searchParams.get('cursor') : null;
      state.comments = append ? state.comments.concat(data.results || []) : (data.results || []);
    } finally { state.isLoading = false; render(); }
  }

  function flashToast(msg) { state.toast = msg; render(); setTimeout(() => { state.toast = ''; render(); }, 2500); }

  root.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]'); if (!btn) return;
    const action = btn.dataset.action; const id = Number(btn.dataset.id);
    if (action === 'load-more') return loadComments(true);
    if (action === 'more') { state.openMenuId = state.openMenuId === id ? null : id; return render(); }
    if (action === 'reply') { state.openReplyFormId = state.openReplyFormId === id ? null : id; if (state.openReplyFormId) state.focusTarget = `[data-input="reply"][data-id="${id}"]`; return render(); }
    if (action === 'compose') { const body = (root.querySelector('[data-input="compose"]')?.value || '').trim(); if (!body) { setError('compose', 'Comment is required.'); return render(); } clearError('compose'); const res = await api('', { method: 'POST', body: JSON.stringify({ content_type: Number(ct), object_id: Number(oid), body }) }); if (res.ok) loadComments(); }
    if (action === 'send-reply') { const body = (root.querySelector(`[data-input="reply"][data-id="${id}"]`)?.value || '').trim(); if (!body) { setError(`reply-${id}`, 'Reply is required.'); return render(); } clearError(`reply-${id}`); const res = await api(`${id}/reply/`, { method: 'POST', body: JSON.stringify({ body }) }); if (res.ok) { state.openReplyFormId = null; loadComments(); } }
    if (action === 'delete') { state.deleteTargetId = id; return render(); }
    if (action === 'cancel-delete') { state.deleteTargetId = null; return render(); }
    if (action === 'confirm-delete') { const res = await api(`${id}/`, { method: 'DELETE' }); if (res.ok) { state.comments = state.comments.map((c) => c.id === id ? { ...c, body: '[deleted]', is_deleted: true } : c); state.deleteTargetId = null; render(); } }
    if (action === 'edit') { const cur = state.comments.find((c) => c.id === id); state.editingCommentId = id; state.editBody = cur?.body || ''; state.focusTarget = `[data-input="edit"][data-id="${id}"]`; return render(); }
    if (action === 'cancel-edit') { state.editingCommentId = null; state.editBody = ''; return render(); }
    if (action === 'save-edit') { const body = (root.querySelector(`[data-input="edit"][data-id="${id}"]`)?.value || '').trim(); if (!body) { setError(`edit-${id}`, 'Edited comment is required.'); return render(); } clearError(`edit-${id}`); const res = await api(`${id}/`, { method: 'PATCH', body: JSON.stringify({ body }) }); if (res.ok) { state.comments = state.comments.map((c) => c.id === id ? { ...c, body, is_edited: true } : c); state.editingCommentId = null; render(); } }
    if (action === 'pin') { const res = await api(`${id}/pin/`, { method: 'POST' }); if (res.ok) loadComments(); }
    if (action === 'flag') { state.flagTargetId = id; state.flagReason = 'other'; return render(); }
    if (action === 'cancel-flag') { state.flagTargetId = null; state.isSubmittingFlag = false; return render(); }
    if (action === 'submit-flag') { if (state.isSubmittingFlag) return; state.isSubmittingFlag = true; render(); const res = await api(`${id}/flag/`, { method: 'POST', body: JSON.stringify({ reason: state.flagReason }) }); state.isSubmittingFlag = false; if (res.ok) { state.flagTargetId = null; flashToast('Comment flagged. Thank you.'); } else render(); }
    if (action === 'copy-link') { await navigator.clipboard?.writeText(`${window.location.href.split('#')[0]}#comment-${id}`); flashToast('Comment link copied.'); }
    if (action === 'like') { const idx = state.comments.findIndex((c) => c.id === id); if (idx < 0) return; const prev = JSON.parse(JSON.stringify(state.comments[idx])); const c = state.comments[idx]; c.user_has_liked = !c.user_has_liked; c.like_count += c.user_has_liked ? 1 : -1; render(); const res = await api(`${id}/like/`, { method: 'POST' }); if (!res.ok) { state.comments[idx] = prev; render(); } }
  });

  root.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    state.deleteTargetId = null;
    state.flagTargetId = null;
    state.openMenuId = null;
    state.openReplyFormId = null;
    if (state.editingCommentId) { state.editingCommentId = null; state.editBody = ''; }
    render();
  });

  root.addEventListener('change', (e) => {
    if (e.target.matches('[data-action="sort"]')) { state.sort = e.target.value; state.cursor = null; loadComments(); }
    if (e.target.name === 'flag-reason') { state.flagReason = e.target.value; }
  });

  loadComments();
})();
