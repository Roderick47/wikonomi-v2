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
