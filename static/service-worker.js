const CACHE_NAME = 'mercado-v3';
const urlsToCache = [
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/fundo-escritorio.jpg',
  '/static/offline.html',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/static/offline.html'))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(response => response || fetch(request))
  );
});
