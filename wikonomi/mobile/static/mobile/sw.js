/* Never cache authenticated HTML, searches, API results, or price photos. */
const CACHE = "wikonomi-mobile-static-v1";
const ASSETS = [
  "/static/mobile/app.css",
  "/static/mobile/app.js",
  "/static/mobile/offline.html",
  "/static/mobile/icons/icon.svg"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key.startsWith("wikonomi-mobile-") && key !== CACHE)
        .map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
    return;
  }
  if (event.request.mode === "navigate" && url.pathname.startsWith("/app/")) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/static/mobile/offline.html"))
    );
  }
});
