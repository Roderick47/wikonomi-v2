const test = require('node:test');
const assert = require('node:assert/strict');
const {focus, validCoordinates} = require('../../static/js/nearby-map-focus.js');

function createMap(zoom) {
    const calls = [];
    return {
        calls,
        getSize: () => ({x: 375, y: 300}),
        getBoundsZoom: (bounds, inside, padding) => {
            calls.push({kind: 'bounds', bounds, inside, padding});
            return zoom ?? {1: 15, 5: 13, 10: 12, 25: 10}[bounds.radiusKm];
        },
        setView: (location, level, options) => {
            calls.push({kind: 'setView', location, level, options});
        },
    };
}

for (const radius of [1, 5, 10, 25]) {
    test(`nearby radius ${radius} km keeps the user's pin at the exact center`, () => {
        const map = createMap();
        const ring = {getBounds: () => ({radiusKm: radius})};
        assert.equal(focus(map, -9.4438, 147.1803, radius, ring), true);
        const calls = map.calls;
        const bounds = calls.find(call => call.kind === 'bounds');
        const view = calls.find(call => call.kind === 'setView');
        assert.equal(bounds.bounds.radiusKm, radius);
        assert.equal(bounds.inside, false);
        assert.ok(bounds.padding[0] > 0);
        assert.deepEqual(view.location, [-9.4438, 147.1803]);
        assert.equal(view.level, {1: 15, 5: 13, 10: 12, 25: 10}[radius]);
        assert.deepEqual(view.options, {animate: false});
    });
}

test('an invalid location or unsupported radius does not move the map', () => {
    const ring = {getBounds: () => ({radiusKm: 5})};
    for (const [lat, lng, radius] of [[91, 147, 5], [-9, 190, 5], [NaN, 0, 5], [-9, 147, 100], [-9, 147, 0]]) {
        const map = createMap();
        assert.equal(focus(map, lat, lng, radius, ring), false);
        assert.equal(map.calls.length, 0);
    }
    assert.equal(validCoordinates(-9.4438, 147.1803), true);
    assert.equal(validCoordinates(999, 147.1803), false);
});

test('bounds calculations are clamped to usable zoom levels', () => {
    for (const [estimate, wanted] of [[23, 16], [2, 8], [Infinity, 12], [NaN, 12]]) {
        const map = createMap(estimate);
        const ring = {getBounds: () => ({radiusKm: 1})};
        focus(map, -6.73, 146.99, 1, ring);
        const view = map.calls.find(call => call.kind === 'setView');
        assert.equal(view.level, wanted);
    }
});

test('no user coordinates or no map/ring means no map movement', () => {
    const map = createMap();
    assert.equal(focus(null, -9.4, 147.2, 5, {}), false);
    assert.equal(focus(map, -9.4, 147.2, 5, null), false);
    assert.equal(map.calls.length, 0);
});
