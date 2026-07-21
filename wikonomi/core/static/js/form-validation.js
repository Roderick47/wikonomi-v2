(function () {
    'use strict';

    const FORM_SELECTOR = 'form[data-wk-validate]';
    const ERROR_ATTRIBUTE = 'data-wk-client-error';
    const DEFAULT_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

    function fieldLabel(field) {
        if (field.dataset.validationLabel) return field.dataset.validationLabel;
        if (field.id) {
            const label = field.form?.querySelector(`label[for="${CSS.escape(field.id)}"]`);
            if (label) return label.textContent.replace(/\s+/g, ' ').replace(/[*:]+$/, '').trim();
        }
        return field.name ? field.name.replace(/_/g, ' ') : 'This field';
    }

    function humanFileSize(bytes) {
        if (bytes >= 1024 * 1024) return `${Math.round(bytes / (1024 * 1024))} MB`;
        return `${Math.round(bytes / 1024)} KB`;
    }

    function acceptedTypes(field) {
        const configured = (field.dataset.allowedTypes || field.accept || '')
            .split(',')
            .map(value => value.trim().toLowerCase())
            .filter(Boolean);
        return configured.length ? configured : DEFAULT_IMAGE_TYPES;
    }

    function fileMatchesType(file, allowed) {
        const fileType = (file.type || '').toLowerCase();
        const fileName = (file.name || '').toLowerCase();
        return allowed.some(rule => {
            if (rule.endsWith('/*')) return fileType.startsWith(rule.slice(0, -1));
            if (rule.startsWith('.')) return fileName.endsWith(rule);
            return fileType === rule;
        });
    }

    function errorAnchor(field) {
        const selector = field.dataset.validationAnchor;
        if (selector) {
            try {
                return field.form.querySelector(selector) || document.querySelector(selector) || field;
            } catch (_) {
                return field;
            }
        }
        return field;
    }

    function clearFieldError(field) {
        field.removeAttribute('aria-invalid');
        field.style.removeProperty('border-color');
        const errorId = field.dataset.clientErrorId;
        if (errorId) document.getElementById(errorId)?.remove();
        delete field.dataset.clientErrorId;
    }

    function showFieldError(field, message) {
        clearFieldError(field);
        const error = document.createElement('p');
        const errorId = `wk-error-${field.id || field.name || 'field'}-${Math.random().toString(36).slice(2, 8)}`;
        error.id = errorId;
        error.setAttribute(ERROR_ATTRIBUTE, '');
        error.className = 'mt-1 text-sm font-medium text-red-700';
        error.textContent = message;
        errorAnchor(field).insertAdjacentElement('afterend', error);
        field.dataset.clientErrorId = errorId;
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'), errorId].filter(Boolean).join(' '));
        if (field.type !== 'hidden') field.style.setProperty('border-color', '#dc2626');
    }

    function nativeMessage(field) {
        const value = typeof field.value === 'string' ? field.value.trim() : field.value;
        const label = fieldLabel(field);
        if (field.required && !value && field.type !== 'file') return `${label} is required.`;
        if (field.validity?.valueMissing) return `${label} is required.`;
        if (field.validity?.typeMismatch) return `Enter a valid ${label.toLowerCase()}.`;
        if (field.validity?.badInput) return `Enter a valid value for ${label.toLowerCase()}.`;
        if (field.validity?.patternMismatch) return field.title || `${label} is not in the expected format.`;
        if (field.validity?.rangeUnderflow) return `${label} must be at least ${field.min}.`;
        if (field.validity?.rangeOverflow) return `${label} must be no more than ${field.max}.`;
        if (field.validity?.stepMismatch) return `${label} must use increments of ${field.step}.`;

        if (typeof value === 'string') {
            const exactLength = Number(field.dataset.exactLength || 0);
            if (exactLength && value && value.length !== exactLength) {
                return `${label} must be exactly ${exactLength} characters.`;
            }
            if (field.minLength > 0 && value.length < field.minLength) {
                return `${label} must be at least ${field.minLength} characters.`;
            }
            if (field.maxLength > 0 && value.length > field.maxLength) {
                return `${label} must be ${field.maxLength} characters or fewer.`;
            }
        }
        return '';
    }

    function fileMessage(field) {
        const files = Array.from(field.files || []);
        if (field.required && files.length === 0) return `${fieldLabel(field)} is required.`;
        if (!files.length) return '';

        const maxFiles = Number(field.dataset.maxFiles || 0);
        const existingFiles = Number(field.dataset.existingFiles || 0);
        const deletedFiles = field.form
            ? field.form.querySelectorAll('[name="delete_photos"]:checked').length
            : 0;
        if (maxFiles && existingFiles - deletedFiles + files.length > maxFiles) {
            const available = Math.max(0, maxFiles - existingFiles + deletedFiles);
            return `Choose no more than ${available} additional photo${available === 1 ? '' : 's'} (${maxFiles} total).`;
        }

        const maxSize = Number(field.dataset.maxFileSize || 0);
        const oversized = maxSize ? files.find(file => file.size > maxSize) : null;
        if (oversized) return `${oversized.name} is too large. Maximum size is ${humanFileSize(maxSize)}.`;

        const allowed = acceptedTypes(field);
        const invalid = files.find(file => !fileMatchesType(file, allowed));
        if (invalid) return `${invalid.name} is not a supported file type. Use JPEG, PNG, or WebP.`;
        return '';
    }

    function validateField(field, options) {
        if (!field || field.disabled || !field.name || ['submit', 'button', 'reset'].includes(field.type)) return '';
        if (field.type === 'hidden' && !field.dataset.validateHidden) return '';
        clearFieldError(field);
        const message = field.type === 'file' ? fileMessage(field) : nativeMessage(field);
        if (message && options?.show !== false) showFieldError(field, message);
        return message;
    }

    function validateGuideSteps(form, errors) {
        if (!form.hasAttribute('data-wk-guide-steps')) return;
        const rows = Array.from(form.querySelectorAll('[data-step-row]'));
        const populatedRows = rows.filter(row => {
            const title = row.querySelector('[data-step-title]')?.value.trim() || '';
            const instruction = row.querySelector('[data-step-instruction]')?.value.trim() || '';
            return title || instruction;
        });

        if (!populatedRows.length) {
            const target = rows[0]?.querySelector('[data-step-instruction]');
            if (target) {
                const message = 'Add at least one step before publishing the guide.';
                showFieldError(target, message);
                errors.push({field: target, message});
            }
            return;
        }

        populatedRows.forEach((row, index) => {
            const instruction = row.querySelector('[data-step-instruction]');
            if (instruction && !instruction.value.trim()) {
                const message = `Step ${index + 1} needs an instruction.`;
                showFieldError(instruction, message);
                errors.push({field: instruction, message});
            }
        });
    }

    function validateCoordinatePair(form, errors) {
        const triggerName = form.dataset.requireLocationFor;
        if (!triggerName) return;
        const trigger = form.elements[triggerName];
        if (!trigger || !String(trigger.value || '').trim()) return;
        const latitude = form.elements.latitude;
        const longitude = form.elements.longitude;
        const lat = Number(latitude?.value);
        const lng = Number(longitude?.value);
        const valid = latitude?.value && longitude?.value
            && Number.isFinite(lat) && lat >= -90 && lat <= 90
            && Number.isFinite(lng) && lng >= -180 && lng <= 180;
        if (!valid) {
            const message = 'Set a valid location for this business before saving the price.';
            showFieldError(trigger, message);
            errors.push({field: trigger, message});
        }
    }

    function showSummary(form, errors) {
        form.querySelector('[data-wk-validation-summary]')?.remove();
        if (!errors.length) return;
        const summary = document.createElement('div');
        summary.setAttribute('data-wk-validation-summary', '');
        summary.setAttribute('role', 'alert');
        summary.className = 'rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800';
        summary.innerHTML = `<p class="font-bold">Please fix ${errors.length} ${errors.length === 1 ? 'error' : 'errors'} before submitting.</p>`;
        form.insertAdjacentElement('afterbegin', summary);
    }

    function validateForm(form, options) {
        const errors = [];
        form.querySelectorAll(`[${ERROR_ATTRIBUTE}]`).forEach(node => node.remove());
        form.querySelector('[data-wk-validation-summary]')?.remove();

        Array.from(form.elements).forEach(field => {
            const message = validateField(field, {show: options?.show !== false});
            if (message) errors.push({field, message});
        });
        validateGuideSteps(form, errors);
        validateCoordinatePair(form, errors);

        if (options?.show !== false) showSummary(form, errors);
        return {valid: errors.length === 0, errors};
    }

    function focusFirstError(errors) {
        const field = errors[0]?.field;
        if (!field) return;
        field.scrollIntoView({behavior: 'smooth', block: 'center'});
        if (field.type !== 'hidden') {
            try { field.focus({preventScroll: true}); } catch (_) { field.focus(); }
        }
    }

    function initForm(form) {
        form.noValidate = true;

        form.addEventListener('submit', event => {
            const result = validateForm(form);
            if (!result.valid) {
                event.preventDefault();
                event.stopImmediatePropagation();
                focusFirstError(result.errors);
            }
        }, true);

        form.addEventListener('focusout', event => {
            if (event.target?.matches('input, select, textarea')) validateField(event.target, {show: true});
        });

        form.addEventListener('change', event => {
            if (event.target?.matches('input, select, textarea')) validateField(event.target, {show: true});
        });

        form.addEventListener('input', event => {
            if (event.target?.getAttribute('aria-invalid') === 'true') validateField(event.target, {show: true});
        });
    }

    function init() {
        document.querySelectorAll(FORM_SELECTOR).forEach(initForm);
    }

    window.WikonomiFormValidation = {
        init,
        validateForm,
        validateField,
        DEFAULT_IMAGE_TYPES,
    };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
