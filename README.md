# Job Market Analyzer

An end-to-end data pipeline that collects remote tech job postings, cleans and
normalises them, loads them into a SQL database, and visualises the result in a
small dashboard.

Built to answer one question: **which skills are actually in demand right now?**

## Pipeline

```
   ┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌─────────────┐
   │ collect  │───▶│  transform  │───▶│   load   │───▶│  analyze    │
   │ (API)    │    │ (clean+norm)│    │ (SQLite) │    │ (SQL → JSON)│
   └──────────┘    └─────────────┘    └──────────┘    └─────────────┘
      raw JSON        tidy records      jobs.db          metrics.json
                                                             │
                                                             ▼
                                                      ┌─────────────┐
                                                      │  dashboard  │
                                                      └─────────────┘
```

## Stack

| Layer | Tool |
| ----- | ---- |
| Language | Python 3 (standard library only — no install needed) |
| Source | Remotive public jobs API |
| Storage | SQLite |
| Analysis | SQL |
| Dashboard | Static HTML + vanilla JS (Chart-free, SVG) |

## Run

```bash
python src/run.py          # collect → transform → load → analyze
```

Then open `web/index.html`.

## Layout

```
src/
  collect.py     fetch raw job postings from the API
  transform.py   parse, clean, normalise, extract skills
  load.py        create schema and insert into SQLite
  analyze.py     run SQL queries, export metrics.json
  run.py         orchestrate the whole pipeline
queries/
  *.sql          the analysis queries, one file per metric
data/
  raw/           raw API snapshots (JSON)
  jobs.db        SQLite database
web/
  index.html     dashboard
  data/          exported metrics
```
