from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .utils import clean_text, parse_int, parse_number, parse_percent


COLUMN_ALIASES = {
    "machine_no": ["台番号", "台番"],
    "model": ["機種名", "機種"],
    "ball_price": ["貸玉", "貸メダル", "レート"],
    "games": ["累計スタート", "累計回転", "総回転", "G数", "ゲーム数", "回転数"],
    "bb": ["BB回数", "BB", "BIG回数", "BIG"],
    "rb": ["RB回数", "RB", "REG回数", "REG"],
    "art": ["ART回数", "AT回数", "ART", "AT"],
    "max_hold": ["最大持玉", "最大出玉", "最大獲得", "最大MY"],
    "bb_rate": ["BB確率", "BIG確率"],
    "rb_rate": ["RB確率", "REG確率"],
    "art_rate": ["ART確率", "AT確率"],
    "combined_rate": ["合成確率", "合算確率"],
    "prev_final": ["前日最終スタート", "前日最終G", "前日最終"],
    "diff": ["差枚", "差枚数", "差玉"],
    "output_rate": ["出率", "機械割"],
}


def normalize_header(s: str) -> str:
    return re.sub(r"[\s　:：・]", "", clean_text(s))


NORMALIZED_ALIAS = {
    key: {normalize_header(v) for v in vals}
    for key, vals in COLUMN_ALIASES.items()
}


@dataclass(frozen=True)
class ModelLink:
    model: str
    ball_price: Optional[str]
    href: str


class SiteBlocked(RuntimeError):
    pass


class GoraggioClient:
    BASE = "https://daidata.goraggio.com"

    def __init__(self, config: dict, logger: logging.Logger):
        self.cfg = config
        self.log = logger
        self.store_id = str(config["store_id"])
        self.delay = float(config.get("request_delay_seconds", 1.0))
        self.timeout = int(config.get("request_timeout_seconds", 30))
        self.max_retries = int(config.get("max_retries", 3))
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.6,en;q=0.4",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Cache-Control": "no-cache",
        })
        self._last_request = 0.0

    def _wait(self):
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            self._wait()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                self._last_request = time.monotonic()
            except requests.RequestException as e:
                last_exc = e
                self.log.warning("通信エラー attempt=%s/%s url=%s: %s", attempt, self.max_retries, url, e)
                time.sleep(min(8, 2 ** attempt))
                continue

            if resp.status_code in (403, 429):
                self.log.warning("HTTP %s: %s", resp.status_code, url)
                if resp.status_code == 403:
                    raise SiteBlocked(
                        "台DATAONLINEから403が返されました。アクセス制御の回避は行いません。"
                        "ブラウザでは閲覧できるか確認し、logs/run.logを送ってください。"
                    )
                if attempt >= self.max_retries:
                    raise SiteBlocked("429 Too Many Requests が続いたため停止しました。時間を空けて再実行してください。")
                time.sleep(min(30, 5 * attempt))
                continue

            if resp.status_code >= 500:
                self.log.warning("HTTP %s retry url=%s", resp.status_code, url)
                time.sleep(min(8, 2 ** attempt))
                continue

            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"
            return resp

        if last_exc:
            raise last_exc
        raise RuntimeError(f"取得に失敗しました: {url}")

    def agree(self) -> None:
        # Public reports indicate an agreement cookie is used. We try the normal
        # consent endpoint, without bypassing any access control.
        candidates = [
            ("POST", f"{self.BASE}/agreement", {"data": {"agree": "1"}}),
            ("POST", f"{self.BASE}/{self.store_id}/accept", {"data": {"agree": "1"}}),
            ("GET", f"{self.BASE}/{self.store_id}/accept", {}),
        ]
        for method, url, kwargs in candidates:
            try:
                resp = self._request(method, url, allow_redirects=True, **kwargs)
                self.log.info("同意導線: %s %s -> %s", method, url, resp.status_code)
                return
            except SiteBlocked as e:
                # A consent endpoint itself may reject a direct request while a
                # different public consent route still works. Try the next normal
                # route, but never attempt to bypass the site's access control.
                self.log.info("同意導線が拒否されました。別の通常導線を試します: %s", e)
            except Exception as e:
                self.log.info("同意導線を続行: %s %s (%s)", method, url, e)
        self.log.info("同意エンドポイントは確認できませんでした。通常ページ取得を試します。")

    def get_text(self, url: str) -> str:
        return self._request("GET", url, allow_redirects=True).text

    def list_url(self) -> str:
        return f"{self.BASE}/{self.store_id}/list?mode=psModelNameSearch&ps=S"

    def all_list_url(self, hist_num: int) -> str:
        return f"{self.BASE}/{self.store_id}/all_list?ps=S&hist_num={hist_num}"

    def get_model_links(self) -> List[ModelLink]:
        html = self.get_text(self.list_url())
        soup = BeautifulSoup(html, "lxml")
        found: Dict[Tuple[str, str], ModelLink] = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(self.BASE, a["href"])
            if "unit_list" not in href:
                continue
            q = parse_qs(urlparse(href).query)
            model = clean_text(q.get("model", [""])[0] or a.get_text(" ", strip=True))
            ball = clean_text(q.get("ballPrice", [""])[0]) or None
            if not model:
                continue
            key = (model, ball or "")
            found[key] = ModelLink(model=model, ball_price=ball, href=href)

        self.log.info("機種リンク検出: %s件", len(found))
        return list(found.values())

    def model_links_from_all_list(self, hist_num: int = 1) -> List[ModelLink]:
        rows = self.fetch_all_list(hist_num)
        found: Dict[Tuple[str, str], ModelLink] = {}
        for r in rows:
            model = clean_text(r.get("model"))
            if not model:
                continue
            raw_ball = clean_text(r.get("ball_price"))
            n = parse_number(raw_ball)
            ball = f"{n:.2f}" if n is not None else None
            params = {"model": model, "disp": "1", "graph": "1"}
            if ball:
                params["ballPrice"] = ball
            href = f"{self.BASE}/{self.store_id}/unit_list?{urlencode(params)}"
            found[(model, ball or "")] = ModelLink(model, ball, href)
        self.log.info("全台一覧から機種URL生成: %s件", len(found))
        return list(found.values())

    def _extract_table(self, html: str) -> Tuple[List[str], List[List[str]]]:
        soup = BeautifulSoup(html, "lxml")
        tables = soup.find_all("table")
        best = None
        best_score = -1
        for table in tables:
            headers = [clean_text(x.get_text(" ", strip=True)) for x in table.find_all("th")]
            nh = {normalize_header(h) for h in headers}
            score = 0
            if any(x in nh for x in NORMALIZED_ALIAS["machine_no"]):
                score += 5
            if any(x in nh for x in NORMALIZED_ALIAS["model"]):
                score += 2
            score += len(headers) / 100
            if score > best_score:
                best_score = score
                best = table
        if best is None:
            raise ValueError("HTML内にtableがありません")

        headers = [clean_text(x.get_text(" ", strip=True)) for x in best.find_all("th")]
        rows: List[List[str]] = []
        for tr in best.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            vals = [clean_text(td.get_text(" ", strip=True)) for td in tds]
            rows.append(vals)

        if not headers and rows:
            # Old pages sometimes rely on a fixed 7-column layout.
            if len(rows[0]) == 7:
                headers = ["", "台番号", "貸玉", "機種名", "BB回数", "RB回数", "前日最終スタート"]
            elif len(rows[0]) == 12:
                headers = ["", "台番号", "累計スタート", "BB回数", "RB回数", "ART回数", "最大持玉", "BB確率", "RB確率", "ART確率", "合成確率", "前日最終スタート"]
        return headers, rows

    def _canonicalize_row(self, headers: List[str], vals: List[str], forced_model: Optional[str] = None) -> dict:
        # align malformed rows defensively
        if len(vals) < len(headers):
            vals = vals + [""] * (len(headers) - len(vals))
        if len(vals) > len(headers):
            headers = headers + [f"extra_{i}" for i in range(len(headers), len(vals))]
        raw = {headers[i] if i < len(headers) else f"extra_{i}": vals[i] for i in range(len(vals))}
        normalized_raw = {normalize_header(k): v for k, v in raw.items()}

        def lookup(key: str):
            for alias in NORMALIZED_ALIAS[key]:
                if alias in normalized_raw:
                    return normalized_raw[alias]
            return None

        machine = parse_int(lookup("machine_no"))
        model = forced_model or clean_text(lookup("model"))
        games = parse_int(lookup("games"))
        bb = parse_int(lookup("bb"))
        rb = parse_int(lookup("rb"))
        art = parse_int(lookup("art"))
        max_hold = parse_number(lookup("max_hold"))
        diff = parse_number(lookup("diff"))
        out = parse_percent(lookup("output_rate"))
        row = {
            "machine_no": machine,
            "model": model,
            "ball_price": clean_text(lookup("ball_price")),
            "games": games,
            "bb": bb,
            "rb": rb,
            "art": art,
            "max_hold": max_hold,
            "bb_rate": parse_number(lookup("bb_rate")),
            "rb_rate": parse_number(lookup("rb_rate")),
            "art_rate": parse_number(lookup("art_rate")),
            "combined_rate": parse_number(lookup("combined_rate")),
            "prev_final": parse_int(lookup("prev_final")),
            "diff": diff,
            "output_rate": out,
            "raw_json": json.dumps(raw, ensure_ascii=False),
        }
        return row

    def fetch_all_list(self, hist_num: int) -> List[dict]:
        url = self.all_list_url(hist_num)
        html = self.get_text(url)
        headers, rows = self._extract_table(html)
        result = []
        for vals in rows:
            row = self._canonicalize_row(headers, vals)
            if row.get("machine_no") is None:
                continue
            row["source_url"] = url
            result.append(row)
        self.log.info("all_list hist=%s rows=%s columns=%s", hist_num, len(result), headers)
        return result

    def fetch_model_day(self, link: ModelLink, hist_num: int) -> List[dict]:
        p = urlparse(link.href)
        q = parse_qs(p.query)
        q["hist_num"] = [str(hist_num)]
        q.setdefault("disp", ["1"])
        q.setdefault("graph", ["1"])
        query = urlencode([(k, v) for k, vals in q.items() for v in vals])
        url = urlunparse((p.scheme or "https", p.netloc or "daidata.goraggio.com", p.path, "", query, ""))
        html = self.get_text(url)
        headers, rows = self._extract_table(html)
        result = []
        for vals in rows:
            row = self._canonicalize_row(headers, vals, forced_model=link.model)
            if row.get("machine_no") is None:
                continue
            if not row.get("ball_price") and link.ball_price:
                row["ball_price"] = link.ball_price
            row["source_url"] = url
            result.append(row)
        self.log.info("unit_list %s hist=%s rows=%s", link.model, hist_num, len(result))
        return result


def merge_rows(base_rows: List[dict], detail_rows: List[dict]) -> List[dict]:
    merged: Dict[int, dict] = {}
    for r in base_rows:
        if r.get("machine_no") is not None:
            merged[int(r["machine_no"])] = dict(r)
    for r in detail_rows:
        m = r.get("machine_no")
        if m is None:
            continue
        m = int(m)
        if m not in merged:
            merged[m] = dict(r)
            continue
        cur = merged[m]
        for k, v in r.items():
            if v not in (None, ""):
                cur[k] = v
    return list(merged.values())


def collect_day(client: GoraggioClient, hist_num: int, mode: str, model_links: Optional[List[ModelLink]]) -> List[dict]:
    base = client.fetch_all_list(hist_num)
    if mode == "fast":
        return base
    if model_links is None:
        try:
            model_links = client.get_model_links()
        except Exception as e:
            client.log.warning("機種一覧リンク取得失敗。全台一覧からURL生成を試します: %s", e)
            model_links = client.model_links_from_all_list(hist_num)

    details: List[dict] = []
    for idx, link in enumerate(model_links, 1):
        try:
            rows = client.fetch_model_day(link, hist_num)
            details.extend(rows)
        except SiteBlocked:
            raise
        except Exception as e:
            client.log.warning("詳細取得失敗 %s (%s/%s): %s", link.model, idx, len(model_links), e)
    return merge_rows(base, details)


def hist_nums_for_config(cfg: dict) -> List[int]:
    days = int(cfg.get("history_days", 10))
    start = 0 if bool(cfg.get("include_today", False)) else 1
    return list(range(start, start + days))


def hist_num_to_date(hist_num: int) -> str:
    return (date.today() - timedelta(days=hist_num)).isoformat()
