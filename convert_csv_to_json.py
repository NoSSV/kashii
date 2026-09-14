from __future__ import annotations
import csv, json, sys
from datetime import datetime
from pathlib import Path

if len(sys.argv) < 2:
    print("使い方: python tools/convert_csv_to_json.py raw_latest.csv [data/latest.json]")
    raise SystemExit(2)
src = Path(sys.argv[1])
out = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path(__file__).resolve().parents[1] / "data" / "latest.json"
with src.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"updated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "mode": "server", "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK: {len(rows)} rows -> {out}")
