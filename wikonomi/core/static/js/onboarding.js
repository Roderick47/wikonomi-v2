(function () {
    'use strict';

    function installResponsiveNavigation() {
        const navbar = document.getElementById('site-navbar');
        const searchForm = document.getElementById('search-form');
        if (!navbar || !searchForm || document.getElementById('wk-mobile-nav')) return;

        const style = document.createElement('style');
        style.textContent = `
            .wk-home-shortcuts {
                display: flex;
                align-items: center;
                gap: .5rem;
                margin-top: .75rem;
                padding: .125rem .125rem .35rem;
                overflow-x: auto;
                scrollbar-width: none;
                -webkit-overflow-scrolling: touch;
            }
            .wk-home-shortcuts::-webkit-scrollbar { display: none; }
            .wk-home-shortcut {
                display: inline-flex;
                flex: 0 0 auto;
                align-items: center;
                justify-content: center;
                min-height: 2.5rem;
                padding: .5rem .875rem;
                border: 1px solid #e2e8f0;
                border-radius: 9999px;
                background: #fff;
                color: #475569;
                font-size: .875rem;
                font-weight: 650;
                line-height: 1.2;
                text-decoration: none;
                box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
                transition: border-color .15s ease, background-color .15s ease, color .15s ease, transform .15s ease;
            }
            .wk-home-shortcut:hover,
            .wk-home-shortcut:focus-visible {
                border-color: rgba(75, 39, 152, .35);
                background: rgba(75, 39, 152, .06);
                color: #4B2798;
                outline: none;
            }
            .wk-home-shortcut:active { transform: translateY(1px); }
            .wk-home-shortcut--primary {
                border-color: rgba(75, 39, 152, .28);
                background: rgba(75, 39, 152, .08);
                color: #4B2798;
            }
            .wk-mobile-nav {
                position: fixed;
                right: 1rem;
                bottom: 1.25rem;
                z-index: 45;
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: .65rem;
            }
            .wk-mobile-nav__panel {
                width: min(18rem, calc(100vw - 2rem));
                padding: .75rem;
                border: 1px solid #e2e8f0;
                border-radius: 1rem;
                background: rgba(255, 255, 255, .98);
                box-shadow: 0 18px 50px rgba(15, 23, 42, .18);
                backdrop-filter: blur(12px);
            }
            .wk-mobile-nav__panel[hidden] { display: none; }
            .wk-mobile-nav__title {
                margin: 0 0 .6rem;
                padding: 0 .25rem;
                color: #64748b;
                font-size: .72rem;
                font-weight: 800;
                letter-spacing: .08em;
                text-transform: uppercase;
            }
            .wk-mobile-nav__grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: .5rem;
            }
            .wk-mobile-nav__link {
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 2.75rem;
                padding: .65rem .75rem;
                border: 1px solid #e2e8f0;
                border-radius: .8rem;
                background: #fff;
                color: #334155;
                font-size: .875rem;
                font-weight: 700;
                text-align: center;
                text-decoration: none;
            }
            .wk-mobile-nav__link:hover,
            .wk-mobile-nav__link:focus-visible {
                border-color: rgba(75, 39, 152, .35);
                background: rgba(75, 39, 152, .06);
                color: #4B2798;
                outline: none;
            }
            .wk-mobile-nav__link--primary {
                grid-column: 1 / -1;
                border-color: #4B2798;
                background: #4B2798;
                color: #fff;
            }
            .wk-mobile-nav__link--primary:hover,
            .wk-mobile-nav__link--primary:focus-visible {
                background: #3d207d;
                color: #fff;
            }
            .wk-mobile-nav__toggle {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: .45rem;
                min-height: 3rem;
                padding: .7rem 1rem;
                border: 1px solid rgba(255, 255, 255, .35);
                border-radius: 9999px;
                background: #4B2798;
                color: #fff;
                font-size: .875rem;
                font-weight: 800;
                box-shadow: 0 10px 28px rgba(75, 39, 152, .28);
            }
            .wk-mobile-nav__toggle svg { width: 1.1rem; height: 1.1rem; }
            @media (min-width: 640px) {
                .wk-home-shortcuts { justify-content: center; flex-wrap: wrap; overflow: visible; }
            }
            @media (min-width: 768px) {
                .wk-mobile-nav { display: none !important; }
            }
        `;
        document.head.appendChild(style);

        const wantedLabels = new Set(['Prices', 'Businesses', 'Guides', 'Transport']);
        const navbarLinks = Array.from(navbar.querySelectorAll('a')).filter(function (link) {
            return wantedLabels.has(link.textContent.trim());
        });

        const controlRow = searchForm.querySelector('#sort')?.parentElement;
        if (controlRow) {
            const shortcutLinks = Array.from(controlRow.querySelectorAll('a')).filter(function (link) {
                const label = link.textContent.trim().toLowerCase();
                return label.includes('add price') || label.includes('browse products') || label.includes('browse businesses') || label.includes('browse guides');
            });

            const shortcuts = document.createElement('nav');
            shortcuts.className = 'wk-home-shortcuts';
            shortcuts.setAttribute('aria-label', 'Wikonomi shortcuts');

            const labels = {
                'browse products': 'Prices',
                'browse businesses': 'Businesses',
                'browse guides': 'Guides'
            };

            shortcutLinks.forEach(function (link) {
                const normalized = link.textContent.trim().toLowerCase();
                link.textContent = labels[normalized] || '+ Add price';
                link.className = normalized.includes('add price')
                    ? 'wk-home-shortcut wk-home-shortcut--primary'
                    : 'wk-home-shortcut';
                shortcuts.appendChild(link);
            });

            const transportLink = navbarLinks.find(function (link) {
                return link.textContent.trim() === 'Transport';
            });
            if (transportLink) {
                const clone = transportLink.cloneNode(true);
                clone.className = 'wk-home-shortcut';
                clone.textContent = 'Transport';
                shortcuts.insertBefore(clone, shortcuts.lastElementChild);
            }

            controlRow.insertAdjacentElement('afterend', shortcuts);
        }

        const floatingNav = document.createElement('div');
        floatingNav.id = 'wk-mobile-nav';
        floatingNav.className = 'wk-mobile-nav';

        const panel = document.createElement('div');
        panel.className = 'wk-mobile-nav__panel';
        panel.id = 'wk-mobile-nav-panel';
        panel.hidden = true;

        const title = document.createElement('p');
        title.className = 'wk-mobile-nav__title';
        title.textContent = 'Explore Wikonomi';
        panel.appendChild(title);

        const grid = document.createElement('div');
        grid.className = 'wk-mobile-nav__grid';
        panel.appendChild(grid);

        navbarLinks.forEach(function (sourceLink) {
            const link = sourceLink.cloneNode(true);
            link.className = 'wk-mobile-nav__link';
            link.removeAttribute('hidden');
            grid.appendChild(link);
        });

        const addPriceLink = document.querySelector('.wk-home-shortcut--primary');
        if (addPriceLink) {
            const addLink = addPriceLink.cloneNode(true);
            addLink.className = 'wk-mobile-nav__link wk-mobile-nav__link--primary';
            addLink.textContent = '+ Add price';
            grid.appendChild(addLink);
        }

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'wk-mobile-nav__toggle';
        toggle.setAttribute('aria-controls', panel.id);
        toggle.setAttribute('aria-expanded', 'false');
        toggle.innerHTML = '<svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg><span>Menu</span>';

        function setOpen(open) {
            panel.hidden = !open;
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        }

        toggle.addEventListener('click', function () {
            setOpen(panel.hidden);
        });

        document.addEventListener('click', function (event) {
            if (!floatingNav.contains(event.target)) setOpen(false);
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !panel.hidden) {
                setOpen(false);
                toggle.focus();
            }
        });

        floatingNav.appendChild(panel);
        floatingNav.appendChild(toggle);
        document.body.appendChild(floatingNav);
    }

    installResponsiveNavigation();
})();

(function () {
    'use strict';

    const root = document.getElementById('wikonomi-onboarding');
    if (!root) return;

    const slides = Array.from(root.querySelectorAll('[data-onboarding-slide]'));
    const progress = root.querySelector('.wk-onboarding__progress');
    const nextButton = root.querySelector('[data-onboarding-next]');
    const backButton = root.querySelector('[data-onboarding-back]');
    const dismissButtons = root.querySelectorAll('[data-onboarding-dismiss]');
    const openButtons = document.querySelectorAll('[data-onboarding-open]');
    const actionLinks = root.querySelectorAll('[data-onboarding-action]');
    const dialog = root.querySelector('[role="dialog"]');
    const isAuthenticated = root.dataset.authenticated === 'true';
    const guestStorageKey = 'wikonomi_onboarding_seen_v1';
    let activeIndex = 0;
    let lastFocusedElement = null;

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        return parts.length === 2 ? parts.pop().split(';').shift() : '';
    }

    function record(action) {
        if (!isAuthenticated) {
            try {
                localStorage.setItem(guestStorageKey, action);
            } catch (error) {
                // Storage can be unavailable in private browsing; the tour still works.
            }
            return Promise.resolve();
        }

        const updateUrl = root.dataset.updateUrl;
        if (!updateUrl) return Promise.resolve();

        const body = new URLSearchParams({ action });
        return fetch(updateUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
            },
            keepalive: true,
            body: body.toString()
        }).catch(function () {
            // Do not block or reopen the UI if persistence briefly fails.
        });
    }

    function renderProgress() {
        progress.replaceChildren();
        slides.forEach(function (_, index) {
            const dot = document.createElement('span');
            dot.className = 'wk-onboarding__progress-dot';
            if (index === activeIndex) dot.setAttribute('aria-current', 'step');
            progress.appendChild(dot);
        });
    }

    function showSlide(index) {
        activeIndex = Math.max(0, Math.min(index, slides.length - 1));
        slides.forEach(function (slide, slideIndex) {
            slide.hidden = slideIndex !== activeIndex;
        });
        backButton.hidden = activeIndex === 0;
        nextButton.textContent = activeIndex === 0
            ? 'Show me around'
            : activeIndex === slides.length - 1
                ? 'Finish'
                : 'Next';
        renderProgress();
        dialog.scrollTop = 0;
        nextButton.focus();
    }

    function openTour() {
        lastFocusedElement = document.activeElement;
        root.hidden = false;
        document.body.classList.add('wk-onboarding-open');
        showSlide(0);
    }

    function closeTour(action) {
        root.hidden = true;
        document.body.classList.remove('wk-onboarding-open');
        record(action || 'dismiss');
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
    }

    nextButton.addEventListener('click', function () {
        if (activeIndex === slides.length - 1) {
            closeTour('complete');
            if (typeof window.showToast === 'function') {
                window.showToast('You are ready to use Wikonomi.', 'success');
            }
            return;
        }
        showSlide(activeIndex + 1);
    });

    backButton.addEventListener('click', function () {
        showSlide(activeIndex - 1);
    });

    dismissButtons.forEach(function (button) {
        button.addEventListener('click', function () {
            closeTour('dismiss');
        });
    });

    openButtons.forEach(function (button) {
        button.addEventListener('click', function (event) {
            event.preventDefault();
            openTour();
        });
    });

    actionLinks.forEach(function (link) {
        link.addEventListener('click', function () {
            record('complete');
        });
    });

    document.addEventListener('keydown', function (event) {
        if (root.hidden) return;

        if (event.key === 'Escape') {
            closeTour('dismiss');
        } else if (event.key === 'ArrowRight') {
            nextButton.click();
        } else if (event.key === 'ArrowLeft' && activeIndex > 0) {
            backButton.click();
        } else if (event.key === 'Tab') {
            const focusable = Array.from(dialog.querySelectorAll(
                'a[href], button:not([disabled]):not([hidden]), [tabindex]:not([tabindex="-1"])'
            )).filter(function (element) {
                return element.offsetParent !== null;
            });
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        let guestHasSeenTour = false;
        try {
            guestHasSeenTour = Boolean(localStorage.getItem(guestStorageKey));
        } catch (error) {
            guestHasSeenTour = false;
        }

        if (root.dataset.autoOpen === 'true' && (isAuthenticated || !guestHasSeenTour)) {
            window.setTimeout(openTour, 700);
        }
    });

    window.WikonomiOnboarding = {
        open: openTour
    };
})();
