-- Mart: one row per (job, skill) pair.
-- Unnests the skills list so every skill metric is a simple GROUP BY away.

with jobs as (
    select * from {{ ref('stg_jobs') }}
)

select
    external_id,
    unnest(skills) as skill
from jobs
