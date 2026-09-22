# nerdjoy // Pipeline

A job search run as a go-to-market motion, on a real modern data stack.

Target companies are accounts. Hiring managers are leads. Referrals are warm
intros. The tracker is the CRM. This repo is the pipeline that runs it, and
[the dashboard](https://nerdjoy.tech/pipeline/) is its live output.

Every tool named below is wired and has run against real data. Nothing here is
aspirational, and nothing here is a toy dataset.

## The stack

| Layer | Tool |
|---|---|
| Sources | Application tracker (Postgres), HubSpot CRM |
| Ingest | Fivetran connectors |
| Warehouse | BigQuery, raw and analytics datasets |
| Transform | dbt Core, staging models into funnel and scoring marts |
| Activate | Hightouch reverse ETL into HubSpot and a targets sheet |
| Orchestrate | Airflow, a single scheduled DAG |
| Control plane | An agent reads the marts and drafts messages for review |

Data flows in a single direction: tracker to Postgres to Fivetran to BigQuery, transformed by
dbt, then back out through Hightouch into the CRM. Fivetran then brings the
CRM's own view back into the warehouse, which closes the loop and lets the
models see CRM activity they did not themselves produce.

## What is public and what is not

The dashboard publishes aggregates only: counts, rates and month buckets. No
company names, no contacts, no personal data. That is enforced in code rather
than by convention, in two layers:

1. A whitelist discards any metric key that is not expected, so an unplanned
   field cannot reach the payload by accident.
2. A guard scans the serialized output against a deny list built from the live
   tracker, and refuses to write the file if a real name survives.

`scripts/repo_privacy_scan.py` applies the same idea to the repository itself,
because a name in a code comment is as published as a name on the dashboard.
It runs before every push and fails the build on any hit.

The source tracker is read-only to this pipeline. Every read path opens it in
mode `r`, and no code here writes to it.

## Layout

```
docs/        project status, local setup, runbook
dags/        Airflow DAG, the full task chain
dbt/         staging models, funnel and scoring marts
src/         tracker reader, loaders, metrics extraction, the privacy guard
dashboard/   static build, metrics injected as JSON at build time
scripts/     privacy scan, publication gate, seed generation
tests/       118 tests
docs/        runbook, including the steps a human performs
```

## Documentation

- `docs/PROJECT_STATUS.md` is the snapshot: what is built, what is live, what is
  decided and what remains open. Start here when picking the project up.
- `docs/LOCAL_SETUP.md` covers the gitignored files a fresh clone does not
  get, and the refresh and publish sequence.
- `docs/runbook.md` holds operational detail and the steps a human performs.

## Running it

Requires Python 3.13. Credentials live in `.env`, which is never committed;
`.env.example` lists the keys without values.

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest              # 118 tests
.venv/bin/python scripts/repo_privacy_scan.py
```

The DAG tests skip unless Airflow is present, since Airflow is installed only
in the deployed image.

## A note on the numbers

Six company and role pairs appear twice in the tracker, so 466 rows collapse to
460 distinct applications. The dashboard reports the deduplicated figure. The
activity chart counts only applications with a submission date, which is fewer
than the total, because rows still queued to apply have no such date by
definition. Both choices are documented in `docs/runbook.md` rather than
smoothed over.
