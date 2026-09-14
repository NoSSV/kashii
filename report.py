from __future__ import annotations

import csv
import html
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .utils import mean
from .xlsx_min import score_style, write_xlsx


def build_heatmap(scored: List[dict], dates: List[str], targets: List[dict]):
    by_machine: Dict[int, Dict[str, dict]] = defaultdict(dict)
    model = {}
    for r in scored:
        m = int(r["machine_no"])
        by_machine[m][r["data_date"]] = r
        model[m] = r.get("model") or ""
    target_map = {int(x["machine_no"]): x for x in targets}
    rows = [["台番", "機種名", *dates, "10日平均", "直近3日", "狙い度", "平均信頼度"]]
    for m in sorted(by_machine):
        vals = [by_machine[m].get(d, {}).get("daily_score") for d in dates]
        avg10 = mean(vals)
        avg3 = mean(vals[:3])
        t = target_map.get(m, {})
        rows.append([
            m, model.get(m, ""), *vals,
            round(avg10, 1) if avg10 is not None else None,
            round(avg3, 1) if avg3 is not None else None,
            t.get("target_score"), t.get("confidence")
        ])
    return rows


def export_csv(path: Path, scored: List[dict]):
    fields = [
        "data_date", "machine_no", "model", "category", "games", "bb", "rb", "art",
        "max_hold", "diff", "output_rate", "bb_rate", "rb_rate", "combined_rate",
        "prev_final", "daily_score", "confidence", "source_url"
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(scored, key=lambda x: (x["data_date"], int(x["machine_no"])), reverse=True):
            w.writerow(r)


def export_xlsx(path: Path, scored: List[dict], dates: List[str], targets: List[dict], cfg: dict):
    heat = build_heatmap(scored, dates, targets)
    top_n = int(cfg.get("excel_top_n", 30))
    ranking = [["順位", "台番", "機種名", "狙い度", "10日平均", "直近3日", "近接台平均", "機種平均", "日数", "平均信頼度"]]
    for i, r in enumerate(targets[:top_n], 1):
        ranking.append([i, r["machine_no"], r["model"], r["target_score"], r["ten_day_avg"], r["recent3_avg"], r["neighbor_avg"], r["model_avg"], r["days"], r["confidence"]])

    raw = [["日付", "台番", "機種名", "G数", "BB", "RB", "ART/AT", "最大持玉", "差枚", "出率", "BB確率", "RB確率", "合算", "日別スコア", "信頼度", "取得URL"]]
    for r in sorted(scored, key=lambda x: (x["data_date"], int(x["machine_no"])), reverse=True):
        raw.append([r.get("data_date"), r.get("machine_no"), r.get("model"), r.get("games"), r.get("bb"), r.get("rb"), r.get("art"), r.get("max_hold"), r.get("diff"), r.get("output_rate"), r.get("bb_rate"), r.get("rb_rate"), r.get("combined_rate"), r.get("daily_score"), r.get("confidence"), r.get("source_url")])

    info = [
        ["ワンダーランド香椎II スロット分析"],
        ["生成日時", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["対象日", " / ".join(dates)],
        ["データ元", cfg.get("source_url")],
        ["注記", "日別スコア/狙い度は公開データの相対評価で、設定や勝利を保証するものではありません。"],
        ["低回転補正", "G数が少ない台は極端な高得点にならないよう50点側へ圧縮しています。"],
        ["Aタイプ", "RB効率を最重視。BB効率、稼働、出玉系指標も加点。"],
        ["AT/ART", "稼働、当たり密度、最大持玉/差枚/出率など取得できる指標を相対評価。"],
        ["狙い度", "台番10日傾向42% + 直近3日23% + 近接台20% + 機種全体15%。履歴日数で50点側に縮小。"],
    ]

    def heat_style(ri, ci, v):
        if ri == 1:
            return 2
        # dates start col=3 and summary scores follow
        if ci >= 3 and isinstance(v, (int, float)):
            return score_style(float(v))
        return 0

    def rank_style(ri, ci, v):
        if ri == 1:
            return 2
        if ci in (4, 5, 6, 7, 8) and isinstance(v, (int, float)):
            return score_style(float(v))
        return 0

    write_xlsx(path, [
        ("Dashboard", info, lambda r,c,v: 1 if r == 1 else 0, [24, 90]),
        ("Ranking", ranking, rank_style, [8, 9, 36, 11, 11, 11, 11, 11, 8, 12]),
        ("Heatmap", heat, heat_style, [9, 36] + [11] * (len(dates) + 4)),
        ("RawData", raw, lambda r,c,v: 2 if r == 1 else 0, [12, 9, 36, 10, 8, 8, 8, 12, 10, 10, 10, 10, 10, 12, 10, 52]),
    ])


def export_html(path: Path, scored: List[dict], dates: List[str], targets: List[dict], cfg: dict):
    heat = build_heatmap(scored, dates, targets)
    headers = heat[0]
    rows = heat[1:]

    def cls(v):
        if not isinstance(v, (int, float)):
            return ""
        if v >= 80: return "s80"
        if v >= 60: return "s60"
        if v < 40: return "s40"
        return "s50"

    ranking_html = []
    for i, r in enumerate(targets[:30], 1):
        ranking_html.append(f"<tr><td>{i}</td><td>{r['machine_no']}</td><td>{html.escape(r['model'])}</td><td class='{cls(r['target_score'])}'>{r['target_score']:.1f}</td><td>{r['ten_day_avg']:.1f}</td><td>{r['recent3_avg']:.1f}</td><td>{r['neighbor_avg']:.1f}</td><td>{r['confidence']:.1f}%</td></tr>")

    heat_html = []
    for row in rows:
        cells = []
        for j, v in enumerate(row):
            c = cls(v) if j >= 2 else ""
            cells.append(f"<td class='{c}'>{'' if v is None else html.escape(str(v))}</td>")
        heat_html.append("<tr>" + "".join(cells) + "</tr>")

    doc = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>香椎II スロット分析</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Yu Gothic",sans-serif;margin:0;background:#f4f7fb;color:#18212f}}main{{max-width:1600px;margin:auto;padding:24px}}h1{{margin:0 0 8px}}.sub{{color:#62748a;margin-bottom:22px}}.card{{background:white;border-radius:16px;padding:18px;margin:18px 0;box-shadow:0 6px 20px #15304a14;overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border:1px solid #dfe7f0;padding:8px;text-align:center;white-space:nowrap}}th{{position:sticky;top:0;background:#1f4e78;color:white;z-index:2}}td:nth-child(2){{text-align:left}}.s80{{background:#f4cccc;font-weight:700}}.s60{{background:#ffe699}}.s50{{background:#fff}}.s40{{background:#e2f0d9}}.note{{font-size:13px;color:#5f6f82;line-height:1.7}}input{{padding:10px 12px;border:1px solid #ccd7e2;border-radius:10px;width:280px;margin-bottom:10px}}
</style></head><body><main><h1>ワンダーランド香椎II スロット分析</h1><div class="sub">生成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ｜ 対象 {html.escape(' / '.join(dates))}</div>
<div class="card"><h2>狙い台ランキング TOP30</h2><p class="note">「狙い度」は過去10日の台番・近接台・機種傾向をまとめた参考スコアです。未来の設定を保証する確率ではありません。</p><table><thead><tr><th>順位</th><th>台番</th><th>機種</th><th>狙い度</th><th>10日平均</th><th>直近3日</th><th>近接台平均</th><th>信頼度</th></tr></thead><tbody>{''.join(ranking_html)}</tbody></table></div>
<div class="card"><h2>10日ヒートマップ</h2><input id="q" placeholder="台番・機種名で絞り込み"><table id="heat"><thead><tr>{''.join(f'<th>{html.escape(str(h))}</th>' for h in headers)}</tr></thead><tbody>{''.join(heat_html)}</tbody></table></div>
<div class="card note"><b>スコア設計</b><br>AタイプはRB効率を強めに評価。AT/ART系は稼働、当たり密度、出玉系指標を相対評価。低回転は50点側へ縮小します。データ元: {html.escape(str(cfg.get('source_url')))}</div>
<script>const q=document.getElementById('q');q.addEventListener('input',()=>{{const s=q.value.toLowerCase();document.querySelectorAll('#heat tbody tr').forEach(tr=>tr.style.display=tr.innerText.toLowerCase().includes(s)?'':'none')}});</script></main></body></html>'''
    path.write_text(doc, encoding="utf-8")
