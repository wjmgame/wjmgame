#!/usr/bin/env python3
"""公開用サイト(_site/)を作る(deploy.yml から呼ばれる。手元でも `python3 scripts/build.py` で試せる)

 - ソースを _site/ へコピーする(scripts/・docs/・README・.git など、公開不要なものは除く)
 - assets/<種類>/ の画像(icons を除く)は、長辺 480px の WebP に縮小して公開する。元画像は公開しない。音声はそのままコピー
   出力名は <元の名前>.<8桁ハッシュ>.webp。写真を差し替えると名前が変わるので、キャッシュの版数を上げなくてよい
 - games.json と assets/<種類>/list.json を生成する(list は元のファイル名の降順(自然順)。1枚目がはじめのリーダー)
 - sw.js の BUILD(公開物全体のハッシュ)を書き換え、先読み対象の一覧 precache.json を生成する(内容が同じなら同じ BUILD)
 - 300KB を超えるファイルがあれば警告する
Pillow が無い環境では、画像を縮小せずそのままコピーする(警告を出す)
"""
import glob, hashlib, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = "_site"
EXCLUDE_ROOT = {".git", ".github", ".gitignore", OUT, "scripts", "docs", "README.md", "assets"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a"}
MAX_EDGE, QUALITY = 480, 80
WARN_BYTES = 300 * 1024
PRECACHE_MAX = 1024 * 1024  # これより大きいファイルは先読みせず、使うときに取得する


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def ignore(d, names):
    if os.path.abspath(d) == ROOT:
        return [n for n in names if n in EXCLUDE_ROOT]
    return [n for n in names if n in ("__pycache__", ".DS_Store")]


def kb(n):
    return f"{n / 1024:.0f}KB"


def build_assets():
    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = None
        print("warning: Pillow が無いため、画像は縮小せずそのままコピーします")
    if os.path.isdir("assets/icons"):
        shutil.copytree("assets/icons", f"{OUT}/assets/icons")
    for d in sorted(glob.glob("assets/*/")):
        name = os.path.basename(os.path.normpath(d))
        if name == "icons":
            continue
        out_dir = f"{OUT}/assets/{name}"
        os.makedirs(out_dir, exist_ok=True)
        files = [f for f in os.listdir(d) if os.path.splitext(f)[1].lower() in IMG_EXTS | AUDIO_EXTS]
        files.sort(key=natural_key, reverse=True)
        entries = []
        for f in files:
            src, ext = os.path.join(d, f), os.path.splitext(f)[1].lower()
            if ext in IMG_EXTS and Image:
                raw = open(src, "rb").read()
                h = hashlib.sha1(raw + f"{MAX_EDGE}-{QUALITY}".encode()).hexdigest()[:8]
                out_name = f"{os.path.splitext(f)[0]}.{h}.webp"
                with Image.open(src) as im:
                    im = ImageOps.exif_transpose(im)  # iPhone写真の向きを反映
                    if im.mode in ("P", "LA", "PA"):
                        im = im.convert("RGBA")
                    elif im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGB")
                    im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)  # 拡大はしない
                    im.save(os.path.join(out_dir, out_name), "WEBP", quality=QUALITY, method=6)
                print(f"  {name}/{f} ({kb(len(raw))}) -> {out_name} ({kb(os.path.getsize(os.path.join(out_dir, out_name)))})")
            else:
                shutil.copy2(src, os.path.join(out_dir, f))
                out_name = f
            entries.append(out_name)
        with open(os.path.join(out_dir, "list.json"), "w", encoding="utf-8") as fp:
            json.dump(entries, fp, ensure_ascii=False)
        print(f"assets/{name}/list.json:", json.dumps(entries, ensure_ascii=False))


def build_games():
    games = []
    for p in sorted(glob.glob("games/*/index.html")):
        gid = os.path.basename(os.path.dirname(p))
        s = open(p, encoding="utf-8").read()

        def meta(n, d):
            m = re.search(r'<meta\s+name="game-' + n + r'"\s+content="([^"]*)"', s)
            return m.group(1) if m else d

        if 'name="game-title"' not in s:
            print(f"warning: {p} に game-title のメタタグがありません(タイル名はフォルダ名になります)")
        try:
            order = int(meta("order", "100"))
        except ValueError:
            order = 100
        games.append({"id": gid, "title": meta("title", gid), "icon": meta("icon", "🎮"),
                      "color": meta("color", "#8e7cff"), "order": order, "href": f"games/{gid}/"})
    games.sort(key=lambda g: (g["order"], g["id"]))
    if not games:
        sys.exit("error: games/<名前>/index.html が1つも見つかりません")
    with open(f"{OUT}/games.json", "w", encoding="utf-8") as fp:
        json.dump({"games": games}, fp, ensure_ascii=False, indent=1)
    print("games.json:", json.dumps([g["id"] for g in games], ensure_ascii=False))


def stamp_build():
    files = []
    for base, _, fs in os.walk(OUT):
        for f in fs:
            files.append(os.path.relpath(os.path.join(base, f), OUT).replace(os.sep, "/"))
    files.sort()
    h = hashlib.sha1()
    for rel in files:
        if rel == "sw.js":
            continue
        h.update(rel.encode())
        h.update(open(os.path.join(OUT, rel), "rb").read())
    build = h.hexdigest()[:10]
    sw_path = os.path.join(OUT, "sw.js")
    sw = open(sw_path, encoding="utf-8").read()
    stamped = sw.replace('const BUILD = "dev";', f'const BUILD = "{build}";')
    if stamped == sw:
        sys.exit('error: sw.js に const BUILD = "dev"; が見つかりません')
    open(sw_path, "w", encoding="utf-8").write(stamped)
    pre = ["./"] + [r for r in files if r != "sw.js" and os.path.getsize(os.path.join(OUT, r)) <= PRECACHE_MAX]
    with open(os.path.join(OUT, "precache.json"), "w", encoding="utf-8") as fp:
        json.dump({"build": build, "files": pre}, fp, ensure_ascii=False)
    print(f"BUILD: {build} / 先読み {len(pre)} ファイル")


def report():
    total = 0
    for base, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(base, f)
            n = os.path.getsize(p)
            total += n
            if n > WARN_BYTES:
                print(f"warning: {os.path.relpath(p, OUT)} が {kb(n)} あります(300KB超。ゲーム専用の画像は小さくしてください)")
    print(f"公開サイズ合計: {kb(total)}")


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(".", OUT, ignore=ignore)
    build_assets()
    build_games()
    stamp_build()
    report()
