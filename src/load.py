"""Load tidy records into the warehouse.

Two outputs on purpose:
  * a DuckDB warehouse  — the analytical store dbt models read from
  * a SQLite copy       — kept so the lightweight dashboard export still works
                          without any extra dependency

Rebuilds from scratch each run so the result is a clean function of the input.

The warehouse keeps every snapshot it is given, tagged with `snapshot_at`. A
trend needs two points in time and a single latest snapshot has exactly one, so
the loader accepts a list rather than a single batch. Rebuilding from the raw
files (instead of appending) keeps the run idempotent: the same set of snapshots
always produces the same warehouse.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
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

def load_duckdb(snapshots: list[tuple[str, list[dict]]]) -> int:
    """Write one row per (posting, snapshot) into the warehouse.

    `snapshots` is a list of (snapshot_at, records). One entry is a normal run;
    several entries build the history a trend needs.
    """
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()

    connection = duckdb.connect(str(DUCKDB_PATH))
    try:
        connection.execute("""
            CREATE TABLE raw_jobs (
                snapshot_at VARCHAR,
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

        columns = ["snapshot_at", *JOB_COLUMNS, "skills"]

        # A temp NDJSON file plus COPY, not executemany. DuckDB's executemany
        # issues one statement per row: a few thousand postings took minutes and
        # an interrupted run left the table half written. COPY reads the whole
        # batch in one vectorised pass and is atomic.
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "rows.ndjson"
            with staged.open("w", encoding="utf-8") as handle:
                for snapshot_at, records in snapshots:
                    for row in _rows(records):
                        handle.write(
                            json.dumps(
                                dict(zip(columns, [snapshot_at, *row])),
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
            connection.execute(
                f"COPY raw_jobs ({', '.join(columns)}) "
                f"FROM '{staged.as_posix()}' (FORMAT JSON, ARRAY false)"
            )

        count = connection.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0]
        distinct = connection.execute(
            "SELECT COUNT(DISTINCT snapshot_at) FROM raw_jobs"
        ).fetchone()[0]
    finally:
        connection.close()

    print(
        f"[load] {count} rows across {distinct} snapshot(s) -> "
        f"{DUCKDB_PATH.name} (warehouse)"
    )
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


def load(snapshots: list[tuple[str, list[dict]]]) -> int:
    """Load into both stores. Returns the warehouse row count.

    The SQLite mirror takes only the newest snapshot: it exists so the dashboard
    export stays dependency-free, and the dashboard shows the present, not the
    history.
    """
    written = load_duckdb(snapshots)
    if snapshots:
        newest_at = max(snapshot_at for snapshot_at, _ in snapshots)
        newest = next(r for a, r in snapshots if a == newest_at)
        load_sqlite(newest)
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
    load([("20260101-000000", transform(demo))])
