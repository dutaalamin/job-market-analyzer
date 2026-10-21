-- Staging: one row per (posting, snapshot), for anything that measures change.
--
-- Why a separate view instead of adding a column to stg_jobs: every existing
-- mart answers "what does the market look like now", so they must read a single
-- snapshot. Mixing history into that view would silently multiply every count.
--
-- snapshot_at is the collector's timestamp (YYYYMMDD-HHMMSS), not the posting's
-- published date. A posting is published once and observed many times; a trend
-- is about the observations.

with source as (
    select * from {{ source('raw', 'raw_jobs') }}
)

select
    snapshot_at,
    external_id,
    trim(title)                                    as title,
    trim(company)                                  as company,
    coalesce(nullif(trim(category), ''), 'Other')   as category,
    coalesce(nullif(trim(seniority), ''), 'Mid')    as seniority,
    coalesce(nullif(trim(location), ''), 'Unspecified') as location,
    job_type,
    try_cast(published as date)                    as published,
    url,
    skills
from source
where title is not null
  and company is not null
