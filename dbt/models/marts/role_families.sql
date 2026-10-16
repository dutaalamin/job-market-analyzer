-- Mart: summary counts by role family.

select
    category                                as role_family,
    count(*)                                as postings,
    count(distinct company)                 as companies,
    round(avg(array_length(skills)), 1)     as avg_skills_listed
from {{ ref('stg_jobs') }}
group by category
order by postings desc
