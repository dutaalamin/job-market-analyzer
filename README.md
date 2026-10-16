# Job Market Analyzer

An end-to-end **data platform** that collects remote tech job postings, models
them in a **dbt**-managed warehouse, and answers one question: **which skills
are actually in demand right now?**

## Architecture

```
   ┌──────────┐   ┌─────────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐
   │ collect  │──▶│  transform  │──▶│   load   │──▶│   dbt    │──▶│  analyze    │
   │ (API)    │   │ (clean+norm)│   │ (DuckDB) │   │ (models) │   │ (marts→JSON)│
   └──────────┘   └─────────────┘   └──────────┘   └──────────┘   └─────────────┘
      raw JSON       tidy records      warehouse     staging+marts      metrics
                                                      + 27 tests            │
                                                                            ▼
                                                                     ┌─────────────┐
                                                                     │  dashboard  │
                                                                     └─────────────┘
```

Orchestrated by an **Apache Airflow** DAG (`dags/`), scheduled daily with retries
and isolated stages.

## Stack

| Layer | Tool |
| ----- | ---- |
| Language | Python 3 |
| Source | Arbeitnow public jobs API |
| Warehouse | DuckDB |
| Transformations | **dbt** (staging + marts, 27 data-quality tests) |
| Orchestration | Apache Airflow |
| Analysis | SQL |
| Dashboard | Static HTML + vanilla JS (SVG charts) |

## Run

```bash
# full pipeline: collect → transform → load → dbt build → analyze
python src/run.py

# reuse the last raw snapshot (no network)
python src/run.py --offline

# skip the dbt layer
python src/run.py --skip-dbt
```

Then open `web/index.html`.

### dbt only

```bash
cd dbt
JMA_WAREHOUSE=../data/warehouse.duckdb dbt build --profiles-dir .
```

## The dbt layer

```
models/
  staging/
    stg_jobs.sql          clean typing, null handling, casts
  marts/
    job_skills.sql        exploded (job, skill) pairs
    skill_demand.sql      skill popularity + share-of-market %
    role_families.sql     counts per role family
    seniority_mix.sql     seniority distribution
    top_skills_by_family.sql   window-function ranking within each family
```

**Data-quality tests** (all passing): uniqueness and null checks on keys,
accepted-value checks on `category` and `seniority`, plus a singular test
asserting share-of-market stays within 0–100%.

## Layout

```
src/
  collect.py     fetch raw job postings from the API
  transform.py   parse, clean, normalise, extract skills
  load.py        load into the DuckDB warehouse (+ SQLite mirror)
  analyze.py     read the dbt marts, export metrics.json
  run.py         orchestrate the whole pipeline
dbt/
  models/        staging + marts
  tests/         singular data tests
  profiles.yml   DuckDB connection
dags/
  job_market_analyzer_dag.py   Airflow DAG (daily schedule)
queries/         standalone SQL used before the dbt layer
data/
  raw/           raw API snapshots (JSON)
  warehouse.duckdb
web/
  index.html     dashboard
  data/          exported metrics
```
