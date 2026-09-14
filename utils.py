from __future__ import annotations

import math
import re
from typing import Any, Iterable, Optional


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\u3000", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def parse_number(value: Any) -> Optional[float]:
    s = clean_text(value)
    if not s or s in {"-", "—", "―", "–", "なし", "null", "None"}:
        return None
    s = s.replace(",", "").replace("枚", "").replace("玉", "").replace("pt", "")
    s = s.replace("回", "").replace("G", "").replace("ｇ", "").replace("％", "%")
    # 1/286 -> 286 (denominator)
    m = re.search(r"1\s*/\s*([0-9]+(?:\.[0-9]+)?)", s)
    if m:
        return float(m.group(1))
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_int(value: Any) -> Optional[int]:
    n = parse_number(value)
    if n is None:
        return None
    return int(round(n))


def parse_percent(value: Any) -> Optional[float]:
    n = parse_number(value)
    if n is None:
        return None
    return float(n)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def mean(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not vals:
        return None
    return sum(vals) / len(vals)


def stdev(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def percentile_rank(values: list[float], x: Optional[float], higher_is_better: bool = True) -> Optional[float]:
    vals = sorted(v for v in values if v is not None and not math.isnan(v))
    if x is None or not vals:
        return None
    if len(vals) == 1:
        p = 0.5
    else:
        less = sum(1 for v in vals if v < x)
        equal = sum(1 for v in vals if v == x)
        p = (less + 0.5 * equal) / len(vals)
    if not higher_is_better:
        p = 1.0 - p
    return 100.0 * p


def japanese_safe_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', '_', s)
