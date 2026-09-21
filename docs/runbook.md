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
both `Applied` and `Phone Screen`. Which one survives depends on load order,
so treat that company's status as unreliable until the tracker is corrected.

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
