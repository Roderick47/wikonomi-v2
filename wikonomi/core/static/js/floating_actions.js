/* One interaction model for all Wikonomi floating action menus. */
(function () {
    'use strict';

    function setupFloatingActionMenu(root) {
        if (root.dataset.wkFabReady) return;
        const toggle = root.querySelector('[data-wk-fab-toggle]');
        const panel = root.querySelector('[data-wk-fab-panel]');
        if (!toggle || !panel) return;
        root.dataset.wkFabReady = 'true';
        const symbol = toggle.querySelector('[data-wk-fab-symbol]');
        const openLabel = toggle.getAttribute('aria-label') || 'Open actions';
        const closedLabel = openLabel.replace(/^Open\b/, 'Close');
        function setOpen(open) {
            const changed = panel.classList.contains('is-open') !== Boolean(open);
            panel.classList.toggle('is-open', Boolean(open));
            panel.inert = !open;
            panel.setAttribute('aria-hidden', String(!open));
            toggle.setAttribute('aria-expanded', String(Boolean(open)));
            toggle.setAttribute('aria-label', open ? closedLabel : openLabel);
            if (symbol) symbol.textContent = open ? '×' : '+';
            if (changed) root.dispatchEvent(new CustomEvent('wk:fab:change', {detail: {open: Boolean(open)}}));
        }

        setOpen(false);
        toggle.addEventListener('click', (event) => {
            event.stopPropagation();
            setOpen(!panel.classList.contains('is-open'));
        });
        root.addEventListener('click', (event) => {
            if (event.target.closest('.wk-fab__item:not([data-wk-fab-keep-open])')) {
                setOpen(false);
            }
        });
        document.addEventListener('click', (event) => {
            if (!root.contains(event.target)) setOpen(false);
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && panel.classList.contains('is-open')) {
                setOpen(false);
                toggle.focus();
            }
        });
    }

    function initFloatingActionMenus() {
        document.querySelectorAll('[data-wk-fab]').forEach(setupFloatingActionMenu);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFloatingActionMenus);
    } else {
        initFloatingActionMenus();
    }
})();
