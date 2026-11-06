/* UTCT tracker service worker.
   Purpose: the app must open even with no signal on the mountain.

   The page itself is network-FIRST so a republished version reaches everyone's
   phone on the next open rather than being pinned to a stale cache; the cached
   copy is the fallback when there's no signal. Race data (api.php) never caches. */

const CACHE = 'utct-shell-v3';
const SHELL = ['./', './index.html', './manifest.webmanifest'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;                 // POSTs always go to the network
  if (url.pathname.endsWith('/api.php')) return;          // never cache race data

  const isPage = e.request.mode === 'navigate' || url.pathname.endsWith('/index.html');

  if (isPage) {
    /* no-store: a plain fetch() inside a worker still consults the browser's
       HTTP cache, which is how a phone can sit on an old build even though this
       is network-first. Going straight to the network is the whole point here. */
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .then(res => {
          if (res && res.ok && url.origin === location.origin) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, copy));
          }
          return res;
        })
        .catch(() => caches.match(e.request).then(hit => hit || caches.match('./index.html')))
    );
    return;
  }

  e.respondWith(
    caches.match(e.request).then(hit => {
      const net = fetch(e.request)
        .then(res => {
          if (res && res.ok && url.origin === location.origin) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || net;
    })
  );
});
