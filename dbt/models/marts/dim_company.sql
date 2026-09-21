-- Company grain with a generalized size descriptor. This mart holds real
-- names and is NEVER published. Only mart_public_metrics is public.
with companies as (
    select * from {{ ref('stg_companies') }}
)

select
    company,
    application_count,
    referral_needed_count,
    conversation_count,
    offer_count,
    first_discovered_date,
    last_applied_date,
    case
        when conversation_count > 0 then 'engaged'
        when application_count > 1 then 'multi-application'
        else 'single-application'
    end as engagement_tier
from companies
