// Service worker: makes the app open instantly and keeps recipes readable offline.
const VERSION = "__VERSION__";
const SHELL = "recipes-shell-" + VERSION;
const DATA = "recipes-data-v1";
const IMAGES = "recipes-img-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL).then((c) =>
      c.addAll([
        "/recipes/",
        `/recipes/static/app.css?v=${VERSION}`,
        `/recipes/static/app.js?v=${VERSION}`,
        "/recipes/static/icons/icon-180.png",
      ]).catch(() => {})
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k.startsWith("recipes-shell-") && k !== SHELL).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Signed media URLs change on every fetch: cache images by path only.
function imageKey(url) {
  const u = new URL(url);
  return u.origin + u.pathname;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // App shell: stale-while-revalidate.
  if (url.pathname === "/recipes/" || url.pathname.startsWith("/recipes/static/")) {
    event.respondWith(
      caches.open(SHELL).then(async (cache) => {
        const hit = await cache.match(req, { ignoreSearch: url.pathname === "/recipes/" });
        const net = fetch(req).then((res) => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => hit);
        return hit || net;
      })
    );
    return;
  }

  // Recipe images: cache first.
  if (/^\/api\/recipes\/media\/[^/]+\/(poster|image)\.jpg$/.test(url.pathname)) {
    event.respondWith(
      caches.open(IMAGES).then(async (cache) => {
        const key = imageKey(req.url);
        const hit = await cache.match(key);
        if (hit) return hit;
        const res = await fetch(req);
        if (res.ok) cache.put(key, res.clone());
        return res;
      })
    );
    return;
  }

  // Recipe JSON: network first, cached copy when offline.
  if (url.pathname.startsWith("/api/recipes") && !url.pathname.startsWith("/api/recipes/media/")) {
    event.respondWith(
      fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(DATA).then((c) => c.put(url.pathname, copy)); }
        return res;
      }).catch(() => caches.open(DATA).then((c) => c.match(url.pathname)).then((hit) => hit || Response.error()))
    );
  }
});
