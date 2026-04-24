// Self-destruct service worker: unregisters itself and clears all caches
// on install. Kept because a previous V3 build registered a cache-first SW
// that is still lingering in some browsers, blocking UI edits from appearing.
// Once every affected browser has picked up this file, this SW can be deleted.

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    const regs = await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach((c) => c.navigate(c.url));
  })());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
