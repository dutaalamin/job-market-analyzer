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


def analyze() -> dict:
    connection = duckdb.connect(str(WAREHOUSE), read_only=True)
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
