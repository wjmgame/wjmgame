// 方針:
//  - HTML・JS・CSS は、キャッシュを即表示し、裏で最新版を取得して次回に反映する
//  - games.json と list.json は通信優先(新しいゲーム・写真をすぐ反映)
//  - 画像は大きいので、キャッシュにあれば再取得しない(同じ名前で差し替えたときは CACHE の版数を上げる)
// ゲームや素材を追加しても、このファイルの更新は不要
const CACHE = "asobo-v5";
const PRECACHE = ["./", "index.html", "shared/common.js", "shared/faces.js", "shared/theme.css", "manifest.webmanifest",
  "assets/icons/icon-192.png", "assets/icons/icon-512.png", "assets/icons/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => Promise.all(PRECACHE.map((u) => c.add(u).catch(() => {})))).then(() => self.skipWaiting()));
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
  const isJson = /\/(games|list)\.json$/.test(url.pathname);
  const isImage = /\.(png|jpe?g|webp|gif|avif)$/i.test(url.pathname);
  const key = isJson ? new Request(url.origin + url.pathname) : req; // ?t=時刻 でキャッシュが増えないようにする
  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(key, { ignoreSearch: true });
      if (isImage && cached) return cached;
      const fetched = fetch(req)
        .then((res) => { if (res.ok && res.status === 200) cache.put(key, res.clone()); return res; })
        .catch(() => cached);
      return isJson ? fetched.then((r) => r || cached) : (cached || fetched);
    })
  );
});
