-- The ONLY mart safe to publish. Long format, aggregate values only.
-- No company names, no roles, no URLs by construction.
with applications as (
    select * from {{ ref('stg_applications') }}
),

referral_base as (
    select count(*) as needed,
           countif(referral_status = 'Got Referral') as got
    from applications
    where referral_needed
)

select 'applications_total' as metric_name,
       cast(count(*) as numeric) as metric_value
from applications

union all
select 'companies_total', cast(count(distinct company) as numeric) from applications

union all
select concat('funnel_', lower(replace(status, ' ', '_'))),
       cast(count(*) as numeric)
from applications
group by status

union all
select 'referrals_needed', cast(needed as numeric) from referral_base

union all
select 'referrals_got', cast(got as numeric) from referral_base

union all
select 'referral_conversion_pct',
       cast(case when needed = 0 then 0 else round(got / needed * 100, 1) end as numeric)
from referral_base
