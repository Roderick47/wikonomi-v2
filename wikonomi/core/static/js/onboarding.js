(function () {
    'use strict';

    const HOME_LOCATION_KEY = 'wikonomi_home_location_v1';
    const HOME_LOCATION_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
    const HOME_LOCAL_RADIUS_KM = 75;

    function validCoordinate(value, min, max) {
        const number = Number(value);
        return Number.isFinite(number) && number >= min && number <= max;
    }

    function readStoredHomeLocation() {
        try {
            const raw = localStorage.getItem(HOME_LOCATION_KEY);
            if (!raw) return null;
            const saved = JSON.parse(raw);
            if (!saved || !validCoordinate(saved.lat, -90, 90) || !validCoordinate(saved.lng, -180, 180)) return null;
            if (!saved.savedAt || Date.now() - saved.savedAt > HOME_LOCATION_MAX_AGE_MS) {
                localStorage.removeItem(HOME_LOCATION_KEY);
                return null;
            }
            return { lat: Number(saved.lat), lng: Number(saved.lng) };
        } catch (error) {
            return null;
        }
    }

    function storeHomeLocation(lat, lng) {
        try {
            localStorage.setItem(HOME_LOCATION_KEY, JSON.stringify({
                lat: Number(lat),
                lng: Number(lng),
                savedAt: Date.now()
            }));
        } catch (error) {
            // Private browsing or storage restrictions should not block homepage use.
        }
    }

    function redirectHomeWithLocation(lat, lng) {
        const url = new URL(window.location.href);
        const alreadyHasLocation = validCoordinate(url.searchParams.get('lat'), -90, 90)
            && validCoordinate(url.searchParams.get('lng'), -180, 180);
        if (alreadyHasLocation) return;

        url.searchParams.set('lat', String(lat));
        url.searchParams.set('lng', String(lng));
        if (!url.searchParams.has('sort') || url.searchParams.get('sort') === 'recent') {
            url.searchParams.set('sort', 'nearest');
        }
        window.location.replace(url.toString());
    }

    function distanceKm(lat1, lng1, lat2, lng2) {
        const earthRadiusKm = 6371;
        const toRadians = value => value * Math.PI / 180;
        const dLat = toRadians(lat2 - lat1);
        const dLng = toRadians(lng2 - lng1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
            + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2))
            * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return earthRadiusKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    function prioritizeHomepageMap(lat, lng) {
        const status = document.getElementById('map-status');
        if (!status || status.dataset.locationPriorityApplied === 'true') return;

        const applyWhenReady = function () {
            const text = status.textContent || '';
            if (text.includes('Loading more')) return;

            try {
                if (typeof mapClusterGroup === 'undefined' || !mapClusterGroup || typeof mapInstance === 'undefined' || !mapInstance) {
                    return;
                }

                const nearbyPoints = [];
                mapClusterGroup.getLayers().forEach(function (layer) {
                    if (typeof layer.getLatLng !== 'function') return;
                    const point = layer.getLatLng();
                    if (distanceKm(lat, lng, point.lat, point.lng) <= HOME_LOCAL_RADIUS_KM) {
                        nearbyPoints.push([point.lat, point.lng]);
                    }
                });

                status.dataset.locationPriorityApplied = 'true';
                if (nearbyPoints.length) {
                    nearbyPoints.push([lat, lng]);
                    mapInstance.fitBounds(nearbyPoints, { padding: [40, 40], maxZoom: 14 });
                    status.textContent = `${nearbyPoints.length - 1} nearby price report${nearbyPoints.length === 2 ? '' : 's'} prioritized · ${text}`;
                } else if (typeof fitAllPrices === 'function') {
                    fitAllPrices();
                    status.textContent = `No nearby price reports yet · Showing all available locations · ${text}`;
                }
            } catch (error) {
                // Keep the normal map behavior if location prioritization cannot be applied.
            }
        };

        const observer = new MutationObserver(applyWhenReady);
        observer.observe(status, { childList: true, characterData: true, subtree: true });
        window.setTimeout(applyWhenReady, 1200);
    }

    function initializeLocationFirstHomepage() {
        if (!document.getElementById('price-feed') || !document.getElementById('map')) return;

        const url = new URL(window.location.href);
        const latParam = url.searchParams.get('lat');
        const lngParam = url.searchParams.get('lng');
        if (validCoordinate(latParam, -90, 90) && validCoordinate(lngParam, -180, 180)) {
            const lat = Number(latParam);
            const lng = Number(lngParam);
            storeHomeLocation(lat, lng);
            prioritizeHomepageMap(lat, lng);
            return;
        }

        const stored = readStoredHomeLocation();
        if (stored) {
            redirectHomeWithLocation(stored.lat, stored.lng);
            return;
        }

        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
            function (position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                if (!validCoordinate(lat, -90, 90) || !validCoordinate(lng, -180, 180)) return;
                storeHomeLocation(lat, lng);
                redirectHomeWithLocation(lat, lng);
            },
            function () {
                // Location is optional. The homepage keeps the existing global fallback.
            },
            {
                enableHighAccuracy: false,
                timeout: 5000,
                maximumAge: 30 * 60 * 1000
            }
        );
    }

    document.addEventListener('DOMContentLoaded', initializeLocationFirstHomepage);

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