"""
Airflow DAG for the Job Market Analyzer pipeline.

    collect → transform → load → analyze

Each stage runs in its own task so failures are isolated and retryable, and the
whole thing is scheduled to refresh the dataset daily.

To use: drop this file in your Airflow `dags/` folder (or point the repo's
`dags/` at it) and set PROJECT_DIR to the project root.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = os.environ.get("JMA_PROJECT_DIR", "/opt/job-market-analyzer")
PY = "python"

default_args = {
    "owner": "duta",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
}

with DAG(
    dag_id="job_market_analyzer",
    description="Collect, clean, load and analyse remote job postings",
    schedule="0 6 * * *",  # every day at 06:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["data", "etl", "portfolio"],
) as dag:

    collect = BashOperator(
        task_id="collect",
        bash_command=f"cd {PROJECT_DIR} && {PY} src/collect.py",
    )

    transform = BashOperator(
        task_id="transform",
        bash_command=f"cd {PROJECT_DIR} && {PY} src/transform.py",
    )

    load = BashOperator(
        task_id="load",
        bash_command=f"cd {PROJECT_DIR} && {PY} src/load.py",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {PROJECT_DIR}/dbt && "
            f"JMA_WAREHOUSE={PROJECT_DIR}/data/warehouse.duckdb "
            f"dbt build --profiles-dir ."
        ),
    )

    analyze = BashOperator(
        task_id="analyze",
        bash_command=f"cd {PROJECT_DIR} && {PY} src/analyze.py",
    )

    # Linear dependency chain — each stage feeds the next.
    collect >> transform >> load >> dbt_build >> analyze
