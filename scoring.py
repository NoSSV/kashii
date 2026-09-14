from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from .utils import clamp, mean, percentile_rank, stdev

ATYPE_KEYWORDS = [
    "ジャグ", "ハナハナ", "ニューパル", "クランキー", "バーサス", "ハナビ",
    "ディスクアップ", "アレックス", "ゲッターマウス", "サンダーV", "ファミスタ"
]


def category(model: str) -> str:
    s = model or ""
    return "A" if any(k.lower() in s.lower() for k in ATYPE_KEYWORDS) else "AT"


def _metric(row: dict, name: str) -> Optional[float]:
    g = row.get("games")
    bb = row.get("bb")
    rb = row.get("rb")
    art = row.get("art")
    if name == "engagement":
        return float(g) if g is not None else None
    if name == "bb_eff":
        if g and bb is not None and g > 0:
            return float(bb) / float(g)
        den = row.get("bb_rate")
        return (1.0 / den) if den and den > 0 else None
    if name == "rb_eff":
        if g and rb is not None and g > 0:
            return float(rb) / float(g)
        den = row.get("rb_rate")
        return (1.0 / den) if den and den > 0 else None
    if name == "hit_eff":
        hits = sum(x or 0 for x in (bb, rb, art))
        if g and g > 0:
            return float(hits) / float(g)
        den = row.get("combined_rate")
        return (1.0 / den) if den and den > 0 else None
    if name == "performance":
        if row.get("diff") is not None:
            return float(row["diff"])
        if row.get("output_rate") is not None:
            return float(row["output_rate"] - 100.0)
        if row.get("max_hold") is not None:
            return float(row["max_hold"])
        return None
    if name == "max_hold":
        return float(row["max_hold"]) if row.get("max_hold") is not None else None
    return None


def _confidence(row: dict) -> float:
    g = row.get("games")
    if g is not None and g >= 0:
        return clamp(math.sqrt(max(0.0, float(g)) / 5000.0), 0.12, 1.0)
    events = sum((row.get(k) or 0) for k in ("bb", "rb", "art"))
    return clamp(0.25 + events / 40.0, 0.25, 0.75)


def _cap_low_sample(score: float, games: Optional[int], caps: dict) -> float:
    if games is None:
        return min(score, 72.0)
    for threshold, cap in sorted((int(k), float(v)) for k, v in caps.items()):
        if games < threshold:
            return min(score, cap)
    return score


def compute_daily_scores(rows: List[dict], low_sample_caps: dict) -> List[dict]:
    # group by date+model; fall back to date+category if a model has too few units
    by_model: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    by_cat: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        by_model[(r["data_date"], r.get("model") or "")].append(r)
        by_cat[(r["data_date"], category(r.get("model") or ""))].append(r)

    out = []
    metrics = ["engagement", "bb_eff", "rb_eff", "hit_eff", "performance", "max_hold"]
    for r in rows:
        c = category(r.get("model") or "")
        peers = by_model[(r["data_date"], r.get("model") or "")]
        if len(peers) < 3:
            peers = by_cat[(r["data_date"], c)]
        pcts = {}
        for m in metrics:
            vals = [v for v in (_metric(p, m) for p in peers) if v is not None]
            pcts[m] = percentile_rank(vals, _metric(r, m), True) if vals else None

        if c == "A":
            weights = {
                "engagement": 0.18,
                "rb_eff": 0.37,
                "bb_eff": 0.20,
                "hit_eff": 0.10,
                "performance": 0.15,
            }
        else:
            weights = {
                "engagement": 0.30,
                "hit_eff": 0.20,
                "performance": 0.35,
                "max_hold": 0.15,
            }

        num = 0.0
        den = 0.0
        for m, w in weights.items():
            p = pcts.get(m)
            if p is None:
                continue
            num += p * w
            den += w
        raw = num / den if den else 50.0
        conf = _confidence(r)
        score = 50.0 + (raw - 50.0) * conf
        score = _cap_low_sample(score, r.get("games"), low_sample_caps)
        score = round(clamp(score, 0.0, 100.0), 1)
        x = dict(r)
        x["category"] = c
        x["confidence"] = round(conf * 100.0, 1)
        x["daily_score"] = score
        out.append(x)
    return out


def compute_target_scores(scored_rows: List[dict], latest_dates: List[str]) -> List[dict]:
    rows_by_machine: Dict[int, List[dict]] = defaultdict(list)
    rows_by_model: Dict[str, List[dict]] = defaultdict(list)
    machine_model: Dict[int, str] = {}
    for r in scored_rows:
        m = r.get("machine_no")
        if m is None:
            continue
        m = int(m)
        rows_by_machine[m].append(r)
        rows_by_model[r.get("model") or ""].append(r)
        # newest row wins because latest_dates is ordered descending in callers, but be explicit below
        machine_model[m] = r.get("model") or ""

    date_rank = {d: i for i, d in enumerate(latest_dates)}
    for arr in rows_by_machine.values():
        arr.sort(key=lambda r: date_rank.get(r["data_date"], 999))

    result = []
    for machine, arr in rows_by_machine.items():
        model = arr[0].get("model") or ""
        scores = [float(r["daily_score"]) for r in arr]
        hist = mean(scores) or 50.0
        recent3 = mean(scores[:3]) or hist
        model_scores = [float(r["daily_score"]) for r in rows_by_model.get(model, [])]
        model_avg = mean(model_scores) or 50.0

        neighbor_scores = []
        for n in (machine - 2, machine - 1, machine + 1, machine + 2):
            narr = rows_by_machine.get(n)
            if narr:
                neighbor_scores.extend(float(x["daily_score"]) for x in narr)
        neighbor_avg = mean(neighbor_scores) if neighbor_scores else 50.0

        raw = 0.42 * hist + 0.23 * recent3 + 0.20 * neighbor_avg + 0.15 * model_avg
        n_days = len({r["data_date"] for r in arr})
        history_conf = clamp(n_days / max(1, len(latest_dates)), 0.2, 1.0)
        target = 50.0 + (raw - 50.0) * history_conf
        vol = stdev(scores) or 0.0
        latest = arr[0]
        result.append({
            "machine_no": machine,
            "model": model,
            "target_score": round(clamp(target, 0, 100), 1),
            "ten_day_avg": round(hist, 1),
            "recent3_avg": round(recent3, 1),
            "neighbor_avg": round(neighbor_avg, 1),
            "model_avg": round(model_avg, 1),
            "volatility": round(vol, 1),
            "days": n_days,
            "latest_games": latest.get("games"),
            "latest_score": latest.get("daily_score"),
            "confidence": round(mean([r.get("confidence") for r in arr]) or 0.0, 1),
        })
    result.sort(key=lambda r: (-r["target_score"], -r["days"], r["machine_no"]))
    return result
