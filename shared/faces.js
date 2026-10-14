// 顔写真の共通読み込み。common.js の「後」に読み込む: <script src="../../shared/faces.js"></script>
// 写真は assets/faces/ に置いて push するだけ。一覧(list.json)は scripts/build.py がデプロイ時に自動生成する
//   Asobo.faces.urls(max)           → Promise<画像URLの配列>(1枚目がはじめのリーダー)
//   Asobo.faces.canvases({max,size,onEach}) → 中央を正方形に切り抜いた canvas を、読めたものから onEach に渡す
(() => {
  const A = window.Asobo;
  if (!A) return;
  const DIR = "assets/faces/";
  const EXTS = ["jpg", "jpeg", "png", "webp"];
  const loadImg = (src) => new Promise((res) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => res(null);
    im.src = src;
  });

  async function urls(max = 12) {
    const dir = A.url(DIR);
    try { // ?t=時刻 と no-store で、毎回最新の一覧を取る(sw.js も list.json は通信優先)
      const r = await fetch(dir + "list.json?t=" + Date.now(), { cache: "no-store" });
      if (r.ok) {
        const arr = await r.json();
        if (Array.isArray(arr) && arr.length) return arr.slice(0, max).map((n) => dir + encodeURIComponent(n));
      }
    } catch (e) {}
    const found = []; // 一覧が無いとき(ローカル確認など)は 1.jpg, 2.jpg … の連番を探す
    for (let n = 1; n <= max; n++) {
      let hit = null;
      for (const ext of EXTS) { if (await loadImg(dir + n + "." + ext)) { hit = dir + n + "." + ext; break; } }
      if (!hit) break;
      found.push(hit);
    }
    return found;
  }

  function crop(im, size) {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const k = Math.max(size / im.naturalWidth, size / im.naturalHeight);
    const w = im.naturalWidth * k, h = im.naturalHeight * k;
    c.getContext("2d").drawImage(im, (size - w) / 2, (size - h) / 2, w, h);
    return c;
  }

  async function canvases({ max = 12, size = 160, onEach } = {}) {
    const out = [];
    for (const u of await urls(max)) {
      const im = await loadImg(u);
      if (!im) continue;
      const c = crop(im, size);
      out.push(c);
      if (onEach) onEach(c);
    }
    return out;
  }

  A.faces = { urls, canvases, loadImg };
})();
