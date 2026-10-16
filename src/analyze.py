"""Run the SQL analysis and export the results as JSON.

Each query lives in its own .sql file so the SQL is easy to read and review —
this module is only responsible for running them and shaping the output.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "jobs.db"
QUERY_DIR = ROOT / "queries"
OUT_DIR = ROOT / "web" / "data"


def run_query(connection: sqlite3.Connection, sql: str, params: dict | None = None) -> list[dict]:
    connection.row_factory = sqlite3.Row
    cursor = connection.execute(sql, params or {})
    return [dict(row) for row in cursor.fetchall()]


def load_sql(name: str) -> str:
    return (QUERY_DIR / f"{name}.sql").read_text(encoding="utf-8")


def summarize(connection: sqlite3.Connection) -> dict:
    """Build the full metrics payload consumed by the dashboard."""
    totals = run_query(
        connection,
        """
        SELECT
            (SELECT COUNT(*) FROM jobs)                     AS jobs,
            (SELECT COUNT(DISTINCT company) FROM jobs)      AS companies,
            (SELECT COUNT(DISTINCT category) FROM jobs)     AS categories,
            (SELECT COUNT(*) FROM job_skills)               AS skill_mentions
        """,
    )[0]

    categories = run_query(connection, load_sql("categories"))
    top_skills = run_query(connection, load_sql("top_skills"))
    seniority = run_query(connection, load_sql("seniority"))

    # Per-category top skills for the biggest categories only, to keep it small.
    by_category = {}
    for row in categories[:6]:
        name = row["category"]
        by_category[name] = run_query(
            connection, load_sql("skills_by_category"), {"category": name}
        )

    # Co-occurrence for the top three skills.
    pairs = {}
    for row in top_skills[:3]:
        name = row["skill"]
        pairs[name] = run_query(connection, load_sql("skill_pairs"), {"skill": name})

    return {
        "totals": totals,
        "categories": categories,
        "topSkills": top_skills,
        "seniority": seniority,
        "byCategory": by_category,
        "skillPairs": pairs,
    }


def analyze() -> dict:
    connection = sqlite3.connect(DB_PATH)
    try:
        payload = summarize(connection)
    finally:
        connection.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[analyze] {len(payload['topSkills'])} skills, "
          f"{len(payload['categories'])} categories -> metrics.json")
    return payload


if __name__ == "__main__":
    analyze()
