/* Keep an opt-in nearby map centered exactly on the user's position.
 * Leaflet calculates a zoom suitable for the currently selected distance ring.
 * This helper deliberately does not access browser geolocation or request data.
 */
(function (root, factory) {
    'use strict';
    const api = factory();
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (root) root.WikonomiNearbyMapFocus = api;
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    const supportedRadiiKm = [1, 5, 10, 25];

    function validCoordinates(lat, lng) {
        return Number.isFinite(lat) && lat >= -90 && lat <= 90
            && Number.isFinite(lng) && lng >= -180 && lng <= 180;
    }

    function focus(map, lat, lng, radiusKm, radiusCircle) {
        const latitude = Number(lat);
        const longitude = Number(lng);
        const radius = Number(radiusKm);
        if (!map || !radiusCircle || !validCoordinates(latitude, longitude)
            || !supportedRadiiKm.includes(radius)) return false;

        // Fit the selected circle in the available mobile/desktop viewport
        // without shifting the map's center away from the user location pin.
        const size = map.getSize();
        const shortestSide = Math.min(size.x, size.y);
        const padding = Math.max(12, Math.min(48, Math.floor(shortestSide * 0.10)));
        const zoomForRadius = map.getBoundsZoom(
            radiusCircle.getBounds(), false, [padding * 2, padding * 2]
        );
        const zoom = Number.isFinite(zoomForRadius)
            ? Math.max(8, Math.min(16, zoomForRadius))
            : 12;
        map.setView([latitude, longitude], zoom, { animate: false });
        return true;
    }

    return { focus, validCoordinates };
});
