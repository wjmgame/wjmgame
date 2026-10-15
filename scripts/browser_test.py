#!/usr/bin/env python3
"""ブラウザでの実行テスト(deploy.yml から check.py の後に呼ばれる。手元でも `python3 scripts/browser_test.py`)

公開用サイト(_site/)を、GitHub Pages と同じ `/wjmgame/` のサブパスで配信して、ヘッドレス Chrome で動かす。
 - トップ: タイルの数が games.json と一致する / JSエラー・通信エラーがない
 - 各ゲーム: 開いて数回タップしても、JSエラー・通信エラーがない / Asobo(common.js)が読み込まれている / 顔写真が読み込める
 - 保護者ゲート: 右上を1.5秒長押しでトップへ戻る
 - ミュート: トップの設定がゲームに反映される
 - 自動更新・オフライン: サービスワーカーが全ファイルを保存し、通信なしでもトップとゲームが開く
失敗したテストは1回だけやり直し、それでも失敗なら終了コード1にする。オン・オフは scripts/checks.json。
"""
import functools, http.server, json, os, subprocess, sys, tempfile, threading
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SITE = os.path.abspath("_site")
PREFIX = "wjmgame"  # GitHub Pages のサブパスを再現する
VIEWPORT = {"width": 390, "height": 844}
ctx = base = games = None
results = []


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    tmp = tempfile.mkdtemp()
    os.symlink(SITE, os.path.join(tmp, PREFIX))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/{PREFIX}/"


def launch(p):
    for kwargs in ({"channel": "chrome"}, {}):  # 実行環境に入っている Chrome を優先する
        try:
            return p.chromium.launch(**kwargs)
        except Exception as e:
            print("ブラウザを起動できませんでした:", kwargs or "chromium", str(e).splitlines()[0][:120])
    print("Chromium を取得します")
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True)
    return p.chromium.launch()


def new_page(errs):
    page = ctx.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda e: errs.append(f"JSエラー: {e}"))
    page.on("console", lambda m: errs.append(f"コンソールエラー: {m.text}")
            if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.on("response", lambda r: errs.append(f"通信エラー {r.status}: {r.url}")
            if r.status >= 400 and "favicon" not in r.url else None)
    page.on("requestfailed", lambda r: errs.append(f"通信失敗: {r.url}") if "favicon" not in r.url else None)
    return page


def no_errors(errs):
    assert not errs, " / ".join(errs[:3])


def face_list():
    p = os.path.join(SITE, "assets/faces/list.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def wait_tiles(page):
    page.wait_for_function("n => document.querySelectorAll('.tile').length === n", arg=len(games))


def t_top():
    errs = []
    page = new_page(errs)
    page.goto(base)
    wait_tiles(page)
    page.wait_for_timeout(500)
    page.close()
    no_errors(errs)


def t_game(href):
    def run():
        errs = []
        page = new_page(errs)
        page.goto(base + href, wait_until="load")
        page.wait_for_timeout(1200)
        assert page.evaluate("typeof window.Asobo") == "object", "Asobo(common.js)が読み込まれていません"
        assert page.evaluate("Asobo.url('assets/')").endswith(f"/{PREFIX}/assets/"), "ルートの位置が正しく取れていません"
        for x, y in [(195, 420), (100, 300), (300, 600), (195, 700)]:
            page.mouse.click(x, y)
            page.wait_for_timeout(150)
        page.wait_for_timeout(600)
        if page.evaluate("!!(window.Asobo && Asobo.faces)") and face_list():
            n, ok = page.evaluate("""async () => {
                const u = await Asobo.faces.urls(12);
                const ok = await Promise.all(u.map((x) => fetch(x).then((r) => r.ok)));
                return [u.length, ok.every(Boolean)];
            }""")
            assert n == min(12, len(face_list())) and ok, f"顔写真を読み込めません(取得 {n} 枚)"
        page.close()
        no_errors(errs)
    return run


def t_gate():
    errs = []
    page = new_page(errs)
    page.goto(base + games[0]["href"], wait_until="load")
    page.wait_for_timeout(500)
    page.mouse.move(VIEWPORT["width"] - 28, 28)
    page.mouse.down()
    try:
        page.wait_for_url(lambda u: u.rstrip("/") == base.rstrip("/"), timeout=4000)
    finally:
        try:
            page.mouse.up()
        except Exception:
            pass
    page.close()


def t_mute():
    errs = []
    page = new_page(errs)
    page.goto(base)
    page.evaluate("localStorage.setItem('muted', 'true')")
    page.goto(base + games[0]["href"], wait_until="load")
    try:
        assert page.evaluate("Asobo.muted()") is True, "トップのミュート設定がゲームに反映されていません"
    finally:
        page.evaluate("localStorage.setItem('muted', 'false')")
        page.close()


def t_offline():
    pre = json.load(open(os.path.join(SITE, "precache.json"), encoding="utf-8"))
    errs = []
    page = new_page(errs)
    page.goto(base)
    ready = page.evaluate("Promise.race([navigator.serviceWorker.ready.then(() => true), new Promise((r) => setTimeout(() => r(false), 8000))])")
    assert ready, "サービスワーカーが有効になりません(先読みするファイルの取得に失敗した可能性)"
    name = f"asobo-{pre['build']}"
    assert name in page.evaluate("caches.keys()"), f"キャッシュ {name} がありません"
    cached = set(page.evaluate("(n) => caches.open(n).then((c) => c.keys()).then((ks) => ks.map((r) => new URL(r.url).pathname))", name))
    expected = {f"/{PREFIX}/" if f == "./" else f"/{PREFIX}/{quote(f)}" for f in pre["files"]}
    assert not (expected - cached), f"先読みされていないファイル: {sorted(expected - cached)[:3]}"
    page.reload()
    page.wait_for_timeout(500)
    ctx.set_offline(True)
    try:
        off_errs = []
        off = new_page(off_errs)
        off.goto(base)
        wait_tiles(off)
        off.goto(base + games[0]["href"], wait_until="load")
        assert off.evaluate("typeof window.Asobo") == "object", "通信なしでゲームを開けません"
        off.close()
    finally:
        ctx.set_offline(False)
        page.close()


def run(name, fn):
    last = ""
    for attempt in (1, 2):
        try:
            fn()
            print(f"✓ {name}")
            results.append((name, True))
            return
        except Exception as e:
            last = str(e).strip().splitlines()[0][:300] if str(e).strip() else repr(e)
            if attempt == 1:
                print(f"… {name} を1回やり直します: {last}")
    print(f"✗ {name}: {last}")
    print(f"::error::ブラウザテストが失敗しました: {name}: {last}")
    results.append((name, False))


def main():
    global ctx, base, games
    if not os.path.isdir(SITE):
        sys.exit("_site/ がありません。先に python3 scripts/build.py を実行してください")
    from playwright.sync_api import sync_playwright
    games = json.load(open(os.path.join(SITE, "games.json"), encoding="utf-8"))["games"]
    srv, base = serve()
    with sync_playwright() as p:
        browser = launch(p)
        ctx = browser.new_context(viewport=VIEWPORT)
        run("トップ画面(タイル表示)", t_top)
        for g in games:
            run(f"ゲーム: {g['title']}", t_game(g["href"]))
        run("保護者ゲート(右上の長押しでトップへ)", t_gate)
        run("ミュート設定の引き継ぎ", t_mute)
        run("自動更新の先読みとオフライン起動", t_offline)
        browser.close()
    srv.shutdown()
    failed = [n for n, ok in results if not ok]
    print(f"\nブラウザテスト: {len(results) - len(failed)}/{len(results)} 件成功")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
