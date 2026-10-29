/* Wikonomi Stage 5: opt-in, on-page tutorials. No browser location calls or test submissions. */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const root = document.getElementById('wikonomi-onboarding');
        if (!root) return;

        const invite = root.querySelector('[data-tour-invite]');
        const chooser = root.querySelector('[data-tour-chooser-dialog]');
        const guide = root.querySelector('[data-tour-guide]');
        const title = root.querySelector('[data-tour-title]');
        const description = root.querySelector('[data-tour-description]');
        const counter = root.querySelector('[data-tour-step-count]');
        const next = root.querySelector('[data-tour-next]');
        const back = root.querySelector('[data-tour-back]');
        const skip = root.querySelector('[data-tour-skip]');
        const guestSeenKey = 'wikonomi_onboarding_seen_v2';
        const legacySeenKey = 'wikonomi_onboarding_seen_v1';
        const progressKey = 'wikonomi_interactive_tour_v1';
        const isAuthenticated = root.dataset.authenticated === 'true';
        const page = document.querySelector('#search-form') ? 'search'
            : document.querySelector('form[data-form-kind="price"]') ? 'record' : 'other';
        root.classList.toggle('wk-tour-home', page === 'search');
        let active = null;
        let highlighted = null;
        let previousDescription = null;
        let returnFocus = null;
        let invitationTimer = null;

        const steps = {
            search: [
                {
                    target: '#search-form input[name="q"]',
                    title: 'Search for a price',
                    body: 'Type a product, for example rice or cooking oil, and press Search. The next step follows your real search results.',
                    hint: 'Try a search or select Next to explore without searching.'
                },
                {
                    target: '#map-panel',
                    title: 'Explore prices on the map',
                    body: 'The map shows where community prices were reported. Tap a pin or cluster to explore. Nearby filtering is optional and only asks for location if you select it.',
                    hint: 'Tap the map or select Next to continue.'
                },
                {
                    target: '#price-feed .price-card, #price-feed',
                    title: 'Open a reported price',
                    body: 'Each report shows the product, shop and when a price was reported. Tap a price card to read more; past reports are useful history, not a guaranteed price today.',
                    hint: 'Open a report or select Finish tour. Search again if there are no matching reports.'
                }
            ],
            record: [
                {
                    target: '#photos-drop-zone',
                    title: 'Take a photo, if you have one',
                    body: 'Take a picture of a shelf label or choose one from your gallery. Photos help others check the reported price, but they are optional.',
                    hint: 'Choose a photo or select Next to skip the photo.'
                },
                {
                    target: '#product_search',
                    title: 'Name the product',
                    body: 'Choose an existing product or type the name you saw. Include a useful size or quantity so other shoppers can compare accurately.',
                    hint: 'Enter a product name, then continue.'
                },
                {
                    target: '#id_price',
                    title: 'Enter the price',
                    body: 'Enter the amount you actually saw. Check the currency, which normally defaults to PNG kina (PGK).',
                    hint: 'Enter the price, then continue.'
                },
                {
                    target: '#business_search',
                    title: 'Choose the shop',
                    body: 'Enter the shop where you found it. Existing shops can reuse their location. For a new shop, open Shop location and place a map pin. A shop is optional.',
                    hint: 'Enter the shop if you know it, or select Next.'
                },
                {
                    target: 'form[data-form-kind="price"] button[name="save_action"][value="finish"]',
                    title: 'Save only when it is a real price',
                    body: 'You can now save the report or save and add another. This walkthrough never posts sample data. Select Finish tour to exit without submitting anything.',
                    hint: 'Submit a real price when ready, or finish the guide without saving.'
                }
            ]
        };

        function getCookie(name) {
            const value = '; ' + document.cookie;
            const sections = value.split('; ' + name + '=');
            return sections.length === 2 ? sections.pop().split(';').shift()
                : (root.querySelector('[name="csrfmiddlewaretoken"]') || {}).value || '';
        }

        function guestHasSeen() {
            try {
                return Boolean(localStorage.getItem(guestSeenKey) || localStorage.getItem(legacySeenKey));
            } catch (_) {
                return false;
            }
        }

        function markGuestSeen() {
            if (isAuthenticated) return;
            try { localStorage.setItem(guestSeenKey, 'seen'); } catch (_) { /* Storage may be unavailable. */ }
        }

        function persist(action) {
            if (!isAuthenticated || !root.dataset.updateUrl) return;
            const body = new URLSearchParams({ action: action });
            fetch(root.dataset.updateUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin',
                keepalive: true,
                body: body.toString()
            }).catch(function () { /* Do not interrupt a real shopping session. */ });
        }

        function saveProgress() {
            try {
                if (active) sessionStorage.setItem(progressKey, JSON.stringify(active));
                else sessionStorage.removeItem(progressKey);
            } catch (_) { /* Continue in the current document. */ }
        }

        function readProgress() {
            try {
                const saved = JSON.parse(sessionStorage.getItem(progressKey) || 'null');
                if (!saved || !Object.prototype.hasOwnProperty.call(steps, saved.path)) return null;
                if (!Number.isInteger(saved.step) || saved.step < 0 || saved.step >= steps[saved.path].length) return null;
                return { path: saved.path, step: saved.step };
            } catch (_) {
                return null;
            }
        }

        function emit(eventName) {
            // Analytics can subscribe without collecting product names, prices or GPS.
            document.dispatchEvent(new CustomEvent('wikonomi:onboarding', {
                detail: { event: eventName, path: active ? active.path : null, step: active ? active.step : null }
            }));
        }

        function clearHighlight() {
            if (highlighted) {
                highlighted.classList.remove('wk-tour-highlight');
                if (previousDescription === null) highlighted.removeAttribute('aria-describedby');
                else highlighted.setAttribute('aria-describedby', previousDescription);
            }
            highlighted = null;
            previousDescription = null;
        }

        function findTarget(selector) {
            const choices = selector.split(',').map(function (s) { return s.trim(); });
            for (const choice of choices) {
                const match = document.querySelector(choice);
                if (match) return match;
            }
            return null;
        }

        function reposition() {
            if (guide.hidden || !highlighted) return;
            if (window.innerWidth < 850) {
                guide.style.removeProperty('left');
                guide.style.removeProperty('top');
                return;
            }
            const target = highlighted.getBoundingClientRect();
            const width = Math.min(340, window.innerWidth - 32);
            const height = guide.offsetHeight;
            let left = target.right + 16;
            if (left + width > window.innerWidth - 12) left = target.left - width - 16;
            if (left < 12) left = Math.max(12, Math.min(window.innerWidth - width - 12, target.left));
            let top = target.top + Math.min(target.height / 2, 70) - height / 2;
            top = Math.max(12, Math.min(window.innerHeight - height - 12, top));
            guide.style.left = Math.round(left) + 'px';
            guide.style.top = Math.round(top) + 'px';
        }

        function revealGuide() {
            if (!active || active.path !== page) {
                guide.hidden = true;
                clearHighlight();
                return;
            }
            const step = steps[active.path][active.step];
            title.textContent = step.title;
            description.textContent = step.body;
            counter.textContent = (active.path === 'search' ? 'Find prices' : 'Record prices')
                + ' · ' + (active.step + 1) + ' of ' + steps[active.path].length;
            back.hidden = active.step === 0;
            skip.hidden = active.step === steps[active.path].length - 1;
            next.textContent = active.step === steps[active.path].length - 1 ? 'Finish tour' : 'Next';
            next.setAttribute('aria-label', step.hint);
            guide.hidden = false;
            clearHighlight();

            let target = findTarget(step.target);
            if (active.path === 'search' && active.step === 1 && target
                && target.classList.contains('map-panel--collapsed')
                && typeof window.toggleMapView === 'function') {
                window.toggleMapView();
            }
            if (target && target.getBoundingClientRect().width > 0) {
                highlighted = target;
                previousDescription = target.getAttribute('aria-describedby');
                target.classList.add('wk-tour-highlight');
                target.setAttribute('aria-describedby',
                    [previousDescription, 'wk-tour-guide-description'].filter(Boolean).join(' '));
                const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                target.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
            } else {
                description.textContent += ' If the control is unavailable, select Next to continue.';
            }
            window.requestAnimationFrame(reposition);
            window.setTimeout(reposition, 350);
            emit('step_view');
        }

        function finish(action) {
            if (!active) return;
            emit(action === 'complete' ? 'complete' : 'dismiss');
            clearHighlight();
            guide.hidden = true;
            active = null;
            saveProgress();
            markGuestSeen();
            persist(action);
        }

        function advance() {
            if (!active) return;
            if (active.step >= steps[active.path].length - 1) {
                finish('complete');
                return;
            }
            active.step += 1;
            saveProgress();
            revealGuide();
        }

        function retreat() {
            if (!active || active.step === 0) return;
            active.step -= 1;
            saveProgress();
            revealGuide();
        }

        function closeChooser() {
            chooser.hidden = true;
            document.body.classList.remove('wk-tour-modal-open');
            if (returnFocus && returnFocus.isConnected) returnFocus.focus();
        }

        function openChooser() {
            if (active) {
                clearHighlight();
                active = null;
                saveProgress();
                guide.hidden = true;
            }
            returnFocus = document.activeElement;
            invite.hidden = true;
            clearTimeout(invitationTimer);
            chooser.hidden = false;
            document.body.classList.add('wk-tour-modal-open');
            chooser.querySelector('[data-tour-start="search"]').focus();
            emit('choose');
        }

        function startPath(path) {
            if (!Object.prototype.hasOwnProperty.call(steps, path)) return;
            closeChooser();
            markGuestSeen();
            active = { path: path, step: 0 };
            saveProgress();
            emit('start');
            if (page !== path) {
                window.location.assign(path === 'search' ? root.dataset.homeUrl : root.dataset.priceUrl);
                return;
            }
            revealGuide();
        }

        root.querySelectorAll('[data-tour-start]').forEach(function (button) {
            button.addEventListener('click', function () { startPath(button.dataset.tourStart); });
        });
        document.querySelectorAll('[data-onboarding-open]').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                openChooser();
            });
        });
        root.querySelectorAll('[data-tour-choose]').forEach(function (button) {
            button.addEventListener('click', openChooser);
        });
        root.querySelectorAll('[data-tour-dismiss]').forEach(function (button) {
            button.addEventListener('click', function () {
                invite.hidden = true;
                markGuestSeen();
                persist('dismiss');
            });
        });
        root.querySelectorAll('[data-tour-close-chooser]').forEach(function (button) {
            button.addEventListener('click', function () {
                closeChooser();
                markGuestSeen();
                persist('dismiss');
            });
        });
        root.querySelector('[data-tour-stop]').addEventListener('click', function () { finish('dismiss'); });
        next.addEventListener('click', advance);
        skip.addEventListener('click', advance);
        back.addEventListener('click', retreat);

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Tab' && !chooser.hidden) {
                const controls = Array.from(chooser.querySelectorAll('button:not([disabled])'));
                if (controls.length) {
                    const first = controls[0];
                    const last = controls[controls.length - 1];
                    if (event.shiftKey && document.activeElement === first) {
                        event.preventDefault(); last.focus();
                    } else if (!event.shiftKey && document.activeElement === last) {
                        event.preventDefault(); first.focus();
                    }
                }
            }
            if (event.key !== 'Escape') return;
            if (!chooser.hidden) {
                closeChooser();
                markGuestSeen();
                persist('dismiss');
            } else if (!guide.hidden) {
                finish('dismiss');
            }
        });

        // Real actions advance the guide. We never fabricate a product, price,
        // location, form submission or map marker.
        document.addEventListener('submit', function (event) {
            if (!active || active.path !== 'search' || active.step !== 0) return;
            if (event.target.id !== 'search-form') return;
            const field = event.target.querySelector('input[name="q"]');
            if (field && field.value.trim()) {
                active.step = 1;
                saveProgress();  // Persists across the real GET navigation.
                emit('search_submitted');
            }
        }, true);
        document.addEventListener('click', function (event) {
            if (!active || active.path !== 'search') return;
            if (active.step === 1 && event.target.closest('#map')) {
                advance();
            } else if (active.step === 2 && event.target.closest('#price-feed a.price-card[href]')) {
                finish('complete');  // The user navigates to the real report.
            }
        }, true);
        document.addEventListener('change', function (event) {
            if (!active || active.path !== 'record') return;
            if (active.step === 0 && event.target.id === 'photos-input'
                && event.target.files && event.target.files.length > 0) advance();
            else if (active.step === 1 && event.target.id === 'product_search'
                && event.target.value.trim()) advance();
            else if (active.step === 2 && event.target.id === 'id_price'
                && Number(event.target.value) > 0) advance();
            else if (active.step === 3 && event.target.id === 'business_search'
                && event.target.value.trim()) advance();
        }, true);

        window.addEventListener('resize', reposition);
        window.addEventListener('scroll', reposition, { passive: true });

        // Resume only on the relevant page. Nothing forces a new visitor
        // to grant GPS permission, register, or submit a dummy report.
        active = readProgress();
        if (active) {
            if (page === active.path) revealGuide();
        } else if (root.dataset.inviteEligible === 'true' && (isAuthenticated || !guestHasSeen())) {
            invitationTimer = window.setTimeout(function () { invite.hidden = false; }, 900);
        }

        window.WikonomiOnboarding = { open: openChooser, start: startPath };
    });
})();
