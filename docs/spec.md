# 共通仕様

## ディレクトリ構成
```
/
├── index.html / sw.js / manifest.webmanifest   ルート固定(公開範囲・PWAの都合)
├── .github/workflows/deploy.yml                push で build.py を実行して公開
├── scripts/   build.py(公開用の _site/ を生成) / check.py(公開前チェック) / browser_test.py(ブラウザでの実行テスト) / checks.json(テストのオン・オフ)
├── shared/    common.js(音・ミュート・保護者ゲート・パス解決) / faces.js(顔写真) / theme.css(配色)
├── assets/    faces/(顔写真の元画像) icons/(アイコン) <用途>/(用途ごとの素材。例 mekuri/)。置いて push するだけ(縮小と list.json は自動)
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
- 素材の一覧: `Asobo.assets.urls("フォルダ", {max, shuffle, ext})` が `assets/<フォルダ>/list.json` を読んで、URLの配列を返す。**順番は毎回ランダム**(`shuffle:false` でファイル名の降順)。`max` を指定すると、全体からランダムにその数だけ選ぶ。`ext` は対象の拡張子の正規表現(既定は画像)。画像の読み込みを自前で書かない
- 画面の隅のボタン: `Asobo.cornerButton({corner, icon, label, onHold})`(`corner` は `'left'`=左上 / `'right'`=右上。`'top-left'` などは使えない。例: `Asobo.cornerButton({corner:'left', icon:'⚙️', label:'設定（長押し）', onHold: openPanel})`)。薄い半透明のアイコンを常に表示し、操作は1.5秒の長押しだけ(長押し中に輪が広がる)。右上=戻る🏠(自動で付く)、左上=設定⚙️(ぞろぞろ)。トップは右上に保護者メニュー⚙️。ゲームごとに隅のボタンを自前で作らない
- 自動で行うこと: 右上に🏠ボタン(長押しでトップへ戻る)、ズーム・長押しメニューの抑止、iOS向け音の初期化。トップは `<html data-asobo="top">` で🏠を付けず、独自の保護者メニュー(音オン/オフ)を持つ

## 顔写真(faces.js)
- `assets/faces/` に画像を置いて push するだけ。大きさは自由(元画像のまま置いてよい)
- 公開時に build.py が、長辺480pxのWebPへ縮小して公開する。元画像は公開されない。出力名は `<元の名前>.<8桁ハッシュ>.webp`(差し替えると名前が変わる)
- `list.json` は build.py が公開側に生成(元のファイル名の降順・自然順。読み込み側が毎回シャッフルする)。形式はファイル名だけの文字列配列。例 `["b.1a2b3c4d.webp","a.5e6f7a8b.webp"]`。手で編集しない
- `Asobo.faces.urls(max, {shuffle})` → 画像URLの配列 / `Asobo.faces.canvases({max,size,onEach,shuffle})` → 中央を正方形に切り抜いた canvas を読めたものから返す。どちらも既定で**毎回ランダム**(1枚目のリーダーも含む)。写真が `max` 枚より多いときは、全体からランダムに選ぶ。固定にするときは `shuffle:false`(ファイル名の降順)。一覧が無いときは 1.jpg, 2.jpg … の連番を探す(ローカル確認用)

## 素材を足す
- `assets/<種類>/` に置いて push。画像は、フォルダごとの方針(`scripts/build.py` の `FOLDER_POLICY`)で縮小して公開される。音声(mp3/wav/ogg/m4a)はそのまま公開
  - `faces` など(既定): 長辺480pxのWebPに変換し、`list.json` を自動生成する。出力名はハッシュ付きなので、`list.json` から読む
  - `icons`: 名前と形式を保ったまま、長辺512pxを超えたら縮小、100KBを超えたら再圧縮する(小さければ元のまま)。ゲームやmanifestから `Asobo.url("assets/icons/star.png")` のように固定の名前で参照できる。`list.json` は作らない。manifest と apple-touch-icon のアイコンは、小さいので元のバイト列のまま公開される
  - 新しい種類のフォルダは既定(WebP変換+list.json)になる。固定の名前で参照したいときは、`FOLDER_POLICY` に `"keep"` で追加する
- 用途が違う素材は、用途ごとに `assets/<用途>/` のフォルダを分ける(例: めくりゲームの写真は `assets/mekuri/`)。`assets/photos/` は廃止。読み込みは `Asobo.assets.urls('<用途>')`。用途のフォルダは、既定でWebPに変換され list.json が作られる
- そのゲーム専用の素材は `games/<名前>/` の中に置く。こちらは縮小されないので、先に小さくしておく(300KB超は check.py が警告)

## ローカルで確認
- `python3 scripts/build.py` で `_site/` ができる(Pillow が必要: `pip install pillow`)。`python3 scripts/check.py` で公開前チェック、`python3 scripts/browser_test.py` でブラウザテスト(Playwright が必要: `pip install playwright`)。`python3 -m http.server -d _site` で開いて確認もできる。`_site/` は git に入れない

## 作りの決まり
- タップのみ・失敗なし・マルチタッチ対応・どこをタップしても反応・文字が読めなくても遊べる
- 通信量を抑える: 公開サイズは小さく保つ(現在の合計は約150KB)
- 画面の隅のボタンは `Asobo.cornerButton` を使う(薄く常に表示、操作は1.5秒の長押し)
- 配色は shared/theme.css(空色 #8fd3f4、コーラル #ff7a6b、サン #ffc83d、リーフ #4ccb8a、グレープ #8e7cff、文字色 #23305a)

## キャッシュと自動更新(sw.js)
- 公開のたびに build.py が、サイト全体のハッシュを sw.js の `BUILD` に書き込む(`precache.json` も生成)。内容が変わると sw.js も変わり、ブラウザが更新を検知する。**`CACHE` の版数を手で上げる必要はない。`sw.js` の `BUILD = "dev"` は書き換えない**
- 更新時は、新しい版の全ファイル(precache.json、1MB超は除く)を先読みしてから切り替える。1つでも失敗したら古い版のまま続ける
- トップ画面は、新しい版に切り替わると1回だけ自動で再読み込みする。ゲーム中は再読み込みせず、次にトップへ戻ったとき新しくなる。アプリを前面に戻したときにも更新を確認する(開き直しは不要)
- 配信中のファイルの扱い: HTML・JS・CSS はキャッシュを即表示して裏で最新版を確認 / games.json と list.json は通信優先 / 画像はキャッシュにあれば再取得しない(差し替えると名前が変わる)
- ゲームや素材の追加で sw.js の更新は不要

## 公開前チェックとブラウザテスト
- 実行のきっかけ: `main` への push(公開あり) / プルリクエスト(チェックのみ、公開しない) / Actions タブからの手動実行(公開あり)。順番は build → check → ブラウザテスト → 公開。**エラーがあれば公開されず、今の公開版が残る**
- **公開を止めるエラー(check.py)**: 参照ファイルの実在(HTML・manifest・games.json・list.json・precache.json) / ゲームのメタタグ4種(game-title・icon・color・order。color は #色コード、order は数字) / JavaScript の構文 / 各ゲームが shared/common.js を読み込んでいること(Asobo.faces を使うなら faces.js も) / 壊れた画像 / 極端に大きいファイル(1MB超、音声は3MB超)
- **警告だけ(公開は止めない)**: 300KB超のファイル / game-order の重複 / 音の自前実装(AudioContext)・ミュートの自前読み込み・相対パスの直書き(`../assets/` など)
- **ブラウザでの実行テスト(browser_test.py)**: トップのタイル数 / 各ゲームを開いて数回タップしたときの JS エラー・通信エラー / 顔写真の読み込み / 素材フォルダの読み込み(list.json の画像がすべて取得できる) / 右上のボタンの表示と、長押しでトップへ戻る / ぞろぞろは左上の長押しで設定 / ミュート設定の引き継ぎ / 自動更新の先読みと、通信なしでの起動。失敗したテストは1回やり直す
- **ブラウザテストのオン・オフ**: `scripts/checks.json` の `browser_test` を `"on"`(失敗で公開を止める) / `"warn"`(失敗しても公開し、警告を出す) / `"off"`(実行しない)に書き換えてコミットする。1回だけ飛ばすときは、コミットメッセージに `[skip-browser]` を入れる
- 自動では判断できないこと: 遊べるか・見た目・音の良し悪しは、実機で確認する

## トラブル時
- タイルが出ない: 公開URLの `games.json` が200で返るか確認。Actions の最後のステップ「公開結果の確認」が各ファイルの応答を出す。反映直後は古い404が残ることがある
