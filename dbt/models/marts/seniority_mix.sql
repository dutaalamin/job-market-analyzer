-- Mart: how seniority breaks down, with the skill count typical of each level.

select
    seniority,
    count(*)                             as postings,
    round(avg(array_length(skills)), 1)  as avg_skills_listed,
    count(distinct company)              as companies
from {{ ref('stg_jobs') }}
group by seniority
order by postings desc
