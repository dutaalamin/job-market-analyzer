"""Export dashboard metrics from the warehouse.

The heavy lifting is done by the dbt models — this module only reads the marts
and shapes them into the JSON the dashboard consumes. The SQL lives in dbt, so
there is a single source of truth for every metric.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
OUT_DIR = ROOT / "web" / "data"


def rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cursor = connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, record)) for record in cursor.fetchall()]


def summarize(connection: duckdb.DuckDBPyConnection) -> dict:
    totals = rows(
        connection,
        """
        select
            (select count(*) from stg_jobs)                    as jobs,
            (select count(distinct company) from stg_jobs)     as companies,
            (select count(*) from job_skills)                  as skill_mentions,
            (select count(distinct category) from stg_jobs)    as categories,
            -- Coverage is the honest counterweight to every skill number on the
            -- page: only these postings yielded a skill at all.
            (select count(distinct external_id) from job_skills) as jobs_with_skills
        """,
    )[0]

    # Provenance belongs next to the numbers: a reader cannot judge a figure
    # without knowing where it came from and how old it is.
    snapshot = sorted((ROOT / "data" / "raw").glob("jobs-*.json"))
    totals["source"] = "Arbeitnow job board API"
    totals["source_url"] = "https://www.arbeitnow.com/api/job-board-api"
    totals["snapshot"] = snapshot[-1].stem.replace("jobs-", "") if snapshot else ""

    top_skills = rows(
        connection,
        "select skill, postings, pct_of_jobs from skill_demand order by postings desc limit 25",
    )
    categories = rows(
        connection,
        "select role_family, postings, companies, avg_skills_listed from role_families order by postings desc",
    )
    seniority = rows(
        connection,
        "select seniority, postings, avg_skills_listed from seniority_mix order by postings desc",
    )
    by_category = rows(
        connection,
        "select role_family, skill, postings from top_skills_by_family order by role_family, rank_in_family",
    )
    pairs = rows(
        connection,
        """
        with top as (
            select skill from skill_demand order by postings desc limit 3
        )
        select
            top.skill as anchor,
            other.skill as companion,
            count(distinct other.external_id) as together
        from job_skills top
        join job_skills other
            on other.external_id = top.external_id and other.skill <> top.skill
        where top.skill in (select skill from top)
        group by top.skill, other.skill
        qualify row_number() over (
            partition by top.skill order by count(distinct other.external_id) desc, other.skill
        ) <= 10
        order by top.skill, together desc
        """,
    )

    # Reshape into the nested shape the dashboard expects.
    by_category_map: dict[str, list] = {}
    for row in by_category:
        by_category_map.setdefault(row["role_family"], []).append(
            {"skill": row["skill"], "postings": row["postings"]}
        )

    pairs_map: dict[str, list] = {}
    for row in pairs:
        pairs_map.setdefault(row["anchor"], []).append(
            {"companion": row["companion"], "together": row["together"]}
        )

    return {
        "totals": totals,
        "categories": categories,
        "topSkills": top_skills,
        "seniority": seniority,
        "byCategory": by_category_map,
        "skillPairs": pairs_map,
    }


HISTORY_CSV = ROOT / "web" / "data" / "skill_history.csv"


def append_skill_history(connection) -> None:
    """Record one compact line per (snapshot, skill) for trend analysis.

    Why not commit the raw snapshots: each is ~5 MB gzipped, so a month of daily
    runs is ~150 MB in git history for data that is already aggregated here. The
    trend needs postings per skill per snapshot: 57 rows, ~3 KB.

    Reads EVERY snapshot in the warehouse, not just the newest. The previous
    version looked only at payload["totals"]["snapshot"], so a --history run that
    loaded two snapshots still recorded one, and the CSV could never grow faster
    than one row-set per run.
    """
    header = "snapshot,skill,postings,pct_of_jobs\n"
    existing = HISTORY_CSV.read_text(encoding="utf-8") if HISTORY_CSV.exists() else ""
    known = {
        line.split(",", 2)[0]
        for line in existing.splitlines()[1:]
        if line.strip()
    }

    snapshots = [
        row[0]
        for row in connection.execute(
            "select distinct snapshot_at from raw_jobs order by snapshot_at"
        ).fetchall()
    ]

    appended = 0
    blocks: list[str] = []
    for snapshot in snapshots:
        if snapshot in known:
            continue
        rows = connection.execute(
            """
            select js.skill,
                   count(distinct js.external_id) as postings,
                   round(100.0 * count(distinct js.external_id)
                         / (select count(*) from raw_jobs where snapshot_at = ?), 1)
            from (
                select snapshot_at, external_id, unnest(skills) as skill
                from raw_jobs where snapshot_at = ?
            ) js
            group by js.skill
            order by postings desc, js.skill
            -- No LIMIT. The dictionary has 57 skills; storing only the top 25
            -- made "absent from the previous list" indistinguishable from "had
            -- zero postings", which turned a rank-26 skill into a fake riser.
            """,
            [snapshot, snapshot],
        ).fetchall()
        for skill, postings, pct in rows:
            blocks.append(f"{snapshot},{skill},{postings},{pct}\n")
        appended += 1
        print(f"[analyze] history: +{len(rows)} rows for {snapshot}")

    if not blocks:
        print("[analyze] history already up to date")
        return

    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_CSV.open("a", encoding="utf-8") as handle:
        if not existing:
            handle.write(header)
        handle.write("".join(blocks))
    print(f"[analyze] appended {len(blocks)} rows across {appended} snapshot(s)")


def analyze() -> dict:
    connection = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        payload = summarize(connection)
        # Inside the try: this reads the warehouse too, and the previous version
        # called it after the connection was already closed.
        append_skill_history(connection)
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
