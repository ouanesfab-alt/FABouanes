// FABOuanes ERP — Robust PWA Service Worker v2.0
const CACHE_NAME = 'fabouanes-v2.0';

const STATIC_ASSETS = [
  '/',
  '/static/offline.html',
  '/static/css/bootstrap.min.css',
  '/static/css/bootstrap-icons.css',
  '/static/css/tokens.css',
  '/static/css/components.css',
  '/static/app.css',
  '/static/fonts/fonts.css',
  '/static/fonts/PlusJakartaSans-Regular.ttf',
  '/static/fonts/PlusJakartaSans-Bold.ttf',
  '/static/js/main.js',
  '/static/js/modules/shortcuts.js',
  '/static/js/offline-db.js',
  '/static/js/offline-sync.js',
  '/static/manifest.json',
  '/static/icon-512.png',
  '/static/icon-192.png',
  '/static/favicon.png'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn("[SW] Dynamic asset cache warn:", err);
      });
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  
  // Ignore non-GET or API POST requests
  if (request.method !== 'GET' || request.url.includes('/api/') || request.url.includes('/login')) {
    return;
  }

  // HTML Page Navigation: Network first, fall back to cache then offline.html
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => {
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) return cachedResponse;
            return caches.match('/static/offline.html') || caches.match('/');
          });
        })
    );
    return;
  }

  // Static Assets (CSS, JS, Images, Fonts): Cache first, background revalidate
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      const fetchPromise = fetch(request).then((networkResponse) => {
        if (networkResponse.status === 200) {
          const copy = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return networkResponse;
      }).catch(() => null);

      return cachedResponse || fetchPromise;
    })
  );
});
