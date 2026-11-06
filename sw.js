/* 备考刷题 Service Worker
   策略：页面导航一律网络优先（更新发布后用户刷新即拿最新版），失败才回退缓存；
   静态资源（图标等）缓存优先。 */
const CACHE = 'beikao-v2';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  /* 页面导航：网络优先，回退缓存（离线可用） */
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    e.respondWith(
      fetch(req).then(resp => {
        if (!resp.ok) throw 0;   // 服务器报错时回退到缓存副本
        const copy = resp.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
        caches.open(CACHE).then(c => c.put('./index.html', resp.clone()));
        return resp;
      }).catch(() => caches.match(req, { ignoreSearch: true })
        .then(hit => hit || caches.match('./index.html')))
    );
    return;
  }
  /* 其余静态资源：缓存优先 */
  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then(hit =>
      hit || fetch(req).then(resp => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
        }
        return resp;
      })
    )
  );
});
