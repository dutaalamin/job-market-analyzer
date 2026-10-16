-- Staging: one clean row per posting.
-- Light typing/casting on top of the raw loader table so downstream models can
-- assume a tidy shape.

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
where title is not null and company is not null
