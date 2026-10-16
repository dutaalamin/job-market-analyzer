-- Mart: skill demand with a share-of-market column.
-- This is the headline metric the dashboard is built around.

with pairs as (
    select * from {{ ref('job_skills') }}
),

total as (
    select count(distinct external_id) as total_jobs from {{ ref('stg_jobs') }}
)

select
    pairs.skill,
    count(distinct pairs.external_id)                       as postings,
    round(
        100.0 * count(distinct pairs.external_id) / total.total_jobs, 1
    )                                                       as pct_of_jobs
from pairs
cross join total
group by pairs.skill, total.total_jobs
order by postings desc
