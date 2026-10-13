// 全ゲーム共通。ゲームHTMLの <head> に <script src="../common.js"></script> を入れるだけで有効になる
//  - 保護者ゲート: 右上を1.5秒長押しでトップ("../")へ戻る
//  - ズーム・長押しメニューの抑止
//  - 音: ミュート設定(localStorage "muted")を自動で反映。音は Asobo.tone / pop / blip を使う
(() => {
  const KEY = "muted";
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
  window.Asobo = { SCALE, muted, setMuted, ctx, tone, noise, blip, pop };

  addEventListener("pointerdown", ctx, true); // iOSは最初のタップ後でないと音が出ない
  document.addEventListener("contextmenu", (e) => e.preventDefault());
  document.addEventListener("gesturestart", (e) => e.preventDefault());

  function addGate() {
    if (document.documentElement.dataset.asobo === "top") return; // トップは独自の保護者メニュー
    const b = document.createElement("button");
    b.setAttribute("aria-label", "トップへ戻る（長押し）");
    b.style.cssText = "position:fixed;top:env(safe-area-inset-top,0px);right:env(safe-area-inset-right,0px);width:56px;height:56px;z-index:10;background:transparent;border:0;opacity:0;";
    const ring = document.createElement("div"); // 長押し中に広がる輪(あと少しで戻る合図)
    ring.style.cssText = "position:fixed;top:calc(env(safe-area-inset-top,0px) + 6px);right:calc(env(safe-area-inset-right,0px) + 6px);width:44px;height:44px;border-radius:50%;border:5px solid #23305a;opacity:0;transform:scale(.4);pointer-events:none;z-index:9;";
    let hold = null;
    const end = () => { clearTimeout(hold); ring.style.transition = "none"; ring.style.opacity = "0"; ring.style.transform = "scale(.4)"; };
    b.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      ring.style.transition = "transform 1.5s linear, opacity .2s"; ring.style.opacity = ".6"; ring.style.transform = "scale(1)";
      hold = setTimeout(() => { location.href = "../"; }, 1500);
    });
    ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => b.addEventListener(ev, end));
    document.body.appendChild(ring);
    document.body.appendChild(b);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addGate); else addGate();
})();
