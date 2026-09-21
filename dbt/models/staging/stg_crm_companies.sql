-- HubSpot's own view of the companies this pipeline pushed to it.
--
-- Only lifecyclestage is used downstream. The other properties HubSpot holds
-- for these records (referral_score, open_application_count) were written by
-- Hightouch from this very warehouse, so reading them back would be circular
-- and would tell us nothing we did not already know. hs_lastmodifieddate is
-- deliberately excluded for the same reason: it records when the Hightouch
-- sync last ran, not when anything about the company actually changed.
--
-- Company name is the only available join key. HubSpot holds 220 rows with
-- 209 distinct names and 11 null names, so rows are deduplicated here to keep
-- the downstream join one-to-one. Where a name is duplicated, the most
-- recently created record wins.
with source as (
    select *
    from {{ source('fivetran_hubspot', 'company') }}
    where not coalesce(_fivetran_deleted, false)
      and property_name is not null
      and trim(property_name) != ''
),

deduplicated as (
    select *
    from source
    qualify row_number() over (
        partition by lower(trim(property_name))
        order by property_createdate desc nulls last, id desc
    ) = 1
)

select
    lower(trim(property_name)) as company_key,
    property_lifecyclestage as lifecycle_stage,
    property_createdate as crm_created_at
from deduplicated
