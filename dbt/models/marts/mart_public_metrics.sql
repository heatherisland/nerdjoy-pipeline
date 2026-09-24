-- The ONLY mart safe to publish. Long format, aggregate values only.
-- No company names, no roles, no URLs by construction.
with applications as (
    select * from {{ ref('stg_applications') }}
),

referral_base as (
    select count(*) as needed,
           countif(referral_status = 'Got Referral') as got,
           countif(referral_status = 'Outreach Sent') as outreach_sent
    from applications
    where referral_needed
),

-- CRM coverage is partial: HubSpot knows a subset of these companies, matched
-- on name. crm_opportunity_pct is therefore a rate over known companies only,
-- and crm_coverage_pct is published beside it so the denominator is visible
-- rather than implied. Reporting the rate without the coverage would suggest
-- it describes the whole pipeline, which it does not.
crm_base as (
    select count(*) as total,
           countif(crm_is_known) as known,
           countif(crm_is_known and crm_lifecycle_stage = 'opportunity') as opportunities
    from {{ ref('dim_company') }}
)

select 'applications_total' as metric_name,
       cast(count(*) as numeric) as metric_value
from applications

union all
select 'interviewed_total', cast(countif(ever_interviewed) as numeric) from applications

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

union all
select 'crm_known_companies', cast(known as numeric) from crm_base

union all
select 'crm_coverage_pct',
       cast(case when total = 0 then 0 else round(known / total * 100, 1) end as numeric)
from crm_base

union all
select 'crm_opportunity_pct',
       cast(case when known = 0 then 0 else round(opportunities / known * 100, 1) end as numeric)
from crm_base

union all
select 'referrals_outreach_sent', cast(outreach_sent as numeric) from referral_base
