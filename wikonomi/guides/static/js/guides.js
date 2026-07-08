document.addEventListener('DOMContentLoaded', function () {
    initGuideRating();
    initTips();
    initStepEditor();
});

function initGuideRating() {
    const widget = document.querySelector('[data-rating-widget][data-rating-target="guide"]');
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
            widget.querySelectorAll('[data-rating-value]').forEach((star) => {
                const filled = Number(star.dataset.ratingValue) <= Number(data.score);
                star.classList.toggle('text-amber-400', filled);
                star.classList.toggle('text-gray-300', !filled);
                star.setAttribute('aria-pressed', filled ? 'true' : 'false');
            });
            widget.querySelector('[data-rating-score]').textContent = Number(data.average_score || 0).toFixed(1);
            widget.querySelector('[data-rating-count]').textContent = `(${data.rating_count} ratings)`;
            showToast('Rating saved', 'success');
        } catch (err) { console.error(err); showToast('Could not save your rating', 'error'); }
    });
}

function initTips() {
    const slug = window.WIKONOMI_GUIDE_SLUG;
    document.addEventListener('click', function (event) {
        const toggle = event.target.closest('[data-add-tip]');
        if (toggle) {
            const form = document.querySelector(`[data-add-tip-form][data-step-id="${toggle.dataset.stepId}"]`);
            if (form) form.classList.toggle('hidden');
        }
        const voteBtn = event.target.closest('[data-tip-vote]');
        if (voteBtn) voteTip(slug, voteBtn);
    });
    document.addEventListener('submit', async function (event) {
        const form = event.target.closest('[data-add-tip-form]');
        if (!form) return;
        event.preventDefault();
        const input = form.querySelector('input');
        const body = input.value.trim();
        if (!body) return;
        try {
            const formData = new FormData();
            formData.append('body', body);
            form.querySelectorAll('input[type="file"]').forEach((fileInput) => {
                Array.from(fileInput.files || []).forEach((file) => formData.append('photos', file));
            });
            const response = await fetch(`/guides/${slug}/steps/${form.dataset.stepId}/tips/`, {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
                body: formData,
            });
            if (!response.ok) throw new Error('Failed to add tip');
            const tip = await response.json();
            form.insertAdjacentElement('beforebegin', buildTipElement(tip));
            input.value = '';
            form.querySelectorAll('input[type="file"]').forEach((fileInput) => { fileInput.value = ''; });
            form.classList.add('hidden');
            showToast('Tip added', 'success');
        } catch (err) { console.error(err); showToast('Could not add your tip', 'error'); }
    });
}

function buildTipElement(tip) {
    const div = document.createElement('div');
    div.className = 'inline-flex items-center gap-1.5 bg-amber-50 text-amber-800 text-xs rounded px-2.5 py-1.5 mr-1.5 mb-1.5';
    div.dataset.tipId = tip.id;
    const photos = (tip.photos || []).map((photo) => `<a href="${escapeHtml(photo.url)}" target="_blank"><img src="${escapeHtml(photo.url)}" alt="Tip photo" class="h-10 w-10 rounded object-cover border border-amber-200"></a>`).join('');
    div.innerHTML = `<span>💡</span><span>${escapeHtml(tip.body)}</span>${photos}<button type="button" data-tip-vote data-tip-id="${tip.id}" class="flex items-center gap-0.5 text-amber-600 hover:text-amber-900 font-semibold">↑ <span data-tip-votes>0</span></button>`;
    return div;
}

async function voteTip(slug, button) {
    try {
        const response = await fetch(`/guides/${slug}/steps/tips/${button.dataset.tipId}/vote/`, {method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}});
        if (response.status === 401 || response.status === 403) { showToast('Please log in to vote on tips', 'info'); return; }
        if (!response.ok) throw new Error('Vote failed');
        const data = await response.json();
        button.querySelector('[data-tip-votes]').textContent = data.upvotes;
    } catch (err) { console.error(err); showToast('Could not register your vote', 'error'); }
}

function escapeHtml(str) { const div = document.createElement('div'); div.textContent = str; return div.innerHTML; }

function initStepEditor() {
    const editor = document.querySelector('[data-steps-editor]');
    if (!editor) return;
    const template = document.getElementById('step-row-template');
    const deletedIds = [];
    ensureTrailingInsert(editor, template);
    renumberSteps(editor);
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
        if (!row || !event.target.closest('[data-drag-handle]')) return;
        row.draggable = true;
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
