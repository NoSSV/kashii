# ワンダーランド香椎II スロット自動分析

対象: `https://daidata.goraggio.com/101219/list?mode=psModelNameSearch&ps=S`

## できること

- 台DATAONLINEから直近10日分を取得
- 取得データをSQLiteへ蓄積し、2回目以降は不足日だけ更新
- 台番×日付の0〜100点ヒートマップ
- 低回転サンプルを50点側へ縮める補正
- Aタイプ系とAT/ART系で重みを分離
- 台番単体・近接台・機種全体の過去傾向を使った「狙い度」ランキング
- Excel / HTML / CSVを自動出力

## 重要

このツールはサイトのアクセス制御を回避しません。プロキシ/IPローテーション、CAPTCHA回避、多重ブラウザ並列などは実装していません。403/429が続く場合は停止します。利用規約・サイト側のルールに従って使用してください。

`request_delay_seconds` は既定1.0秒です。負荷を増やす方向への設定変更は推奨しません。

## 初回

1. Python 3.11+ をインストール
2. `setup.bat`
3. `run.bat`

## 通常実行

`run.bat`

高速確認だけなら `run_fast.bat`。fastモードは全台一覧中心で、詳細ページを巡回しないためG数等が不足する場合があります。

## スコアの意味

`日別スコア` は「その日の公開データが同一機種の他台と比べて高設定っぽい挙動にどれだけ近いか」を相対評価した参考値です。設定を断定するものではありません。

- ジャグラー等のAタイプ: RB効率を最重視、次にBB効率・稼働・出玉系指標
- AT/ART/スマスロ: 稼働、当たり密度、最大持玉/差枚/出率など取得できる指標を相対評価
- 低回転: 強い数字でもスコアを50付近へ圧縮

`狙い度` は直近10日の台番傾向、近接台傾向、機種傾向をまとめたランキングです。未来の設定を保証する確率ではありません。

## 取得方式

過去の公開事例では、台DATAONLINEに以下のURL形式が存在します。

- `/{store_id}/all_list?ps=S&hist_num=N`
- `/{store_id}/unit_list?model=...&ballPrice=...&hist_num=N`
- 利用同意Cookieが必要な構成では `/agreement` への同意POST

本ツールはHTMLの見出し名を見て列を判定するため、列順が多少変わっても動くようにしています。

## データ保存

- `data/kashii2.db` : SQLite本体
- `output/kashii2_analysis.xlsx`
- `output/dashboard.html`
- `output/raw_latest.csv`
- `logs/run.log`

## サイト仕様変更時

`logs/run.log` と、可能ならブラウザで対象ページを「Webページ、HTMLのみ」で保存したファイルを送れば、パーサーを修正できます。

## 参考URL

- 公式店舗ページ: https://www.wonderland.gr.jp/kashii2/profile.html
- 台DATAONLINE: https://daidata.goraggio.com/101219
- GOLUCK サービス説明: https://www.goluck.co.jp/service/daidataonline_info.html
