#!/usr/bin/env python3
"""公開用サイト(_site/)を作る(deploy.yml から呼ばれる。手元でも `python3 scripts/build.py` で試せる)

 - ソースを _site/ へコピーする(scripts/・docs/・README・.git など、公開不要なものは除く)
 - assets/<種類>/ の画像は、フォルダごとの方針(FOLDER_POLICY)で縮小して公開する。元画像は公開しない。音声はそのままコピー
     webp: 長辺 480px の WebP に変換する(例: faces)。出力名は <元の名前>.<8桁ハッシュ>.webp で、list.json を作る
     keep: 名前と形式を保ったまま、大きければ縮小・再圧縮する(例: icons)。ゲームやmanifestから固定の名前で参照できる
 - games.json と assets/<種類>/list.json を生成する(list は元のファイル名の降順(自然順)。1枚目がはじめのリーダー)
 - sw.js の BUILD(公開物全体のハッシュ)を書き換え、先読み対象の一覧 precache.json を生成する(内容が同じなら同じ BUILD)
Pillow が無い環境では、画像を縮小せずそのままコピーする(警告を出す)
"""
import glob, hashlib, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = "_site"
EXCLUDE_ROOT = {".git", ".github", ".gitignore", OUT, "scripts", "docs", "README.md", "assets"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a"}
QUALITY = 80
# フォルダごとの縮小方針。ここに無いフォルダは DEFAULT_POLICY(WebP に変換して list.json を作る)
FOLDER_POLICY = {
    "icons": {"mode": "keep", "max_edge": 512},  # 長辺が 512px 超なら縮小。100KB 超なら再圧縮。小さければ元のまま
}
DEFAULT_POLICY = {"mode": "webp", "max_edge": 480}
KEEP_REENCODE_BYTES = 100 * 1024
PRECACHE_MAX = 1024 * 1024  # これより大きいファイルは先読みせず、使うときに取得する


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def ignore(d, names):
    if os.path.abspath(d) == ROOT:
        return [n for n in names if n in EXCLUDE_ROOT]
    return [n for n in names if n in ("__pycache__", ".DS_Store")]


def kb(n):
    return f"{n / 1024:.0f}KB"


def keep_image(Image, ImageOps, src, dst, max_edge):
    """名前と形式を保ったまま縮小する。小さければ元のバイト列のままコピーする。(変更前, 変更後)のサイズを返す"""
    ext, before = os.path.splitext(src)[1].lower(), os.path.getsize(src)
    if Image is None or ext not in (".png", ".jpg", ".jpeg", ".webp"):
        shutil.copy2(src, dst)
        return before, before
    with Image.open(src) as im:
        longest = max(im.size)
        if longest <= max_edge and before <= KEEP_REENCODE_BYTES:
            shutil.copy2(src, dst)
            return before, before
        im = ImageOps.exif_transpose(im)
        if im.mode in ("P", "LA", "PA"):
            im = im.convert("RGBA")
        elif im.mode not in ("RGB", "RGBA", "L"):
            im = im.convert("RGB")
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)  # 拡大はしない
        if ext == ".png":
            im.save(dst, "PNG", optimize=True)
        elif ext == ".webp":
            im.save(dst, "WEBP", quality=90, method=6)
        else:
            im.convert("RGB").save(dst, "JPEG", quality=85, optimize=True, progressive=True)
    after = os.path.getsize(dst)
    if after >= before and longest <= max_edge:  # 縮小できず、かえって大きくなるなら元のまま
        shutil.copy2(src, dst)
        after = before
    return before, after


def build_assets():
    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = ImageOps = None
        print("warning: Pillow が無いため、画像は縮小せずそのままコピーします")
    for d in sorted(glob.glob("assets/*/")):
        name = os.path.basename(os.path.normpath(d))
        policy = FOLDER_POLICY.get(name, DEFAULT_POLICY)
        max_edge = policy["max_edge"]
        out_dir = f"{OUT}/assets/{name}"
        os.makedirs(out_dir, exist_ok=True)
        if policy["mode"] == "keep":
            for f in sorted(os.listdir(d)):
                src = os.path.join(d, f)
                if not os.path.isfile(src):
                    continue
                before, after = keep_image(Image, ImageOps, src, os.path.join(out_dir, f), max_edge)
                if after != before:
                    print(f"  {name}/{f} ({kb(before)}) -> {kb(after)}")
            continue
        files = [f for f in os.listdir(d) if os.path.splitext(f)[1].lower() in IMG_EXTS | AUDIO_EXTS]
        files.sort(key=natural_key, reverse=True)
        entries = []
        for f in files:
            src, ext = os.path.join(d, f), os.path.splitext(f)[1].lower()
            if ext in IMG_EXTS and Image:
                raw = open(src, "rb").read()
                h = hashlib.sha1(raw + f"{max_edge}-{QUALITY}".encode()).hexdigest()[:8]
                out_name = f"{os.path.splitext(f)[0]}.{h}.webp"
                with Image.open(src) as im:
                    im = ImageOps.exif_transpose(im)  # iPhone写真の向きを反映
                    if im.mode in ("P", "LA", "PA"):
                        im = im.convert("RGBA")
                    elif im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGB")
                    im.thumbnail((max_edge, max_edge), Image.LANCZOS)  # 拡大はしない
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
    total = sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(OUT) for f in fs)
    print(f"公開サイズ合計: {kb(total)}")


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(".", OUT, ignore=ignore)
    build_assets()
    build_games()
    stamp_build()
    report()
