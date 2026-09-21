-- Source is the Fivetran-replicated table in BigQuery. The contract below is
-- what every downstream model depends on, so it must not change.
--
-- The tracker is keyed on (company, role) but does not enforce that pair as
-- unique: 466 tracker rows collapse to 460 distinct application_keys, six
-- (company, role) pairs having been entered twice. That collapse now happens
-- upstream in Postgres, so this source already arrives with 460 distinct keys
-- and the dedupe below is a safety net rather than an active reduction. It
-- stays because the schema contract requires application_key to be unique and
-- because a future source change must not silently break that: keep the
-- most-advanced row per key by funnel position, then the earliest discovery
-- date, then the latest applied date. Nothing here drops a distinct
-- application; only repeated entries of the same company and role collapse.
with source as (
    -- Soft delete mode keeps removed source rows with _fivetran_deleted = true.
    -- They are excluded here so a deleted application never reaches a mart.
    select * from {{ source('fivetran_supabase', 'applications') }}
    where not coalesce(_fivetran_deleted, false)
),

deduplicated as (
    select *
    from source
    where company is not null and company != ''
    qualify row_number() over (
        partition by application_key
        order by
            case status
                -- Rejected and Withdrew are terminal: they record a real
                -- outcome and outrank an unresolved earlier entry.
                when 'Rejected' then 7
                when 'Withdrew' then 7
                when 'Offer' then 6
                when 'Onsite' then 5
                when 'Phone Screen' then 4
                when 'Recruiter Call' then 3
                when 'Applied' then 2
                when 'To Apply' then 1
                else 0
            end desc,
            discovered_date asc nulls last,
            applied_date desc nulls last
    ) = 1
)

select
    application_key,
    company,
    role,
    status,
    priority,
    referral_needed,
    referral_status,
    apply_via,
    applied_date,
    discovered_date,
    case
        when status in ('Recruiter Call', 'Phone Screen', 'Onsite', 'Offer') then true
        else false
    end as reached_conversation,
    case when status = 'Offer' then true else false end as reached_offer
from deduplicated
