from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.database import StoreDB
from src.report import export_csv, export_html, export_xlsx
from src.scoring import compute_daily_scores, compute_target_scores
from src.scraper import GoraggioClient, SiteBlocked, collect_day, hist_num_to_date, hist_nums_for_config


def setup_logger() -> logging.Logger:
    (ROOT / "logs").mkdir(exist_ok=True)
    logger = logging.getLogger("kashii2")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(ROOT / "logs" / "run.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(sh)
    return logger


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="詳細ページを巡回しない高速モード")
    ap.add_argument("--refresh-all", action="store_true", help="直近N日をすべて再取得")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if args.fast:
        cfg["collection_mode"] = "fast"
    logger = setup_logger()
    logger.info("============================================")
    logger.info("%s スロット分析を開始", cfg.get("store_name"))
    logger.info("mode=%s history_days=%s", cfg.get("collection_mode"), cfg.get("history_days"))

    db = StoreDB(ROOT / "data" / "kashii2.db")
    try:
        client = GoraggioClient(cfg, logger)
        client.agree()
        hist_nums = hist_nums_for_config(cfg)
        target_dates = [hist_num_to_date(h) for h in hist_nums]
        latest_completed_date = target_dates[0] if target_dates else None

        model_links = None
        if cfg.get("collection_mode") == "full":
            try:
                model_links = client.get_model_links()
            except Exception as e:
                logger.warning("機種リンク事前取得に失敗。日別取得時に代替します: %s", e)

        for h, d in zip(hist_nums, target_dates):
            should_refresh = args.refresh_all or not db.has_date(d)
            if cfg.get("refresh_latest_completed_day", True) and d == latest_completed_date:
                should_refresh = True
            if not should_refresh:
                logger.info("[SKIP] %s は保存済み", d)
                continue
            logger.info("[GET] %s (hist_num=%s)", d, h)
            rows = collect_day(client, h, str(cfg.get("collection_mode", "full")), model_links)
            if not rows:
                logger.warning("%s は0件でした。既存データは消しません。", d)
                continue
            db.delete_date(d)
            db.upsert_rows(d, rows)
            logger.info("[SAVE] %s: %s台", d, len(rows))

        raw = db.read_dates(target_dates)
        if not raw:
            raise RuntimeError("対象期間のデータが1件もありません。")
        scored = compute_daily_scores(raw, cfg.get("low_sample_caps", {}))
        targets = compute_target_scores(scored, target_dates)

        out = ROOT / "output"
        out.mkdir(exist_ok=True)
        export_csv(out / "raw_latest.csv", scored)
        export_html(out / "dashboard.html", scored, target_dates, targets, cfg)
        export_xlsx(out / "kashii2_analysis.xlsx", scored, target_dates, targets, cfg)

        logger.info("--------------------------------------------")
        logger.info("完了: %s台 / %s日分", len({r['machine_no'] for r in scored}), len(target_dates))
        logger.info("Excel: %s", out / "kashii2_analysis.xlsx")
        logger.info("HTML : %s", out / "dashboard.html")
        logger.info("CSV  : %s", out / "raw_latest.csv")
        if targets:
            logger.info("TOP5")
            for i, r in enumerate(targets[:5], 1):
                logger.info("%s位 台%s %s 狙い度 %.1f", i, r['machine_no'], r['model'], r['target_score'])
        return 0
    except SiteBlocked as e:
        logger.error(str(e))
        return 2
    except Exception:
        logger.exception("実行中にエラーが発生しました")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
