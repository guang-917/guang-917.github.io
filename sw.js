const VERSION = '4';
const CACHE = 'kb-workbench-v' + VERSION;
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

// 页面可发 SKIP_WAITING 让等待中的新 SW 立即接管
self.addEventListener('message', function (e) {
  if (e.data && e.data.type === 'SKIP_WAITING') { self.skipWaiting(); }
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (ks) {
      return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
      .then(function () {
        // 新版 SW 接管后，通知所有已打开页面去拉最新 index.html 并刷新，
        // 避免旧页面继续停留在旧版本（部署后用户无需手动重开）
        return self.clients.matchAll({ type: 'window' });
      })
      .then(function (cs) { (cs || []).forEach(function (c) { c.postMessage({ type: 'SW_UPDATED', version: VERSION }); }); })
  );
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  var u = new URL(e.request.url);
  if (u.origin !== self.location.origin) return;

  // 版本探针：永远走网络，绝不缓存，保证页面能实时比对到最新版本号
  if (u.pathname.indexOf('version.json') >= 0) {
    e.respondWith(fetch(e.request, { cache: 'no-store' }).catch(function () { return new Response('{}', { headers: { 'Content-Type': 'application/json' } }); }));
    return;
  }

  // 页面导航：强制绕过浏览器/CDN 缓存拿最新 index.html（部署后立即可见）；
  // 仅当网络彻底失败时才回退到缓存副本（保证离线可开）
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' }).then(function (r) {
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
