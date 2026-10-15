// 方針:
//  - 公開のたびに build.py が BUILD(サイト全体のハッシュ)を書き込む。内容が変わると sw.js も変わり、ブラウザが更新を検知する
//  - 更新時は、新しい版の全ファイル(precache.json)を先読みしてから切り替える。1つでも失敗したら古い版のまま続ける
//  - HTML・JS・CSS は、キャッシュを即表示し、裏で最新版を確認する
//  - games.json と list.json は通信優先(新しいゲーム・写真をすぐ反映)
//  - 画像は大きいので、キャッシュにあれば再取得しない(差し替えると名前が変わる)
// ゲームや素材の追加で、このファイルの更新は不要。BUILD は手で書き換えない
const BUILD = "dev";
const CACHE = "asobo-" + BUILD;

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    let files = ["./", "index.html"];
    try {
      const r = await fetch("precache.json", { cache: "no-store" });
      if (r.ok) files = (await r.json()).files;
    } catch (err) {}
    // cache:"reload" で、ブラウザの一時保存(古い可能性)を使わず必ず最新を取る
    await Promise.all(files.map((u) => cache.add(new Request(u, { cache: "reload" }))));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || req.headers.has("range")) return;
  const isJson = /\/(games|list)\.json$/.test(url.pathname);
  const isImage = /\.(png|jpe?g|webp|gif|avif)$/i.test(url.pathname);
  const key = isJson ? new Request(url.origin + url.pathname) : req; // ?t=時刻 でキャッシュが増えないようにする
  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(key, { ignoreSearch: true });
      if (isImage && cached) return cached;
      const fresh = req.mode === "navigate" ? req : new Request(req, { cache: "no-cache" }); // 古い一時保存で上書きしない
      const fetched = fetch(fresh)
        .then((res) => { if (res.ok && res.status === 200) cache.put(key, res.clone()); return res; })
        .catch(() => cached);
      return isJson ? fetched.then((r) => r || cached) : (cached || fetched);
    })
  );
});
