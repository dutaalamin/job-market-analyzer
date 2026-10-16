"""Load tidy records into the warehouse.

Two outputs on purpose:
  * a DuckDB warehouse  — the analytical store dbt models read from
  * a SQLite copy       — kept so the lightweight dashboard export still works
                          without any extra dependency

Rebuilds from scratch each run so the result is a clean function of the input.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
SQLITE_PATH = ROOT / "data" / "jobs.db"
DUCKDB_PATH = ROOT / "data" / "warehouse.duckdb"

JOB_COLUMNS = (
    "external_id", "title", "company", "category",
    "job_type", "seniority", "location", "salary", "published", "url",
)


def _rows(records: list[dict]):
    for record in records:
        yield [record.get(column, "") for column in JOB_COLUMNS] + [
            record.get("skills", [])
        ]


# --------------------------------------------------------------------------- #
# DuckDB warehouse — read by the dbt models
# --------------------------------------------------------------------------- #

def load_duckdb(records: list[dict]) -> int:
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()

    connection = duckdb.connect(str(DUCKDB_PATH))
    try:
        connection.execute("""
            CREATE TABLE raw_jobs (
                external_id VARCHAR,
                title       VARCHAR,
                company     VARCHAR,
                category    VARCHAR,
                job_type    VARCHAR,
                seniority   VARCHAR,
                location    VARCHAR,
                salary      VARCHAR,
                published   VARCHAR,
                url         VARCHAR,
                skills      VARCHAR[]
            )
        """)

        columns = ", ".join(JOB_COLUMNS) + ", skills"
        placeholders = ", ".join("?" for _ in JOB_COLUMNS) + ", ?"
        connection.executemany(
            f"INSERT INTO raw_jobs ({columns}) VALUES ({placeholders})",
            list(_rows(records)),
        )
        count = connection.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0]
    finally:
        connection.close()

    print(f"[load] {count} jobs -> {DUCKDB_PATH.name} (warehouse)")
    return count


# --------------------------------------------------------------------------- #
# SQLite mirror — kept for the dependency-free dashboard export
# --------------------------------------------------------------------------- #

def load_sqlite(records: list[dict]) -> int:
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()

    connection = sqlite3.connect(SQLITE_PATH)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        placeholders = ", ".join("?" for _ in JOB_COLUMNS)
        insert_job = f"INSERT INTO jobs ({', '.join(JOB_COLUMNS)}) VALUES ({placeholders})"
        insert_skill = "INSERT OR IGNORE INTO job_skills (job_id, skill) VALUES (?, ?)"

        for record in records:
            values = [record.get(column, "") for column in JOB_COLUMNS]
            job_id = connection.execute(insert_job, values).lastrowid
            for skill in record.get("skills", []):
                connection.execute(insert_skill, (job_id, skill))

        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    finally:
        connection.close()

    print(f"[load] {count} jobs -> {SQLITE_PATH.name} (sqlite mirror)")
    return count


def load(records: list[dict]) -> int:
    """Load into both stores. Returns the row count."""
    written = load_duckdb(records)
    load_sqlite(records)
    return written


if __name__ == "__main__":
    from transform import transform

    demo = {
        "data": [
            {"slug": "acme-data-engineer", "title": "Data Engineer",
             "company_name": "Acme", "location": "Berlin",
             "tags": ["Python", "SQL"], "job_types": ["full_time"],
             "created_at": 1790000000, "url": "https://example.com",
             "description": "Python, SQL, Airflow"},
        ]
    }
    load(transform(demo))
