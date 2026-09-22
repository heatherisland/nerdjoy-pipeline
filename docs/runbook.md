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
17:17 by the Hightouch sync itself.

Corrected again 2026-09-22, prior correction was a misdiagnosis: "89 created
by the sync" and "209 distinct names plus 11 null" were read as evidence of
a broken upsert creating duplicate name variants. Investigated and
independently re-verified: there are zero duplicate names in the table,
exact or case/whitespace normalized. The Hightouch sync config is `mode:
upsert` matching HubSpot `name` to the mart's `company`, not an insert-only
mode. Of the 98 `mart_referral_scoring` companies, exactly 9 already existed
in HubSpot from unrelated prior activity and were matched and updated in
place (the specific 9 names are not repeated here per the deny-list rule
below); the remaining 89 had no prior HubSpot record and were correctly
inserted, all in the same sync run (hence the shared 17:17 timestamp). 9 + 89
= 98, no residual. The 220 total minus 209 distinct plus 11 null accounts
for every row exactly once with no collision. Nothing to clean up.

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

### CLOSED 2026-09-22: the conflicting-status row

Previously open: swapping the source changed two published metrics,
`funnel_applied` 234 -> 235 and `funnel_phone_screen` 2 -> 1, caused by one
(company, role) pair recorded as both 'Applied' and 'Phone Screen'. Postgres
collapsed duplicates on `application_key` before Fivetran saw them, keeping
whichever row loaded last, so the dbt funnel-position ranking never got to
choose.

The tracker row was corrected at the source (in
`../claude-linkedin-assistant/job_tracker.csv`, outside this repo). Reloaded
and reverified end to end 2026-09-22: `pg_loader` upsert, Postgres 460 rows,
manual Fivetran sync, BigQuery 460 rows, `dbt run` and `dbt test` both clean
(9 models, 38 tests, 0 errors). `funnel_phone_screen` is back to 2, matching
the pre-conflict baseline, and no longer load-order dependent: both rows now
resolve to distinct, non-colliding statuses regardless of load order.

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

## HUMAN STEP: narrow the service account from roles/owner

The pipeline service account still holds `roles/owner` on the project. Owner can
delete the project, mint keys and grant itself anything, and the account's
address was published in this file until 2026-09-21. Everything the pipeline
actually does is covered by four narrow roles.

Claude does not run these: they need an authenticated gcloud session.

```bash
gcloud auth login
PROJECT="$BIGQUERY_PROJECT"                 # from .env
SA="$(gcloud iam service-accounts list --project "$PROJECT" \
      --format='value(email)' --filter='displayName:gtm OR email:gtm-job-search')"
echo "$PROJECT / $SA"                       # confirm before continuing

# 1. What does it hold today? Record this before changing anything.
gcloud projects get-iam-policy "$PROJECT" \
  --flatten='bindings[].members' \
  --filter="bindings.members:$SA" \
  --format='value(bindings.role)'

# 2. Grant only what the pipeline uses: dbt runs queries and writes tables,
#    Hightouch reads, and the sheet sync needs no project role.
for ROLE in roles/bigquery.dataEditor roles/bigquery.jobUser roles/bigquery.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" --role="$ROLE" --condition=None >/dev/null
done

# 3. Verify the pipeline still works BEFORE removing owner, so a failure here
#    is recoverable. Both must succeed.
(cd dbt && dbt run && dbt test)

# 4. Only after step 3 passes, drop owner.
gcloud projects remove-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA" --role='roles/owner' --condition=None

# 5. Confirm owner is gone and the narrow roles remain.
gcloud projects get-iam-policy "$PROJECT" \
  --flatten='bindings[].members' \
  --filter="bindings.members:$SA" \
  --format='value(bindings.role)'
```

If step 3 fails, add the missing role rather than restoring owner. Hightouch and
Fivetran authenticate with their own credentials and are unaffected by this
change.

Note: the project id and this account's address remain in pushed git history
from commits made before 2026-09-21. Neither is a credential and no key was ever
committed, so the decision was to leave history intact and narrow the roles
instead. Narrowing the roles is what actually reduces the risk.
