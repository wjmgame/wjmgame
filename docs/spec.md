# 共通仕様

## ディレクトリ構成
```
/
├── index.html / sw.js / manifest.webmanifest   ルート固定(公開範囲・PWAの都合)
├── .github/workflows/deploy.yml                push で build.py を実行して公開
├── scripts/build.py                            games.json と assets/*/list.json の生成
├── shared/    common.js(音・ミュート・保護者ゲート・パス解決) / faces.js(顔写真) / theme.css(配色)
├── assets/    faces/(顔写真) icons/(アイコン) ほか。置いて push するだけ(list.json は自動生成)
├── games/<名前>/index.html   ゲーム本体(必要なら同じフォルダに game.js・style.css・専用素材)
└── docs/spec.md              この文書
```

## 新しいゲームを足す
1. `games/<名前>/index.html` を作り、`<head>` に次を入れる(meta は name → content の順で書く)
```html
<meta name="game-title" content="ぬりえ">
<meta name="game-icon" content="🎨">
<meta name="game-color" content="#ffc83d">
<meta name="game-order" content="20">   <!-- 小さいほどトップの先頭 -->
<script src="../../shared/common.js"></script>
<script src="../../shared/faces.js"></script>  <!-- 顔写真を使うときだけ -->
```
2. コミットして push するだけ。index.html・sw.js の更新は不要

## 共通機能 Asobo(common.js)
- パス: `Asobo.url("assets/...")` でルート基準のURLを得る / `Asobo.home()` でトップへ戻る。`../` などの相対パスを直書きしない(フォルダの深さが変わっても動く)
- 音: `muted()` / `setMuted(v)` / `tone(freq,dur,vol,glide=1.5)`(音階は glide=1) / `noise()` / `blip(i)` / `pop()` / `SCALE`。ミュートは localStorage の `muted` で全ゲーム共通。音やミュートを自前実装しない
- 自動で行うこと: 右上1.5秒長押しでトップへ戻る保護者ゲート(長押し中に輪が広がる)、ズーム・長押しメニューの抑止、iOS向け音の初期化。トップは `<html data-asobo="top">` でゲートを無効化し、独自の保護者メニュー(音オン/オフ)を持つ

## 顔写真(faces.js)
- `assets/faces/` に画像を置いて push。`list.json` は build.py が生成(ファイル名の降順・自然順。1枚目がはじめのリーダー)
- `list.json` の形式: ファイル名だけの文字列配列。例 `["b.jpg","a.png","10.webp"]`。対象拡張子は jpg/jpeg/png/webp/gif/avif。手で編集しない
- `Asobo.faces.urls(max)` → 画像URLの配列 / `Asobo.faces.canvases({max,size,onEach})` → 中央を正方形に切り抜いた canvas を読めたものから返す。一覧が無いときは 1.jpg, 2.jpg … の連番を探す
- 大きい写真は読み込みが遅いので、300px四方くらいに縮小して置くのがおすすめ

## 素材を足す
- `assets/<種類>/` に置いて push。icons 以外のフォルダは list.json が自動で作られる(画像と mp3/wav/ogg/m4a が対象)
- そのゲーム専用の素材は `games/<名前>/` の中に置く

## 作りの決まり
- タップのみ・失敗なし・マルチタッチ対応・どこをタップしても反応・文字が読めなくても遊べる
- 配色は shared/theme.css(空色 #8fd3f4、コーラル #ff7a6b、サン #ffc83d、リーフ #4ccb8a、グレープ #8e7cff、文字色 #23305a)

## キャッシュ(sw.js)
- HTML・JS・CSS はキャッシュ優先で裏で更新(反映は次に開いたとき) / games.json と list.json は通信優先 / 画像はキャッシュにあれば再取得しない
- sw.js 自体を変えたとき、または同じ名前で画像を差し替えたときは `CACHE` の版数を上げる
- ホーム画面のアプリは、更新後に2回開くと新しくなる

## トラブル時
- タイルが出ない: 公開URLの `games.json` が200で返るか確認。Actions の最後のステップ「公開結果の確認」が各ファイルの応答を出す。反映直後は古い404が残ることがある
