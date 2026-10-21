-- Staging: one clean row per posting, from the NEWEST snapshot only.
-- Light typing/casting on top of the raw loader table so downstream models can
-- assume a tidy shape.
--
-- The raw table holds one row per (posting, snapshot) once history is loaded.
-- Keeping this view pinned to the latest snapshot preserves two things: the
-- `unique` test on external_id, and the meaning of every existing mart (they all
-- describe the present, not a sum over time). Trends read `stg_job_history`.

with source as (
    select * from {{ source('raw', 'raw_jobs') }}
)

select
    external_id,
    trim(title)                          as title,
    trim(company)                        as company,
    coalesce(nullif(trim(category), ''), 'Other') as category,
    coalesce(nullif(trim(seniority), ''), 'Mid')  as seniority,
    coalesce(nullif(trim(location), ''), 'Unspecified') as location,
    job_type,
    nullif(trim(salary), '')             as salary,
    try_cast(published as date)          as published,
    url,
    skills
from source
where title is not null
  and company is not null
  and snapshot_at = (select max(snapshot_at) from source)
