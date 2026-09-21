# Runbook

Auth and setup steps that Claude never performs. Each one is for Heather.

## HUMAN STEP: HubSpot private app (Task 7)

1. Create a free HubSpot account at hubspot.com.
2. Settings > Integrations > Private Apps > Create a private app, named `nerdjoy-pipeline`.
3. Scopes: `crm.objects.companies.read`, `crm.objects.companies.write`.
4. Copy the access token into `.env` as `HUBSPOT_TOKEN`.
5. Settings > Properties > Companies: create four single-line text properties with the internal names `ats_platform`, `ats_slug`, `target_domain`, `stage_size`.
6. Run: `source .venv/bin/activate && python3 -m nerdjoy_pipeline.hubspot_loader`
7. Confirm the companies appear under CRM > Companies.

Note: step 5 is already done. The four properties were created via the API
during the Task 7 build, so they exist in the portal already. Verify rather
than recreate.

## Known data property: 466 applications, 460 distinct keys

`application_key` is the SHA-256 of `company|role`. Six (company, role) pairs
appear twice in the tracker, so 466 applications collapse to 460 rows in
Postgres and in the warehouse. This is expected, not a load failure.

One of the six is a real conflict: the same company and role recorded with
both `Applied` and `Phone Screen`. In Postgres, which one survives depends on
load order, so treat that company's status as unreliable until the tracker is
corrected.

In dbt this is no longer load-order dependent. `stg_applications` deduplicates
on `application_key` with `qualify row_number()`, keeping the most-advanced row
by funnel position (`Rejected`/`Withdrew` treated as terminal and ranked above
`Offer`), tie-broken by earliest `discovered_date` then latest `applied_date`.
The conflicting pair therefore resolves to `Phone Screen` every run. The
warehouse answer is stable, but it is still a guess at Heather's intent: the
underlying tracker row is what needs fixing.

If every tracker line must persist as its own row, the key needs a third
component (discovered_date would do it). That is a schema change affecting
Postgres, dbt and Hightouch, so it is a decision for Heather, not a silent fix.

## Local config that is never committed

- `.env` holds all credentials.
- `config/agency_channels.txt` holds the real staffing agency names used to
  collapse them into one "Staffing Agency" channel. Copy the committed
  `config/agency_channels.example.txt` to recreate it. Without this file the
  agency names are published verbatim, which leaks real companies.

## Before any push

Run `python scripts/repo_privacy_scan.py`. It must print PASS. It fails the
build if any real company name from the tracker reaches a git-tracked file.

## HUMAN STEP: BigQuery project and service account (Task 8)

BigQuery must be a **billing-enabled** project. The pure sandbox is rejected by
Fivetran as a destination (spec §11). Free-tier credits cover this volume;
expect no real spend.

1. In the Google Cloud console, create a project named `nerdjoy-pipeline`.
2. Billing > link a billing account. This is the step that makes Fivetran accept it.
3. APIs & Services > enable the BigQuery API.
4. IAM > Service Accounts > create `dbt-runner` with roles `BigQuery Data Editor` and `BigQuery Job User`.
5. Create a JSON key, save it OUTSIDE the repo (for example `~/.config/nerdjoy/bq-service-account.json`).
6. In `.env`, set `BIGQUERY_PROJECT`, `BIGQUERY_DATASET=nerdjoy_pipeline`, and `GOOGLE_APPLICATION_CREDENTIALS` to that path.
7. BigQuery > create the dataset `nerdjoy_pipeline`, location US.
8. `cp dbt/profiles.yml.example ~/.dbt/profiles.yml`

## Hightouch (free tier) - DONE 2026-09-21

Verified end to end. Source id in `.env`.

Prerequisites already completed, do not redo:

- IAM: `roles/bigquery.user` and `roles/bigquery.dataViewer` granted to the
  pipeline service account (address in `.env`, not recorded here: this file is
  public and a named owner-privileged identity is a social-engineering target).
  That account also still holds `roles/owner` on the project, so these grants
  were already implied. OPEN: drop owner now that every integration is wired.
- Lightning sync schemas `hightouch_audit` and `hightouch_planner` exist in
  BigQuery. The Hightouch UI shows these as shell commands, but they are SQL:
  run them in the BigQuery console or via `bq query --use_legacy_sql=false`.
- HubSpot company properties `referral_score` and `open_application_count`
  were created via the API, both numeric, in the Company information group.
  Plan Task 10 step 6 says to create them first; that is done.

Models: `mart_referral_scoring` (98 rows, key `company`), `fct_funnel`
(6 rows, key `status`). `fct_funnel` has no sync, by design.

Syncs, both enabled on a 1 hour interval:

- HUBSPOT sync (id in `.env`): upsert into Companies, match `company` to `name`,
  maps `referral_score` and `open_application_count`. Verified against the
  HubSpot API: 98 companies carry a real score, 0 failed.
- SHEET sync (id in `.env`): mode `mirror` into the warm-intro targets sheet. Verified by reading the sheet: 98 data rows plus header
  (`company`, `open_application_count`, `latest_discovered_date`,
  `referral_score`).

98 companies get a score. That is correct: the mart only includes companies
that qualify for warm intro scoring. Blank is not failure.

Corrected 2026-09-21: this line previously said "98 of the 131 HubSpot
companies". HubSpot now holds 220 company records, 89 of them created at
17:17 by the Hightouch sync itself, so the sync has been inserting rather
than only updating. Those 220 rows carry only 209 distinct names plus 11
null names, which means Hightouch is also creating duplicates on name
variants. Worth cleaning up before the CRM count is quoted anywhere public.

Deviations from the plan, both accepted:

- The plan specifies sync mode `overwrite`; the sheet sync uses `mirror`.
  Mirror deletes rows that leave the model, which self-cleans stale targets.
- A third destination existed, `Google Sheets (Service Account)`, with no sync
  attached. Deleted.

Reading the sheet from code requires two things that are easy to miss: the
Google Sheets API enabled on the project, and the sheet shared with the
pipeline service account as Viewer. Hightouch itself does not need
either, since it writes with its own Google authorization.

`.env` keys: `HIGHTOUCH_API_KEY`, `HIGHTOUCH_SYNC_ID_HUBSPOT`,
`HIGHTOUCH_SYNC_ID_SHEET`, `HIGHTOUCH_SHEET_ID`.

Proof screenshots: SKIPPED at Heather's direction, 2026-09-21. `docs/proof/`
stays gitignored in case any are captured later. Proof for the honesty
principle is instead the API verification recorded above: 98 scored companies
read back from the HubSpot API, and 98 data rows read back from the sheet.
That is stronger evidence than a screenshot, since it was re-derived from the
live services rather than photographed.

## Fivetran Postgres connector - DONE 2026-09-21

Connection `supabase_postgres`, in the Fivetran group named in `.env`, destination
`Warehouse` (BigQuery). Verified: successful historical sync, 460 loaded
rows, 25 seconds, confirmed independently from BigQuery.

Landed at the Fivetran-named dataset `<project>.supabase_postgres_public.applications`.
Fivetran names the dataset from the connection name plus source schema and
ignores whatever dataset you pre-create, so `nerdjoy_pipeline_raw` exists but
is unused. `sources.yml` points at the real name.

Replication is QUERY-BASED, not CDC. Logical replication cannot work here:
the Supabase session pooler is required for IPv4 but does not support the
replication protocol, and the direct host `db.<ref>.supabase.co` is IPv6-only
while Fivetran egresses from IPv4. Fivetran will still create
`fivetran_pub` and `fivetran_pg_slot` when you pick CDC, then fail to
connect to the slot; both were dropped. Nothing public claims CDC, so the
honesty principle needs no wording change.

Two traps worth knowing on a rebuild:

- A destination belongs to a GROUP. A connection can only write to the
  destination in its own group. Creating a destination from the wrong screen
  makes a second group, and the connector then shows "no destination" while a
  perfectly good destination sits in the other group.
- After creating a destination, Fivetran walks you into the Fivetran Platform
  Connector, which syncs 34 tables of Fivetran's own account metadata. It
  looks like part of setup. It is not. Use "Complete Later".

Schema selection defaulted to ALL 5 Supabase schemas, 39 tables, including
`auth` (user identities, hashed passwords, sessions, MFA factors) and
`vault` (encrypted secrets). Only `public.applications` is selected. Never
let this default through: syncing `auth` into the warehouse would put
credentials behind a pipeline that feeds a public dashboard.

Sync mode is soft delete, so the raw table carries `_fivetran_deleted`,
`_fivetran_synced` and `ctid_fivetran_id`. `stg_applications` filters on
`not coalesce(_fivetran_deleted, false)`.

`statement_timeout` was 120s, below Fivetran's 300s floor. Fixed with
`alter role postgres set statement_timeout = 0;` (verified in `rolconfig`).

### Open: the conflicting-status row

Swapping the source changed two published metrics: `funnel_applied` 234 ->
235 and `funnel_phone_screen` 2 -> 1. Totals are unaffected at 460.

Cause: the one (company, role) pair recorded as both 'Applied' and
'Phone Screen'. Postgres collapses duplicates on `application_key` before
Fivetran sees them, keeping whichever row loaded last, so the dbt
funnel-position ranking never gets to choose. The dedupe in
`stg_applications` still guarantees uniqueness but no longer decides which
status wins.

That makes `funnel_phone_screen` honestly describable as "whichever row
Postgres loaded last", which is weaker than intended for a number headed to
a public dashboard. Fix by correcting the row in `job_tracker.csv` and
reloading. The alternative, adding `discovered_date` to `application_key` so
all 466 rows survive, changes `applications_total` to 466 and touches
Postgres, dbt and Hightouch.

## Fivetran HubSpot connector - DONE 2026-09-21

Closes the loop. Hightouch writes scored companies into HubSpot; Fivetran
brings HubSpot's own view back so the warehouse can see CRM state it does not
itself produce.

Landed at `<project>.hubspot.company`, 220 rows.
`company_property_history` (8,997 rows) syncs automatically alongside it and
is not used.

Schema selection defaulted to ALL schemas here too. Only `company` is
selected. Same warning as the Postgres connector: never let the default
through.

Only `lifecyclestage` is genuinely independent of this pipeline.
`referral_score` and `open_application_count` were written by Hightouch from
this very warehouse, so reading them back would be circular.
`hs_lastmodifieddate` was evaluated and REJECTED as an enrichment field: 98
records are stamped at exactly 17:17, matching the 98 Hightouch writes, so it
measures when the sync ran rather than when anything changed. Publishing it
would have been a cron timestamp presented as engagement data.

Fivetran prefixes HubSpot properties with `property_`, so the columns are
`property_name`, `property_lifecyclestage`, `property_createdate`.

Company name is the only key the two systems share. `stg_crm_companies`
deduplicates on lowercased, trimmed name (most recent `createdate` wins) to
keep the join one-to-one; `unique_dim_company_company` is the guard that
catches any fan-out.

The join is partial and that is published honestly: 128 of 378 companies
match, 33.9 percent. The matched subset was checked for skew and is
representative (86 vs 87 percent single-application, same average
applications per tier), so a lifecycle rate over it is defensible. Three
metrics ship together so the denominator is visible rather than implied:

- `crm_known_companies` 128
- `crm_coverage_pct` 33.9
- `crm_opportunity_pct` 16.4 (21 of 128)

Reporting the opportunity rate without the coverage would suggest it
describes the whole pipeline. It does not.
