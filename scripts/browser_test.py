#!/usr/bin/env python3
"""ブラウザでの実行テスト(deploy.yml から check.py の後に呼ばれる。手元でも `python3 scripts/browser_test.py`)

公開用サイト(_site/)を、GitHub Pages と同じ `/wjmgame/` のサブパスで配信して、ヘッドレス Chrome で動かす。
 - トップ: タイルの数が games.json と一致する / JSエラー・通信エラーがない
 - 各ゲーム: 開いて数回タップしても、JSエラー・通信エラーがない / Asobo(common.js)が読み込まれている / 顔写真が読み込める
 - 画面の隅のボタン: 右上の薄いボタンが表示される / 右上の長押しでトップへ戻る / ぞろぞろは左上の長押しで設定が開く
 - ゲームが増えたとき: 9個までは、スクロールしなくても全タイルが見える。20個でも、縦・横どちらの向きでも全タイルに届く(タッチでスクロール)。タイルは100px以上
 - 素材フォルダ: assets/*/list.json の画像がすべて読み込める(順番は毎回ランダム)
 - ミュート: トップの設定がゲームに反映される
 - 自動更新・オフライン: サービスワーカーが全ファイルを保存し、通信なしでもトップとゲームが開く
失敗したテストは1回だけやり直し、それでも失敗なら終了コード1にする。オン・オフは scripts/checks.json。
"""
import functools, glob, http.server, json, os, re, shutil, subprocess, sys, tempfile, threading
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SITE = os.path.abspath("_site")
PREFIX = "wjmgame"  # GitHub Pages のサブパスを再現する
VIEWPORT = {"width": 390, "height": 844}
ctx = base = games = browser = None
results = []


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(site=None):
    tmp = tempfile.mkdtemp()
    os.symlink(site or SITE, os.path.join(tmp, PREFIX))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/{PREFIX}/"


def make_many_site(n):
    """今のサイトを複製し、既存ゲームのコピーでゲームを n 個に増やした試験用サイトを作る"""
    site = os.path.join(tempfile.mkdtemp(), "site")
    shutil.copytree(SITE, site)
    data = json.load(open(os.path.join(site, "games.json"), encoding="utf-8"))
    base_games = data["games"][:]
    while len(data["games"]) < n:
        k = len(data["games"]) + 1
        src = base_games[(k - 1) % len(base_games)]
        shutil.copytree(os.path.join(site, src["href"]), os.path.join(site, f"games/dummy{k}"))
        data["games"].append({**src, "id": f"dummy{k}", "title": f"ゲーム{k}", "href": f"games/dummy{k}/", "order": 100 + k})
    data["games"] = data["games"][:n]
    json.dump(data, open(os.path.join(site, "games.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return site


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
    assert page.evaluate("!!document.querySelector('[data-asobo-corner=\"right\"]')"), "右上の保護者メニューのボタンがありません"
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
        assert page.evaluate("!!document.querySelector('[data-asobo-corner=\"right\"]')"), "右上の戻るボタンがありません"
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


def t_assets():
    folders = []
    for lst in sorted(glob.glob(os.path.join(SITE, "assets/*/list.json"))):
        names = [n for n in json.load(open(lst, encoding="utf-8")) if re.search(r"\.(jpe?g|png|webp|gif|avif)$", n, re.I)]
        if names:
            folders.append((os.path.basename(os.path.dirname(lst)), len(names)))
    errs = []
    page = new_page(errs)
    page.goto(base)
    page.wait_for_timeout(300)
    for folder, n in folders:
        got, ok = page.evaluate("""async (f) => {
            const u = await Asobo.assets.urls(f);
            const ok = await Promise.all(u.map((x) => fetch(x).then((r) => r.ok)));
            return [u.length, ok.every(Boolean)];
        }""", folder)
        assert got == n and ok, f"assets/{folder}: 一覧 {n} 枚のうち {got} 枚を取得(すべて読み込めるか: {ok})"
    page.close()
    no_errors(errs)


def t_settings(href):
    def run():
        errs = []
        page = new_page(errs)
        page.goto(base + href, wait_until="load")
        page.wait_for_timeout(800)
        assert page.evaluate("!!document.querySelector('[data-asobo-corner=\"left\"]')"), "左上の設定ボタンがありません"
        page.mouse.move(28, 28)
        page.mouse.down()
        page.wait_for_timeout(1800)
        try:
            opened = page.evaluate("!document.getElementById('panel').hidden")
        finally:
            try:
                page.mouse.up()
            except Exception:
                pass
        page.close()
        assert opened, "左上の長押しで設定が開きません"
    return run


def swipe_up(page, cdp, x, y_from, y_to, step=20):
    """タッチイベントを1つずつ送って、指で上へスワイプする(synthesizeScrollGesture は環境によって効かない)"""
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y_from}]})
    y = y_from
    while y > y_to:
        y = max(y - step, y_to)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
        page.wait_for_timeout(16)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(400)


def t_many_games():
    last_visible = """(() => { const t = [...document.querySelectorAll('.tile')].pop().getBoundingClientRect();
        return t.bottom <= innerHeight + 1 && t.top >= 0; })()"""
    for n in (9, 20):
        srv, url = serve(make_many_site(n))
        try:
            for vp in ({"width": 390, "height": 844}, {"width": 844, "height": 390}):
                c = browser.new_context(viewport=vp, has_touch=True, is_mobile=True)
                page = c.new_page()
                page.set_default_timeout(10000)
                page.goto(url)
                page.wait_for_function("n => document.querySelectorAll('.tile').length === n", arg=n)
                page.wait_for_timeout(300)
                cdp = c.new_cdp_session(page)
                label = f"{n}個・{vp['width']}x{vp['height']}"
                if n == 9:  # 9個までは、スクロールしなくても全部のタイルが見える(スクロールに気づかなくても選べる)
                    assert page.evaluate(last_visible), f"{label}: スクロールしないと最後のタイルが見えません"
                for _ in range(8):  # 最後のタイルが見えるまで、指で上へスワイプ(スクロール)する
                    if page.evaluate(last_visible):
                        break
                    swipe_up(page, cdp, vp["width"] // 2, int(vp["height"] * 0.8), int(vp["height"] * 0.3))
                assert page.evaluate(last_visible), f"{label}: 最後のタイルに届きません(スクロールできない可能性)"
                side = page.evaluate("Math.min(...[...document.querySelectorAll('.tile')].map((t) => { const r = t.getBoundingClientRect(); return Math.min(r.width, r.height); }))")
                assert side >= 100, f"{label}: タイルが小さすぎます({side:.0f}px)"
                c.close()
        finally:
            srv.shutdown()


def t_resize(href):
    """iPadのウインドウサイズ変更を想定: 大きさを変えても、画面を作り直さない(進行状況が消えない)"""
    def run():
        errs = []
        page = new_page(errs)
        page.goto(base + href, wait_until="load")
        page.wait_for_timeout(1000)
        for x, y in [(195, 420), (120, 300)]:
            page.mouse.click(x, y)
            page.wait_for_timeout(150)
        page.evaluate("() => { window.__marker = Math.random(); window.__m0 = window.__marker; window.__els = [...document.body.querySelectorAll('*')]; }")
        for w, h in [(300, 500), (760, 600), (1024, 700), (390, 844)]:
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(350)
        kept, total, same = page.evaluate("() => [window.__els.filter((e) => e.isConnected).length, window.__els.length, window.__marker === window.__m0]")
        page.close()
        assert same, "大きさを変えるとページが再読み込みされます"
        assert kept >= total * 0.8, f"大きさを変えると画面が作り直されます(元の要素 {total} 個のうち {kept} 個しか残っていません。進行状況が消える可能性)"
        no_errors(errs)
    return run


def t_back_trap():
    """Safariの左端スワイプ(戻る)でトップへ戻らない。戻れるのは🏠の長押しだけ"""
    errs = []
    page = new_page(errs)
    page.goto(base)
    wait_tiles(page)
    page.click(".tile")  # 通常どおり、トップからゲームへ入る
    page.wait_for_url(lambda u: "/games/" in u)
    page.wait_for_timeout(800)
    page.mouse.click(200, 400)
    game_url = page.url
    page.go_back()
    page.wait_for_timeout(600)
    assert page.url == game_url, "戻る操作で、ゲームからトップへ戻ってしまいます"
    page.mouse.move(VIEWPORT["width"] - 28, 28)
    page.mouse.down()
    try:
        page.wait_for_url(lambda u: u.rstrip("/") == base.rstrip("/"), timeout=4000)
    finally:
        try:
            page.mouse.up()
        except Exception:
            pass
    page.wait_for_timeout(500)
    page.go_back()
    page.wait_for_timeout(500)
    assert "/games/" not in page.url, "🏠で戻ったあと、戻る操作でゲームに戻ってしまいます(履歴が残っています)"
    page.close()


def run(name, fn):
    if os.environ.get("ONLY") and os.environ["ONLY"] not in name:  # 手元で一部のテストだけ動かす: ONLY=リサイズ python3 scripts/browser_test.py
        return
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
    global ctx, base, games, browser
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
        run("戻るスワイプの抑止(戻れるのは🏠の長押しだけ)", t_back_trap)
        for g in games:
            run(f"リサイズしても進行状況が消えない: {g['title']}", t_resize(g["href"]))
        run("ミュート設定の引き継ぎ", t_mute)
        run("ゲームが増えても全タイルに届く(9個・20個)", t_many_games)
        run("素材フォルダの読み込み", t_assets)
        for g in games:
            if g["id"] == "zorozoro":
                run("設定ボタン(ぞろぞろ・左上の長押し)", t_settings(g["href"]))
        run("自動更新の先読みとオフライン起動", t_offline)
        browser.close()
    srv.shutdown()
    failed = [n for n, ok in results if not ok]
    print(f"\nブラウザテスト: {len(results) - len(failed)}/{len(results)} 件成功")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
