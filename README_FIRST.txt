【最初にここだけ読めばOK】

1. Windows PCでこのフォルダを展開する
2. setup.bat をダブルクリック（初回だけ）
3. 以後は run.bat をダブルクリック
4. 終わると output フォルダが自動で開く

出力物
- kashii2_analysis.xlsx : Excel
- dashboard.html       : ブラウザで見るヒートマップ＋狙い台ランキング
- raw_latest.csv       : 取得した直近データ

初回は過去10日分を集めるため時間がかかります。
2回目以降はSQLiteに蓄積し、基本的に新しい日だけ取得します。

もし失敗したら logs/run.log をChatGPTに送ってください。
403の場合は無理に回避せず停止する設計です。
