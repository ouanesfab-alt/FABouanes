const VERSION = "fabouanes-v37-offline-hardening";
const STATIC_CACHE = `${VERSION}-static`;
const RUNTIME_CACHE = `${VERSION}-runtime`;
const OFFLINE_URL = "/static/offline.html";
const MAX_RUNTIME_ENTRIES = 40;

// Pages online-only → fallback offline.html si hors-ligne
const ONLINE_ONLY_PREFIXES = ["/reports", "/production", "/admin", "/purchases"];

const PRECACHE = [
  OFFLINE_URL,
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/favicon.png",
  "/static/fab_logo.webp",
  "/static/desktop_logo_shield.webp",
  "/static/dashboard.webp",
  "/static/fab_invoice_logo.png",
  "/static/fab_invoice_logo_clean.webp",

  "/static/fonts/PlusJakartaSans-Regular.ttf",
  "/static/fonts/PlusJakartaSans-Bold.ttf",
  "/static/fonts/PlusJakartaSans-Regular.woff2",
  "/static/fonts/PlusJakartaSans-Bold.woff2",
  "/static/app.css",
  "/static/app.js",
  "/static/css/tokens.css",
  "/static/css/components.css",
  "/static/js/api.js",
  "/static/js/forms.js",
  "/static/js/theme.js",
  "/static/js/layout.js",
  "/static/js/tables.js",
  "/static/js/notifications.js",
  "/static/js/offline-db.js",
  "/static/js/offline-sync.js",
  "/static/css/bootstrap.min.css",
  "/static/css/bootstrap-icons.css",
  "/static/js/bootstrap.bundle.min.js",
  "/static/css/fonts/bootstrap-icons.woff2",
  "/static/css/fonts/bootstrap-icons.woff"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(PRECACHE).catch(() => null)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => ![STATIC_CACHE, RUNTIME_CACHE].includes(key)).map(key => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("message", event => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  const cache = await caches.open(STATIC_CACHE);
  cache.put(request, response.clone());
  return response;
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(request, response.clone());
    trimCache(RUNTIME_CACHE, MAX_RUNTIME_ENTRIES);
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) return cached;
    if (request.mode === "navigate") {
      return caches.match(OFFLINE_URL);
    }
    throw error;
  }
}

async function trimCache(cacheName, maxEntries) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length <= maxEntries) return;
  await cache.delete(keys[0]);
  return trimCache(cacheName, maxEntries);
}

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  // Laisser passer les requêtes API (POST offline sync inclus)
  if (url.pathname.startsWith("/api/")) return;

  const isStaticAsset = url.origin === self.location.origin && (
    url.pathname.startsWith("/static/") ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".webp") ||
    url.pathname.endsWith(".jpg") ||
    url.pathname.endsWith(".svg")
  );

  // Pages online-only → offline.html si hors-ligne
  const isOnlineOnly = ONLINE_ONLY_PREFIXES.some(p => url.pathname.startsWith(p));
  if (isOnlineOnly) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  const isApiGet = url.origin === self.location.origin && url.pathname.startsWith("/api/");
  const isDocument = event.request.mode === "navigate" || event.request.headers.get("accept")?.includes("text/html");

  if (isStaticAsset || url.hostname.includes("jsdelivr")) {
    event.respondWith(cacheFirst(event.request));
    return;
  }
  if (isApiGet || isDocument) {
    event.respondWith(networkFirst(event.request));
  }
});
