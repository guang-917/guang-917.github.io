const CACHE = 'kb-workbench-v1';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './icon-apple.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(ASSETS); }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (ks) {
      return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  var u = new URL(e.request.url);
  if (u.origin !== self.location.origin) return;

  // 页面导航：网络优先，失败回退缓存的 index.html（离线也能开）
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).then(function (r) {
        var cp = r.clone();
        caches.open(CACHE).then(function (c) { c.put('./index.html', cp); });
        return r;
      }).catch(function () { return caches.match('./index.html'); })
    );
    return;
  }

  // 静态资源：缓存优先，回源并写入缓存
  e.respondWith(
    caches.match(e.request).then(function (hit) {
      if (hit) return hit;
      return fetch(e.request).then(function (r) {
        if (r.ok && /\.(png|webmanifest|js|css|html|svg|woff2?)$/.test(u.pathname)) {
          var cp = r.clone();
          caches.open(CACHE).then(function (c) { c.put(e.request, cp); });
        }
        return r;
      }).catch(function () { return caches.match(e.request); });
    })
  );
});
