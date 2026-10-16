-- Mart: top skill per role family, using a window function to rank within
-- each family. Demonstrates analytic SQL beyond simple aggregation.

with pairs as (
    select
        j.category as role_family,
        p.skill,
        count(distinct p.external_id) as postings
    from {{ ref('job_skills') }} p
    join {{ ref('stg_jobs') }} j on j.external_id = p.external_id
    group by j.category, p.skill
),

ranked as (
    select
        role_family,
        skill,
        postings,
        row_number() over (
            partition by role_family order by postings desc, skill
        ) as rank_in_family
    from pairs
)

select *
from ranked
where rank_in_family <= 8
order by role_family, rank_in_family
