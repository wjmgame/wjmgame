#!/usr/bin/env python3
"""公開前の生成処理(deploy.yml から呼ばれる。手元でも `python3 scripts/build.py` で試せる)

 - games.json        : games/<名前>/index.html の <meta name="game-*"> から作る(トップのタイル一覧)
 - assets/<種類>/list.json : assets/ 配下の各フォルダ(icons を除く)の素材一覧。ファイル名の降順(自然順)
                       例: ["IMG_5626.jpeg","IMG_5600.png"]。素材フォルダを足すだけで list.json も増える
"""
import glob, json, os, re, sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIST_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".mp3", ".wav", ".ogg", ".m4a"}
SKIP_DIRS = {"icons"}


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


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
    with open("games.json", "w", encoding="utf-8") as f:
        json.dump({"games": games}, f, ensure_ascii=False, indent=1)
    print("games.json:", json.dumps([g["id"] for g in games], ensure_ascii=False))


def build_lists():
    for d in sorted(glob.glob("assets/*/")):
        name = os.path.basename(os.path.normpath(d))
        if name in SKIP_DIRS:
            continue
        files = [f for f in os.listdir(d) if os.path.splitext(f)[1].lower() in LIST_EXTS]
        files.sort(key=natural_key, reverse=True)
        with open(os.path.join(d, "list.json"), "w", encoding="utf-8") as f:
            json.dump(files, f, ensure_ascii=False)
        print(f"assets/{name}/list.json:", json.dumps(files, ensure_ascii=False))


if __name__ == "__main__":
    build_games()
    build_lists()
