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

Verified end to end. Source id 53438 (BigQuery).

Prerequisites already completed, do not redo:

- IAM: `roles/bigquery.user` and `roles/bigquery.dataViewer` granted to
  `gtm-job-search@gtm-job-search-engine.iam.gserviceaccount.com`. Note the
  service account also holds `roles/owner` on the project, so these grants were
  already implied. Consider dropping owner once every integration is wired.
- Lightning sync schemas `hightouch_audit` and `hightouch_planner` exist in
  BigQuery. The Hightouch UI shows these as shell commands, but they are SQL:
  run them in the BigQuery console or via `bq query --use_legacy_sql=false`.
- HubSpot company properties `referral_score` and `open_application_count`
  were created via the API, both numeric, in the Company information group.
  Plan Task 10 step 6 says to create them first; that is done.

Models: `mart_referral_scoring` (98 rows, key `company`), `fct_funnel`
(6 rows, key `status`). `fct_funnel` has no sync, by design.

Syncs, both enabled on a 1 hour interval:

- HUBSPOT `15546905`: upsert into Companies, match `company` to `name`,
  maps `referral_score` and `open_application_count`. Verified against the
  HubSpot API: 98 companies carry a real score, 0 failed.
- SHEET `15547600`: mode `mirror` into "NerdJoy Pipeline - Warm Intro
  Targets". Verified by reading the sheet: 98 data rows plus header
  (`company`, `open_application_count`, `latest_discovered_date`,
  `referral_score`).

98 of the 131 HubSpot companies get a score. That is correct: the mart only
includes companies that qualify for warm intro scoring. Blank is not failure.

Deviations from the plan, both accepted:

- The plan specifies sync mode `overwrite`; the sheet sync uses `mirror`.
  Mirror deletes rows that leave the model, which self-cleans stale targets.
- A third destination exists, `Google Sheets (Service Account)` id 169318,
  with no sync attached. Safe to delete.

Reading the sheet from code requires two things that are easy to miss: the
Google Sheets API enabled on the project, and the sheet shared with the
service account address above as Viewer. Hightouch itself does not need
either, since it writes with its own Google authorization.

`.env` keys: `HIGHTOUCH_API_KEY`, `HIGHTOUCH_SYNC_ID_HUBSPOT`,
`HIGHTOUCH_SYNC_ID_SHEET`, `HIGHTOUCH_SHEET_ID`.

Proof screenshots: SKIPPED at Heather's direction, 2026-09-21. `docs/proof/`
stays gitignored in case any are captured later. Proof for the honesty
principle is instead the API verification recorded above: 98 scored companies
read back from the HubSpot API, and 98 data rows read back from the sheet.
That is stronger evidence than a screenshot, since it was re-derived from the
live services rather than photographed.

The unused `Google Sheets (Service Account)` destination id 169318 was deleted.
