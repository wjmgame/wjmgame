// 全ゲーム共通。ゲームHTMLの <head> に <script src="../../shared/common.js"></script> を入れるだけで有効になる
//  - 右上に薄い🏠ボタン: 1.5秒長押しでトップへ戻る(長押し中に輪が広がる)。隅のボタンは Asobo.cornerButton で作る
//  - 戻るスワイプ(Safariの左端スワイプなど)の抑止: ゲームからトップへ戻れるのは🏠の長押し(Asobo.home)だけ
//  - パス解決: このファイルの場所からサイトのルートを割り出す。Asobo.url("assets/...") / Asobo.home() を使い、相対パスを直書きしない
//  - ズーム・長押しメニューの抑止
//  - 素材の一覧: Asobo.assets.urls("フォルダ") で assets/<フォルダ>/list.json を読む(毎回ランダム)
//  - 音: ミュート設定(localStorage "muted")を自動で反映。音は Asobo.tone / pop / blip を使う
(() => {
  const KEY = "muted";
  const SRC = (document.currentScript && document.currentScript.src) || "";
  const ROOT = SRC ? new URL("../", SRC).href : new URL("./", location.href).href; // shared/ の1つ上がルート
  const url = (path) => new URL(path, ROOT).href;
  // トップへ戻る。戻るスワイプの抑止(trapBack)で足した履歴を先に1つ戻してから移動するので、履歴にゲームが残らない
  let trapped = false, leaving = false;
  const home = () => {
    if (!trapped) { location.href = ROOT; return; }
    leaving = true;
    history.back();
    setTimeout(() => location.replace(ROOT), 500); // popstate が来なかったときの保険
  };
  // Safari の左端スワイプ(戻る)でトップへ戻ってしまうのを防ぐ。戻れるのは🏠の長押しだけ
  function trapBack() {
    try {
      history.pushState({ asobo: 1 }, "", location.href);
      trapped = true;
      addEventListener("popstate", () => {
        if (leaving) { location.replace(ROOT); return; }
        history.pushState({ asobo: 1 }, "", location.href);
      });
    } catch (e) {}
  }
  // --- 素材の一覧(assets/<フォルダ>/list.json は build.py が自動生成)---
  const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const probe = (src) => new Promise((res) => { const im = new Image(); im.onload = () => res(true); im.onerror = () => res(false); im.src = src; });
  const IMG_RE = /\.(jpe?g|png|webp|gif|avif)$/i;
  // opts: max=取得する最大数(既定:すべて) / shuffle=毎回ランダム(既定:true。false でファイル名の降順) / ext=対象の拡張子の正規表現(既定:画像)
  async function assetUrls(folder, { max = Infinity, shuffle: doShuffle = true, ext = IMG_RE } = {}) {
    const dir = url("assets/" + folder + "/");
    let urls = [];
    try {
      const r = await fetch(dir + "list.json?t=" + Date.now(), { cache: "no-store" });
      if (r.ok) {
        const arr = await r.json();
        if (Array.isArray(arr)) urls = arr.filter((n) => ext.test(n)).map((n) => dir + encodeURIComponent(n));
      }
    } catch (e) {}
    if (!urls.length) { // 一覧が無いとき(ローカル確認など)は 1.jpg, 2.jpg … の連番を探す
      const limit = isFinite(max) ? max : 12;
      for (let n = 1; n <= limit; n++) {
        let hit = null;
        for (const x of ["jpg", "jpeg", "png", "webp"]) { if (await probe(dir + n + "." + x)) { hit = dir + n + "." + x; break; } }
        if (!hit) break;
        urls.push(hit);
      }
    }
    if (doShuffle) shuffle(urls);
    return isFinite(max) ? urls.slice(0, max) : urls;
  }

  const SCALE = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5];
  let ac = null, noiseBuf = null;
  const muted = () => { try { return JSON.parse(localStorage.getItem(KEY)) === true; } catch (e) { return false; } };
  const setMuted = (v) => { try { localStorage.setItem(KEY, JSON.stringify(!!v)); } catch (e) {} };
  const ctx = () => {
    if (!ac) { try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return null; } }
    if (ac.state === "suspended") ac.resume();
    return ac;
  };
  function tone(freq, dur = .25, vol = .18, glide = 1.5) { // glide=1 で音程を変えない(音階用)
    if (muted()) return;
    const a = ctx(); if (!a) return;
    const t = a.currentTime, o = a.createOscillator(), g = a.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(freq, t);
    o.frequency.exponentialRampToValueAtTime(freq * glide, t + .12);
    g.gain.setValueAtTime(.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + .02);
    g.gain.exponentialRampToValueAtTime(.0001, t + dur);
    o.connect(g).connect(a.destination);
    o.start(t); o.stop(t + dur + .02);
  }
  function noise() {
    if (muted()) return;
    const a = ctx(); if (!a) return;
    const t = a.currentTime;
    if (!noiseBuf) {
      noiseBuf = a.createBuffer(1, Math.floor(a.sampleRate * .15), a.sampleRate);
      const d = noiseBuf.getChannelData(0);
      for (let k = 0; k < d.length; k++) d[k] = (Math.random() * 2 - 1) * (1 - k / d.length);
    }
    const n = a.createBufferSource(), f = a.createBiquadFilter(), g = a.createGain();
    n.buffer = noiseBuf; f.type = "bandpass"; f.frequency.value = 1800;
    g.gain.setValueAtTime(.5, t); g.gain.exponentialRampToValueAtTime(.001, t + .12);
    n.connect(f).connect(g).connect(a.destination); n.start(t);
  }
  const blip = (i = Math.floor(Math.random() * SCALE.length)) => tone(SCALE[i % SCALE.length], .25, .15);
  const pop = () => { noise(); blip(); };
  window.Asobo = { root: ROOT, url, home, assets: { urls: assetUrls }, shuffle, cornerButton, SCALE, muted, setMuted, ctx, tone, noise, blip, pop };

  addEventListener("pointerdown", ctx, true); // iOSは最初のタップ後でないと音が出ない
  document.addEventListener("contextmenu", (e) => e.preventDefault());
  document.addEventListener("gesturestart", (e) => e.preventDefault());

  // --- 画面の隅のボタン: 薄いアイコンを常に表示し、操作は1.5秒の長押しだけ ---
  //   corner: "right"(戻る・保護者メニュー) / "left"(設定)   icon: 絵文字   label: 読み上げ用の名前   onHold: 長押しで呼ばれる
  const ready = (fn) => (document.body ? fn() : document.addEventListener("DOMContentLoaded", fn));
  function cornerButton({ corner = "right", icon = "🏠", label = "", onHold } = {}) {
    const side = corner === "left" ? "left" : "right";
    const top = "env(safe-area-inset-top,0px)", inset = `env(safe-area-inset-${side},0px)`;
    const mark = document.createElement("div"); // 見た目(薄い丸いアイコン。タッチは受けない)
    mark.textContent = icon;
    mark.style.cssText = `position:fixed;top:calc(${top} + 8px);${side}:calc(${inset} + 8px);width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;line-height:1;background:rgba(255,255,255,.4);border:2px solid rgba(35,48,90,.25);opacity:.55;pointer-events:none;z-index:9;`;
    const ring = document.createElement("div"); // 長押し中に広がる輪(あと少しの合図)
    ring.style.cssText = `position:fixed;top:calc(${top} + 3px);${side}:calc(${inset} + 3px);width:50px;height:50px;border-radius:50%;border:5px solid #23305a;opacity:0;transform:scale(.4);pointer-events:none;z-index:9;`;
    const hit = document.createElement("button"); // タッチを受ける透明な領域(56px四方)
    hit.setAttribute("aria-label", label || icon);
    hit.dataset.asoboCorner = side;
    hit.style.cssText = `position:fixed;top:${top};${side}:${inset};width:56px;height:56px;z-index:10;background:transparent;border:0;padding:0;`;
    let hold = null;
    const end = () => { clearTimeout(hold); ring.style.transition = "none"; ring.style.opacity = "0"; ring.style.transform = "scale(.4)"; };
    hit.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      ring.style.transition = "transform 1.5s linear, opacity .2s"; ring.style.opacity = ".6"; ring.style.transform = "scale(1)";
      hold = setTimeout(() => { end(); if (onHold) onHold(); }, 1500);
    });
    ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => hit.addEventListener(ev, end));
    ready(() => document.body.append(mark, ring, hit));
    return hit;
  }

  function addGate() {
    if (document.documentElement.dataset.asobo === "top") return; // トップは独自の保護者メニュー(右上に⚙️)
    trapBack();
    cornerButton({ corner: "right", icon: "🏠", label: "トップへ戻る（長押し）", onHold: home });
  }
  addGate();
})();
