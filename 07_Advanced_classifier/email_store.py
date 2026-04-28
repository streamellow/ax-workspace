"""
email_store.py — 이메일 자동 수집 이력 저장 (SQLite)
"""

import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get(
    "SQLITE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db"),
)


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_email_tables() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS email_sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT NOT NULL,
                fetched_at   TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end   TEXT NOT NULL,
                total_count  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS email_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL,
                subject     TEXT,
                sender      TEXT,
                received_at TEXT,
                category    TEXT,
                ai_summary  TEXT,
                FOREIGN KEY (session_id) REFERENCES email_sessions(id)
            );
        """)


def store_session(
    source: str,
    period_start: datetime,
    period_end: datetime,
    emails: list[dict],
) -> int:
    init_email_tables()
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO email_sessions
               (source, fetched_at, period_start, period_end, total_count)
               VALUES (?, ?, ?, ?, ?)""",
            (
                source,
                datetime.now().isoformat(),
                period_start.isoformat(),
                period_end.isoformat(),
                len(emails),
            ),
        )
        session_id = cur.lastrowid
        for e in emails:
            con.execute(
                """INSERT INTO email_items
                   (session_id, subject, sender, received_at, category, ai_summary)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, e.get("subject"), e.get("sender"),
                 e.get("received_at"), e.get("category"), e.get("ai_summary")),
            )
    return session_id


def get_available_months() -> list[tuple[int, int]]:
    init_email_tables()
    with _conn() as con:
        rows = con.execute(
            """SELECT DISTINCT substr(period_start, 1, 7) as ym
               FROM email_sessions ORDER BY ym DESC"""
        ).fetchall()
    result = []
    for r in rows:
        try:
            y, m = r["ym"].split("-")
            result.append((int(y), int(m)))
        except Exception:
            pass
    return result


def get_monthly_stats(year: int, month: int) -> dict[str, int]:
    init_email_tables()
    ym = f"{year:04d}-{month:02d}"
    with _conn() as con:
        rows = con.execute(
            """SELECT i.category, COUNT(*) as cnt
               FROM email_items i
               JOIN email_sessions s ON s.id = i.session_id
               WHERE s.period_start LIKE ?
               GROUP BY i.category ORDER BY cnt DESC""",
            (f"{ym}%",),
        ).fetchall()
    return {r["category"]: r["cnt"] for r in rows}


def get_monthly_emails(year: int, month: int, category: str | None = None) -> list[dict]:
    init_email_tables()
    ym = f"{year:04d}-{month:02d}"
    with _conn() as con:
        if category:
            rows = con.execute(
                """SELECT i.*, s.source
                   FROM email_items i
                   JOIN email_sessions s ON s.id = i.session_id
                   WHERE s.period_start LIKE ? AND i.category = ?
                   ORDER BY i.received_at DESC""",
                (f"{ym}%", category),
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT i.*, s.source
                   FROM email_items i
                   JOIN email_sessions s ON s.id = i.session_id
                   WHERE s.period_start LIKE ?
                   ORDER BY i.received_at DESC""",
                (f"{ym}%",),
            ).fetchall()
    return [dict(r) for r in rows]


def get_last_period_end(source: str) -> datetime | None:
    """해당 소스의 마지막 수집 종료 시각 반환. 데이터 없으면 None."""
    init_email_tables()
    with _conn() as con:
        row = con.execute(
            "SELECT MAX(period_end) as last_end FROM email_sessions WHERE source = ?",
            (source.lower(),),
        ).fetchone()
    if row and row["last_end"]:
        try:
            return datetime.fromisoformat(row["last_end"])
        except Exception:
            return None
    return None


def get_session_history(limit: int = 20) -> list[dict]:
    init_email_tables()
    with _conn() as con:
        rows = con.execute(
            """SELECT id, source, fetched_at, period_start, period_end, total_count
               FROM email_sessions ORDER BY fetched_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
