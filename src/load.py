"""Load tidy records into SQLite.

Rebuilds the database from scratch each run so the result is always a clean
function of the input — no stale rows hiding in there.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

JOB_COLUMNS = (
    "external_id", "title", "company", "category",
    "job_type", "seniority", "location", "salary", "published", "url",
)


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def load(records: list[dict]) -> int:
    """Insert all records and return how many jobs were written."""
    connection = connect()
    try:
        create_schema(connection)

        placeholders = ", ".join("?" for _ in JOB_COLUMNS)
        insert_job = f"INSERT INTO jobs ({', '.join(JOB_COLUMNS)}) VALUES ({placeholders})"
        insert_skill = "INSERT OR IGNORE INTO job_skills (job_id, skill) VALUES (?, ?)"

        written = 0
        for record in records:
            values = [record.get(column, "") for column in JOB_COLUMNS]
            cursor = connection.execute(insert_job, values)
            job_id = cursor.lastrowid
            for skill in record.get("skills", []):
                connection.execute(insert_skill, (job_id, skill))
            written += 1

        connection.commit()
        print(f"[load] {written} jobs written to {DB_PATH.name}")
        return written
    finally:
        connection.close()


if __name__ == "__main__":
    from transform import transform

    demo = {
        "jobs": [
            {"id": 1, "title": "Data Engineer", "company_name": "Acme",
             "category": "Data", "job_type": "full_time",
             "description": "Python, SQL, Airflow"},
        ]
    }
    load(transform(demo))
