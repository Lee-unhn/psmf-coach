"""SQLite schema + 存取輔助。8 張表對應 PSMF-COACH.md §7.4。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import DB_PATH

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS body_metrics (
    date TEXT PRIMARY KEY CHECK (date LIKE '____-__-__'),
    weight REAL, body_fat_pct REAL, fat_mass REAL, lbm REAL,
    visceral_fat REAL, waist_cm REAL
);
CREATE TABLE IF NOT EXISTS daily_log (
    date TEXT PRIMARY KEY CHECK (date LIKE '____-__-__'),
    trained INTEGER NOT NULL DEFAULT 0 CHECK (trained IN (0,1)),
    hunger INTEGER CHECK (hunger IS NULL OR hunger BETWEEN 1 AND 5),
    energy INTEGER CHECK (energy IS NULL OR energy BETWEEN 1 AND 5),
    adherence INTEGER CHECK (adherence IS NULL OR adherence BETWEEN 1 AND 5),
    notes TEXT
);
CREATE TABLE IF NOT EXISTS supplement_log (
    date TEXT PRIMARY KEY CHECK (date LIKE '____-__-__'),
    sodium_mg REAL, potassium_mg REAL, magnesium_mg REAL,
    multivit INTEGER, fishoil INTEGER, creatine INTEGER
);
CREATE TABLE IF NOT EXISTS research_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT, source TEXT, title TEXT, url TEXT UNIQUE,
    year INTEGER, summary TEXT, relevance_score REAL
);
CREATE TABLE IF NOT EXISTS menu_plan (
    date TEXT PRIMARY KEY CHECK (date LIKE '____-__-__'),
    day_type TEXT, kcal_target REAL, protein_target REAL,
    menu_json TEXT, training_note TEXT, reason TEXT, generated_by TEXT
);
CREATE TABLE IF NOT EXISTS weekly_report (
    week_no INTEGER PRIMARY KEY,
    sent_at TEXT, summary TEXT, adjustments TEXT, email_status TEXT
);
CREATE TABLE IF NOT EXISTS plan_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, field TEXT, old_value TEXT, new_value TEXT,
    reason TEXT, evidence_paper_id INTEGER
);
CREATE TABLE IF NOT EXISTS cost_log (
    date TEXT PRIMARY KEY CHECK (date LIKE '____-__-__'),
    food_cost REAL, supplement_cost REAL, total_cost REAL
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection, from_version: int) -> None:
    """未來加欄位放這 —— 只用 ADD COLUMN（additive），每句 try/except 容許重跑。
    SQLite 不能用 ALTER 加 CHECK 或 DROP 欄位；破壞性變更要靠 rename→create→copy→drop。
    例：
        for ddl in ("ALTER TABLE menu_plan ADD COLUMN kcal_actual REAL",):
            try: conn.execute(ddl)
            except sqlite3.OperationalError: pass
    """
    return


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)              # 全新 DB 直接建好
        v = conn.execute("PRAGMA user_version").fetchone()[0]
        if v < SCHEMA_VERSION:
            _migrate(conn, v)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _upsert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = ", ".join(row)
    placeholders = ", ".join(["?"] * len(row))
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
        list(row.values()),
    )


def upsert_body_metrics(conn: sqlite3.Connection, row: dict) -> None:
    _upsert(conn, "body_metrics", row)


def upsert_daily_log(conn: sqlite3.Connection, row: dict) -> None:
    _upsert(conn, "daily_log", row)


def upsert_supplement_log(conn: sqlite3.Connection, row: dict) -> None:
    _upsert(conn, "supplement_log", row)


def upsert_menu_plan(conn: sqlite3.Connection, row: dict) -> None:
    _upsert(conn, "menu_plan", row)


def upsert_cost_log(conn: sqlite3.Connection, row: dict) -> None:
    _upsert(conn, "cost_log", row)


def pick_daily_paper(conn: sqlite3.Connection, day_index: int) -> dict | None:
    """挑一則「當週可信權威」論文當每日新知。只取同儕審查來源；依 day_index 每天輪不同篇。"""
    cur = conn.execute(
        "SELECT title, url, year, summary, source FROM research_papers "
        "WHERE source IN ('PubMed','EuropePMC','PMC','Nature') AND relevance_score >= 0.7 "
        "ORDER BY relevance_score DESC, year DESC, fetched_at DESC LIMIT 20"
    )
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return None
    return rows[day_index % len(rows)]


def cost_since(conn: sqlite3.Connection, start_date: str) -> dict:
    """回傳 >= start_date 的花費加總與天數。"""
    cur = conn.execute(
        "SELECT COUNT(*) AS days, COALESCE(SUM(total_cost),0) AS total, "
        "COALESCE(SUM(food_cost),0) AS food, COALESCE(SUM(supplement_cost),0) AS supp "
        "FROM cost_log WHERE date >= ?", (start_date,)
    )
    return dict(cur.fetchone())


def recent_daily_logs(conn: sqlite3.Connection, n: int = 7) -> list[dict]:
    cur = conn.execute(
        "SELECT * FROM daily_log ORDER BY date DESC LIMIT ?", (n,)
    )
    return [dict(r) for r in cur.fetchall()]


def recent_body_metrics(conn: sqlite3.Connection, n: int = 14) -> list[dict]:
    cur = conn.execute(
        "SELECT * FROM body_metrics ORDER BY date DESC LIMIT ?", (n,)
    )
    return [dict(r) for r in cur.fetchall()]


def latest_weight(conn: sqlite3.Connection) -> float | None:
    cur = conn.execute(
        "SELECT weight FROM body_metrics ORDER BY date DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row["weight"] if row else None
