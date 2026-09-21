-- Company grain with a generalized size descriptor. This mart holds real
-- names and is NEVER published. Only mart_public_metrics is public.
--
-- CRM columns come from HubSpot via Fivetran, joined on company name because
-- that is the only key both systems share. The join is partial by nature:
-- HubSpot knows a subset of these companies, so crm_is_known distinguishes
-- "HubSpot has no record" from "HubSpot has a record with no stage". Any
-- downstream rate over lifecycle_stage must use crm_is_known as its
-- denominator, never the full company count.
with companies as (
    select * from {{ ref('stg_companies') }}
),

crm as (
    select * from {{ ref('stg_crm_companies') }}
)

select
    companies.company,
    companies.application_count,
    companies.referral_needed_count,
    companies.conversation_count,
    companies.offer_count,
    companies.first_discovered_date,
    companies.last_applied_date,
    case
        when companies.conversation_count > 0 then 'engaged'
        when companies.application_count > 1 then 'multi-application'
        else 'single-application'
    end as engagement_tier,
    crm.company_key is not null as crm_is_known,
    crm.lifecycle_stage as crm_lifecycle_stage
from companies
left join crm
    on lower(trim(companies.company)) = crm.company_key
