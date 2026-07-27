// FABouanes PWA Service Worker
const CACHE_NAME = 'fabouanes-v1';
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/static/icon_512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request);
    })
  );
});
