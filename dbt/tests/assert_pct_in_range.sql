-- Singular test: the market-share column must stay within 0–100%.
-- A value outside that range means the denominator or join is wrong.

select *
from {{ ref('skill_demand') }}
where pct_of_jobs < 0 or pct_of_jobs > 100
