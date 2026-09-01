const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('wikonomi/core/static/js/maps.js', 'utf8');

function harness({token = 'pk.test', supported = true, sdk = true, loaded = true} = {}) {
    const elements = new Map();
    const element = () => ({style: {}, classList: {add() {}}, setAttribute() {}, addEventListener() {}, appendChild() {}, replaceChildren() {}});
    const calls = {mapbox: 0, leaflet: 0, tiles: 0, markerAdds: 0, popups: []};
    class Engine {
        constructor(options) { this.options = options; this.events = {}; this.sources = {}; this.touchZoomRotate = {disableRotation() {}}; this.scrollZoom = {disable() {}}; }
        on(event, layer, cb) { this.events[cb ? event + ':' + layer : event] = cb || layer; return this; }
        once(event, cb) { return this.on(event, cb); }
        off(event) { delete this.events[event]; }
        jumpTo(value) { this.view = value; }
        setView(position, zoom) { this.view = {position, zoom}; }
        fitBounds(bounds, options) { this.bounds = {bounds, options}; }
        addControl() {} resize() { this.resized = true; } invalidateSize() { this.resized = true; }
        getContainer() { return element(); } getCanvas() { return element(); }
        remove() { this.removed = true; } addLayer() {} removeLayer() {}
        isStyleLoaded() { return loaded; } isSourceLoaded() { return true; }
        addSource(id, value) { this.sources[id] = value; }
        querySourceFeatures() { return this.features || []; }
        getZoom() { return this.zoom || 12; }
        easeTo(value) { this.eased = value; }
        getSource(id) { return {
            getClusterExpansionZoom: (cluster, cb) => cb(null, 18),
            getClusterLeaves: (cluster, limit, offset, cb) => cb(null, this.sources[id].data.features),
        }; }
    }
    class Marker {
        constructor(options) { this.options = options; this.element = element(); }
        setLngLat(value) { this.position = value; return this; }
        addTo() { calls.markerAdds++; return this; }
        getElement() { return this.element; }
        setPopup(value) { this.popup = value; return this; }
        togglePopup() { this.open = true; } remove() { this.removed = true; }
        bindPopup(value) { this.html = value; return this; }
        setLatLng(value) { this.position = value; return this; }
    }
    class Popup {
        setHTML(value) { this.html = value; return this; }
        setLngLat(value) { this.position = value; return this; }
        addTo() { calls.popups.push(this); return this; }
    }
    const document = {
        getElementById(id) { if (id === 'wikonomi-map-config') return {textContent: JSON.stringify({accessToken: token})}; if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
        createElement: element,
    };
    const L = {
        map(id, options) { calls.leaflet++; return new Engine(options); },
        tileLayer() { calls.tiles++; return {addTo() {}}; },
        marker(position, options) { return new Marker(options).setLatLng(position); },
        circleMarker(position, options) { return new Marker(options).setLatLng(position); },
        divIcon: options => options,
        markerClusterGroup: () => ({addLayer() {}}),
    };
    const window = {L};
    if (sdk) window.mapboxgl = {
        supported: () => supported,
        Map: class extends Engine { constructor(options) { super(options); calls.mapbox++; } },
        Marker, Popup, NavigationControl: class {},
        LngLatBounds: class { constructor() { this.points = []; } extend(point) { this.points.push(point); } },
    };
    vm.runInNewContext(source, {window, document});
    return {api: window.WkMaps, calls};
}
const plain = value => JSON.parse(JSON.stringify(value));

test('Mapbox converts map, bounds, pins and clicks at the latitude/longitude boundary', () => {
    const {api, calls} = harness();
    const map = api.map('map').setView([-9.4438, 147.1803], 15);
    assert.deepEqual(plain(map.engine.view), {center: [147.1803, -9.4438], zoom: 15});
    const pin = api.marker([-9, 147]).addTo(map).bindPopup('Saved location');
    assert.deepEqual(plain(pin.engine.position), [147, -9]);
    pin.setLatLng({lat: 0, lng: 148});
    assert.deepEqual(plain(pin.engine.position), [148, 0]);
    let clicked;
    map.on('click', event => { clicked = event.latlng; });
    map.engine.events.click({lngLat: {lat: -8, lng: 149}});
    assert.deepEqual(plain(clicked), {lat: -8, lng: 149});
    map.fitBounds([[-9, 147], [-8, 149]], {padding: [40, 40], maxZoom: 14});
    assert.deepEqual(plain(map.engine.bounds.bounds.points), [[147, -9], [149, -8]]);
    map.invalidateSize(); map.invalidateSize();
    assert.equal(calls.mapbox, 1);
    assert.equal(calls.tiles, 0);
    map.remove(); assert.equal(map.engine.removed, true);
});
for (const options of [{token: ''}, {sdk: false}, {supported: false}]) {
    test('Fallback retains locations: ' + JSON.stringify(options), () => {
        const {api, calls} = harness(options);
        const map = api.map('map').setView([-9, 147], 13);
        const pin = api.marker([-9, 147]).addTo(map);
        pin.setLatLng({lat: -8, lng: 148});
        assert.deepEqual(plain(pin.engine.position), {lat: -8, lng: 148});
        assert.equal(calls.leaflet, 1); assert.equal(calls.tiles, 1); assert.equal(calls.mapbox, 0);
    });
}
test('Clusters preserve coordinates, avoid marker churn and expose colocated prices', () => {
    const {api, calls} = harness();
    const map = api.map('map');
    const group = api.markerClusterGroup().addLayer(api.marker([-9, 147]).bindPopup('Price one')).addLayer(api.marker([-9, 147]).bindPopup('Price two'));
    map.addLayer(group);
    assert.deepEqual(plain(map.engine.sources[group.id].data.features[0].geometry.coordinates), [147, -9]);
    map.engine.features = [{properties: {index: 0}}];
    map.engine.events.render(); map.engine.events.render();
    assert.equal(calls.markerAdds, 1);
    map.engine.zoom = 17;
    map.engine.events['click:' + group.id]({features: [{properties: {cluster_id: 1}, geometry: {coordinates: [147, -9]}}]});
    assert.match(calls.popups[0].html, /Price one.*Price two/);
    map.remove(); assert.equal(map.engine.events.render, undefined);
});
test('Removal before style load cancels cluster setup', () => {
    const {api} = harness({loaded: false});
    const map = api.map('map');
    map.addLayer(api.markerClusterGroup());
    assert.equal(typeof map.engine.events.load, 'function');
    map.remove(); assert.equal(map.engine.events.load, undefined);
});
test('Price colours compare only the same product and currency; equal and singleton prices stay neutral', () => {
    const {api} = harness();
    const items = [
        {productId: 1, currency: 'PGK', rawPrice: 10},
        {productId: 1, currency: 'PGK', rawPrice: 20},
        {productId: 1, currency: 'PGK', rawPrice: 15},
        {productId: 2, currency: 'PGK', rawPrice: 1},
        {productId: 1, currency: 'USD', rawPrice: 1},
        {productId: 3, currency: 'PGK', rawPrice: 5},
        {productId: 3, currency: 'PGK', rawPrice: 5},
    ];
    assert.deepEqual(plain(api.priceTiers(items)), ['cheap', 'expensive', 'mid', 'other', 'other', 'other', 'other']);
    assert.equal(api.escapeHtml('<img onerror="x">'), '&lt;img onerror=&quot;x&quot;&gt;');
});
