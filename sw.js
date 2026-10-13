// 方針: キャッシュがあれば即表示し、裏で最新版を取得して次回に反映する(games.json だけは通信優先)
// ゲームを追加しても、このファイルの更新は不要
const CACHE = "asobo-v3";
const PRECACHE = ["./", "index.html", "common.js", "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  const networkFirst = url.pathname.endsWith("/games.json");
  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(req, { ignoreSearch: true });
      const fetched = fetch(req)
        .then((res) => { if (res.ok) cache.put(req, res.clone()); return res; })
        .catch(() => cached);
      return networkFirst ? fetched.then((r) => r || cached) : (cached || fetched);
    })
  );
});
