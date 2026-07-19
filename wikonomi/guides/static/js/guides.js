document.addEventListener('DOMContentLoaded', function () {
    initGuideRating();
    initTips();
    initStepEditor();
    initGuidePhotoPreview();
    initGuideDraft();
    initGuideActions();
    initGuideQuestions();
    initGuideDeletion();
});

function initGuidePhotoPreview() {
    const input = document.querySelector('[data-guide-photo-input]');
    const preview = document.querySelector('[data-guide-photo-preview]');
    const empty = document.querySelector('[data-guide-photo-empty]');
    const change = document.querySelector('[data-guide-photo-change]');
    if (!input || !preview) return;
    if (preview.getAttribute('src')) change?.classList.remove('hidden');
    input.addEventListener('change', function () {
        const file = input.files && input.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) { input.value = ''; return; }
        preview.src = URL.createObjectURL(file);
        preview.classList.remove('hidden');
        empty?.classList.add('hidden');
        change?.classList.remove('hidden');
    });
}

function initGuideDraft() {
    const form = document.getElementById('guide-editor-form');
    const key = form?.dataset.guideDraftKey;
    if (!form || !key) return;
    const status = document.querySelector('[data-draft-status]');
    let timer;
    try {
        const saved = JSON.parse(localStorage.getItem(key) || 'null');
        if (saved) {
            ['title', 'summary', 'organization_name', 'category_name', 'edit_summary'].forEach((name) => {
                const field = form.elements[name];
                if (field && saved[name] !== undefined) field.value = saved[name];
            });
            if (Array.isArray(saved.steps)) restoreDraftSteps(saved.steps);
            if (status) status.textContent = 'Your saved draft has been restored.';
        }
    } catch (_) { /* Browsers may block local storage. The form still works normally. */ }

    form.addEventListener('input', function () {
        clearTimeout(timer);
        if (status) status.textContent = 'Saving draft…';
        timer = setTimeout(() => {
            const draft = {};
            ['title', 'summary', 'organization_name', 'category_name', 'edit_summary'].forEach((name) => {
                const field = form.elements[name];
                if (field) draft[name] = field.value;
            });
            draft.steps = Array.from(form.querySelectorAll('[data-step-row]')).map((row) => ({
                title: row.querySelector('[data-step-title]')?.value || '',
                instruction: row.querySelector('[data-step-instruction]')?.value || '',
            }));
            try { localStorage.setItem(key, JSON.stringify(draft)); if (status) status.textContent = 'Draft saved on this device.'; } catch (_) {}
        }, 500);
    });
    form.addEventListener('submit', () => { try { localStorage.removeItem(key); } catch (_) {} });
}

function restoreDraftSteps(steps) {
    const editor = document.querySelector('[data-steps-editor]');
    const template = document.getElementById('step-row-template');
    if (!editor || !template || !steps.length) return;
    editor.innerHTML = '';
    steps.forEach((step) => {
        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector('[data-step-row]');
        row.querySelector('[data-step-title]').value = step.title || '';
        row.querySelector('[data-step-instruction]').value = step.instruction || '';
        editor.appendChild(fragment);
    });
    renumberSteps(editor);
}

function initGuideRating() {
    const widget = document.querySelector('[data-rating-widget][data-rating-target="guide"] [data-rating-value]')?.closest('[data-rating-widget]');
    if (!widget) return;
    widget.addEventListener('click', async function (event) {
        const button = event.target.closest('[data-rating-value]');
        if (!button) return;
        try {
            const response = await fetch(`/guides/${window.WIKONOMI_GUIDE_SLUG}/rate/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
                body: JSON.stringify({score: button.dataset.ratingValue}),
            });
            if (response.status === 401 || response.status === 403) {
                showToast('Please log in to rate this guide', 'info');
                window.location.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`;
                return;
            }
            if (!response.ok) throw new Error('Rating request failed');
            const data = await response.json();
            document.querySelectorAll('[data-rating-widget][data-rating-target="guide"] [data-rating-value]').forEach((star) => {
                const filled = Number(star.dataset.ratingValue) <= Number(data.score);
                star.classList.toggle('text-amber-400', filled);
                star.classList.toggle('text-gray-300', !filled);
                star.setAttribute('aria-pressed', filled ? 'true' : 'false');
            });
            document.querySelectorAll('[data-rating-score]').forEach((el) => { el.textContent = Number(data.average_score || 0).toFixed(1); });
            document.querySelectorAll('[data-rating-count]').forEach((el) => { el.textContent = `(${data.rating_count} ratings)`; });
            showToast('Rating saved', 'success');
        } catch (err) { console.error(err); showToast('Could not save your rating', 'error'); }
    });
}

function initTips() {
    const slug = window.WIKONOMI_GUIDE_SLUG;
    const modal = document.querySelector('[data-tip-modal]');
    const form = document.querySelector('[data-tip-modal-form]');
    const stepInput = document.querySelector('[data-tip-step-id]');
    const bodyInput = document.querySelector('[data-tip-body]');
    const photoInput = document.querySelector('[data-tip-photo-input]');
    const previewWrap = document.querySelector('[data-tip-preview-wrap]');
    const preview = document.querySelector('[data-tip-preview]');
    const error = document.querySelector('[data-tip-error]');
    const submitButton = document.querySelector('[data-tip-submit]');

    function openModal(stepId) {
        if (!modal || !form) return;
        resetModal(false);
        stepInput.value = stepId;
        modal.classList.remove('hidden');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('overflow-hidden');
        setTimeout(() => bodyInput.focus(), 0);
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('overflow-hidden');
        resetModal(true);
    }

    function resetModal(clearStep) {
        if (!form) return;
        form.reset();
        if (clearStep && stepInput) stepInput.value = '';
        if (preview) preview.src = '';
        if (previewWrap) previewWrap.classList.add('hidden');
        if (error) { error.textContent = ''; error.classList.add('hidden'); }
        if (submitButton) { submitButton.disabled = false; submitButton.textContent = 'Post Tip'; }
    }

    function showFormError(message) {
        if (!error) return;
        error.textContent = message;
        error.classList.remove('hidden');
    }

    document.addEventListener('click', async function (event) {
        const toggle = event.target.closest('[data-add-tip]');
        if (toggle) openModal(toggle.dataset.stepId);
        if (event.target.closest('[data-tip-modal-close]')) closeModal();
        const voteBtn = event.target.closest('[data-tip-vote]');
        if (voteBtn) voteTip(slug, voteBtn);
        const editBtn = event.target.closest('[data-edit-tip]');
        if (editBtn) editTip(slug, editBtn.closest('[data-tip-id]'));
        const deleteBtn = event.target.closest('[data-delete-tip]');
        if (deleteBtn) deleteTip(slug, deleteBtn.closest('[data-tip-id]'));
        const expandBtn = event.target.closest('[data-expand-tips]');
        if (expandBtn) expandTips(slug, expandBtn);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && modal && !modal.classList.contains('hidden')) closeModal();
    });

    if (photoInput) {
        photoInput.addEventListener('change', function () {
            const file = photoInput.files && photoInput.files[0];
            if (!file) { if (previewWrap) previewWrap.classList.add('hidden'); return; }
            if (!file.type.startsWith('image/')) { showFormError('Please choose an image file.'); photoInput.value = ''; return; }
            if (preview) preview.src = URL.createObjectURL(file);
            if (previewWrap) previewWrap.classList.remove('hidden');
        });
    }

    if (form) {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            const stepId = stepInput.value;
            const body = bodyInput.value.trim();
            if (!stepId) { showFormError('Choose a step before posting a tip.'); return; }
            if (!body) { showFormError('Write a tip before posting.'); return; }
            const formData = new FormData();
            formData.append('body', body);
            if (photoInput.files && photoInput.files[0]) formData.append('photos', photoInput.files[0]);
            try {
                submitButton.disabled = true;
                submitButton.textContent = 'Posting...';
                const response = await fetch(`/guides/${slug}/steps/${stepId}/tips/`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
                    body: formData,
                });
                const data = await response.json().catch(() => ({}));
                if (response.status === 401 || response.status === 403) { window.location.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`; return; }
                if (!response.ok) throw new Error(data.error || firstFormError(data.errors) || 'Failed to add tip');
                const tipList = document.querySelector(`[data-step-tips][data-step-id="${stepId}"]`);
                if (tipList) tipList.appendChild(buildTipElement(data));
                closeModal();
                showToast('Tip added', 'success');
            } catch (err) {
                console.error(err);
                showFormError(err.message || 'Could not add your tip');
                showToast('Could not add your tip', 'error');
                if (submitButton) { submitButton.disabled = false; submitButton.textContent = 'Post Tip'; }
            }
        });
    }
}

function firstFormError(errors) {
    if (!errors) return '';
    const firstKey = Object.keys(errors)[0];
    if (!firstKey) return '';
    const value = errors[firstKey];
    if (Array.isArray(value)) {
        const firstValue = value[0];
        return firstValue && firstValue.message ? firstValue.message : String(firstValue);
    }
    return value && value.message ? value.message : String(value);
}


function buildTipElement(tip) {
    const div = document.createElement('article');
    div.className = 'tip-card';
    div.dataset.tipId = tip.id;
    const photos = (tip.photos || []).map((photo) => `<a href="${escapeHtml(photo.url)}" target="_blank"><img src="${escapeHtml(photo.url)}" alt="Tip photo" class="h-10 w-10 rounded object-cover border border-amber-200"></a>`).join('');
    const edit = tip.can_edit ? '<button type="button" data-edit-tip class="font-bold text-brand-purple hover:underline">Edit</button>' : '';
    const remove = tip.can_delete ? '<button type="button" data-delete-tip class="font-bold text-red-500 hover:underline">Delete</button>' : '';
    div.innerHTML = `<div class="tip-votes"><button type="button" data-tip-vote data-vote-value="1" aria-label="Upvote tip" class="tip-vote-button ${tip.user_vote === 1 ? 'is-active-up' : ''}">▲</button><span data-tip-score>${Number(tip.score || 0)}</span><button type="button" data-tip-vote data-vote-value="-1" aria-label="Downvote tip" class="tip-vote-button ${tip.user_vote === -1 ? 'is-active-down' : ''}">▼</button></div><div class="min-w-0 flex-1"><p class="text-sm leading-5 text-slate-700" data-tip-body-text>${escapeHtml(tip.body)}</p>${photos ? `<div class="mt-2 flex gap-2">${photos}</div>` : ''}<div class="mt-2 flex items-center gap-3 text-xs text-slate-400"><span>Tip by <strong class="text-slate-600">@${escapeHtml(tip.username || 'deleted-user')}</strong></span>${edit}${remove}</div></div>`;
    return div;
}

async function voteTip(slug, button) {
    try {
        const card = button.closest('[data-tip-id]');
        const response = await fetch(`/guides/${slug}/steps/tips/${card.dataset.tipId}/vote/`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}, body: JSON.stringify({value: Number(button.dataset.voteValue)})});
        if (response.status === 401 || response.status === 403) { window.location.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`; return; }
        if (!response.ok) throw new Error('Vote failed');
        const data = await response.json();
        card.querySelector('[data-tip-score]').textContent = data.score;
        card.querySelectorAll('[data-tip-vote]').forEach((btn) => {
            const value = Number(btn.dataset.voteValue);
            btn.classList.toggle('is-active-up', data.user_vote === 1 && value === 1);
            btn.classList.toggle('is-active-down', data.user_vote === -1 && value === -1);
        });
        sortTipCards(card.parentElement);
    } catch (err) { console.error(err); showToast('Could not register your vote', 'error'); }
}

async function editTip(slug, card) {
    const bodyElement = card.querySelector('[data-tip-body-text]');
    const nextBody = window.prompt('Edit your tip', bodyElement.textContent.trim());
    if (nextBody === null || !nextBody.trim()) return;
    try {
        const response = await fetch(`/guides/${slug}/steps/tips/${card.dataset.tipId}/edit/`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}, body: JSON.stringify({body: nextBody.trim()})});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || firstFormError(data.errors) || 'Could not edit tip');
        bodyElement.textContent = data.body;
        showToast('Tip updated', 'success');
    } catch (err) { showToast(err.message, 'error'); }
}

async function deleteTip(slug, card) {
    if (!card || !window.confirm('Delete this tip permanently?')) return;
    try {
        const response = await fetch(`/guides/${slug}/steps/tips/${card.dataset.tipId}/delete/`, {
            method: 'POST',
            headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || 'Could not delete tip');
        card.remove();
        showToast('Tip deleted', 'success');
    } catch (err) { showToast(err.message, 'error'); }
}

async function expandTips(slug, button) {
    button.disabled = true;
    const label = button.querySelector('span');
    if (label) label.textContent = 'Loading tips…';
    try {
        const response = await fetch(`/guides/${slug}/steps/${button.dataset.stepId}/tips/list/?offset=5`, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
        if (!response.ok) throw new Error('Could not load tips');
        const data = await response.json();
        const list = document.querySelector(`[data-step-tips][data-step-id="${button.dataset.stepId}"]`);
        data.tips.forEach((tip) => list.appendChild(buildTipElement(tip)));
        button.remove();
    } catch (err) { button.disabled = false; if (label) label.textContent = 'Try loading tips again'; showToast(err.message, 'error'); }
}

function sortTipCards(list) {
    if (!list) return;
    [...list.querySelectorAll(':scope > [data-tip-id]')]
        .sort((a, b) => Number(b.querySelector('[data-tip-score]').textContent) - Number(a.querySelector('[data-tip-score]').textContent))
        .forEach((card) => list.appendChild(card));
}

function initGuideActions() {
    const root = document.querySelector('[data-guide-actions]');
    if (!root) return;
    const toggle = root.querySelector('[data-guide-action-toggle]');
    const menu = root.querySelector('[data-guide-action-menu]');
    const closeMenu = () => { menu.classList.add('hidden'); toggle.setAttribute('aria-expanded', 'false'); toggle.textContent = '+'; };
    toggle.addEventListener('click', (event) => { event.stopPropagation(); const opening = menu.classList.contains('hidden'); menu.classList.toggle('hidden', !opening); toggle.setAttribute('aria-expanded', String(opening)); toggle.textContent = opening ? '×' : '+'; });
    document.addEventListener('click', (event) => { if (!root.contains(event.target)) closeMenu(); });
    document.addEventListener('click', (event) => {
        const rating = event.target.closest('[data-open-rating]');
        const fork = event.target.closest('[data-open-fork]');
        const share = event.target.closest('[data-share-guide]');
        if (rating) openGuidePopover(document.querySelector('[data-rating-popover]'));
        if (fork) openGuidePopover(document.querySelector('[data-fork-popover]'));
        if (share) sharePriceReport(event, {title: share.dataset.title, text: buildGuideShareText(share.dataset.title), url: window.location.href});
        if (rating || fork || share) closeMenu();
        if (event.target.closest('[data-close-popover]')) closeGuidePopovers();
    });
    const forkForm = document.querySelector('[data-fork-form]');
    forkForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submit = forkForm.querySelector('[data-fork-submit]');
        const error = forkForm.querySelector('[data-fork-error]');
        submit.disabled = true; submit.textContent = 'Copying…'; error.classList.add('hidden');
        try {
            const response = await fetch(forkForm.action, {method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}, body: new FormData(forkForm)});
            if (response.redirected && response.url.includes('/login/')) { window.location.href = response.url; return; }
            const data = await response.json().catch(() => ({}));
            if (response.status === 401 || response.status === 403) { window.location.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`; return; }
            if (!response.ok) throw new Error(firstFormError(data.errors) || data.error || 'Could not copy guide');
            window.location.href = data.url;
        } catch (err) { error.textContent = err.message; error.classList.remove('hidden'); submit.disabled = false; submit.textContent = 'Copy Guide'; }
    });
}

function buildGuideShareText(title) {
    const maxTitleLength = 120;
    const maxStepLength = 220;
    const cleanText = (value) => (value || '').replace(/\s+/g, ' ').trim();
    const truncate = (value, maxLength) => {
        const text = cleanText(value);
        return text.length > maxLength ? text.slice(0, maxLength - 1).trimEnd() + '…' : text;
    };
    const steps = [...document.querySelectorAll('[data-steps-list] > [data-step-id]')].map((step, index) => {
        const stepTitle = cleanText(step.querySelector('[data-step-title]')?.textContent);
        const instruction = cleanText(step.querySelector('[data-step-instruction]')?.textContent);
        const summary = [stepTitle, instruction].filter(Boolean).join(': ');
        return summary ? `${index + 1}. ${truncate(summary, maxStepLength)}` : '';
    }).filter(Boolean);
    return [
        `How to: ${truncate(title, maxTitleLength)}`,
        steps.length ? `\nSteps:\n${steps.join('\n')}` : '',
    ].join('');
}

function initGuideQuestions() {
    const slug = window.WIKONOMI_GUIDE_SLUG;
    const popover = document.querySelector('[data-question-popover]');
    const form = document.querySelector('[data-question-form]');
    const stepSelect = document.querySelector('[data-question-step-select]');
    const body = form?.querySelector('[name="body"]');
    const error = document.querySelector('[data-question-error]');
    const submit = document.querySelector('[data-question-submit]');

    function openQuestion(stepId = 'general') {
        if (!popover || !form) {
            window.location.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`;
            return;
        }
        form.reset();
        stepSelect.value = stepId || 'general';
        error?.classList.add('hidden');
        popover.classList.remove('hidden');
        popover.setAttribute('aria-hidden', 'false');
        document.body.classList.add('overflow-hidden');
        setTimeout(() => body?.focus(), 0);
    }
    function closeQuestion() {
        popover?.classList.add('hidden');
        popover?.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('overflow-hidden');
        form?.reset();
    }

    document.addEventListener('click', (event) => {
        const ask = event.target.closest('[data-ask-question]');
        if (ask) { event.preventDefault(); openQuestion(ask.dataset.stepId); }
        if (event.target.closest('[data-close-question]')) closeQuestion();
        const filter = event.target.closest('[data-question-filter]');
        if (filter) filterQuestions(filter.dataset.questionFilter, filter);
    });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeQuestion(); });

    form?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const question = body.value.trim();
        if (!question) return;
        submit.disabled = true;
        submit.textContent = 'Posting…';
        error.classList.add('hidden');
        try {
            const response = await fetch(`/guides/${slug}/questions/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
                body: JSON.stringify({body: question, step_id: stepSelect.value}),
            });
            const data = await response.json().catch(() => ({}));
            if (response.status === 401 || response.status === 403) { window.location.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`; return; }
            if (!response.ok) throw new Error(data.error || firstFormError(data.errors) || 'Could not post question');
            window.location.assign(data.target_url);
        } catch (err) {
            error.textContent = err.message;
            error.classList.remove('hidden');
            submit.disabled = false;
            submit.textContent = 'Post Question';
        }
    });
}

function filterQuestions(filter, activeButton) {
    let visible = 0;
    document.querySelectorAll('[data-question-filter]').forEach((button) => button.classList.toggle('is-active', button === activeButton));
    document.querySelectorAll('[data-question-card]').forEach((card) => {
        const show = filter === 'all' || card.dataset.status === filter || card.dataset.questionStep === filter;
        card.classList.toggle('hidden', !show);
        if (show) visible += 1;
    });
    document.querySelector('[data-no-filtered-questions]')?.classList.toggle('hidden', visible !== 0);
}

function initGuideDeletion() {
    const slug = window.WIKONOMI_GUIDE_SLUG;
    const popover = document.querySelector('[data-delete-popover]');
    const form = document.querySelector('[data-delete-guide-form]');
    const title = document.querySelector('[data-delete-guide-title]');
    const copy = document.querySelector('[data-delete-guide-copy]');
    const reasonWrap = document.querySelector('[data-delete-reason-wrap]');
    const error = document.querySelector('[data-delete-guide-error]');
    const submit = document.querySelector('[data-delete-guide-submit]');
    let mode = 'mark';

    function openDelete(nextMode) {
        if (!popover || !form) return;
        mode = nextMode;
        form.reset();
        error.classList.add('hidden');
        const direct = mode === 'direct';
        title.textContent = direct ? 'Delete this guide permanently?' : 'Mark guide for deletion?';
        copy.textContent = direct ? 'This cannot be undone. The guide, its questions, answers and tips will be removed.' : 'Another user must independently confirm before the guide is removed.';
        reasonWrap.classList.toggle('hidden', direct);
        submit.textContent = direct ? 'Delete guide permanently' : 'Mark for deletion';
        popover.classList.remove('hidden');
        popover.setAttribute('aria-hidden', 'false');
        document.body.classList.add('overflow-hidden');
    }
    function closeDelete() {
        popover?.classList.add('hidden');
        popover?.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('overflow-hidden');
    }
    async function postDeleteAction(url, bodyData) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
            body: bodyData,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || 'Could not complete deletion action');
        return data;
    }

    document.addEventListener('click', async (event) => {
        if (event.target.closest('[data-mark-guide-delete]')) openDelete('mark');
        if (event.target.closest('[data-delete-guide-direct]')) openDelete('direct');
        if (event.target.closest('[data-close-delete-guide]')) closeDelete();
        if (event.target.closest('[data-confirm-guide-delete]')) {
            if (!window.confirm('Confirm this deletion? The guide will be removed permanently.')) return;
            try {
                const data = await postDeleteAction(`/guides/${slug}/confirm-delete/`);
                window.location.href = data.redirect_url;
            } catch (err) { showToast(err.message, 'error'); }
        }
    });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDelete(); });
    form?.addEventListener('submit', async (event) => {
        event.preventDefault();
        submit.disabled = true;
        const originalText = submit.textContent;
        submit.textContent = mode === 'direct' ? 'Deleting…' : 'Marking…';
        try {
            const url = mode === 'direct' ? `/guides/${slug}/delete/` : `/guides/${slug}/mark-delete/`;
            const data = await postDeleteAction(url, new FormData(form));
            if (data.redirect_url) window.location.href = data.redirect_url;
            else window.location.reload();
        } catch (err) {
            error.textContent = err.message;
            error.classList.remove('hidden');
            submit.disabled = false;
            submit.textContent = originalText;
        }
    });
}

function openGuidePopover(popover) { if (!popover) return; closeGuidePopovers(); popover.classList.remove('hidden'); popover.setAttribute('aria-hidden', 'false'); document.body.classList.add('overflow-hidden'); }
function closeGuidePopovers() { document.querySelectorAll('[data-rating-popover], [data-fork-popover]').forEach((el) => { el.classList.add('hidden'); el.setAttribute('aria-hidden', 'true'); }); document.body.classList.remove('overflow-hidden'); }

function escapeHtml(str) { const div = document.createElement('div'); div.textContent = str; return div.innerHTML; }

function initStepEditor() {
    const editor = document.querySelector('[data-steps-editor]');
    if (!editor) return;
    const template = document.getElementById('step-row-template');
    const deletedIds = [];
    ensureTrailingInsert(editor, template);
    renumberSteps(editor);
    editor.querySelectorAll('[data-step-row]').forEach((row) => { row.draggable = false; });
    editor.addEventListener('pointerdown', function (event) {
        const handle = event.target.closest('[data-drag-handle]');
        if (handle) handle.closest('[data-step-row]').draggable = true;
    });
    editor.addEventListener('pointerup', function (event) {
        const row = event.target.closest('[data-step-row]');
        if (row && !row.classList.contains('opacity-60')) row.draggable = false;
    });
    editor.addEventListener('click', function (event) {
        const insertBtn = event.target.closest('[data-insert-after]');
        if (insertBtn) { insertStepAfter(editor, template, insertBtn); return; }
        const deleteBtn = event.target.closest('[data-delete-step]');
        if (deleteBtn) {
            const row = deleteBtn.closest('[data-step-row]');
            const divider = row.nextElementSibling;
            if (row.dataset.stepId) deletedIds.push(row.dataset.stepId);
            row.remove();
            if (divider && divider.querySelector('[data-insert-after]')) divider.remove();
            ensureTrailingInsert(editor, template);
            renumberSteps(editor);
        }
    });
    editor.addEventListener('dragstart', function (event) {
        const row = event.target.closest('[data-step-row]');
        if (!row || !row.draggable) return;
        row.classList.add('opacity-60');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', row.dataset.stepId || 'new-step');
    });
    editor.addEventListener('dragend', function (event) {
        const row = event.target.closest('[data-step-row]');
        if (row) { row.classList.remove('opacity-60'); row.draggable = false; }
        refreshStepPositions(editor);
        ensureTrailingInsert(editor, template);
        renumberSteps(editor);
    });
    editor.addEventListener('dragover', function (event) {
        const dragging = editor.querySelector('[data-step-row].opacity-60');
        const target = event.target.closest('[data-step-row]');
        if (!dragging || !target || dragging === target) return;
        event.preventDefault();
        const rect = target.getBoundingClientRect();
        const after = event.clientY > rect.top + rect.height / 2;
        const draggingDivider = dragging.nextElementSibling && dragging.nextElementSibling.querySelector('[data-insert-after]') ? dragging.nextElementSibling : null;
        const targetDivider = target.nextElementSibling && target.nextElementSibling.querySelector('[data-insert-after]') ? target.nextElementSibling : null;
        if (after) {
            if (targetDivider) targetDivider.after(dragging); else target.after(dragging);
            if (draggingDivider) dragging.after(draggingDivider);
        } else {
            target.before(dragging);
            if (draggingDivider) dragging.after(draggingDivider);
        }
    });
    const form = document.getElementById('guide-editor-form');
    if (form) form.addEventListener('submit', function () {
        const steps = Array.from(editor.querySelectorAll('[data-step-row]')).map((row, index) => ({
            id: row.dataset.stepId || null,
            title: (row.querySelector('[data-step-title]')?.value || '').trim(),
            instruction: row.querySelector('[data-step-instruction]').value.trim(),
            position: index + 1,
        }));
        editor.querySelectorAll('[data-step-row]').forEach((row, index) => {
            row.querySelectorAll('[data-step-photo-input]').forEach((input) => { input.name = `step_photos_${index}`; });
        });
        addHidden(form, 'steps_json', JSON.stringify(steps));
        addHidden(form, 'deleted_step_ids', JSON.stringify(deletedIds));
    });
}

function addHidden(form, name, value) {
    let hidden = form.querySelector(`input[name="${name}"]`);
    if (!hidden) { hidden = document.createElement('input'); hidden.type = 'hidden'; hidden.name = name; form.appendChild(hidden); }
    hidden.value = value;
}

function insertStepAfter(editor, template, insertBtn) {
    const dividerRow = insertBtn.closest('div');
    const prevRow = dividerRow.previousElementSibling;
    const nextRow = dividerRow.nextElementSibling;
    const prevPos = prevRow ? parseFloat(prevRow.dataset.position) : 0;
    const nextPos = nextRow && nextRow.matches('[data-step-row]') ? parseFloat(nextRow.dataset.position) : prevPos + 2;
    const fragment = template.content.cloneNode(true);
    const newRow = fragment.querySelector('[data-step-row]');
    newRow.dataset.position = (prevPos + nextPos) / 2;
    dividerRow.after(fragment);
    ensureTrailingInsert(editor, template);
    renumberSteps(editor);
    newRow.querySelector('[data-step-title]').focus();
}

function ensureTrailingInsert(editor, template) {
    if (!template) return;
    const hasInsertButton = editor.querySelector('[data-insert-after]');
    if (!hasInsertButton) {
        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector('[data-step-row]');
        if (row) row.remove();
        editor.appendChild(fragment);
        return;
    }
    const last = editor.lastElementChild;
    if (last && last.matches('[data-step-row]')) {
        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector('[data-step-row]');
        if (row) row.remove();
        editor.appendChild(fragment);
    }
}

function refreshStepPositions(editor) {
    editor.querySelectorAll('[data-step-row]').forEach((row, index) => { row.dataset.position = index + 1; });
}

function renumberSteps(editor) {
    editor.querySelectorAll('[data-step-row]').forEach((row, index) => {
        const badge = row.querySelector('[data-step-number]');
        row.dataset.position = index + 1;
        if (badge && !badge.querySelector('svg')) badge.textContent = index + 1;
    });
}
