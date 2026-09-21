-- Applications per channel, publishable as-is.
--
-- apply_via arrives already generalized: staffing agency names are collapsed
-- to a single descriptor in pg_loader, at the boundary, so no real agency
-- name is present in this warehouse to leak. Everything remaining is an ATS
-- platform or job board, which are tools rather than employers and carry no
-- privacy weight.
--
-- This is a separate model from mart_public_metrics because that one is a
-- fixed name/value table, and channels are a variable-width set of keys.
select
    coalesce(nullif(trim(apply_via), ''), 'Unknown') as channel,
    count(*) as application_count
from {{ ref('stg_applications') }}
group by channel
order by application_count desc, channel
