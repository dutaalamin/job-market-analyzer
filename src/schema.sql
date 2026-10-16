-- Schema for the job market database.
-- Two tables: one row per posting, one row per (posting, skill) pair.
-- Keeping skills in their own table is what lets the analysis queries do real
-- joins and GROUP BYs instead of string hacks.

DROP TABLE IF EXISTS job_skills;
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    company     TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    job_type    TEXT    NOT NULL,
    seniority   TEXT    NOT NULL,
    location    TEXT    NOT NULL,
    salary      TEXT,
    published   TEXT,
    url         TEXT,
    UNIQUE (external_id)
);

CREATE TABLE job_skills (
    job_id  INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill   TEXT    NOT NULL,
    PRIMARY KEY (job_id, skill)
);

CREATE INDEX idx_jobs_category  ON jobs(category);
CREATE INDEX idx_jobs_seniority ON jobs(seniority);
CREATE INDEX idx_skills_skill   ON job_skills(skill);
