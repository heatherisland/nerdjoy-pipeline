# Local setup

What a fresh clone does NOT give you, and how to rebuild it.

Several files are deliberately gitignored because they hold real names or
credentials. A clone without them runs, but silently produces different
output: agency names stop collapsing, excluded companies stop being excluded,
and the privacy scan loses part of its deny list. None of that raises an error.
Rebuild all of them before trusting any run.

## Required local files

| File | Holds | Rebuild from |
|---|---|---|
| `.env` | all credentials | `.env.example` |
| `config/agency_channels.txt` | real staffing agency names | `config/agency_channels.example.txt` |
| `config/excluded_companies.txt` | companies withheld from the pipeline | `config/excluded_companies.example.txt` |
| `~/.dbt/profiles.yml` | dbt warehouse connection | `dbt/profiles.yml.example` |
| `metrics.json` | generated output | regenerate, see below |
| `dbt/seeds/applications_seed.csv` | generated seed | `python scripts/make_seed.py` |

The source tracker itself lives OUTSIDE this repo, in a sibling private repo,
and is never copied in. Point at it with `TRACKER_PATH` if it is not at the
default relative location `../claude-linkedin-assistant/job_tracker.csv`.

## Why the two config files matter

`agency_channels.txt` lists agencies that are both channels and employers.
`generalize_channel()` collapses them to the single label `Staffing Agency`,
preserving the funnel total. Without the file the loader publishes the agency
names verbatim, which leaks real companies onto the dashboard.

`excluded_companies.txt` lists companies withheld from the pipeline entirely,
dropped on read so they reach no downstream consumer. The names live here
rather than in source because an excluded company is a real company, and
hardcoding it republishes in source the very name the exclusion was meant to
withhold. See `docs/PROJECT_STATUS.md` for the bug this caused.

Both loaders return an empty set when the file is missing rather than raising.
That is deliberate, so CI and a fresh clone still run, but it does mean a
missing file degrades privacy silently. Check both exist before any publish.

## Environment keys

`.env` keys currently in use, values not recorded here:

```
PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD DATABASE_URL
GOOGLE_APPLICATION_CREDENTIALS BIGQUERY_PROJECT BIGQUERY_DATASET
HUBSPOT_TOKEN
GSHEET_URL GSHEET_ID
HIGHTOUCH_API_KEY HIGHTOUCH_SYNC_ID_HUBSPOT HIGHTOUCH_SYNC_ID_SHEET
HIGHTOUCH_SHEET_ID
GITHUB_REPO
```

`GOOGLE_APPLICATION_CREDENTIALS` points at a service-account JSON kept OUTSIDE
the repo. Never move it inside, even temporarily.

## From clone to verified

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"

cp .env.example .env                                     # then fill in
cp config/agency_channels.example.txt config/agency_channels.txt
cp config/excluded_companies.example.txt config/excluded_companies.txt
cp dbt/profiles.yml.example ~/.dbt/profiles.yml

.venv/bin/python -m pytest                    # expect 118 passed, 1 skipped
.venv/bin/python scripts/repo_privacy_scan.py # expect PASS
```

The 1 skip is the Airflow DAG test, which skips unless Airflow is installed.
That is expected locally and is NOT evidence the DAG works. See open item 2 in
`docs/PROJECT_STATUS.md`.

Every network command needs the SSL workaround:

```bash
export SSL_CERT_FILE=$(.venv/bin/python -c "import certifi;print(certifi.where())")
export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE
```

## Refresh and publish

```bash
set -a && . ./.env && set +a
export SSL_CERT_FILE=$(.venv/bin/python -c "import certifi;print(certifi.where())")
export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE

.venv/bin/python -m nerdjoy_pipeline.pg_loader          # tracker -> Postgres
# Fivetran syncs on its own schedule, or trigger it in the UI
(cd dbt && ../.venv/bin/dbt run && ../.venv/bin/dbt test)
.venv/bin/python -m nerdjoy_pipeline.metrics_extract    # marts -> metrics.json
.venv/bin/python dashboard/build.py                     # -> dashboard/dist/
.venv/bin/python scripts/verify_public.py               # MUST print clean
```

`verify_public.py` is the last gate before anything goes public. If it fails,
nothing gets published until it passes. Do not edit the guard to make a
violation go away; rewrite the copy instead.

Deploy is a copy of `dashboard/dist/` to `public_html/pipeline/` on the host.
Verify by fetching the live URL and diffing against the local artifact, not by
loading it in a browser and eyeballing it.

## Proving a gate still works

Both privacy gates must be proven able to fail after any change to them:

```bash
cp metrics.json /tmp/m.bak
# insert a known real company name into metrics.json
.venv/bin/python scripts/verify_public.py   # MUST fail and name the term
cp /tmp/m.bak metrics.json
.venv/bin/python scripts/verify_public.py   # MUST pass
```

A green result from a check that has never been seen to fail proves nothing.
