with applications as (
    select * from {{ ref('stg_applications') }}
)

select
    status,
    count(*) as application_count,
    count(distinct company) as company_count,
    countif(referral_needed) as referral_needed_count
from applications
group by status
