-- Singular test: a posting may appear once per snapshot, never twice.
--
-- This replaces the old `unique` test on external_id. That test was correct when
-- the warehouse held a single snapshot; once history is loaded the same posting
-- legitimately repeats across snapshots, so uniqueness now belongs to the pair.

select
    snapshot_at,
    external_id,
    count(*) as occurrences
from {{ source('raw', 'raw_jobs') }}
group by snapshot_at, external_id
having count(*) > 1
