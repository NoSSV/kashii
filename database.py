from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS machine_day (
    data_date TEXT NOT NULL,
    machine_no INTEGER NOT NULL,
    model TEXT,
    ball_price TEXT,
    games INTEGER,
    bb INTEGER,
    rb INTEGER,
    art INTEGER,
    max_hold REAL,
    bb_rate REAL,
    rb_rate REAL,
    art_rate REAL,
    combined_rate REAL,
    prev_final INTEGER,
    diff REAL,
    output_rate REAL,
    source_url TEXT,
    raw_json TEXT,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (data_date, machine_no)
);
CREATE INDEX IF NOT EXISTS idx_machine_day_model ON machine_day(model);
CREATE INDEX IF NOT EXISTS idx_machine_day_machine ON machine_day(machine_no);
"""


FIELDS = [
    "data_date", "machine_no", "model", "ball_price", "games", "bb", "rb", "art",
    "max_hold", "bb_rate", "rb_rate", "art_rate", "combined_rate", "prev_final",
    "diff", "output_rate", "source_url", "raw_json"
]


class StoreDB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def upsert_rows(self, data_date: str, rows: Iterable[dict]):
        sql = f"""
        INSERT INTO machine_day ({', '.join(FIELDS)})
        VALUES ({', '.join('?' for _ in FIELDS)})
        ON CONFLICT(data_date, machine_no) DO UPDATE SET
        {', '.join(f'{f}=excluded.{f}' for f in FIELDS if f not in ('data_date', 'machine_no'))},
        fetched_at=CURRENT_TIMESTAMP
        """
        vals = []
        for r in rows:
            x = dict(r)
            x["data_date"] = data_date
            vals.append(tuple(x.get(f) for f in FIELDS))
        self.conn.executemany(sql, vals)
        self.conn.commit()

    def has_date(self, data_date: str) -> bool:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM machine_day WHERE data_date=?", (data_date,)).fetchone()
        return bool(row and row["n"] > 0)

    def delete_date(self, data_date: str):
        self.conn.execute("DELETE FROM machine_day WHERE data_date=?", (data_date,))
        self.conn.commit()

    def read_dates(self, dates: List[str]) -> List[dict]:
        if not dates:
            return []
        placeholders = ",".join("?" for _ in dates)
        cur = self.conn.execute(
            f"SELECT * FROM machine_day WHERE data_date IN ({placeholders}) ORDER BY data_date DESC, machine_no",
            dates,
        )
        return [dict(r) for r in cur.fetchall()]

    def all_dates(self) -> List[str]:
        cur = self.conn.execute("SELECT DISTINCT data_date FROM machine_day ORDER BY data_date DESC")
        return [r[0] for r in cur.fetchall()]
