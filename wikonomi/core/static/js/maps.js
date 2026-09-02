/* Wikonomi coordinates remain [latitude, longitude]; only this boundary reverses
 * them for Mapbox. H3 indexing and nearby queries remain server-side. */
(function (global) {
    'use strict';
    const configNode = document.getElementById('wikonomi-map-config');
    const config = configNode ? JSON.parse(configNode.textContent) : {};
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g,
        char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
    const lngLat = value => Array.isArray(value) ? [Number(value[1]), Number(value[0])] : [Number(value.lng), Number(value.lat)];
    let groupId = 0;

    class PriceMap {
        constructor(container, options = {}) {
            this.groups = [];
            this.markers = [];
            this.removed = false;
            this.fallbackReason = !config.accessToken ? 'not-configured'
                : !global.mapboxgl ? 'sdk-unavailable'
                : !global.mapboxgl.supported() ? 'webgl-unsupported' : '';
            this.native = !this.fallbackReason;
            if (this.native) {
                try {
                    this.engine = new global.mapboxgl.Map({
                        container, accessToken: config.accessToken,
                        style: config.style || 'mapbox://styles/mapbox/streets-v12',
                        center: [147.1803, -9.4438], zoom: 12, maxZoom: 19,
                        attributionControl: true, dragRotate: false, pitchWithRotate: false,
                    });
                    this.engine.touchZoomRotate.disableRotation();
                    this.engine.addControl(new global.mapboxgl.NavigationControl({showCompass: false}), 'top-right');
                    if (options.scrollWheelZoom === false) this.engine.scrollZoom.disable();
                    this.engine.on('error', () => this.showError());
                    this.engine.on('idle', () => { if (this.notice) this.notice.hidden = true; });
                } catch (error) {
                    document.getElementById(container).replaceChildren();
                    this.native = false;
                    this.fallbackReason = 'initialization-failed';
                }
            }
            if (!this.native) {
                this.engine = global.L.map(container, options);
                global.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                }).addTo(this.engine);
            }
            // Expose provider diagnostics without tokens or user data for support.
            const element = document.getElementById(container);
            element.setAttribute('data-map-provider', this.native ? 'mapbox' : 'leaflet');
            element.setAttribute('data-map-fallback-reason', this.fallbackReason);
            // Handles mobile overlays and desktop panel changes without another map load.
            if (global.ResizeObserver) {
                this.observer = new global.ResizeObserver(() => this.invalidateSize());
                this.observer.observe(document.getElementById(container));
            }
        }
        showError() {
            if (this.removed) return;
            if (!this.notice) {
                this.notice = document.createElement('div');
                this.notice.className = 'wk-map-notice';
                this.notice.setAttribute('role', 'status');
                this.notice.textContent = 'The background map could not load. You can still use the price list and saved locations.';
                this.engine.getContainer().appendChild(this.notice);
            }
            this.notice.hidden = false;
        }
        setView(position, zoom) {
            if (this.native) this.engine.jumpTo({center: lngLat(position), zoom});
            else this.engine.setView(position, zoom);
            return this;
        }
        fitBounds(points, options = {}) {
            if (!points.length) return this;
            if (this.native) {
                const bounds = new global.mapboxgl.LngLatBounds();
                points.forEach(point => bounds.extend(lngLat(point)));
                this.engine.fitBounds(bounds, {padding: Math.max(...(options.padding || [40, 40])), maxZoom: options.maxZoom || 15, duration: 0});
            } else this.engine.fitBounds(points, options);
            return this;
        }
        on(event, callback) {
            this.engine.on(event, this.native && event === 'click' ? e => callback({latlng: {lat: e.lngLat.lat, lng: e.lngLat.lng}}) : callback);
            return this;
        }
        addLayer(group) { group.addTo(this); return this; }
        invalidateSize() {
            if (!this.removed) this.native ? this.engine.resize() : this.engine.invalidateSize();
            return this;
        }
        remove() {
            this.removed = true;
            if (this.observer) this.observer.disconnect();
            this.groups.forEach(group => group.remove());
            this.markers.forEach(marker => marker.remove());
            this.engine.remove();
        }
    }

    class Pin {
        constructor(position, options = {}, circle = false) {
            this.position = position;
            this.options = options;
            this.circle = circle;
            this.html = '';
        }
        addTo(map) {
            if (this.attached) return this;
            this.attached = true;
            this.map = map;
            if (!map.markers.includes(this)) map.markers.push(this);
            if (this.engine) { this.engine.addTo(map.engine); return this; }
            const options = this.options;
            if (map.native) {
                const markerOptions = {color: options.color || '#4B2798'};
                if (options.icon || this.circle) {
                    const element = document.createElement('div');
                    if (this.circle) {
                        const diameter = (options.radius || 8) * 2;
                        element.style.cssText = `width:${diameter}px;height:${diameter}px;border-radius:50%;border:2px solid ${options.color || '#4B2798'};background:${options.fillColor || '#4B2798'};opacity:${options.fillOpacity ?? 0.9}`;
                        markerOptions.anchor = 'center';
                    } else {
                        element.className = options.icon.className || '';
                        element.innerHTML = options.icon.html || '';
                        markerOptions.anchor = 'bottom';
                    }
                    element.classList.add('wk-map-pin');
                    markerOptions.element = element;
                }
                this.engine = new global.mapboxgl.Marker(markerOptions).setLngLat(lngLat(this.position)).addTo(map.engine);
                this.engine.getElement().setAttribute('aria-label', 'View location details');
                this.engine.getElement().setAttribute('role', 'button');
                this.engine.getElement().tabIndex = 0;
                this.engine.getElement().addEventListener('keydown', event => {
                    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); this.engine.togglePopup(); }
                });
            } else {
                const leafOptions = {...options};
                if (options.icon) leafOptions.icon = global.L.divIcon(options.icon);
                else if (options.color && !this.circle) leafOptions.icon = global.L.divIcon({
                    className: 'wk-map-pin', iconSize: [20, 20], iconAnchor: [10, 10],
                    html: `<span style="display:block;width:20px;height:20px;border-radius:50%;border:2px solid white;background:${escapeHtml(options.color)}"></span>`,
                });
                this.engine = (this.circle ? global.L.circleMarker(this.position, leafOptions) : global.L.marker(this.position, leafOptions)).addTo(map.engine);
            }
            if (this.html) this.bindPopup(this.html);
            return this;
        }
        bindPopup(html) {
            this.html = html;
            if (this.engine) {
                if (this.map.native) this.engine.setPopup(new global.mapboxgl.Popup({maxWidth: '300px'}).setHTML(html));
                else this.engine.bindPopup(html);
            }
            return this;
        }
        openPopup() { if (this.engine) this.map.native ? this.engine.togglePopup() : this.engine.openPopup(); return this; }
        setLatLng(position) {
            this.position = position;
            if (this.engine) this.map.native ? this.engine.setLngLat(lngLat(position)) : this.engine.setLatLng(position);
            return this;
        }
        remove() { if (this.engine && this.attached) this.engine.remove(); this.attached = false; }
    }

    class PinGroup {
        constructor(options = {}) { this.options = options; this.pins = []; this.id = `wk-prices-${++groupId}`; }
        addLayer(pin) { this.pins.push(pin); return this; }
        addTo(map) {
            this.map = map;
            map.groups.push(this);
            if (!map.native) {
                this.leafGroup = global.L.markerClusterGroup(this.options);
                this.pins.forEach(pin => {
                    pin.addTo(map);
                    map.engine.removeLayer(pin.engine);
                    this.leafGroup.addLayer(pin.engine);
                });
                map.engine.addLayer(this.leafGroup);
                return this;
            }
            const engine = map.engine;
            this.setup = () => {
                if (map.removed) return;
                engine.addSource(this.id, {
                    type: 'geojson', maxzoom: 20, cluster: true, clusterMaxZoom: 19,
                    clusterRadius: this.options.maxClusterRadius || 45,
                    data: {type: 'FeatureCollection', features: this.pins.map((pin, index) => ({
                        type: 'Feature', properties: {index}, geometry: {type: 'Point', coordinates: lngLat(pin.position)},
                    }))},
                });
                engine.addLayer({id: this.id, type: 'circle', source: this.id, filter: ['has', 'point_count'],
                    paint: {'circle-color': '#4B2798', 'circle-radius': 21, 'circle-stroke-width': 3, 'circle-stroke-color': '#4DB8FF'}});
                engine.addLayer({id: `${this.id}-count`, type: 'symbol', source: this.id, filter: ['has', 'point_count'],
                    layout: {'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12}, paint: {'text-color': '#ffffff'}});
                // Transparent unclustered layer ensures source tiles are available at every zoom.
                engine.addLayer({id: `${this.id}-points`, type: 'circle', source: this.id, filter: ['!', ['has', 'point_count']], paint: {'circle-opacity': 0}});
                this.render = () => {
                    if (!engine.isSourceLoaded(this.id)) return;
                    const visible = new Set(engine.querySourceFeatures(this.id).filter(f => !f.properties.cluster).map(f => Number(f.properties.index)));
                    this.pins.forEach((pin, index) => visible.has(index) ? pin.addTo(map) : pin.remove());
                };
                engine.on('render', this.render);
                engine.on('click', this.id, event => {
                    const feature = event.features[0];
                    const source = engine.getSource(this.id);
                    const cluster = feature.properties.cluster_id;
                    // At close zoom show all colocated prices, rather than hiding overlapping pins.
                    if (engine.getZoom() >= 17) {
                        source.getClusterLeaves(cluster, this.pins.length, 0, (error, leaves) => {
                            if (error || map.removed) return;
                            new global.mapboxgl.Popup({maxWidth: '320px'}).setLngLat(feature.geometry.coordinates)
                                .setHTML('<div class="wk-map-price-list">' + leaves.map(f => this.pins[f.properties.index].html).join('<hr>') + '</div>').addTo(engine);
                        });
                    } else source.getClusterExpansionZoom(cluster, (error, zoom) => {
                        if (!error && !map.removed) engine.easeTo({center: feature.geometry.coordinates, zoom: Math.min(zoom, 17)});
                    });
                });
                engine.on('mouseenter', this.id, () => { engine.getCanvas().style.cursor = 'pointer'; });
                engine.on('mouseleave', this.id, () => { engine.getCanvas().style.cursor = ''; });
            };
            if (engine.isStyleLoaded()) this.setup();
            else engine.once('load', this.setup);
            return this;
        }
        remove() {
            if (this.map.native) {
                this.map.engine.off('load', this.setup);
                if (this.render) this.map.engine.off('render', this.render);
            }
            this.pins.forEach(pin => pin.remove());
        }
    }

    // Compare only identical product/currency groups, never rice against a fridge.
    function priceTiers(items) {
        const groups = new Map();
        items.forEach(item => {
            const key = JSON.stringify([item.productId, item.currency]);
            if (!item.productId || !item.currency || !Number.isFinite(item.rawPrice)) return;
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(item.rawPrice);
        });
        return items.map(item => {
            const values = groups.get(JSON.stringify([item.productId, item.currency])) || [];
            const min = Math.min(...values), max = Math.max(...values);
            if (values.length < 2 || min === max) return 'other';
            return item.rawPrice === min ? 'cheap' : item.rawPrice === max ? 'expensive' : 'mid';
        });
    }
    global.WkMaps = {
        map: (container, options) => new PriceMap(container, options),
        marker: (position, options) => new Pin(position, options),
        circleMarker: (position, options) => new Pin(position, options, true),
        divIcon: options => options,
        markerClusterGroup: options => new PinGroup(options),
        escapeHtml, priceTiers,
    };
})(window);
