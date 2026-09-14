# Kashii Slot Analyzer PWA v0.2

ワンダーランド香椎II向けのスマホ対応PWAです。

## できること
- ホーム: 今日の注目候補 / TOP10
- 狙い台ランキング: 検索・機種・点数で絞り込み
- 全台一覧: 台番順に確認
- 10日ヒートマップ
- 台詳細: 10日スコア推移 / G数 / 差枚 / BB / RB
- CSV読込: PC版 `raw_latest.csv` をスマホで直接読込
- オフライン: 最後のデータを端末保存
- PWA: Androidのホーム画面へインストール可能

## まず試す
`data/latest.json` が空の場合はデモデータを表示します。

実データはアプリの「設定」→「CSVを選択」から、PC版が作る `raw_latest.csv` を読み込んでください。

## GitHub Pagesで公開
このフォルダをリポジトリに置き、GitHub Pagesを有効化すればHTTPSでPWAとして使えます。
`.github/workflows/pages.yml` も同梱しています。

## PC版CSVを公開データへ変換
Windowsでは `tools/sync_from_pc_analyzer.bat` に `raw_latest.csv` をドラッグ＆ドロップすると `data/latest.json` を更新します。

コマンドなら:
```bash
python tools/convert_csv_to_json.py path/to/raw_latest.csv data/latest.json
```

## 注意
スコアは公開データを使った相対評価です。設定や勝利を保証するものではありません。
