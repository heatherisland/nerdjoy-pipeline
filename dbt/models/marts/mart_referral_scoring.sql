-- Hightouch source: which companies need a warm intro next, ranked.
with applications as (
    select * from {{ ref('stg_applications') }}
)

select
    company,
    count(*) as open_application_count,
    max(discovered_date) as latest_discovered_date,
    -- Higher score means more worth a warm intro today.
    sum(
        case
            when referral_status = 'Outreach Pending' then 30
            when referral_status = 'Connection Pending' then 20
            when referral_status = 'Outreach Sent' then 5
            else 0
        end
        + case when priority = 'HIGH' then 20 when priority = 'MEDIUM' then 10 else 0 end
        + case when status = 'To Apply' then 15 when status = 'Applied' then 10 else 0 end
    ) as referral_score
from applications
where referral_needed
  and referral_status not in ('Got Referral', 'Declined', 'No Referral')
  and status not in ('Rejected', 'Withdrew')
group by company
order by referral_score desc
