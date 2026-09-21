with applications as (
    select * from {{ ref('stg_applications') }}
)

select
    company,
    count(*) as application_count,
    countif(referral_needed) as referral_needed_count,
    countif(reached_conversation) as conversation_count,
    countif(reached_offer) as offer_count,
    min(discovered_date) as first_discovered_date,
    max(applied_date) as last_applied_date
from applications
group by company
