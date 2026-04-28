"""
KeywordStore — SQLite FTS5 기반 키워드 저장/검색
채용공고·이력서를 전문 검색 인덱스에 저장하고 키워드 정확 매칭
"""

import os
import json
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


def _migrate(con: sqlite3.Connection) -> None:
    for col, typedef in [
        ("sections_json", "TEXT"),
        ("deadline", "TEXT"),
    ]:
        try:
            con.execute(f"ALTER TABLE job_postings ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS job_postings (
                id            TEXT PRIMARY KEY,
                job_title     TEXT NOT NULL,
                company       TEXT NOT NULL,
                location      TEXT,
                url           TEXT,
                source_email  TEXT,
                sections_text TEXT,
                sections_json TEXT,
                deadline      TEXT,
                created_at    TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS job_postings_fts USING fts5(
                id            UNINDEXED,
                job_title,
                company,
                location,
                sections_text,
                tokenize      = 'unicode61'
            );

            CREATE TABLE IF NOT EXISTS resumes (
                id             TEXT PRIMARY KEY,
                name           TEXT,
                filename       TEXT,
                career_summary TEXT,
                skills         TEXT,
                suitable_jobs  TEXT,
                strengths      TEXT,
                job_keywords   TEXT,
                full_text      TEXT,
                created_at     TEXT NOT NULL
            );
        """)
        _migrate(con)


# ── 채용공고 ─────────────────────────────────────────────────────────────────

def store_job_postings(postings: list[dict]) -> int:
    init_db()
    count = 0
    with _conn() as con:
        for p in postings:
            sections_text = " ".join(
                f"{s['heading']} {s['content']}" for s in p.get("sections", [])
            )
            doc_id = f"{p['company']}_{p['job_title']}".replace(" ", "_")[:64]
            sections_json = json.dumps(p.get("sections", []), ensure_ascii=False)
            con.execute(
                """INSERT OR REPLACE INTO job_postings
                   (id, job_title, company, location, url, source_email,
                    sections_text, sections_json, deadline, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, p["job_title"], p["company"],
                 p.get("location") or "", p.get("url") or "",
                 p.get("source_email") or "", sections_text, sections_json,
                 p.get("deadline") or "", datetime.now().isoformat()),
            )
            con.execute("DELETE FROM job_postings_fts WHERE id = ?", (doc_id,))
            con.execute(
                """INSERT INTO job_postings_fts
                   (id, job_title, company, location, sections_text)
                   VALUES (?, ?, ?, ?, ?)""",
                (doc_id, p["job_title"], p["company"],
                 p.get("location") or "", sections_text),
            )
            count += 1
    return count


def get_job_postings_by_month(year: int, month: int) -> list[dict]:
    """해당 월에 수집된 채용공고 목록 반환."""
    init_db()
    ym = f"{year:04d}-{month:02d}"
    with _conn() as con:
        rows = con.execute(
            """SELECT job_title, company, location, url, deadline, created_at
               FROM job_postings
               WHERE created_at LIKE ?
               ORDER BY company ASC""",
            (f"{ym}%",),
        ).fetchall()
    return [dict(r) for r in rows]


def search_jobs_by_keywords(keywords: list[str], limit: int = 10) -> list[dict]:
    init_db()
    terms = [kw.strip() for kw in keywords if kw.strip()]
    if not terms:
        return []
    query = " OR ".join(f'"{t}"' for t in terms)
    try:
        with _conn() as con:
            rows = con.execute(
                """SELECT j.*, fts.rank
                   FROM job_postings_fts fts
                   JOIN job_postings j ON j.id = fts.id
                   WHERE job_postings_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        {
            "job_title":    r["job_title"],
            "company":      r["company"],
            "location":     r["location"],
            "url":          r["url"],
            "source_email": r["source_email"],
            "score":        abs(r["rank"]),
            "source":       "keyword",
        }
        for r in rows
    ]


# ── 이력서 ───────────────────────────────────────────────────────────────────

def store_resume(resume_id: str, resume: dict, filename: str, full_text: str) -> None:
    init_db()
    with _conn() as con:
        con.execute(
            """INSERT OR REPLACE INTO resumes
               (id, name, filename, career_summary, skills, suitable_jobs,
                strengths, job_keywords, full_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                resume_id, resume.get("name", ""), filename,
                resume.get("career_summary", ""),
                json.dumps(resume.get("skills", []),         ensure_ascii=False),
                json.dumps(resume.get("suitable_jobs", []),  ensure_ascii=False),
                json.dumps(resume.get("strengths", []),      ensure_ascii=False),
                json.dumps(resume.get("job_keywords", []),   ensure_ascii=False),
                full_text, datetime.now().isoformat(),
            ),
        )


def get_job_posting(company: str, job_title: str) -> dict | None:
    """회사명+직무명으로 저장된 채용공고 상세(sections_json 포함) 조회."""
    init_db()
    doc_id = f"{company}_{job_title}".replace(" ", "_")[:64]
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM job_postings WHERE id = ?", (doc_id,)
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    try:
        result["sections"] = json.loads(result.get("sections_json") or "[]")
    except (json.JSONDecodeError, TypeError):
        result["sections"] = []
    return result


def get_resume_full(resume_id: str) -> dict | None:
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
    return dict(row) if row else None


def get_all_resumes() -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            """SELECT id, name, filename, suitable_jobs, skills, created_at
               FROM resumes ORDER BY created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]
