"""Tests for drafts/skill_trend.sql — run once the query exists.

    python -m pytest drafts/test_skill_trend.py    (or unittest)

Same three rules as tests/test_transform.py: every case below is a way the
query can be wrong while still returning rows.
"""

from __future__ import annotations

import duckdb
import pytest


@pytest.fixture()
def con():
    """A tiny warehouse with two snapshots and known counts."""
    c = duckdb.connect()
    c.execute("""
        create table history (
            snapshot_at varchar,
            external_id varchar,
            skill       varchar
        )
    """)
    rows = []
    # Snapshot 1: Python in 2 postings, Rust in 1, Vue in 0
    rows += [("20260101-000000", "p1", "Python"),
             ("20260101-000000", "p2", "Python"),
             ("20260101-000000", "p1", "Rust")]
    # Snapshot 2: Python in 3, Rust in 0, Svelte in 1 (brand new)
    rows += [("20260102-000000", "p1", "Python"),
             ("20260102-000000", "p2", "Python"),
             ("20260102-000000", "p3", "Python"),
             ("20260102-000000", "p3", "Svelte")]
    c.executemany("insert into history values (?, ?, ?)", rows)
    c.execute("create view input as select * from history")
    return c


def run(con):
    sql = open(__file__.replace("test_skill_trend.py", "skill_trend.sql")).read()
    query = sql.split("Write the query below this line.")[1]
    return con.execute(query).fetchdf().set_index("skill")


def test_rising_skill(con):
    r = run(con)
    assert r.loc["Python", "postings_now"] == 3
    assert r.loc["Python", "postings_prev"] == 2


def test_falling_skill(con):
    # Rust went from 1 to 0 and must NOT disappear from the table.
    r = run(con)
    assert "Rust" in r.index, "a skill that fell to zero must still be reported"
    assert r.loc["Rust", "postings_now"] == 0


def test_new_skill_is_not_dropped(con):
    # Svelte exists only in the newest snapshot.
    r = run(con)
    assert "Svelte" in r.index, "a brand-new skill is the most interesting row"
    assert r.loc["Svelte", "postings_prev"] == 0


def test_change_is_percentage_points_not_percent(con):
    # Python: 2/2 = 100% -> 3/3 = 100%, so change_pp must be 0.0, not a divide
    # by zero and not a percent-of-percent.
    r = run(con)
    assert r.loc["Python", "change_pp"] == pytest.approx(0.0)


def test_one_row_per_skill(con):
    r = run(con)
    assert len(r.index) == len(set(r.index))
