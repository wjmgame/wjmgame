#!/usr/bin/env python3
"""公開前チェック(deploy.yml から build.py の後に呼ばれる。手元でも `python3 scripts/check.py`)

公開用サイト(_site/)を検査する。エラーが1つでもあれば終了コード1になり、公開されない。警告は表示だけ。
 エラー: 参照ファイルの実在 / ゲームのメタタグ / JavaScript の構文 / common.js の読み込み / 壊れた画像 / 極端に大きいファイル
 警告  : 300KB超のファイル / order の重複 / 共通仕様に反する書き方(音の自前実装・相対パスの直書き)
"""
import glob, json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SITE = sys.argv[1] if len(sys.argv) > 1 else "_site"
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a"}
WARN_BYTES, MAX_BYTES, MAX_AUDIO_BYTES = 300 * 1024, 1024 * 1024, 3 * 1024 * 1024
SKIP_REF = re.compile(r"^(https?:|data:|#|mailto:|javascript:|//)")
errors, warnings = [], []


def _ann(kind, msg, file):
    where = f" file={file}" if file else ""
    print(f"::{kind}{where}::{msg}")


def err(msg, file=None):
    errors.append(msg)
    _ann("error", msg, file)


def warn(msg, file=None):
    warnings.append(msg)
    _ann("warning", msg, file)


def path(rel):
    return os.path.join(SITE, rel)


def read(rel):
    return open(path(rel), encoding="utf-8").read()


def kb(n):
    return f"{n / 1024:.0f}KB"


def check_refs(page):
    base = os.path.dirname(page)
    for ref in re.findall(r'(?:src|href)\s*=\s*"([^"]*)"', read(page)):
        if not ref or SKIP_REF.match(ref):
            continue
        rel = os.path.normpath(os.path.join(base, ref.split("#")[0].split("?")[0]))
        if rel.startswith(".."):
            err(f"サイトの外を参照しています: {ref}", page)
            continue
        if os.path.isdir(path(rel)):
            rel = os.path.join(rel, "index.html")
        if not os.path.exists(path(rel)):
            err(f"参照先がありません: {ref}", page)


def node_check(code_or_file, label, is_code):
    try:
        if is_code:
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(code_or_file)
            target = f.name
        else:
            target = code_or_file
        r = subprocess.run(["node", "--check", target], capture_output=True, text=True)
        if is_code:
            os.unlink(target)
        if r.returncode != 0:
            detail = " ".join(r.stderr.strip().splitlines()[:4])
            err(f"JavaScript の構文エラー: {detail}", label)
    except FileNotFoundError:
        warn("node が見つからないため、JavaScript の構文チェックを省略しました")


def main():
    if not os.path.isdir(SITE):
        sys.exit(f"{SITE}/ がありません。先に python3 scripts/build.py を実行してください")

    pages = ["index.html"] + sorted(os.path.relpath(p, SITE).replace(os.sep, "/") for p in glob.glob(path("games/*/index.html")))

    # --- 参照ファイルの実在 ---
    for page in pages:
        check_refs(page)
    manifest = json.loads(read("manifest.webmanifest"))
    for icon in manifest.get("icons", []):
        if not os.path.exists(path(icon["src"])):
            err(f"manifest のアイコンがありません: {icon['src']}", "manifest.webmanifest")
    games = json.loads(read("games.json"))["games"]
    for g in games:
        if not os.path.exists(path(os.path.join(g["href"], "index.html"))):
            err(f"games.json のリンク先がありません: {g['href']}", "games.json")
    for lst in glob.glob(path("assets/*/list.json")):
        folder = os.path.dirname(lst)
        for name in json.load(open(lst, encoding="utf-8")):
            if not os.path.exists(os.path.join(folder, name)):
                err(f"list.json に載っているファイルがありません: {name}", os.path.relpath(lst, SITE))
    pre = json.loads(read("precache.json"))
    for rel in pre["files"]:
        if rel != "./" and not os.path.exists(path(rel)):
            err(f"先読み一覧(precache.json)のファイルがありません: {rel}")
    if f'const BUILD = "{pre["build"]}";' not in read("sw.js"):
        err("sw.js に版数(BUILD)が書き込まれていません", "sw.js")

    # --- ゲームのメタタグ・common.js・共通仕様 ---
    orders = {}
    for page in pages[1:]:
        html = read(page)
        gid = page.split("/")[1]
        meta = {}
        for n in ("title", "icon", "color", "order"):
            m = re.search(r'<meta\s+name="game-' + n + r'"\s+content="([^"]*)"', html)
            if not m or not m.group(1).strip():
                err(f'メタタグ game-{n} がありません(name → content の順で書く)', page)
            else:
                meta[n] = m.group(1).strip()
        if "color" in meta and not re.fullmatch(r"#[0-9a-fA-F]{3,8}", meta["color"]):
            err(f"game-color は #ffc83d のような色コードにしてください: {meta['color']}", page)
        if "order" in meta:
            if not re.fullmatch(r"-?\d+", meta["order"]):
                err(f"game-order は数字にしてください: {meta['order']}", page)
            else:
                orders.setdefault(int(meta["order"]), []).append(gid)
        if not re.search(r'<script[^>]+src="(?:\.\./)+shared/common\.js"', html):
            err("shared/common.js を読み込んでいません(ミュートと保護者ゲートが効きません)", page)
        if "Asobo.faces" in html and "shared/faces.js" not in html:
            err("Asobo.faces を使っていますが shared/faces.js を読み込んでいません", page)
        if "AudioContext" in html:
            warn("音を自前で実装しています。Asobo.tone / pop / blip を使うと、ミュート設定が反映されます", page)
        if re.search(r"localStorage[^;\n]*['\"]muted['\"]", html):
            warn("ミュート設定を自前で読んでいます。Asobo.muted() を使ってください", page)
        for code in re.findall(r"<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>", html, re.S):
            if re.search(r"[\"'`](?:\.\./)+(?:assets|faces|shared|games)/", code):
                warn("相対パスを直書きしています。Asobo.url('assets/...') を使ってください", page)
                break
    for order, ids in orders.items():
        if len(ids) > 1:
            warn(f"game-order {order} が重複しています: {', '.join(ids)}(並び順が不安定になります)")

    # --- JavaScript の構文 ---
    for page in pages:
        for i, code in enumerate(re.findall(r"<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>", read(page), re.S)):
            node_check(code, page, True)
    for js in sorted(glob.glob(path("shared/*.js"))) + [path("sw.js")]:
        node_check(js, os.path.relpath(js, SITE), False)

    # --- 壊れた画像・ファイルサイズ ---
    try:
        from PIL import Image
    except ImportError:
        Image = None
        warn("Pillow が無いため、壊れた画像のチェックを省略しました")
    for base, _, files in os.walk(SITE):
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, SITE).replace(os.sep, "/")
            ext, size = os.path.splitext(f)[1].lower(), os.path.getsize(p)
            if ext in IMG_EXTS and Image:
                try:
                    with Image.open(p) as im:
                        im.verify()
                except Exception as e:
                    err(f"画像が壊れています: {e}", rel)
            limit = MAX_AUDIO_BYTES if ext in AUDIO_EXTS else MAX_BYTES
            if size > limit:
                err(f"ファイルが大きすぎます({kb(size)}。上限 {kb(limit)})", rel)
            elif size > WARN_BYTES:
                warn(f"ファイルが {kb(size)} あります(300KB超。ゲーム専用の画像などは小さくしてください)", rel)

    print(f"\nチェック結果: エラー {len(errors)} 件 / 警告 {len(warnings)} 件")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
