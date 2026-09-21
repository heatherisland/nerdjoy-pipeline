# nerdjoy // Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully-wired modern GTM data stack that runs Heather's job search like a go-to-market pipeline, surfaced through one public interactive dashboard on real anonymized funnel data.

**Architecture:** A read-only extract of `job_tracker.csv` plus target companies lands in cloud Postgres and HubSpot. Fivetran syncs both into BigQuery, dbt Core builds funnel and referral-scoring marts, Hightouch activates them back into HubSpot and a Google Sheet, and an Astro/Airflow DAG orchestrates the run. A metrics export with a hard anonymization guard emits `metrics.json`, which a static dashboard renders. Every layer is independently testable; the lower layers ship before the trial-bound layers (Fivetran, Astro) are wired.

**Tech Stack:** Python 3.13 (stdlib + `psycopg[binary]`, `pytest`), Postgres (Neon free tier), HubSpot free CRM, Fivetran, BigQuery (billing-enabled project), dbt Core 1.8+ with `dbt-bigquery`, Hightouch free tier, Astronomer Astro (`astro dev`), static HTML/CSS/JS dashboard.

**Spec:** `docs/superpowers/specs/2026-09-20-gtm-job-search-engine-design.md`
**Handoff:** `docs/superpowers/specs/2026-09-20-gtm-job-search-engine-HANDOFF.md`

## Locked Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Public brand name | `nerdjoy // Pipeline` |
| 2 | Warehouse | BigQuery on a **billing-enabled** project (NOT the sandbox, which Fivetran rejects) |
| 3 | Hightouch second destination | Google Sheet |
| 4 | Public repo home | `github.com/heatherisland` |

## Global Constraints

Every task's requirements implicitly include this section.

- **No em-dashes (`—`) in any outgoing copy.** Applies to: the dashboard (all rendered strings), `metrics.json` string values, the README, and the LinkedIn reveal post. Enforced by an automated check (Task 3), not by eyeballing. Internal specs, plans, code comments, and commit messages are not outgoing copy.
- **No PII in anything public or committed.** No company names, person names, emails, phone numbers, or URLs in `metrics.json`, the dashboard, or the public repo. Aggregates and generalized descriptors only (e.g. "Series C, ~250 employees, martech"). Enforced by two checks in Task 3: a deny list built from the tracker's `Company` column, and a pattern check for emails and phone numbers that catches PII in columns the deny list never reads.
- **PII hides outside the Company column.** The live tracker stores a real email inside `Apply Via` (`Email (dana@northwind.invalid)`), and `Apply Via` values are published as channel labels. Never assume a column is name-free just because it is not the name column.
- **`job_tracker.csv` is read-only to the pipeline.** No build step may write, move, or rewrite it. Every read opens the file in `"r"` mode. Enforced by a test (Task 2).
- **Claude never enters credentials.** Every secret is read from an environment variable or an untracked `.env`. No task instructs an agent to open a login page, paste a token, or complete OAuth. Auth steps are written as instructions **for Heather** and marked `HUMAN STEP`.
- **Never commit** resume content, search profile, contacts, HubSpot exports, tracker data, or `.env`. Enforced by `.gitignore` (Task 1) plus the guard (Task 3).
- **Source tracker path:** `~/claude-linkedin-assistant/job_tracker.csv` (467 data rows, 16 columns). Read via the `TRACKER_PATH` env var, defaulting to that path. It lives in a **different repo** and is never copied into this one.
- **Outreach stays human-in-the-loop.** No task may send a DM or email. The pipeline surfaces targets; Heather sends.
- **Canonical statuses:** `To Apply` · `Applied` · `Recruiter Call` · `Phone Screen` · `Onsite` · `Offer` · `Rejected` · `Withdrew`
- **Canonical priorities:** `HIGH` · `MEDIUM` · `LOW`
- **Canonical referral statuses:** `Not Needed` · `Outreach Pending` · `Connection Pending` · `Outreach Sent` · `Got Referral` · `Declined` · `No Referral`
- **Dirty source data is expected.** The live tracker contains out-of-domain values: `Referral Needed` holds 3 date strings, `Referral Status` holds 3 `NO` values, and `Apply Via` has case variants (`Company Site` / `Company site` / `Company Website`). Normalization is a required feature, not a bug. Never assume a column is clean.

- **Commit messages:** conventional format (`type: description`), subject **50 characters or fewer**, and no AI attribution trailer. A commit hook rejects violations, which stalls the task mid-step. Every commit message in this plan already complies; keep new ones under the limit.

## Build Order Rationale

Tasks 1-9 have zero external-trial dependency and produce a shippable spine: a working export, a guard, and a live dashboard. Tasks 10-13 wire the trial-bound platforms (Fivetran ~14 days, Astro) **last**, per spec §10, with proof capture immediately after each first real run. If a trial lapses before the reveal: Airbyte replaces Fivetran, local `astro dev` replaces hosted Astro. Both fallbacks keep the honesty principle intact as long as the diagram is updated to match.

## File Structure

```
nerdjoy-pipeline/
├── .env.example              # variable names only, no values (committed)
├── .gitignore
├── README.md                 # public-facing, sanitized (Task 15)
├── pyproject.toml            # deps + pytest config
├── src/nerdjoy_pipeline/
│   ├── __init__.py
│   ├── tracker.py            # Task 2: read-only tracker reader + normalizer
│   ├── guard.py              # Task 3: deny-list + em-dash guard
│   ├── metrics.py            # Task 4: aggregate computation
│   ├── metrics_extract.py    # Task 5: CLI, writes metrics.json
│   ├── pg_loader.py          # Task 6: tracker -> Postgres
│   └── hubspot_loader.py     # Task 7: target companies -> HubSpot
├── dbt/                      # Task 8
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── seeds/applications_seed.csv   # real data, GITIGNORED
│   ├── seeds/sample_seed.csv         # fictional, committed for CI
│   └── models/
│       ├── staging/{stg_applications,stg_companies}.sql + schema.yml
│       └── marts/{fct_funnel,dim_company,mart_referral_scoring,mart_public_metrics}.sql + schema.yml
├── dashboard/                # Task 9
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── build.py              # inlines metrics.json, runs the guard
├── dags/gtm_pipeline_dag.py  # Task 13
├── docs/
│   ├── superpowers/{specs,plans}/
│   ├── runbook.md            # Task 14: HUMAN STEP auth instructions
│   └── proof/                # Task 14: screenshots per tool
└── tests/
    ├── conftest.py           # Task 1: shared fixtures
    ├── fixtures/sample_tracker.csv  # Task 1: synthetic, no real names
    ├── test_tracker.py
    ├── test_guard.py
    ├── test_metrics.py
    ├── test_metrics_extract.py
    ├── test_pg_loader.py
    ├── test_hubspot_loader.py
    └── test_dashboard_build.py
```

Design note: `tracker.py` (read + normalize), `guard.py` (safety), and `metrics.py` (aggregate) are split so the guard is reusable by both the export and the dashboard build, and so aggregation is testable without touching the filesystem.

---

### Task 1: Project scaffold, test fixtures, and gitignore

Establishes the repo, the dependency set, and a synthetic tracker fixture that every later test uses. The fixture contains **no real names** and deliberately includes the dirty-data cases from the live tracker.

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/nerdjoy_pipeline/__init__.py`, `tests/conftest.py`, `tests/fixtures/sample_tracker.csv`

**Interfaces:**
- Consumes: nothing
- Produces: pytest fixture `sample_tracker_path` (a `pathlib.Path` to the CSV fixture); fixture `sample_tracker_rows` (list of raw `dict[str, str]`)

- [x] **Step 1: Initialize the repo and directory tree**

```bash
cd ~/nerdjoy-pipeline
git init
mkdir -p src/nerdjoy_pipeline tests/fixtures dashboard dags docs/proof dbt/models/staging dbt/models/marts dbt/seeds
touch src/nerdjoy_pipeline/__init__.py
```

- [x] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "nerdjoy-pipeline"
version = "0.1.0"
description = "GTM data stack that runs a job search like a go-to-market pipeline"
requires-python = ">=3.11"
dependencies = [
    "psycopg[binary]>=3.2",
    "requests>=2.32",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]
dbt = ["dbt-core>=1.8", "dbt-bigquery>=1.8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
```

- [x] **Step 3: Write `.gitignore`**

The `resumes/`, `outreach/`, and `*.csv` entries are the committed enforcement of the "never commit PII" rule.

```gitignore
# Secrets — never commit
.env
*.pem
*-service-account*.json
service_account.json

# Personal data — never commit
resumes/
outreach/
contacts/
*.csv
!tests/fixtures/sample_tracker.csv
# dbt/seeds/applications_seed.csv is generated from the real tracker and holds
# real company names. It is NEVER committed. CI uses the fictional fixture below.
!dbt/seeds/sample_seed.csv

# Generated artifacts
metrics.json
dashboard/dist/
dbt/target/
dbt/logs/
dbt/dbt_packages/

# Python
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
.coverage

# macOS / editors
.DS_Store
.idea/
*.swp
```

- [x] **Step 4: Write `.env.example`** (names only, never values)

```bash
# Copy to .env and fill in. .env is gitignored. Heather fills these in herself.
TRACKER_PATH=/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv
TARGET_COMPANIES_PATH=/Users/heatherbarry/claude-linkedin-assistant/resumes/target_companies.md

# Neon Postgres (Task 6)
PG_CONNECTION_STRING=

# HubSpot private app token (Task 7)
HUBSPOT_TOKEN=

# BigQuery (Task 8)
BIGQUERY_PROJECT=
BIGQUERY_DATASET=nerdjoy_pipeline
GOOGLE_APPLICATION_CREDENTIALS=

# Fivetran (Task 13)
FIVETRAN_API_KEY=
FIVETRAN_API_SECRET=
FIVETRAN_CONNECTOR_ID_POSTGRES=
FIVETRAN_CONNECTOR_ID_HUBSPOT=

# Hightouch (Task 13)
HIGHTOUCH_API_KEY=
HIGHTOUCH_SYNC_ID_HUBSPOT=
HIGHTOUCH_SYNC_ID_SHEET=
```

- [x] **Step 5: Write `tests/fixtures/sample_tracker.csv`**

16 columns matching the live tracker exactly. Names are fictional. Rows 5-7 carry the dirty-data cases.

```csv
Priority,Company,Role,Location,Type,Salary,Status,Applied Date,Next Action,URL,Notes,Discovered Date,Referral Needed,Referral Status,Referral Deadline,Apply Via
HIGH,Acme Data Co,Analytics Engineer,Remote,Remote,$180K-$210K,Applied,2026-08-01,Follow up,https://example.invalid/1,Strong fit,2026-07-25,YES,Outreach Sent,2026-07-30,Greenhouse
HIGH,Borealis Systems,Data Platform Engineer,Remote,Remote,$190K-$220K,Phone Screen,2026-08-05,Prep screen,https://example.invalid/2,Referral landed,2026-07-28,YES,Got Referral,2026-08-02,Lever
MEDIUM,Cindergrid,Solutions Architect,"Remote, US",Remote,$170K-$200K,To Apply,,Apply,https://example.invalid/3,Queued,2026-08-10,NO,Not Needed,,Ashby
LOW,Delta Loop,BI Developer,Remote,Remote,$150K-$170K,Rejected,2026-07-15,None,https://example.invalid/4,Closed,2026-07-10,NO,Not Needed,,LinkedIn
MEDIUM,Everwake Labs,MarTech Engineer,Remote,Remote,$175K-$195K,Applied,2026-08-12,Wait,https://example.invalid/5,Dirty referral-needed value,2026-08-01,2026-08-01,Outreach Pending,2026-08-06,Company Site
MEDIUM,Foxglove AI,Integrations Engineer,Remote,Remote,$165K-$185K,Applied,2026-08-14,Wait,https://example.invalid/6,Dirty referral-status value,2026-08-03,NO,NO,,Company site
LOW,Grayharbor,Data Analyst,Remote,Remote,$140K-$160K,Withdrew,2026-08-15,None,https://example.invalid/7,Case-variant apply via,2026-08-04,NO,Not Needed,,Company Website
HIGH,Hollowpine,Forward Deployed Engineer,Remote,Remote,$200K-$230K,Offer,2026-08-20,Negotiate,https://example.invalid/8,Best outcome,2026-08-05,YES,Got Referral,2026-08-10,Greenhouse
MEDIUM,Ironvale,Sales Engineer,Remote,Remote,$160K-$180K,Recruiter Call,2026-08-22,Call Thursday,https://example.invalid/9,In progress,2026-08-08,YES,Connection Pending,2026-08-13,LinkedIn Easy Apply
MEDIUM,Junipergate,Implementation Consultant,Remote,Remote,$155K-$175K,To Apply,,Apply,https://example.invalid/10,Queued,2026-08-18,NO,Not Needed,,Workable
```

- [x] **Step 6: Write `tests/conftest.py`**

```python
import csv
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_tracker_path() -> Path:
    return FIXTURE_DIR / "sample_tracker.csv"


@pytest.fixture
def sample_tracker_rows(sample_tracker_path: Path) -> list[dict[str, str]]:
    with open(sample_tracker_path, "r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
```

- [x] **Step 7: Install and verify the scaffold collects**

```bash
cd ~/nerdjoy-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --collect-only
```

Expected: exits 0, collects 0 tests, no import errors.

- [x] **Step 8: Verify the fixture has exactly 10 rows and 16 columns**

```bash
python3 -c "
import csv
rows = list(csv.DictReader(open('tests/fixtures/sample_tracker.csv')))
assert len(rows) == 10, len(rows)
assert len(rows[0]) == 16, len(rows[0])
print('fixture ok')
"
```

Expected: `fixture ok`

- [x] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore .env.example src tests
git commit -m "chore: scaffold project with test fixtures"
```

---

### Task 2: Read-only tracker reader and normalizer

Reads the tracker and normalizes the dirty values found in the live file. The read-only guarantee is enforced by a test that asserts the file's mtime and bytes are unchanged after a read.

**Files:**
- Create: `src/nerdjoy_pipeline/tracker.py`
- Test: `tests/test_tracker.py`

**Interfaces:**
- Consumes: `sample_tracker_path`, `sample_tracker_rows` fixtures (Task 1)
- Produces:
  - `VALID_STATUSES: frozenset[str]`, `VALID_PRIORITIES: frozenset[str]`, `VALID_REFERRAL_STATUSES: frozenset[str]`
  - `@dataclass(frozen=True) Application` with fields: `company: str`, `role: str`, `status: str`, `priority: str`, `referral_needed: bool`, `referral_status: str`, `apply_via: str`, `applied_date: date | None`, `discovered_date: date | None`
  - `read_tracker(path: str | Path) -> list[Application]`
  - `normalize_apply_via(raw: str) -> str`
  - `parse_date(raw: str) -> date | None`

- [x] **Step 1: Write the failing tests**

`tests/test_tracker.py`:

```python
import os
from datetime import date
from pathlib import Path

import pytest

from nerdjoy_pipeline.tracker import (
    VALID_PRIORITIES,
    VALID_REFERRAL_STATUSES,
    VALID_STATUSES,
    Application,
    normalize_apply_via,
    parse_date,
    read_tracker,
)


def test_reads_every_row(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert len(apps) == 10
    assert all(isinstance(a, Application) for a in apps)


def test_does_not_mutate_the_tracker(sample_tracker_path: Path):
    before_bytes = sample_tracker_path.read_bytes()
    before_mtime = os.stat(sample_tracker_path).st_mtime_ns
    read_tracker(sample_tracker_path)
    assert sample_tracker_path.read_bytes() == before_bytes
    assert os.stat(sample_tracker_path).st_mtime_ns == before_mtime


def test_every_status_is_canonical(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert {a.status for a in apps} <= VALID_STATUSES


def test_every_priority_is_canonical(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert {a.priority for a in apps} <= VALID_PRIORITIES


def test_dirty_referral_needed_date_becomes_false(sample_tracker_path: Path):
    # Everwake Labs has the literal string "2026-08-01" in Referral Needed.
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Everwake Labs")
    assert app.referral_needed is False


def test_dirty_referral_status_falls_back_to_not_needed(sample_tracker_path: Path):
    # Foxglove AI has the out-of-domain value "NO" in Referral Status.
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Foxglove AI")
    assert app.referral_status == "Not Needed"
    assert app.referral_status in VALID_REFERRAL_STATUSES


def test_referral_needed_yes_parses_true(sample_tracker_path: Path):
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Acme Data Co")
    assert app.referral_needed is True


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Company Site", "Company Site"),
        ("Company site", "Company Site"),
        ("Company Website", "Company Site"),
        ("Company", "Company Site"),
        ("LinkedIn Easy Apply", "LinkedIn Easy Apply"),
        ("Greenhouse", "Greenhouse"),
        ("", "Unknown"),
        ("   ", "Unknown"),
        # The live tracker embeds a real address in this column.
        ("Email (dana@northwind.invalid)", "Email"),
        ("dana@northwind.invalid", "Email"),
    ],
)
def test_normalize_apply_via(raw: str, expected: str):
    assert normalize_apply_via(raw) == expected


def test_normalize_apply_via_never_returns_an_address():
    for raw in ("Email (dana@northwind.invalid)", "someone@example.com", "Referral (a@b.co)"):
        assert "@" not in normalize_apply_via(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-08-01", date(2026, 8, 1)),
        ("", None),
        ("   ", None),
        ("not a date", None),
    ],
)
def test_parse_date(raw: str, expected):
    assert parse_date(raw) == expected


def test_applied_date_parsed(sample_tracker_path: Path):
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Acme Data Co")
    assert app.applied_date == date(2026, 8, 1)


def test_missing_applied_date_is_none(sample_tracker_path: Path):
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Cindergrid")
    assert app.applied_date is None
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tracker.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'nerdjoy_pipeline.tracker'`

- [x] **Step 3: Write the implementation**

`src/nerdjoy_pipeline/tracker.py`:

```python
"""Read-only reader for job_tracker.csv.

The tracker is the single source of truth and is NEVER mutated by this
pipeline. Every open() here uses mode "r".
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

VALID_STATUSES = frozenset(
    {
        "To Apply",
        "Applied",
        "Recruiter Call",
        "Phone Screen",
        "Onsite",
        "Offer",
        "Rejected",
        "Withdrew",
    }
)
VALID_PRIORITIES = frozenset({"HIGH", "MEDIUM", "LOW"})
VALID_REFERRAL_STATUSES = frozenset(
    {
        "Not Needed",
        "Outreach Pending",
        "Connection Pending",
        "Outreach Sent",
        "Got Referral",
        "Declined",
        "No Referral",
    }
)

# The live tracker has drifted into case and wording variants. Collapse them.
_APPLY_VIA_ALIASES = {
    "company site": "Company Site",
    "company website": "Company Site",
    "company": "Company Site",
}


@dataclass(frozen=True)
class Application:
    company: str
    role: str
    status: str
    priority: str
    referral_needed: bool
    referral_status: str
    apply_via: str
    applied_date: date | None
    discovered_date: date | None


def parse_date(raw: str) -> date | None:
    """Parse YYYY-MM-DD, returning None for blank or unparseable input."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_apply_via(raw: str) -> str:
    """Collapse variants and strip any contact details out of the label.

    Channel labels are published verbatim in metrics.json, and the live
    tracker stores "Email (dana@northwind.invalid)" here. Reduce anything holding
    an address to its bare channel name so no PII ever reaches the label.
    """
    raw = (raw or "").strip()
    if not raw:
        return "Unknown"
    if "@" in raw:
        # Keep the leading channel word, drop the address. A bare address with
        # no channel word falls back to the generic "Email".
        head = raw.split("(")[0].strip()
        raw = "Email" if (not head or "@" in head) else head
    return _APPLY_VIA_ALIASES.get(raw.lower(), raw)


def _normalize_referral_needed(raw: str) -> bool:
    """Only a literal YES counts. Stray dates in this column mean False."""
    return (raw or "").strip().upper() == "YES"


def _normalize_referral_status(raw: str) -> str:
    raw = (raw or "").strip()
    return raw if raw in VALID_REFERRAL_STATUSES else "Not Needed"


def _normalize_choice(raw: str, valid: frozenset[str], fallback: str) -> str:
    raw = (raw or "").strip()
    return raw if raw in valid else fallback


def read_tracker(path: str | Path) -> list[Application]:
    """Read the tracker into normalized Application records. Never writes."""
    with open(path, "r", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    return [
        Application(
            company=(r.get("Company") or "").strip(),
            role=(r.get("Role") or "").strip(),
            status=_normalize_choice(r.get("Status", ""), VALID_STATUSES, "To Apply"),
            priority=_normalize_choice(r.get("Priority", ""), VALID_PRIORITIES, "LOW"),
            referral_needed=_normalize_referral_needed(r.get("Referral Needed", "")),
            referral_status=_normalize_referral_status(r.get("Referral Status", "")),
            apply_via=normalize_apply_via(r.get("Apply Via", "")),
            applied_date=parse_date(r.get("Applied Date", "")),
            discovered_date=parse_date(r.get("Discovered Date", "")),
        )
        for r in rows
    ]
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_tracker.py -v`
Expected: 24 passed

- [x] **Step 5: Verify against the real tracker (read-only smoke check)**

```bash
python3 -c "
from nerdjoy_pipeline.tracker import read_tracker, VALID_STATUSES
apps = read_tracker('/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv')
print('rows:', len(apps))
assert len(apps) == 467, len(apps)
assert {a.status for a in apps} <= VALID_STATUSES
print('normalized statuses:', sorted({a.status for a in apps}))
print('real tracker ok')
"
```

Expected: `rows: 467`, then `real tracker ok`

- [x] **Step 6: Commit**

```bash
git add src/nerdjoy_pipeline/tracker.py tests/test_tracker.py
git commit -m "feat: add tracker reader with normalization"
```

---

### Task 3: Anonymization and em-dash guard

The single safety gate. Both the metrics export (Task 5) and the dashboard build (Task 9) call it. It fails loudly; it never sanitizes silently, because a silent rewrite would hide a leak.

**Files:**
- Create: `src/nerdjoy_pipeline/guard.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `read_tracker` (Task 2)
- Produces:
  - `class GuardViolation(Exception)`
  - `build_denylist(tracker_path: str | Path) -> set[str]`
  - `check_no_em_dashes(text: str, *, label: str = "content") -> None`
  - `check_no_denylisted_terms(text: str, denylist: set[str], *, label: str = "content") -> None`
  - `check_no_contact_details(text: str, *, label: str = "content") -> None`
  - `guard_text(text: str, denylist: set[str], *, label: str = "content") -> None`

**Why the contact-details check exists:** the deny-list is built from the `Company` column, so it cannot catch PII hiding in other columns. The live tracker has a real email address sitting inside `Apply Via` (`Email (dana@northwind.invalid)`), and `channel_counts` surfaces `Apply Via` values straight into `metrics.json`. A deny-list alone would ship that address. This check is pattern-based rather than value-based, so it catches emails and phone numbers the tracker has not seen yet.

- [x] **Step 1: Write the failing tests**

`tests/test_guard.py`:

```python
from pathlib import Path

import pytest

from nerdjoy_pipeline.guard import (
    GuardViolation,
    build_denylist,
    check_no_contact_details,
    check_no_denylisted_terms,
    check_no_em_dashes,
    guard_text,
)


def test_denylist_includes_every_company(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    assert "acme data co" in denylist
    assert "hollowpine" in denylist


def test_denylist_excludes_short_generic_tokens(sample_tracker_path: Path):
    # Two-character and shorter tokens would false-positive on ordinary prose.
    denylist = build_denylist(sample_tracker_path)
    assert all(len(term) > 2 for term in denylist)


def test_em_dash_raises():
    with pytest.raises(GuardViolation, match="em-dash"):
        check_no_em_dashes("This is the pipeline — it works.")


def test_clean_text_passes_em_dash_check():
    check_no_em_dashes("This is the pipeline. It works.")


def test_hyphen_and_en_dash_are_allowed():
    # Only U+2014 is banned. Hyphens and en-dashes are ordinary punctuation.
    check_no_em_dashes("well-wired stack, 2026-09-20, pages 3–5")


def test_denylisted_company_raises(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation, match="Hollowpine"):
        check_no_denylisted_terms("We interviewed at Hollowpine last week.", denylist)


def test_denylist_match_is_case_insensitive(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation):
        check_no_denylisted_terms("we interviewed at HOLLOWPINE", denylist)


def test_denylist_match_respects_word_boundaries(sample_tracker_path: Path):
    # "Merge" style substrings must not fire inside unrelated words.
    denylist = {"merge"}
    check_no_denylisted_terms("The models were merged and remerged.", denylist)


def test_generic_corporate_words_are_not_denylisted(sample_tracker_path: Path):
    # Company names contain ordinary English. If "data", "company" and "solutions"
    # land on the deny list, the README of a GTM DATA stack cannot be written.
    denylist = build_denylist(sample_tracker_path)
    for word in ("data", "company", "solutions", "software", "group", "cloud"):
        assert word not in denylist


def test_generic_words_pass_the_guard_in_prose(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    check_no_denylisted_terms(
        "A modern data stack: ingestion, a cloud warehouse, and analytics. "
        "No company names appear anywhere in this repo.",
        denylist,
    )


def test_full_company_name_still_blocked_despite_generic_word(tmp_path: Path):
    # Dropping the token "data" must NOT unprotect "Northwind Data" itself.
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "Priority,Company,Role,Location,Type,Salary,Status,Applied Date,Next Action,"
        "URL,Notes,Discovered Date,Referral Needed,Referral Status,Referral Deadline,"
        "Apply Via\n"
        "HIGH,Northwind Data,Analyst,Remote,Full-time,,Applied,2026-09-01,,http://x,,"
        "2026-09-01,NO,Not Needed,,Greenhouse\n",
        encoding="utf-8",
    )
    denylist = build_denylist(csv_path)
    assert "data" not in denylist
    assert "simon" in denylist
    with pytest.raises(GuardViolation):
        check_no_denylisted_terms("We spoke with Northwind Data.", denylist)


def test_gtm_vocabulary_allowed_but_company_still_protected():
    # "Outreach" and "Revenue.io" are real companies in the tracker AND ordinary
    # GTM words. They stay on the deny list and are separated by context only.
    denylist = {"outreach", "revenue", "revenue.io"}
    check_no_denylisted_terms(
        "The control plane drafts outreach for me. "
        "GTM Engineers wire up the revenue stack.",
        denylist,
    )
    with pytest.raises(GuardViolation):
        check_no_denylisted_terms("Outreach rejected my application.", denylist)


def test_vendor_name_allowed_as_stack_tooling():
    # Hightouch, Fivetran, Airbyte and Greenhouse are companies in the tracker AND
    # tools on the public diagram. The honesty principle requires naming them.
    denylist = {"hightouch", "fivetran", "airbyte"}
    check_no_denylisted_terms(
        "Fivetran lands Postgres into BigQuery. Hightouch syncs the mart to "
        "HubSpot and a Google Sheet. Airbyte is the documented fallback.",
        denylist,
    )


def test_vendor_name_still_blocked_in_application_context():
    # The carve-out must not become a hole. A status word in the same sentence
    # turns a tool mention back into a disclosure about a real application.
    denylist = {"fivetran"}
    with pytest.raises(GuardViolation, match="fivetran"):
        check_no_denylisted_terms(
            "Applied to Fivetran for a Senior Solutions Architect role.", denylist
        )


def test_vendor_carveout_is_per_sentence():
    # A clean tooling sentence must not launder a leak elsewhere in the text.
    denylist = {"hightouch"}
    with pytest.raises(GuardViolation, match="hightouch"):
        check_no_denylisted_terms(
            "Hightouch syncs the mart to HubSpot.\nHightouch rejected me in August.",
            denylist,
        )


def test_non_vendor_company_has_no_carveout():
    # Only the four stack vendors are exempt. Every other tracker name is
    # rejected even in a sentence with no application words at all.
    denylist = {"hollowpine"}
    with pytest.raises(GuardViolation, match="hollowpine"):
        check_no_denylisted_terms("Hollowpine builds data tooling.", denylist)


def test_anonymized_aggregate_text_passes(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    clean = "467 applications, 124 needing referrals. Series C, ~250 employees, martech."
    guard_text(clean, denylist)


def test_guard_text_reports_the_label(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation, match="metrics.json"):
        guard_text("Acme Data Co", denylist, label="metrics.json")


def test_email_address_raises():
    # The live tracker stores "Email (dana@northwind.invalid)" in Apply Via, and
    # Apply Via values reach metrics.json through channel_counts.
    with pytest.raises(GuardViolation, match="email"):
        check_no_contact_details("Email (dana@northwind.invalid)")


def test_bare_email_raises():
    with pytest.raises(GuardViolation, match="email"):
        check_no_contact_details("reach me at someone@example.com")


def test_phone_number_raises():
    with pytest.raises(GuardViolation, match="phone"):
        check_no_contact_details("call 415-555-0142")


def test_aggregate_text_has_no_contact_details():
    check_no_contact_details("467 applications across 379 companies, 1.6% conversion")


def test_dates_and_versions_are_not_phone_numbers():
    # Guards against a naive digit-run regex firing on ordinary content.
    check_no_contact_details("2026-09-20, version 1.8.2, 100-250 employees")


def test_guard_text_runs_the_contact_check(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation, match="email"):
        guard_text("Email (dana@northwind.invalid)", denylist, label="metrics.json")
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_guard.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'nerdjoy_pipeline.guard'`

- [x] **Step 3: Write the implementation**

`src/nerdjoy_pipeline/guard.py`:

```python
"""Safety gate for every outgoing artifact.

Three independent checks:
  1. No em-dash (U+2014) anywhere in outgoing copy.
  2. No real company or contact name from the tracker.
  3. No email address or phone number, whatever their source.

Check 3 exists because the deny list is built from the Company column and
therefore cannot see PII in other columns. The live tracker has a real
email inside Apply Via, and Apply Via reaches metrics.json.

The guard raises. It never silently rewrites, because a silent rewrite
would hide a leak instead of surfacing it.
"""
from __future__ import annotations

import re
from pathlib import Path

from nerdjoy_pipeline.tracker import read_tracker

EM_DASH = "—"

# Tokens this short would false-positive against ordinary prose.
_MIN_TERM_LENGTH = 3

# Corporate filler that appears INSIDE company names but is ordinary English on
# its own. Splitting "Northwind Data" or "GTX Solutions (a CourtAvenue Company)" into
# words otherwise puts "data", "solutions" and "company" on the deny list, and a
# GTM data-stack README cannot be written without them. The full multi-word name
# stays on the deny list, so the real company is still blocked; only the useless
# fragment is dropped.
_GENERIC_NAME_TOKENS = frozenset({
    "company", "companies", "software", "data", "group", "labs", "lab",
    "technologies", "technology", "systems", "system", "solutions", "solution",
    "health", "global", "partners", "digital", "services", "service", "network",
    "cloud", "security", "capital", "ventures", "studio", "works", "tech",
    "corp", "corporation", "holdings", "industries", "international", "media",
    "consulting", "analytics", "platform", "platforms", "science", "sciences",
    "search", "talent", "team", "world", "first", "next", "open", "core",
    "smart", "prime", "united", "american", "national", "associates", "agency",
    "studios", "enterprises", "ventures", "advisors", "brands", "collective",
    "engineering", "flow",
    # Fragments of multi-word tracker names that are also ordinary words the
    # public artifacts need. The full name stays on the deny list in every case:
    # "Ironvale Analytics", "Borealis Systems", "Grayharbor Code", "Junipergate List",
    # "Cindergrid Digital", "Everwake Privacy", "Ironvale Recruiting", "Revenue.io".
    "analytics", "aria", "code", "list", "main", "privacy", "search", "revenue",
})

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Three groups of 3-3-4 with a separator. Anchored on a non-digit boundary so
# an ISO date (2026-09-20) or a range (100-250) does not match.
_PHONE_RE = re.compile(r"(?<!\d)\d{3}[.\-\s]\d{3}[.\-\s]\d{4}(?!\d)")

# Companies in the tracker that are also tools in this stack. These stay ON the
# deny list; they are merely permitted outside application context. Keep this set
# tiny and explicit. Adding a name here unprotects a real application, so a new
# entry needs the same justification the original four had: the tool is wired and
# named on the public diagram.
VENDOR_TOOL_NAMES = frozenset({
    # Tools on the public diagram that are also companies in the tracker.
    "hightouch", "fivetran", "airbyte", "greenhouse", "greenhouse software",
    # Whole company names that are also ordinary GTM vocabulary. These cannot go
    # on the generic stop list: the company IS the word, so dropping the term
    # would unprotect a real application. Context is the only safe separator.
    "outreach", "revenue", "revenue.io",
})

# Words that make a sentence about an application rather than about tooling.
_APPLICATION_CONTEXT_RE = re.compile(
    r"\b(applied|applying|application|rejected|rejection|withdrew|withdrawn|"
    r"offer|interview|interviewing|recruiter|phone screen|onsite|referral|"
    r"resume|hiring manager|role|position|opening|req|candidate|"
    r"to apply|status)\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


class GuardViolation(Exception):
    """Raised when outgoing content fails an anonymization or copy rule."""


def build_denylist(tracker_path: str | Path) -> set[str]:
    """Collect every real company name from the tracker, lowercased.

    Includes both the full name and its individually distinctive words so a
    partial mention ("Hollowpine" out of "Hollowpine Systems") still trips.
    Generic corporate filler is excluded as a WORD only: the full name it came
    from stays on the list, so "Northwind Data" is still blocked while the bare word
    "data" stays usable in ordinary prose.
    """
    terms: set[str] = set()
    for app in read_tracker(tracker_path):
        name = app.company.strip()
        if len(name) < _MIN_TERM_LENGTH:
            continue
        terms.add(name.lower())
        for word in re.split(r"[^\w]+", name):
            lowered = word.lower()
            if len(word) > _MIN_TERM_LENGTH and lowered not in _GENERIC_NAME_TOKENS:
                terms.add(lowered)
    return {t for t in terms if len(t) > _MIN_TERM_LENGTH - 1}


def check_no_em_dashes(text: str, *, label: str = "content") -> None:
    if EM_DASH in text:
        index = text.index(EM_DASH)
        excerpt = text[max(0, index - 40) : index + 40]
        raise GuardViolation(
            f"{label} contains an em-dash (U+2014). Rewrite it. Near: ...{excerpt}..."
        )


def check_no_denylisted_terms(
    text: str, denylist: set[str], *, label: str = "content"
) -> None:
    """Reject tracker names, judged one sentence at a time.

    Four companies in the tracker share a name with a tool in this stack
    (Hightouch, Fivetran, Airbyte, Greenhouse). The honesty principle requires
    naming every tool that is genuinely wired, so a blanket ban on those strings
    would make the README unwritable. Dropping them from the deny list instead
    would silently unprotect four live applications, including one rejection.

    So the carve-out is by CONTEXT, not by name: a vendor name is allowed only in
    a sentence that says nothing about an application. The moment a status, role,
    date or outreach word shares the sentence, it is a leak again. Every other
    denylisted term is rejected unconditionally.
    """
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        haystack = sentence.lower()
        for term in sorted(denylist, key=len, reverse=True):
            if not re.search(rf"\b{re.escape(term)}\b", haystack):
                continue
            if term in VENDOR_TOOL_NAMES and not _APPLICATION_CONTEXT_RE.search(sentence):
                continue
            raise GuardViolation(
                f"{label} contains the denylisted term {term!r} in application "
                f"context. Near: ...{sentence.strip()[:80]}... "
                "Public artifacts must use aggregates and generalized descriptors only."
            )


def check_no_contact_details(text: str, *, label: str = "content") -> None:
    """Reject emails and phone numbers by pattern, not by value.

    The deny list only knows names the tracker has already seen. This catches
    contact details wherever they hide, including columns the deny list never
    reads.
    """
    match = _EMAIL_RE.search(text)
    if match:
        raise GuardViolation(
            f"{label} contains an email address ({match.group()!r}). "
            "Public artifacts carry aggregates only."
        )

    match = _PHONE_RE.search(text)
    if match:
        raise GuardViolation(
            f"{label} contains a phone number ({match.group()!r}). "
            "Public artifacts carry aggregates only."
        )


def guard_text(text: str, denylist: set[str], *, label: str = "content") -> None:
    """Run every outgoing-copy check. Raises GuardViolation on the first failure."""
    check_no_em_dashes(text, label=label)
    check_no_contact_details(text, label=label)
    check_no_denylisted_terms(text, denylist, label=label)
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_guard.py -v`
Expected: 24 passed

- [x] **Step 5: Verify the guard catches a real tracker name and the real embedded email**

```bash
python3 -c "
from nerdjoy_pipeline.guard import build_denylist, guard_text, GuardViolation
dl = build_denylist('/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv')
print('denylist terms:', len(dl))

for probe, why in [
    ('We spoke with Northwind Data about the role.', 'company name'),
    ('Email (dana@northwind.invalid)', 'embedded email'),
]:
    try:
        guard_text(probe, dl, label='smoke')
        raise SystemExit(f'FAIL: guard did not fire on {why}')
    except GuardViolation:
        print(f'guard fired correctly on {why}')

guard_text('467 applications across 379 companies.', dl, label='smoke')
print('clean aggregate text passes')
"
```

Expected: a term count, `guard fired correctly on company name`, `guard fired correctly on embedded email`, then `clean aggregate text passes`.

The second probe is the exact string sitting in the live tracker's `Apply Via` column. If it does not fire, the email regex is wrong and `metrics.json` will leak a real address.

- [x] **Step 6: Commit**

```bash
git add src/nerdjoy_pipeline/guard.py tests/test_guard.py
git commit -m "feat: add anonymization and em-dash guard"
```

---

### Task 4: Metrics aggregation

Pure functions over `list[Application]`. No filesystem, no network, so the aggregation logic is testable in isolation and the numbers can be reconciled by hand.

**Files:**
- Create: `src/nerdjoy_pipeline/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `Application`, `read_tracker` (Task 2)
- Produces:
  - `funnel_counts(apps: list[Application]) -> dict[str, int]` (every canonical status present, zero-filled, in funnel order)
  - `referral_metrics(apps: list[Application]) -> dict[str, int | float]` with keys `needed`, `outreach_sent`, `got_referral`, `conversion_pct`
  - `channel_counts(apps: list[Application]) -> dict[str, int]` (descending by count)
  - `activity_timeseries(apps: list[Application]) -> list[dict[str, str | int]]` (entries `{"month": "YYYY-MM", "applied": int}`, ascending)
  - `summary(apps: list[Application]) -> dict` (the full anonymized payload, no company names)
  - `FUNNEL_ORDER: tuple[str, ...]`

- [x] **Step 1: Write the failing tests**

`tests/test_metrics.py`:

```python
from pathlib import Path

from nerdjoy_pipeline.metrics import (
    FUNNEL_ORDER,
    activity_timeseries,
    channel_counts,
    funnel_counts,
    referral_metrics,
    summary,
)
from nerdjoy_pipeline.tracker import read_tracker


def _apps(path: Path):
    return read_tracker(path)


def test_funnel_counts_match_the_fixture(sample_tracker_path: Path):
    counts = funnel_counts(_apps(sample_tracker_path))
    assert counts["To Apply"] == 2
    assert counts["Applied"] == 3
    assert counts["Recruiter Call"] == 1
    assert counts["Phone Screen"] == 1
    assert counts["Offer"] == 1
    assert counts["Rejected"] == 1
    assert counts["Withdrew"] == 1


def test_funnel_counts_include_every_status_zero_filled(sample_tracker_path: Path):
    counts = funnel_counts(_apps(sample_tracker_path))
    assert set(counts) == set(FUNNEL_ORDER)
    assert counts["Onsite"] == 0


def test_funnel_counts_are_in_funnel_order(sample_tracker_path: Path):
    counts = funnel_counts(_apps(sample_tracker_path))
    assert tuple(counts) == FUNNEL_ORDER


def test_funnel_total_reconciles_with_row_count(sample_tracker_path: Path):
    apps = _apps(sample_tracker_path)
    assert sum(funnel_counts(apps).values()) == len(apps)


def test_referral_metrics(sample_tracker_path: Path):
    m = referral_metrics(_apps(sample_tracker_path))
    # Acme, Borealis, Hollowpine, Ironvale carry a literal YES.
    assert m["needed"] == 4
    assert m["outreach_sent"] == 1
    assert m["got_referral"] == 2
    assert m["conversion_pct"] == 50.0


def test_referral_conversion_is_zero_when_none_needed():
    assert referral_metrics([])["conversion_pct"] == 0.0


def test_channel_counts_collapse_case_variants(sample_tracker_path: Path):
    counts = channel_counts(_apps(sample_tracker_path))
    # Company Site + Company site + Company Website all collapse to one key.
    assert counts["Company Site"] == 3


def test_channel_counts_are_descending(sample_tracker_path: Path):
    values = list(channel_counts(_apps(sample_tracker_path)).values())
    assert values == sorted(values, reverse=True)


def test_channel_labels_never_carry_contact_details():
    # The live tracker has "Email (dana@northwind.invalid)" in Apply Via, and channel
    # labels are published verbatim in metrics.json. Bucket anything with an
    # address in it rather than letting the guard fail the whole build.
    from nerdjoy_pipeline.tracker import Application

    apps = [
        Application(
            company="Acme Data Co",
            role="Analytics Engineer",
            status="Applied",
            priority="HIGH",
            referral_needed=False,
            referral_status="Not Needed",
            apply_via="Email (dana@northwind.invalid)",
            applied_date=None,
            discovered_date=None,
        )
    ]
    counts = channel_counts(apps)
    assert counts == {"Email": 1}
    assert "@" not in "".join(counts)


def test_activity_timeseries_is_ascending_by_month(sample_tracker_path: Path):
    series = activity_timeseries(_apps(sample_tracker_path))
    months = [e["month"] for e in series]
    assert months == sorted(months)
    assert all(len(str(m)) == 7 for m in months)


def test_activity_timeseries_counts_only_applied_dates(sample_tracker_path: Path):
    series = activity_timeseries(_apps(sample_tracker_path))
    # 8 of 10 fixture rows carry an Applied Date.
    assert sum(int(e["applied"]) for e in series) == 8


def test_summary_has_no_company_names(sample_tracker_path: Path):
    import json

    payload = json.dumps(summary(_apps(sample_tracker_path)))
    for name in ("Acme", "Hollowpine", "Borealis", "Foxglove"):
        assert name.lower() not in payload.lower()


def test_summary_reports_totals(sample_tracker_path: Path):
    s = summary(_apps(sample_tracker_path))
    assert s["totals"]["applications"] == 10
    assert s["totals"]["companies"] == 10
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_metrics.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'nerdjoy_pipeline.metrics'`

- [x] **Step 3: Write the implementation**

`src/nerdjoy_pipeline/metrics.py`:

```python
"""Aggregate a list of Applications into anonymized public metrics.

Pure functions only: no filesystem, no network. Output contains counts,
rates, and time buckets. It never contains a company or person name.
"""
from __future__ import annotations

from collections import Counter

from nerdjoy_pipeline.tracker import Application, normalize_apply_via

FUNNEL_ORDER: tuple[str, ...] = (
    "To Apply",
    "Applied",
    "Recruiter Call",
    "Phone Screen",
    "Onsite",
    "Offer",
    "Rejected",
    "Withdrew",
)


def funnel_counts(apps: list[Application]) -> dict[str, int]:
    """Count applications per status, zero-filled and in funnel order."""
    counts = Counter(a.status for a in apps)
    return {status: counts.get(status, 0) for status in FUNNEL_ORDER}


def referral_metrics(apps: list[Application]) -> dict[str, int | float]:
    needed = [a for a in apps if a.referral_needed]
    outreach_sent = sum(1 for a in needed if a.referral_status == "Outreach Sent")
    got_referral = sum(1 for a in needed if a.referral_status == "Got Referral")
    conversion = round(got_referral / len(needed) * 100, 1) if needed else 0.0
    return {
        "needed": len(needed),
        "outreach_sent": outreach_sent,
        "got_referral": got_referral,
        "conversion_pct": conversion,
    }


def channel_counts(apps: list[Application]) -> dict[str, int]:
    """Applications per normalized apply channel, descending by count."""
    counts = Counter(normalize_apply_via(a.apply_via) for a in apps)
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def activity_timeseries(apps: list[Application]) -> list[dict[str, str | int]]:
    """Applications submitted per calendar month, ascending."""
    counts = Counter(
        a.applied_date.strftime("%Y-%m") for a in apps if a.applied_date is not None
    )
    return [{"month": m, "applied": counts[m]} for m in sorted(counts)]


def summary(apps: list[Application]) -> dict:
    """The full anonymized payload that becomes metrics.json."""
    return {
        "totals": {
            "applications": len(apps),
            "companies": len({a.company for a in apps if a.company}),
        },
        "funnel": funnel_counts(apps),
        "referrals": referral_metrics(apps),
        "channels": channel_counts(apps),
        "activity": activity_timeseries(apps),
    }
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_metrics.py -v`
Expected: 13 passed

- [x] **Step 5: Reconcile the real tracker numbers by hand**

```bash
python3 -c "
from nerdjoy_pipeline.tracker import read_tracker
from nerdjoy_pipeline.metrics import summary
s = summary(read_tracker('/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv'))
print('applications:', s['totals']['applications'])
print('companies:', s['totals']['companies'])
print('funnel:', s['funnel'])
print('referrals:', s['referrals'])
assert s['totals']['applications'] == 467
assert s['totals']['companies'] == 379
assert sum(s['funnel'].values()) == 467
print('reconciles')
"
```

Expected: `Applied` 238, `To Apply` 199, `companies` 379, then `reconciles`

- [x] **Step 6: Commit**

```bash
git add src/nerdjoy_pipeline/metrics.py tests/test_metrics.py
git commit -m "feat: add anonymized metrics aggregation"
```

---

### Task 5: Metrics export CLI

Wires tracker + metrics + guard into `metrics.json`. This is the tracker-fallback path from spec §8.7; Task 12 adds the BigQuery source behind the same output contract.

**Files:**
- Create: `src/nerdjoy_pipeline/metrics_extract.py`
- Test: `tests/test_metrics_extract.py`

**Interfaces:**
- Consumes: `read_tracker` (Task 2), `build_denylist`/`guard_text`/`GuardViolation` (Task 3), `summary` (Task 4)
- Produces:
  - `export_metrics(tracker_path: str | Path, output_path: str | Path) -> dict` (writes the file, returns the payload)
  - `main(argv: list[str] | None = None) -> int` (CLI entry, `0` on success, `1` on guard violation)

- [x] **Step 1: Write the failing tests**

`tests/test_metrics_extract.py`:

```python
import json
from pathlib import Path

import pytest

from nerdjoy_pipeline.guard import GuardViolation
from nerdjoy_pipeline.metrics_extract import export_metrics, main


def test_writes_valid_json(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    export_metrics(sample_tracker_path, out)
    payload = json.loads(out.read_text())
    assert payload["totals"]["applications"] == 10


def test_output_has_required_top_level_keys(sample_tracker_path: Path, tmp_path: Path):
    payload = export_metrics(sample_tracker_path, tmp_path / "m.json")
    assert set(payload) == {"generated_at", "totals", "funnel", "referrals", "channels", "activity"}


def test_generated_at_is_iso_date(sample_tracker_path: Path, tmp_path: Path):
    from datetime import date

    payload = export_metrics(sample_tracker_path, tmp_path / "m.json")
    date.fromisoformat(payload["generated_at"])  # raises if malformed


def test_output_contains_no_company_names(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    export_metrics(sample_tracker_path, out)
    text = out.read_text().lower()
    for name in ("acme", "hollowpine", "borealis", "foxglove", "junipergate"):
        assert name not in text


def test_output_contains_no_em_dash(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    export_metrics(sample_tracker_path, out)
    assert "—" not in out.read_text()


def test_guard_violation_prevents_writing_the_file(
    sample_tracker_path: Path, tmp_path: Path, monkeypatch
):
    out = tmp_path / "metrics.json"

    def leaky_summary(_apps):
        return {"totals": {"applications": 1, "companies": 1}, "leak": "Hollowpine"}

    monkeypatch.setattr("nerdjoy_pipeline.metrics_extract.summary", leaky_summary)
    with pytest.raises(GuardViolation):
        export_metrics(sample_tracker_path, out)
    assert not out.exists()


def test_does_not_mutate_the_tracker(sample_tracker_path: Path, tmp_path: Path):
    before = sample_tracker_path.read_bytes()
    export_metrics(sample_tracker_path, tmp_path / "m.json")
    assert sample_tracker_path.read_bytes() == before


def test_main_returns_zero_on_success(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    code = main(["--tracker", str(sample_tracker_path), "--output", str(out)])
    assert code == 0
    assert out.exists()


def test_main_returns_one_on_guard_violation(
    sample_tracker_path: Path, tmp_path: Path, monkeypatch
):
    def leaky_summary(_apps):
        return {"totals": {"applications": 1, "companies": 1}, "leak": "Hollowpine"}

    monkeypatch.setattr("nerdjoy_pipeline.metrics_extract.summary", leaky_summary)
    code = main(["--tracker", str(sample_tracker_path), "--output", str(tmp_path / "m.json")])
    assert code == 1
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_metrics_extract.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'nerdjoy_pipeline.metrics_extract'`

- [x] **Step 3: Write the implementation**

`src/nerdjoy_pipeline/metrics_extract.py`:

```python
"""Export anonymized metrics.json from the tracker.

The guard runs against the serialized payload BEFORE anything is written,
so a violation can never leave a leaked file on disk.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from nerdjoy_pipeline.guard import GuardViolation, build_denylist, guard_text
from nerdjoy_pipeline.metrics import summary
from nerdjoy_pipeline.tracker import read_tracker

DEFAULT_TRACKER = os.environ.get(
    "TRACKER_PATH", "/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv"
)
DEFAULT_OUTPUT = "metrics.json"


def export_metrics(tracker_path: str | Path, output_path: str | Path) -> dict:
    apps = read_tracker(tracker_path)
    payload = {"generated_at": date.today().isoformat(), **summary(apps)}

    serialized = json.dumps(payload, indent=2, sort_keys=False)
    denylist = build_denylist(tracker_path)
    guard_text(serialized, denylist, label="metrics.json")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export anonymized metrics.json")
    parser.add_argument("--tracker", default=DEFAULT_TRACKER)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    try:
        payload = export_metrics(args.tracker, args.output)
    except GuardViolation as exc:
        print(f"GUARD FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote {args.output}: "
        f"{payload['totals']['applications']} applications, "
        f"{payload['totals']['companies']} companies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_metrics_extract.py -v`
Expected: 9 passed

- [ ] **Step 5: Generate the real `metrics.json` and inspect it** BLOCKED - see note below

```bash
python3 -m nerdjoy_pipeline.metrics_extract --output metrics.json
cat metrics.json
grep -c "$(printf '—')" metrics.json || echo "no em-dashes"
```

Expected: `Wrote metrics.json: 466 applications, 378 companies`, a payload of pure numbers, `no em-dashes`. Confirm `metrics.json` is gitignored.

- [x] **Step 6: Run the whole suite**

Run: `pytest -v`
Expected: 70 passed

> **RESOLVED (2026-09-20).** Step 5 initially failed the guard. Three separate
> name collisions were found and fixed, none by weakening the deny list:
>
> 1. **Agency channels leaked real companies.** `Northwind Staffing`, `Hollowpine Talent`,
>    `Grayharbor Seven`, `Delta Loop Talent`, `Foxglove Creative`, `Ironvale Recruiting` are staffing
>    agencies that are both channels and employers. Heather chose bucketing:
>    `generalize_channel()` in `metrics.py` collapses them to `Staffing Agency`
>    (26 apps), preserving the funnel total.
> 2. **`apply` collided with the funnel label `"To Apply"`**, because the tracker
>    contains the company `Apply Digital`. Heather chose to remove that company
>    from the pipeline entirely. `EXCLUDED_COMPANIES` in `tracker.py` drops it on
>    read, so it reaches no downstream consumer. `job_tracker.csv` is NOT
>    modified: its SHA-256 is unchanged. Consequence, accepted by Heather:
>    totals drop 467 -> 466 apps, 379 -> 378 companies, and Offer 1 -> 0.
> 3. **`linkedin` and `staffing` collided** via `Undisclosed (LinkedIn partner)`
>    and `Coda Search (Staffing)`. A parenthetical is a descriptor, not identity,
>    so `build_denylist` no longer indexes qualifier words. Full names stay
>    blocked; `coda` still trips.
>
> Audited the generated `metrics.json` independently of the guard: zero company
> names, zero emails, zero URLs, zero em-dashes, funnel and channels each summing
> to 466. The single `greenhouse` hit is the deliberate `VENDOR_TOOL_NAMES`
> carve-out; `Greenhouse Software` the employer is still blocked in both
> directions. Suite: 75 passed.

- [x] **Step 7: Commit**

```bash
git add src/nerdjoy_pipeline/metrics_extract.py tests/test_metrics_extract.py
git commit -m "feat: add guarded metrics export CLI"
```

---

### Task 6: Tracker to Postgres loader

Idempotent upsert into cloud Postgres (Neon). Fivetran is a cloud service and cannot reach localhost, so the host must be cloud-reachable (spec §8.1). Tests use a fake connection, so no live database is needed to go green.

**Files:**
- Create: `src/nerdjoy_pipeline/pg_loader.py`
- Test: `tests/test_pg_loader.py`

**Interfaces:**
- Consumes: `Application`, `read_tracker` (Task 2)
- Produces:
  - `CREATE_TABLE_SQL: str`
  - `UPSERT_SQL: str`
  - `application_key(app: Application) -> str` (stable SHA-256 hex of company + role)
  - `to_row(app: Application) -> tuple` (matching `UPSERT_SQL` placeholders)
  - `load_applications(apps: list[Application], conn) -> int` (returns rows upserted)
  - `main(argv: list[str] | None = None) -> int`

- [x] **Step 1: Write the failing tests**

`tests/test_pg_loader.py`:

```python
from pathlib import Path

from nerdjoy_pipeline.pg_loader import (
    CREATE_TABLE_SQL,
    UPSERT_SQL,
    application_key,
    load_applications,
    to_row,
)
from nerdjoy_pipeline.tracker import read_tracker


class FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def executemany(self, sql, seq):
        for params in seq:
            self.executed.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def test_application_key_is_stable(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert application_key(apps[0]) == application_key(apps[0])
    assert len(application_key(apps[0])) == 64


def test_application_key_differs_per_application(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert len({application_key(a) for a in apps}) == len(apps)


def test_to_row_matches_upsert_placeholder_count(sample_tracker_path: Path):
    app = read_tracker(sample_tracker_path)[0]
    assert len(to_row(app)) == UPSERT_SQL.count("%s")


def test_upsert_is_idempotent_by_key():
    assert "ON CONFLICT (application_key) DO UPDATE" in UPSERT_SQL


def test_create_table_declares_the_conflict_target():
    assert "application_key" in CREATE_TABLE_SQL
    assert "PRIMARY KEY" in CREATE_TABLE_SQL.upper()


def test_load_creates_the_table_then_upserts_every_row(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    conn = FakeConn()
    count = load_applications(apps, conn)
    assert count == 10
    statements = [sql for sql, _ in conn.cursor_obj.executed]
    assert statements[0] == CREATE_TABLE_SQL
    assert statements.count(UPSERT_SQL) == 10
    assert conn.commits == 1


def test_load_does_not_mutate_the_tracker(sample_tracker_path: Path):
    before = sample_tracker_path.read_bytes()
    load_applications(read_tracker(sample_tracker_path), FakeConn())
    assert sample_tracker_path.read_bytes() == before


def test_running_load_twice_produces_the_same_rows(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    first = [to_row(a) for a in apps]
    second = [to_row(a) for a in read_tracker(sample_tracker_path)]
    assert first == second
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pg_loader.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'nerdjoy_pipeline.pg_loader'`

- [x] **Step 3: Write the implementation**

`src/nerdjoy_pipeline/pg_loader.py`:

```python
"""Load the tracker into cloud Postgres as a Fivetran source.

Postgres MUST be cloud-reachable (Neon or Supabase free tier). Fivetran is
a hosted service and cannot reach localhost. Reads of the tracker are
read-only; Postgres holds a copy, never the original.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

from nerdjoy_pipeline.tracker import Application, read_tracker

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    application_key TEXT PRIMARY KEY,
    company         TEXT NOT NULL,
    role            TEXT NOT NULL,
    status          TEXT NOT NULL,
    priority        TEXT NOT NULL,
    referral_needed BOOLEAN NOT NULL,
    referral_status TEXT NOT NULL,
    apply_via       TEXT NOT NULL,
    applied_date    DATE,
    discovered_date DATE,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

UPSERT_SQL = """
INSERT INTO applications (
    application_key, company, role, status, priority,
    referral_needed, referral_status, apply_via, applied_date, discovered_date
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (application_key) DO UPDATE SET
    status          = EXCLUDED.status,
    priority        = EXCLUDED.priority,
    referral_needed = EXCLUDED.referral_needed,
    referral_status = EXCLUDED.referral_status,
    apply_via       = EXCLUDED.apply_via,
    applied_date    = EXCLUDED.applied_date,
    discovered_date = EXCLUDED.discovered_date,
    loaded_at       = now()
"""


def application_key(app: Application) -> str:
    """Stable identity for an application: company plus role."""
    raw = f"{app.company.strip().lower()}|{app.role.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def to_row(app: Application) -> tuple:
    return (
        application_key(app),
        app.company,
        app.role,
        app.status,
        app.priority,
        app.referral_needed,
        app.referral_status,
        app.apply_via,
        app.applied_date,
        app.discovered_date,
    )


def load_applications(apps: list[Application], conn) -> int:
    """Create the table if needed and upsert every application. Idempotent."""
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.executemany(UPSERT_SQL, [to_row(a) for a in apps])
    conn.commit()
    return len(apps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the tracker into Postgres")
    parser.add_argument(
        "--tracker",
        default=os.environ.get(
            "TRACKER_PATH", "/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv"
        ),
    )
    args = parser.parse_args(argv)

    dsn = os.environ.get("PG_CONNECTION_STRING")
    if not dsn:
        print(
            "PG_CONNECTION_STRING is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1

    import psycopg  # imported here so the tests never need the driver

    apps = read_tracker(args.tracker)
    with psycopg.connect(dsn) as conn:
        count = load_applications(apps, conn)
    print(f"Upserted {count} applications into Postgres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pg_loader.py -v`
Expected: 8 passed

- [x] **Step 5: HUMAN STEP — Heather provisions Neon and runs the loader**

Write these instructions into `docs/runbook.md` (create the file if it does not exist). **Claude does not perform this step.**

> 1. Sign up at neon.tech (free tier) and create a project named `nerdjoy-pipeline`.
> 2. Copy the connection string from the Neon dashboard (the pooled one, ending in `?sslmode=require`).
> 3. `cp .env.example .env`, then paste it as `PG_CONNECTION_STRING`. `.env` is gitignored.
> 4. Run: `source .venv/bin/activate && python3 -m nerdjoy_pipeline.pg_loader`
> 5. Confirm in the Neon SQL editor: `SELECT count(*) FROM applications;` should return 467.
> 6. Run the loader a second time and confirm the count is still 467. That proves the upsert is idempotent.

Expected after Heather runs it: 467 rows, unchanged on the second run.

- [x] **Step 6: Commit**

```bash
git add src/nerdjoy_pipeline/pg_loader.py tests/test_pg_loader.py docs/runbook.md
git commit -m "feat: add idempotent tracker to Postgres loader"
```

---

### Task 7: Target companies to HubSpot loader

Parses `resumes/target_companies.md` (markdown tables, ~83 lines across 5 domain sections) and upserts each company into HubSpot's free CRM. Tests use a fake HTTP client, so no token is needed to go green.

**Files:**
- Create: `src/nerdjoy_pipeline/hubspot_loader.py`
- Test: `tests/test_hubspot_loader.py`, `tests/fixtures/sample_targets.md`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `@dataclass(frozen=True) TargetCompany` with fields `name: str`, `why_fit: str`, `stage_size: str`, `ats: str`, `slug: str`, `board_url: str`, `domain: str`
  - `parse_target_companies(path: str | Path) -> list[TargetCompany]`
  - `to_hubspot_properties(company: TargetCompany) -> dict[str, str]`
  - `upsert_companies(companies: list[TargetCompany], client) -> int` where `client` exposes `post(url: str, json: dict) -> dict`
  - `main(argv: list[str] | None = None) -> int`

- [x] **Step 1: Write `tests/fixtures/sample_targets.md`**

Mirrors the real file's structure with fictional companies.

```markdown
# Target Companies — direct ATS board polling

> Curated for `/jobs targets`. Boards are polled directly via ATS JSON endpoints.

## Domain 1 — MarTech Data Infrastructure & Integrations
| Company | Why fit | Stage/Size | ATS | Slug | Board URL |
|---|---|---|---|---|---|
| Acme Data Co | Reverse ETL and warehouse activation | Series C, ~250 | Greenhouse | acmedata | https://example.invalid/acmedata |
| Borealis Systems | Event-driven messaging automation | Growth, ~350 | Lever | borealis | https://example.invalid/borealis |

## Domain 2 — Customer Data Platforms
| Company | Why fit | Stage/Size | ATS | Slug | Board URL |
|---|---|---|---|---|---|
| Cindergrid | Snowflake-native CDP | Series D, ~150 | Ashby | cindergrid | https://example.invalid/cindergrid |
```

- [x] **Step 2: Write the failing tests**

`tests/test_hubspot_loader.py`:

```python
from pathlib import Path

import pytest

from nerdjoy_pipeline.hubspot_loader import (
    TargetCompany,
    parse_target_companies,
    to_hubspot_properties,
    upsert_companies,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_targets.md"


class FakeClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict) -> dict:
        self.calls.append((url, json))
        return {"id": str(len(self.calls))}


def test_parses_every_table_row():
    companies = parse_target_companies(FIXTURE)
    assert len(companies) == 3
    assert {c.name for c in companies} == {"Acme Data Co", "Borealis Systems", "Cindergrid"}


def test_skips_header_and_separator_rows():
    companies = parse_target_companies(FIXTURE)
    assert all(c.name not in {"Company", "---"} for c in companies)


def test_captures_every_column():
    company = next(c for c in parse_target_companies(FIXTURE) if c.name == "Acme Data Co")
    assert company.why_fit == "Reverse ETL and warehouse activation"
    assert company.stage_size == "Series C, ~250"
    assert company.ats == "Greenhouse"
    assert company.slug == "acmedata"
    assert company.board_url == "https://example.invalid/acmedata"


def test_captures_the_domain_section():
    companies = parse_target_companies(FIXTURE)
    acme = next(c for c in companies if c.name == "Acme Data Co")
    cinder = next(c for c in companies if c.name == "Cindergrid")
    assert acme.domain == "Domain 1 - MarTech Data Infrastructure & Integrations"
    assert cinder.domain == "Domain 2 - Customer Data Platforms"


def test_domain_labels_carry_no_em_dash():
    # Section headings in the source use an em-dash; parsing must strip it so
    # the value is safe if it ever reaches an outgoing surface.
    for company in parse_target_companies(FIXTURE):
        assert "—" not in company.domain


def test_hubspot_properties_shape():
    company = TargetCompany(
        name="Acme Data Co",
        why_fit="Reverse ETL",
        stage_size="Series C, ~250",
        ats="Greenhouse",
        slug="acmedata",
        board_url="https://example.invalid/acmedata",
        domain="Domain 1 - MarTech",
    )
    props = to_hubspot_properties(company)
    assert props["name"] == "Acme Data Co"
    assert props["ats_platform"] == "Greenhouse"
    assert props["target_domain"] == "Domain 1 - MarTech"
    assert all(isinstance(v, str) for v in props.values())


def test_upsert_posts_once_per_company():
    companies = parse_target_companies(FIXTURE)
    client = FakeClient()
    count = upsert_companies(companies, client)
    assert count == 3
    assert len(client.calls) == 3


def test_upsert_targets_the_companies_endpoint():
    client = FakeClient()
    upsert_companies(parse_target_companies(FIXTURE), client)
    url, payload = client.calls[0]
    assert url.endswith("/crm/v3/objects/companies")
    assert "properties" in payload


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_target_companies(Path("/nonexistent/targets.md"))
```

- [x] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/test_hubspot_loader.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'nerdjoy_pipeline.hubspot_loader'`

- [x] **Step 4: Write the implementation**

`src/nerdjoy_pipeline/hubspot_loader.py`:

```python
"""Load target companies from the markdown table into HubSpot's free CRM.

The source file lives in the job-search repo and is never copied here.
HubSpot becomes the CRM of record and a Fivetran source.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HUBSPOT_BASE = "https://api.hubapi.com"
COMPANIES_ENDPOINT = f"{HUBSPOT_BASE}/crm/v3/objects/companies"

_SECTION_RE = re.compile(r"^##\s+(.*)$")
_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")


@dataclass(frozen=True)
class TargetCompany:
    name: str
    why_fit: str
    stage_size: str
    ats: str
    slug: str
    board_url: str
    domain: str


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_target_companies(path: str | Path) -> list[TargetCompany]:
    """Parse the markdown tables under each Domain heading."""
    text = Path(path).read_text(encoding="utf-8")
    companies: list[TargetCompany] = []
    current_domain = ""

    for line in text.splitlines():
        section = _SECTION_RE.match(line)
        if section:
            # Headings use an em-dash; normalize so the value is safe downstream.
            current_domain = section.group(1).replace("—", "-").strip()
            continue

        if not line.startswith("|") or _SEPARATOR_RE.match(line):
            continue

        cells = _split_row(line)
        if len(cells) < 6 or cells[0].lower() == "company":
            continue

        companies.append(
            TargetCompany(
                name=cells[0],
                why_fit=cells[1],
                stage_size=cells[2],
                ats=cells[3],
                slug=cells[4],
                board_url=cells[5],
                domain=current_domain,
            )
        )

    return companies


def to_hubspot_properties(company: TargetCompany) -> dict[str, str]:
    return {
        "name": company.name,
        "description": company.why_fit,
        "lifecyclestage": "opportunity",
        "ats_platform": company.ats,
        "ats_slug": company.slug,
        "target_domain": company.domain,
        "stage_size": company.stage_size,
    }


def upsert_companies(companies: list[TargetCompany], client) -> int:
    """POST each company. `client` needs a post(url, json) -> dict method."""
    for company in companies:
        client.post(COMPANIES_ENDPOINT, {"properties": to_hubspot_properties(company)})
    return len(companies)


class _RequestsClient:
    def __init__(self, token: str):
        import requests

        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def post(self, url: str, json: dict) -> dict:
        response = self._session.post(url, json=json, timeout=30)
        response.raise_for_status()
        return response.json()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load target companies into HubSpot")
    parser.add_argument(
        "--targets",
        default=os.environ.get(
            "TARGET_COMPANIES_PATH",
            "/Users/heatherbarry/claude-linkedin-assistant/resumes/target_companies.md",
        ),
    )
    args = parser.parse_args(argv)

    token = os.environ.get("HUBSPOT_TOKEN")
    if not token:
        print(
            "HUBSPOT_TOKEN is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1

    companies = parse_target_companies(args.targets)
    count = upsert_companies(companies, _RequestsClient(token))
    print(f"Upserted {count} companies into HubSpot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_hubspot_loader.py -v`
Expected: 9 passed

- [x] **Step 6: Verify the parser against the real target file (read-only)**

```bash
python3 -c "
from nerdjoy_pipeline.hubspot_loader import parse_target_companies
cs = parse_target_companies('/Users/heatherbarry/claude-linkedin-assistant/resumes/target_companies.md')
print('parsed:', len(cs))
print('domains:', sorted({c.domain for c in cs}))
assert len(cs) > 30, 'expected the full target list'
assert all(c.slug and c.ats for c in cs), 'every row needs a slug and ATS'
print('parser ok')
"
```

Expected: a count above 30, the domain list, then `parser ok`

- [x] **Step 7: HUMAN STEP — Heather creates the HubSpot private app**

Append to `docs/runbook.md`. **Claude does not perform this step.**

> 1. Create a free HubSpot account at hubspot.com.
> 2. Settings > Integrations > Private Apps > Create a private app, named `nerdjoy-pipeline`.
> 3. Scopes: `crm.objects.companies.read`, `crm.objects.companies.write`.
> 4. Copy the access token into `.env` as `HUBSPOT_TOKEN`.
> 5. Settings > Properties > Companies: create four single-line text properties with the internal names `ats_platform`, `ats_slug`, `target_domain`, `stage_size`.
> 6. Run: `source .venv/bin/activate && python3 -m nerdjoy_pipeline.hubspot_loader`
> 7. Confirm the companies appear under CRM > Companies.

- [x] **Step 8: Commit**

```bash
git add src/nerdjoy_pipeline/hubspot_loader.py tests/test_hubspot_loader.py tests/fixtures/sample_targets.md docs/runbook.md
git commit -m "feat: add target companies to HubSpot loader"
```

---

### Task 8: dbt Core project with seed data

Built against a **seed** so every model and test is green before Fivetran exists (spec §10.2). When Fivetran lands raw tables in Task 12, only the staging models' `FROM` clauses change.

**Files:**
- Create: `dbt/dbt_project.yml`, `dbt/profiles.yml.example`, `dbt/seeds/applications_seed.csv`, `dbt/models/staging/{stg_applications.sql,stg_companies.sql,schema.yml}`, `dbt/models/marts/{fct_funnel.sql,dim_company.sql,mart_referral_scoring.sql,mart_public_metrics.sql,schema.yml}`
- Create: `scripts/make_seed.py`

**Interfaces:**
- Consumes: `read_tracker` (Task 2)
- Produces: BigQuery relations `stg_applications`, `stg_companies`, `fct_funnel`, `dim_company`, `mart_referral_scoring`, `mart_public_metrics`. `mart_public_metrics` has columns `metric_name STRING`, `metric_value NUMERIC` and is the only mart safe to publish.

- [x] **Step 1: Write the seed generator**

`scripts/make_seed.py`:

```python
#!/usr/bin/env python3
"""Generate dbt/seeds/applications_seed.csv from the real tracker.

The seed is REAL data and is therefore gitignored except for the sample
committed for CI. It exists so dbt models can be built and tested before
Fivetran is wired.
"""
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nerdjoy_pipeline.pg_loader import application_key  # noqa: E402
from nerdjoy_pipeline.tracker import read_tracker  # noqa: E402

TRACKER = os.environ.get(
    "TRACKER_PATH", "/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv"
)
OUT = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "applications_seed.csv"

FIELDS = [
    "application_key",
    "company",
    "role",
    "status",
    "priority",
    "referral_needed",
    "referral_status",
    "apply_via",
    "applied_date",
    "discovered_date",
]


def main() -> int:
    apps = read_tracker(TRACKER)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for app in apps:
            writer.writerow(
                {
                    "application_key": application_key(app),
                    "company": app.company,
                    "role": app.role,
                    "status": app.status,
                    "priority": app.priority,
                    "referral_needed": str(app.referral_needed).lower(),
                    "referral_status": app.referral_status,
                    "apply_via": app.apply_via,
                    "applied_date": app.applied_date.isoformat() if app.applied_date else "",
                    "discovered_date": (
                        app.discovered_date.isoformat() if app.discovered_date else ""
                    ),
                }
            )
    print(f"Wrote {OUT} with {len(apps)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 2: Write `dbt/dbt_project.yml`**

```yaml
name: nerdjoy_pipeline
version: "1.0.0"
config-version: 2

profile: nerdjoy_pipeline

model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

models:
  nerdjoy_pipeline:
    staging:
      +materialized: view
    marts:
      +materialized: table

seeds:
  nerdjoy_pipeline:
    applications_seed:
      +column_types:
        application_key: STRING
        company: STRING
        role: STRING
        status: STRING
        priority: STRING
        referral_needed: BOOLEAN
        referral_status: STRING
        apply_via: STRING
        applied_date: DATE
        discovered_date: DATE
```

- [x] **Step 3: Write `dbt/profiles.yml.example`**

```yaml
# Copy to ~/.dbt/profiles.yml and fill in. Never commit the filled version.
nerdjoy_pipeline:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: service-account
      project: "{{ env_var('BIGQUERY_PROJECT') }}"
      dataset: "{{ env_var('BIGQUERY_DATASET', 'nerdjoy_pipeline') }}"
      keyfile: "{{ env_var('GOOGLE_APPLICATION_CREDENTIALS') }}"
      threads: 4
      location: US
      priority: interactive
```

- [x] **Step 4: Write the staging models**

`dbt/models/staging/stg_applications.sql`:

```sql
-- Source swaps to the Fivetran raw table in Task 12; the contract below is
-- what every downstream model depends on, so it must not change.
with source as (
    select * from {{ ref('applications_seed') }}
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
from source
where company is not null and company != ''
```

`dbt/models/staging/stg_companies.sql`:

```sql
with applications as (
    select * from {{ ref('stg_applications') }}
)

select
    company,
    count(*) as application_count,
    countif(referral_needed) as referral_needed_count,
    countif(reached_conversation) as conversation_count,
    countif(reached_offer) as offer_count,
    min(discovered_date) as first_discovered_date,
    max(applied_date) as last_applied_date
from applications
group by company
```

`dbt/models/staging/schema.yml`:

```yaml
version: 2

models:
  - name: stg_applications
    description: One row per application, normalized from the tracker.
    columns:
      - name: application_key
        description: Stable SHA-256 of company plus role.
        tests:
          - not_null
          - unique
      - name: company
        tests: [not_null]
      - name: status
        tests:
          - not_null
          - accepted_values:
              values:
                ["To Apply", "Applied", "Recruiter Call", "Phone Screen",
                 "Onsite", "Offer", "Rejected", "Withdrew"]
      - name: priority
        tests:
          - not_null
          - accepted_values:
              values: ["HIGH", "MEDIUM", "LOW"]
      - name: referral_status
        tests:
          - not_null
          - accepted_values:
              values:
                ["Not Needed", "Outreach Pending", "Connection Pending",
                 "Outreach Sent", "Got Referral", "Declined", "No Referral"]

  - name: stg_companies
    description: One row per company with rolled-up application counts.
    columns:
      - name: company
        tests: [not_null, unique]
      - name: application_count
        tests: [not_null]
```

- [x] **Step 5: Write the mart models**

`dbt/models/marts/fct_funnel.sql`:

```sql
with applications as (
    select * from {{ ref('stg_applications') }}
)

select
    status,
    count(*) as application_count,
    count(distinct company) as company_count,
    countif(referral_needed) as referral_needed_count
from applications
group by status
```

`dbt/models/marts/dim_company.sql`:

```sql
-- Company grain with a generalized size descriptor. This mart holds real
-- names and is NEVER published. Only mart_public_metrics is public.
with companies as (
    select * from {{ ref('stg_companies') }}
)

select
    company,
    application_count,
    referral_needed_count,
    conversation_count,
    offer_count,
    first_discovered_date,
    last_applied_date,
    case
        when conversation_count > 0 then 'engaged'
        when application_count > 1 then 'multi-application'
        else 'single-application'
    end as engagement_tier
from companies
```

`dbt/models/marts/mart_referral_scoring.sql`:

```sql
-- Hightouch source: which companies need a warm intro next, ranked.
with applications as (
    select * from {{ ref('stg_applications') }}
)

select
    company,
    count(*) as open_application_count,
    max(discovered_date) as latest_discovered_date,
    -- Higher score means more worth a warm intro today.
    sum(
        case
            when referral_status = 'Outreach Pending' then 30
            when referral_status = 'Connection Pending' then 20
            when referral_status = 'Outreach Sent' then 5
            else 0
        end
        + case when priority = 'HIGH' then 20 when priority = 'MEDIUM' then 10 else 0 end
        + case when status = 'To Apply' then 15 when status = 'Applied' then 10 else 0 end
    ) as referral_score
from applications
where referral_needed
  and referral_status not in ('Got Referral', 'Declined', 'No Referral')
  and status not in ('Rejected', 'Withdrew')
group by company
order by referral_score desc
```

`dbt/models/marts/mart_public_metrics.sql`:

```sql
-- The ONLY mart safe to publish. Long format, aggregate values only.
-- No company names, no roles, no URLs by construction.
with applications as (
    select * from {{ ref('stg_applications') }}
),

referral_base as (
    select count(*) as needed,
           countif(referral_status = 'Got Referral') as got
    from applications
    where referral_needed
)

select 'applications_total' as metric_name,
       cast(count(*) as numeric) as metric_value
from applications

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
```

`dbt/models/marts/schema.yml`:

```yaml
version: 2

models:
  - name: fct_funnel
    description: Application counts by funnel status.
    columns:
      - name: status
        tests: [not_null, unique]
      - name: application_count
        tests: [not_null]

  - name: dim_company
    description: Company grain. Contains real names, never published.
    columns:
      - name: company
        tests: [not_null, unique]
      - name: engagement_tier
        tests:
          - accepted_values:
              values: ["engaged", "multi-application", "single-application"]

  - name: mart_referral_scoring
    description: Hightouch source. Companies ranked by warm-intro priority.
    columns:
      - name: company
        tests: [not_null, unique]
      - name: referral_score
        tests: [not_null]

  - name: mart_public_metrics
    description: The only publishable mart. Aggregate values only, no names.
    columns:
      - name: metric_name
        tests: [not_null, unique]
      - name: metric_value
        tests: [not_null]
```

- [x] **Step 6: HUMAN STEP — Heather provisions BigQuery**

Append to `docs/runbook.md`. **Claude does not perform this step.**

> BigQuery must be a **billing-enabled** project. The pure sandbox is rejected by Fivetran as a destination (spec §11). Free-tier credits cover this volume; expect no real spend.
>
> 1. In the Google Cloud console, create a project named `nerdjoy-pipeline`.
> 2. Billing > link a billing account. This is the step that makes Fivetran accept it.
> 3. APIs & Services > enable the BigQuery API.
> 4. IAM > Service Accounts > create `dbt-runner` with roles `BigQuery Data Editor` and `BigQuery Job User`.
> 5. Create a JSON key, save it OUTSIDE the repo (for example `~/.config/nerdjoy/bq-service-account.json`).
> 6. In `.env`, set `BIGQUERY_PROJECT`, `BIGQUERY_DATASET=nerdjoy_pipeline`, and `GOOGLE_APPLICATION_CREDENTIALS` to that path.
> 7. BigQuery > create the dataset `nerdjoy_pipeline`, location US.
> 8. `cp dbt/profiles.yml.example ~/.dbt/profiles.yml`

- [x] **Step 7: Generate the seed and run dbt**

```bash
source .venv/bin/activate
pip install -e ".[dbt]"
python3 scripts/make_seed.py
cd dbt
dbt deps
dbt seed
dbt run
dbt test
```

Expected: `dbt seed` loads 467 rows; `dbt run` builds 6 models; `dbt test` passes every test. If `accepted_values` fails, the normalizer in Task 2 has a gap. Fix `tracker.py` and regenerate the seed rather than loosening the test.

- [x] **Step 8: Verify the public mart contains no names**

```bash
cd dbt
dbt show --select mart_public_metrics --limit 50
```

Expected: only `metric_name` / `metric_value` pairs. Confirm by eye that no company name appears in any `metric_name`.

- [x] **Step 9: Commit**

```bash
cd ~/nerdjoy-pipeline
git add dbt/dbt_project.yml dbt/profiles.yml.example dbt/models scripts/make_seed.py docs/runbook.md
git commit -m "feat: add dbt project with models and tests"
```

Note: `dbt/seeds/applications_seed.csv` holds real company names and stays gitignored.

---

### Task 9: Dashboard shell and guarded build

A static page that renders `metrics.json`, plus a build step that inlines the metrics and runs the guard over the **final rendered HTML**. The guard runs over the built output, not the source, so an em-dash or a name introduced by templating still gets caught.

**Files:**
- Create: `dashboard/index.html`, `dashboard/style.css`, `dashboard/app.js`, `dashboard/build.py`
- Test: `tests/test_dashboard_build.py`

**Interfaces:**
- Consumes: `build_denylist`, `guard_text`, `GuardViolation` (Task 3); `metrics.json` (Task 5)
- Produces: `build_dashboard(metrics_path, template_dir, output_dir, tracker_path) -> Path`; `main(argv=None) -> int`

- [ ] **Step 1: Write the failing tests**

`tests/test_dashboard_build.py`:

```python
import json
from pathlib import Path

import pytest

from nerdjoy_pipeline.guard import GuardViolation

from dashboard.build import build_dashboard

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dashboard"


@pytest.fixture
def metrics_file(tmp_path: Path) -> Path:
    payload = {
        "generated_at": "2026-09-20",
        "totals": {"applications": 466, "companies": 378},
        "funnel": {"To Apply": 199, "Applied": 238, "Offer": 0},
        "referrals": {"needed": 124, "outreach_sent": 3, "got_referral": 2,
                      "conversion_pct": 0.8},
        "channels": {"LinkedIn Easy Apply": 81, "LinkedIn": 79},
        "activity": [{"month": "2026-08", "applied": 40}],
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(payload))
    return path


def test_build_writes_index_html(metrics_file: Path, tmp_path: Path, sample_tracker_path: Path):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert out.name == "index.html"
    assert out.exists()


def test_metrics_are_inlined_not_fetched(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    html = out.read_text()
    assert "466" in html
    assert "fetch(" not in html  # no runtime fetch; the page is self-contained


def test_built_html_has_no_em_dash(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert "—" not in out.read_text()


def test_built_html_has_no_denylisted_name(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert "hollowpine" not in out.read_text().lower()


def test_guard_violation_prevents_output(tmp_path: Path, sample_tracker_path: Path):
    leaky = tmp_path / "metrics.json"
    leaky.write_text(json.dumps({"totals": {"applications": 1}, "note": "Hollowpine"}))
    dist = tmp_path / "dist"
    with pytest.raises(GuardViolation):
        build_dashboard(leaky, TEMPLATE_DIR, dist, sample_tracker_path)
    assert not (dist / "index.html").exists()


def test_css_and_js_are_copied(metrics_file: Path, tmp_path: Path, sample_tracker_path: Path):
    dist = tmp_path / "dist"
    build_dashboard(metrics_file, TEMPLATE_DIR, dist, sample_tracker_path)
    assert (dist / "style.css").exists()
    assert (dist / "app.js").exists()


def test_page_declares_a_viewport_for_mobile(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert 'name="viewport"' in out.read_text()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_dashboard_build.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'dashboard'`

- [ ] **Step 3: Write `dashboard/index.html`**

Note the copy: no em-dashes anywhere. `__METRICS_JSON__` is the inline injection point.

```html
<!DOCTYPE html>
<html lang="en" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>nerdjoy // Pipeline</title>
<meta name="description" content="A job search run as a go-to-market pipeline, on a real modern data stack.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<main>
  <header class="hero">
    <p class="eyebrow">nerdjoy // Pipeline</p>
    <h1>I run my job search like a go-to-market motion.</h1>
    <p class="sub">
      Target companies are accounts. Hiring managers are leads. Referrals are warm intros.
      The tracker is the CRM. Here is the stack that runs it, and the real pipeline data.
    </p>
  </header>

  <section class="tiles" id="tiles" aria-label="Pipeline metrics"></section>

  <section aria-labelledby="funnel-heading">
    <h2 id="funnel-heading">The funnel</h2>
    <div class="funnel" id="funnel"></div>
  </section>

  <section aria-labelledby="arch-heading">
    <h2 id="arch-heading">The stack</h2>
    <p class="note">Every tool below is wired and has run for real. Nothing here is aspirational.</p>
    <ol class="arch">
      <li><span class="lane">Sources</span> Application tracker (Postgres), HubSpot CRM, ATS boards</li>
      <li><span class="lane">Ingest</span> Fivetran connectors</li>
      <li><span class="lane">Warehouse</span> BigQuery, raw and analytics datasets</li>
      <li><span class="lane">Transform</span> dbt Core, staging models into funnel and scoring marts</li>
      <li><span class="lane">Activate</span> Hightouch reverse ETL into HubSpot and a daily targets sheet</li>
      <li><span class="lane">Orchestrate</span> Airflow on Astro, one scheduled DAG</li>
      <li><span class="lane">Control plane</span> A Claude agent reads the marts and drafts outreach for me to approve</li>
    </ol>
  </section>

  <section aria-labelledby="activity-heading">
    <h2 id="activity-heading">Activity over time</h2>
    <div class="activity" id="activity"></div>
  </section>

  <section aria-labelledby="channels-heading">
    <h2 id="channels-heading">Where applications go</h2>
    <div class="channels" id="channels"></div>
  </section>

  <footer>
    <p>Aggregates only. No company names, no contacts, no personal data.</p>
    <p class="generated">Last refreshed <span id="generated"></span></p>
  </footer>
</main>

<script id="metrics-data" type="application/json">__METRICS_JSON__</script>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Write `dashboard/style.css`**

```css
:root {
  --bg: #ffffff;
  --fg: #12141a;
  --muted: #5b6272;
  --line: #e3e6ec;
  --accent: #4338ca;
  --accent-soft: #eef0ff;
  --radius: 12px;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d0f14;
    --fg: #eef0f5;
    --muted: #9aa3b5;
    --line: #232733;
    --accent: #a5b4fc;
    --accent-soft: #1a1f33;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}

main { max-width: 860px; margin: 0 auto; padding: 48px 16px 64px; }

.eyebrow {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  letter-spacing: 0.08em;
  color: var(--accent);
  margin: 0 0 12px;
}

.hero h1 { font-size: clamp(28px, 5vw, 42px); line-height: 1.15; margin: 0 0 16px; }
.hero .sub { color: var(--muted); font-size: 18px; max-width: 62ch; margin: 0; }

h2 { font-size: 20px; margin: 48px 0 16px; }
.note { color: var(--muted); font-size: 15px; margin: 0 0 16px; }

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-top: 40px;
}

.tile {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  background: var(--accent-soft);
}

.tile .value { font-size: 30px; font-weight: 650; line-height: 1.1; }
.tile .label { color: var(--muted); font-size: 13px; margin-top: 4px; }

.bar-row { display: grid; grid-template-columns: 130px 1fr 48px; gap: 10px; align-items: center; margin-bottom: 8px; }
.bar-row .name { font-size: 14px; color: var(--muted); }
.bar-row .count { font-size: 14px; text-align: right; font-variant-numeric: tabular-nums; }
.bar { height: 10px; border-radius: 999px; background: var(--accent); min-width: 2px; }
.bar-track { background: var(--line); border-radius: 999px; }

.arch { list-style: none; padding: 0; margin: 0; }
.arch li { border-left: 2px solid var(--line); padding: 10px 0 10px 16px; font-size: 15px; }
.lane {
  display: inline-block;
  min-width: 108px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

footer { margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--line); color: var(--muted); font-size: 14px; }
.generated { font-size: 13px; }

@media (max-width: 520px) {
  .bar-row { grid-template-columns: 96px 1fr 40px; }
  .lane { display: block; min-width: 0; margin-bottom: 2px; }
}
```

- [ ] **Step 5: Write `dashboard/app.js`**

```js
(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("metrics-data").textContent);

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function renderTiles() {
    var host = document.getElementById("tiles");
    var refs = data.referrals || {};
    var tiles = [
      { value: data.totals.applications, label: "applications tracked" },
      { value: data.totals.companies, label: "companies in the pipeline" },
      { value: refs.needed || 0, label: "needed a warm intro" },
      { value: (refs.conversion_pct || 0) + "%", label: "referral conversion" }
    ];
    tiles.forEach(function (t) {
      var tile = el("div", "tile");
      tile.appendChild(el("div", "value", t.value));
      tile.appendChild(el("div", "label", t.label));
      host.appendChild(tile);
    });
  }

  function renderBars(hostId, entries) {
    var host = document.getElementById(hostId);
    var max = entries.reduce(function (m, e) { return Math.max(m, e[1]); }, 0) || 1;
    entries.forEach(function (entry) {
      var row = el("div", "bar-row");
      row.appendChild(el("div", "name", entry[0]));
      var track = el("div", "bar-track");
      var bar = el("div", "bar");
      bar.style.width = Math.round((entry[1] / max) * 100) + "%";
      track.appendChild(bar);
      row.appendChild(track);
      row.appendChild(el("div", "count", entry[1]));
      host.appendChild(row);
    });
  }

  renderTiles();
  renderBars("funnel", Object.keys(data.funnel).map(function (k) { return [k, data.funnel[k]]; }));
  renderBars("activity", (data.activity || []).map(function (a) { return [a.month, a.applied]; }));
  renderBars("channels", Object.keys(data.channels || {}).slice(0, 8).map(function (k) {
    return [k, data.channels[k]];
  }));

  document.getElementById("generated").textContent = data.generated_at || "";
})();
```

- [ ] **Step 6: Write `dashboard/build.py`**

```python
"""Build the publishable dashboard.

Metrics are inlined at build time so the page is a single self-contained
artifact with no runtime fetch. The guard runs over the FINAL rendered HTML,
so anything introduced by templating is still caught.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nerdjoy_pipeline.guard import (  # noqa: E402
    GuardViolation,
    build_denylist,
    guard_text,
)

PLACEHOLDER = "__METRICS_JSON__"
STATIC_FILES = ("style.css", "app.js")
DEFAULT_TRACKER = "/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv"


def build_dashboard(
    metrics_path: str | Path,
    template_dir: str | Path,
    output_dir: str | Path,
    tracker_path: str | Path,
) -> Path:
    template_dir = Path(template_dir)
    output_dir = Path(output_dir)

    metrics_json = Path(metrics_path).read_text(encoding="utf-8").strip()
    html = (template_dir / "index.html").read_text(encoding="utf-8")
    rendered = html.replace(PLACEHOLDER, metrics_json)

    # Guard the final artifact, before anything touches disk.
    denylist = build_denylist(tracker_path)
    guard_text(rendered, denylist, label="dashboard/index.html")
    for name in STATIC_FILES:
        guard_text(
            (template_dir / name).read_text(encoding="utf-8"),
            denylist,
            label=f"dashboard/{name}",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "index.html"
    out.write_text(rendered, encoding="utf-8")
    for name in STATIC_FILES:
        shutil.copy2(template_dir / name, output_dir / name)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the dashboard")
    parser.add_argument("--metrics", default="metrics.json")
    parser.add_argument("--templates", default="dashboard")
    parser.add_argument("--output", default="dashboard/dist")
    parser.add_argument("--tracker", default=DEFAULT_TRACKER)
    args = parser.parse_args(argv)

    try:
        out = build_dashboard(args.metrics, args.templates, args.output, args.tracker)
    except GuardViolation as exc:
        print(f"GUARD FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"Built {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Add `dashboard/__init__.py` so the tests can import the module**

```bash
touch dashboard/__init__.py
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `pytest tests/test_dashboard_build.py -v`
Expected: 7 passed

- [ ] **Step 9: Build the real dashboard and check it in a browser**

```bash
python3 -m nerdjoy_pipeline.metrics_extract --output metrics.json
python3 dashboard/build.py
open dashboard/dist/index.html
```

Verify by hand: numbers match `metrics.json`; the layout holds at 375px width; light and dark both readable; no em-dash visible anywhere.

- [ ] **Step 10: Run the whole suite**

Run: `pytest -v`
Expected: 94 passed

- [ ] **Step 11: Commit**

```bash
git add dashboard tests/test_dashboard_build.py
git commit -m "feat: add dashboard shell with guarded build"
```

---

### Task 10: HUMAN STEP — Hightouch syncs

Hightouch has no meaningful local test surface; it is UI configuration. This task's deliverable is a runbook section plus captured proof.

**Files:**
- Modify: `docs/runbook.md`
- Create: `docs/proof/` entries

- [ ] **Step 1: Write the runbook section**

Append to `docs/runbook.md`:

> ## Hightouch (free tier)
>
> Verify the free tier covers 2 syncs from a BigQuery source before committing (spec §11).
>
> 1. Sign up at hightouch.io, free tier.
> 2. Sources > add BigQuery. Upload the same service-account JSON from the BigQuery step. Point it at the `nerdjoy_pipeline` dataset.
> 3. Models > new model from `mart_referral_scoring`, primary key `company`.
> 4. Models > new model from `fct_funnel`, primary key `status`.
> 5. Destinations > HubSpot. Authorize with the same HubSpot account.
> 6. Sync 1: `mart_referral_scoring` to HubSpot Companies. Match on company name. Map `referral_score` to a new HubSpot company property `referral_score` (number), and `open_application_count` to `open_application_count` (number). Create those two properties in HubSpot first.
> 7. Destinations > Google Sheets. Authorize with the Google account that owns the BigQuery project.
> 8. Create a sheet named `nerdjoy-pipeline-warm-intros`.
> 9. Sync 2: `mart_referral_scoring` to that sheet, mode "overwrite". This is the daily warm-intro targets list the agent reads.
> 10. Run both syncs manually once.
> 11. Note each sync's ID from its URL. Put them in `.env` as `HIGHTOUCH_SYNC_ID_HUBSPOT` and `HIGHTOUCH_SYNC_ID_SHEET`.
> 12. Settings > API keys > create one. Put it in `.env` as `HIGHTOUCH_API_KEY`.

- [ ] **Step 2: Capture proof**

Save to `docs/proof/`: `hightouch-sync-hubspot.png` (a successful run with a row count), `hightouch-sync-sheet.png`, `hubspot-companies-with-score.png`, `google-sheet-warm-intros.png`.

Confirm each screenshot is cropped so no company name is legible, or note in the runbook that these proof images are **local only and gitignored**. Add `docs/proof/` to `.gitignore` if any image shows real names.

- [ ] **Step 3: Commit**

```bash
git add docs/runbook.md .gitignore
git commit -m "docs: add Hightouch sync runbook"
```

---

### Task 11: HUMAN STEP — Fivetran connectors (trial starts here)

**This task starts the ~14-day Fivetran trial clock.** Do not begin it until Tasks 1-10 are done and the dashboard renders. Capture proof immediately after the first successful sync.

**Files:**
- Modify: `docs/runbook.md`, `dbt/models/staging/stg_applications.sql`
- Create: `dbt/models/staging/sources.yml`

- [ ] **Step 1: Write the runbook section**

Append to `docs/runbook.md`:

> ## Fivetran (trial clock starts now)
>
> Record today's date. The trial is roughly 14 days. Capture proof the moment the first sync succeeds.
>
> 1. Destinations > add BigQuery. Use the **billing-enabled** project. A pure sandbox project is rejected here; that is why billing was enabled earlier.
> 2. Connectors > add Postgres. Host is the Neon endpoint, not localhost. Fivetran is hosted and cannot reach a local database. Enable `sslmode=require`. Sync the `public.applications` table only.
> 3. Connectors > add HubSpot. Authorize with the same HubSpot account. Sync the Companies object only, to keep row counts low.
> 4. Run both connectors' initial sync.
> 5. Confirm in BigQuery that `<raw_schema>.applications` and the HubSpot company table exist and are populated.
> 6. Settings > API config > create an API key and secret. Put them in `.env` as `FIVETRAN_API_KEY` and `FIVETRAN_API_SECRET`.
> 7. Note each connector's ID from its Setup tab. Put them in `.env` as `FIVETRAN_CONNECTOR_ID_POSTGRES` and `FIVETRAN_CONNECTOR_ID_HUBSPOT`.
>
> **Fallback if the trial lapses before the reveal:** swap to Airbyte Cloud's free tier with the same two connectors, and update the dashboard's stack list plus the README diagram to say Airbyte. The honesty principle requires the diagram to match what actually ran.

- [ ] **Step 2: Capture proof immediately**

Save to `docs/proof/`: `fivetran-postgres-sync.png` and `fivetran-hubspot-sync.png`, each showing a green sync with a row count and a timestamp. Also record a 10 second screen clip of the connector dashboard.

- [ ] **Step 3: Write `dbt/models/staging/sources.yml`**

Replace `<raw_schema>` with the actual Fivetran-created schema name.

```yaml
version: 2

sources:
  - name: fivetran_postgres
    database: "{{ env_var('BIGQUERY_PROJECT') }}"
    schema: public
    tables:
      - name: applications
        description: Tracker applications landed by the Fivetran Postgres connector.

  - name: fivetran_hubspot
    database: "{{ env_var('BIGQUERY_PROJECT') }}"
    schema: hubspot
    tables:
      - name: company
        description: HubSpot companies landed by the Fivetran HubSpot connector.
```

- [ ] **Step 4: Repoint the staging model from the seed to the Fivetran source**

Edit `dbt/models/staging/stg_applications.sql`. Change only the `source` CTE; every column below it is unchanged, which is why the mart contract holds.

Replace:

```sql
with source as (
    select * from {{ ref('applications_seed') }}
)
```

with:

```sql
with source as (
    select * from {{ source('fivetran_postgres', 'applications') }}
)
```

- [ ] **Step 5: Rebuild and re-test against real synced data**

```bash
cd dbt
dbt run
dbt test
```

Expected: every model builds from the Fivetran-landed table; every test still passes. Row counts match the seed run (467 applications). If a test fails now but passed on the seed, the connector's type mapping differs; fix the staging cast, not the test.

- [ ] **Step 6: Commit**

```bash
cd ~/nerdjoy-pipeline
git add dbt/models/staging docs/runbook.md
git commit -m "feat: repoint dbt staging to Fivetran"
```

---

### Task 12: BigQuery-backed metrics export

Adds a second source for `metrics.json` behind the same output contract, so the export can read the warehouse mart instead of the tracker. The tracker path stays as the fallback (spec §8.7).

**Files:**
- Modify: `src/nerdjoy_pipeline/metrics_extract.py`
- Modify: `tests/test_metrics_extract.py`

**Interfaces:**
- Consumes: `mart_public_metrics` (Task 8), `guard_text` (Task 3)
- Produces: `payload_from_bigquery_rows(rows: list[dict]) -> dict` (same shape as `summary`); `export_metrics(..., source: str = "tracker")`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_metrics_extract.py`:

```python
def test_payload_from_bigquery_rows_matches_the_tracker_shape():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 467},
        {"metric_name": "companies_total", "metric_value": 379},
        {"metric_name": "funnel_applied", "metric_value": 238},
        {"metric_name": "funnel_to_apply", "metric_value": 199},
        {"metric_name": "referrals_needed", "metric_value": 124},
        {"metric_name": "referrals_got", "metric_value": 2},
        {"metric_name": "referral_conversion_pct", "metric_value": 1.6},
    ]
    payload = payload_from_bigquery_rows(rows)
    assert payload["totals"]["applications"] == 467
    assert payload["totals"]["companies"] == 379
    assert payload["funnel"]["Applied"] == 238
    assert payload["funnel"]["To Apply"] == 199
    assert payload["referrals"]["needed"] == 124
    assert payload["referrals"]["conversion_pct"] == 1.6


def test_bigquery_payload_has_no_names():
    import json

    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 1},
        {"metric_name": "companies_total", "metric_value": 1},
    ]
    text = json.dumps(payload_from_bigquery_rows(rows))
    assert "hollowpine" not in text.lower()


def test_unknown_metric_names_are_ignored():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 5},
        {"metric_name": "companies_total", "metric_value": 5},
        {"metric_name": "some_future_metric", "metric_value": 9},
    ]
    payload = payload_from_bigquery_rows(rows)
    assert payload["totals"]["applications"] == 5
    assert "some_future_metric" not in str(payload["funnel"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_metrics_extract.py -k bigquery -v`
Expected: FAIL with `ImportError: cannot import name 'payload_from_bigquery_rows'`

- [ ] **Step 3: Add the implementation**

Insert into `src/nerdjoy_pipeline/metrics_extract.py`, above `export_metrics`:

```python
from nerdjoy_pipeline.metrics import FUNNEL_ORDER

_FUNNEL_PREFIX = "funnel_"


def _status_from_metric(metric_name: str) -> str | None:
    """Map funnel_to_apply back to the canonical "To Apply"."""
    if not metric_name.startswith(_FUNNEL_PREFIX):
        return None
    slug = metric_name[len(_FUNNEL_PREFIX) :]
    for status in FUNNEL_ORDER:
        if status.lower().replace(" ", "_") == slug:
            return status
    return None


def payload_from_bigquery_rows(rows: list[dict]) -> dict:
    """Rebuild the metrics.json shape from mart_public_metrics rows."""
    values = {r["metric_name"]: r["metric_value"] for r in rows}

    funnel = {status: 0 for status in FUNNEL_ORDER}
    for name, value in values.items():
        status = _status_from_metric(name)
        if status is not None:
            funnel[status] = int(value)

    return {
        "totals": {
            "applications": int(values.get("applications_total", 0)),
            "companies": int(values.get("companies_total", 0)),
        },
        "funnel": funnel,
        "referrals": {
            "needed": int(values.get("referrals_needed", 0)),
            "outreach_sent": int(values.get("referrals_outreach_sent", 0)),
            "got_referral": int(values.get("referrals_got", 0)),
            "conversion_pct": float(values.get("referral_conversion_pct", 0.0)),
        },
        "channels": {},
        "activity": [],
    }


def _fetch_bigquery_rows() -> list[dict]:
    from google.cloud import bigquery

    project = os.environ["BIGQUERY_PROJECT"]
    dataset = os.environ.get("BIGQUERY_DATASET", "nerdjoy_pipeline")
    client = bigquery.Client(project=project)
    query = f"SELECT metric_name, metric_value FROM `{project}.{dataset}.mart_public_metrics`"
    return [dict(row) for row in client.query(query).result()]
```

Then change `export_metrics` to accept a source, replacing its first two lines:

```python
def export_metrics(
    tracker_path: str | Path, output_path: str | Path, source: str = "tracker"
) -> dict:
    if source == "bigquery":
        body = payload_from_bigquery_rows(_fetch_bigquery_rows())
    else:
        body = summary(read_tracker(tracker_path))
    payload = {"generated_at": date.today().isoformat(), **body}
```

And add the CLI flag in `main`, after the `--output` argument:

```python
    parser.add_argument("--source", choices=["tracker", "bigquery"], default="tracker")
```

then pass it through:

```python
        payload = export_metrics(args.tracker, args.output, source=args.source)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_metrics_extract.py -v`
Expected: 12 passed. The guard still runs on both source paths, since it sits below the branch.

- [ ] **Step 5: Run the real BigQuery export**

```bash
pip install google-cloud-bigquery
python3 -m nerdjoy_pipeline.metrics_extract --source bigquery --output metrics.json
```

Expected: totals match the tracker run (467 / 379). A mismatch means dbt is stale; re-run `dbt run` first.

- [ ] **Step 6: Commit**

```bash
git add src/nerdjoy_pipeline/metrics_extract.py tests/test_metrics_extract.py
git commit -m "feat: add BigQuery source to metrics export"
```

---

### Task 13: Airflow DAG on Astro (trial-bound)

One scheduled DAG chaining the full run. Tested with `pytest` DAG-integrity checks, which need no running Airflow.

**Files:**
- Create: `dags/gtm_pipeline_dag.py`, `tests/test_dag.py`, `Dockerfile`, `requirements.txt`
- Modify: `docs/runbook.md`

**Interfaces:**
- Consumes: every prior task's CLI entry point
- Produces: DAG `gtm_pipeline` with tasks `harvest_sources`, `load_postgres`, `fivetran_sync`, `dbt_run`, `dbt_test`, `hightouch_sync`, `refresh_metrics`, `build_dashboard`

- [ ] **Step 1: Write the failing tests**

`tests/test_dag.py`:

```python
import pytest

pytest.importorskip("airflow", reason="Airflow is only installed in the Astro image")

from airflow.models import DagBag  # noqa: E402

EXPECTED_TASKS = {
    "harvest_sources",
    "load_postgres",
    "fivetran_sync",
    "dbt_run",
    "dbt_test",
    "hightouch_sync",
    "refresh_metrics",
    "build_dashboard",
}


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder="dags", include_examples=False)


def test_dag_imports_without_error(dagbag):
    assert dagbag.import_errors == {}


def test_dag_exists(dagbag):
    assert "gtm_pipeline" in dagbag.dags


def test_dag_has_every_task(dagbag):
    dag = dagbag.dags["gtm_pipeline"]
    assert {t.task_id for t in dag.tasks} == EXPECTED_TASKS


def test_dag_runs_in_the_correct_order(dagbag):
    dag = dagbag.dags["gtm_pipeline"]

    def downstream(task_id):
        return {t.task_id for t in dag.get_task(task_id).downstream_list}

    assert downstream("harvest_sources") == {"load_postgres"}
    assert downstream("load_postgres") == {"fivetran_sync"}
    assert downstream("fivetran_sync") == {"dbt_run"}
    assert downstream("dbt_run") == {"dbt_test"}
    assert downstream("dbt_test") == {"hightouch_sync"}
    assert downstream("hightouch_sync") == {"refresh_metrics"}
    assert downstream("refresh_metrics") == {"build_dashboard"}


def test_dag_does_not_backfill(dagbag):
    assert dagbag.dags["gtm_pipeline"].catchup is False


def test_dbt_test_failure_stops_publication(dagbag):
    # refresh_metrics must never run on a dbt_test failure, or the dashboard
    # could publish numbers that failed validation.
    dag = dagbag.dags["gtm_pipeline"]
    assert dag.get_task("refresh_metrics").trigger_rule == "all_success"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_dag.py -v`
Expected: SKIPPED until Airflow is installed, then FAIL on the missing DAG once it is.

- [ ] **Step 3: Write `dags/gtm_pipeline_dag.py`**

```python
"""The full GTM pipeline run, once a day.

harvest -> load Postgres -> Fivetran sync -> dbt run -> dbt test ->
Hightouch sync -> refresh metrics -> rebuild the dashboard.

Every task shells out to a CLI that is independently testable and
independently runnable, so a failure is debuggable outside Airflow.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = os.environ.get("NERDJOY_PROJECT_DIR", "/usr/local/airflow")

default_args = {
    "owner": "nerdjoy",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="gtm_pipeline",
    description="Run the job-search GTM pipeline end to end",
    start_date=datetime(2026, 9, 1),
    schedule="0 13 * * *",
    catchup=False,
    default_args=default_args,
    tags=["gtm", "nerdjoy"],
) as dag:
    harvest_sources = BashOperator(
        task_id="harvest_sources",
        bash_command=f"cd {PROJECT_DIR} && python3 scripts/harvest_sources.py --all || true",
        doc_md="Poll target-company ATS boards. Fail-soft: a dead board never stops the run.",
    )

    load_postgres = BashOperator(
        task_id="load_postgres",
        bash_command=f"cd {PROJECT_DIR} && python3 -m nerdjoy_pipeline.pg_loader",
    )

    fivetran_sync = BashOperator(
        task_id="fivetran_sync",
        bash_command=(
            "curl -sS -X POST --fail "
            "-u \"$FIVETRAN_API_KEY:$FIVETRAN_API_SECRET\" "
            "\"https://api.fivetran.com/v1/connectors/$FIVETRAN_CONNECTOR_ID_POSTGRES/force\""
        ),
        doc_md="Trigger the Postgres connector. HubSpot syncs on its own schedule.",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt test",
        doc_md="Gate. Nothing downstream publishes if the marts fail validation.",
    )

    hightouch_sync = BashOperator(
        task_id="hightouch_sync",
        bash_command=(
            "curl -sS -X POST --fail "
            "-H \"Authorization: Bearer $HIGHTOUCH_API_KEY\" "
            "-H 'Content-Type: application/json' "
            "\"https://api.hightouch.com/api/v1/syncs/$HIGHTOUCH_SYNC_ID_SHEET/trigger\" "
            "-d '{\"fullResync\": false}'"
        ),
    )

    refresh_metrics = BashOperator(
        task_id="refresh_metrics",
        bash_command=(
            f"cd {PROJECT_DIR} && "
            "python3 -m nerdjoy_pipeline.metrics_extract --source bigquery --output metrics.json"
        ),
        doc_md="Runs the anonymization guard. A guard failure exits non-zero and stops the run.",
    )

    build_dashboard = BashOperator(
        task_id="build_dashboard",
        bash_command=f"cd {PROJECT_DIR} && python3 dashboard/build.py",
    )

    (
        harvest_sources
        >> load_postgres
        >> fivetran_sync
        >> dbt_run
        >> dbt_test
        >> hightouch_sync
        >> refresh_metrics
        >> build_dashboard
    )
```

- [ ] **Step 4: Write `requirements.txt` and `Dockerfile` for Astro**

`requirements.txt`:

```
psycopg[binary]>=3.2
requests>=2.32
dbt-core>=1.8
dbt-bigquery>=1.8
google-cloud-bigquery>=3.25
```

`Dockerfile`:

```dockerfile
FROM quay.io/astronomer/astro-runtime:12.1.1

COPY src /usr/local/airflow/src
COPY dbt /usr/local/airflow/dbt
COPY dashboard /usr/local/airflow/dashboard
COPY scripts /usr/local/airflow/scripts

ENV PYTHONPATH=/usr/local/airflow/src:$PYTHONPATH
```

- [ ] **Step 5: HUMAN STEP — Heather starts Astro**

Append to `docs/runbook.md`:

> ## Astro
>
> Local `astro dev` is free and is the honest fallback if the hosted trial lapses.
>
> 1. `brew install astro`
> 2. `cd ~/nerdjoy-pipeline && astro dev start`
> 3. Open localhost:8080, log in with `admin` / `admin`.
> 4. Admin > Variables, or the `.env` file, must carry every secret the DAG reads: `PG_CONNECTION_STRING`, `FIVETRAN_API_KEY`, `FIVETRAN_API_SECRET`, `FIVETRAN_CONNECTOR_ID_POSTGRES`, `HIGHTOUCH_API_KEY`, `HIGHTOUCH_SYNC_ID_SHEET`, `BIGQUERY_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`.
> 5. Copy `scripts/harvest_sources.py` from the job-search repo into `scripts/` here, or drop the harvest task if you prefer to keep the repos separate.
> 6. Trigger `gtm_pipeline` manually. Watch every task go green.
> 7. Capture proof immediately: the graph view with all 8 tasks green, plus one task's log.

- [ ] **Step 6: Run the DAG integrity tests inside the Astro image**

```bash
astro dev bash -c "cd /usr/local/airflow && pytest tests/test_dag.py -v"
```

Expected: 6 passed

- [ ] **Step 7: Capture proof**

Save `docs/proof/astro-dag-success.png` (all 8 tasks green with a timestamp) and `docs/proof/astro-task-log.png`.

- [ ] **Step 8: Commit**

```bash
git add dags Dockerfile requirements.txt tests/test_dag.py docs/runbook.md
git commit -m "feat: add Airflow DAG for full pipeline"
```

---

### Task 14: Honesty audit and full verification

Spec §12 in one runnable pass. This is the gate before anything goes public.

**Files:**
- Create: `scripts/verify_public.py`
- Test: run against the real built artifacts

**Interfaces:**
- Consumes: `build_denylist`, `guard_text` (Task 3); `metrics.json`; `dashboard/dist/index.html`
- Produces: `verify(paths: list[Path], tracker_path) -> list[str]` (violations, empty means clean); `main(argv=None) -> int`

- [ ] **Step 1: Write `scripts/verify_public.py`**

```python
#!/usr/bin/env python3
"""Final gate before anything goes public.

Runs the guard across every artifact that will be published or committed,
and reports every violation at once rather than stopping at the first.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nerdjoy_pipeline.guard import (  # noqa: E402
    GuardViolation,
    build_denylist,
    guard_text,
)

DEFAULT_TARGETS = [
    "metrics.json",
    "dashboard/dist/index.html",
    "dashboard/index.html",
    "dashboard/app.js",
    "dashboard/style.css",
    "README.md",
]
DEFAULT_TRACKER = os.environ.get(
    "TRACKER_PATH", "/Users/heatherbarry/claude-linkedin-assistant/job_tracker.csv"
)


def verify(paths: list[Path], tracker_path: str | Path) -> list[str]:
    denylist = build_denylist(tracker_path)
    violations: list[str] = []
    for path in paths:
        if not path.exists():
            violations.append(f"MISSING: {path}")
            continue
        try:
            guard_text(path.read_text(encoding="utf-8"), denylist, label=str(path))
        except GuardViolation as exc:
            violations.append(str(exc))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify every public artifact")
    parser.add_argument("paths", nargs="*", default=DEFAULT_TARGETS)
    parser.add_argument("--tracker", default=DEFAULT_TRACKER)
    args = parser.parse_args(argv)

    violations = verify([Path(p) for p in args.paths], args.tracker)
    if violations:
        print(f"{len(violations)} violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"All {len(args.paths)} public artifacts are clean.")
    return 0
```

- [ ] **Step 2: Run the full test suite**

```bash
source .venv/bin/activate
pytest -v
```

Expected: every test passes. Record the count.

- [ ] **Step 3: Run the public verification**

```bash
python3 scripts/verify_public.py
```

Expected: `All 6 public artifacts are clean.` Any violation must be fixed by rewriting the copy, never by weakening the guard.

- [ ] **Step 4: Run the honesty audit**

Every tool named on the dashboard's stack list and in the README must have a proof artifact in `docs/proof/`. Check each one:

```bash
ls docs/proof/
```

Required: Fivetran (both connectors), BigQuery (a dataset with the marts), dbt (a `dbt test` pass), Hightouch (both syncs), HubSpot (companies with `referral_score`), Google Sheets (the warm-intro list), Astro (a green DAG run). Any tool without proof must be **removed from the dashboard list and the README**, or moved to a visually distinct roadmap lane labeled as such.

- [ ] **Step 5: Verify the dashboard by hand**

- Open `dashboard/dist/index.html` at 375px width. No horizontal scroll.
- Toggle the OS between light and dark. Both readable.
- Every number matches `metrics.json`.
- Search the rendered page for `—`. Zero hits.

- [ ] **Step 6: Confirm the tracker was never mutated**

```bash
cd /Users/heatherbarry/claude-linkedin-assistant && git status --porcelain job_tracker.csv
```

Expected: **empty output.** Any modification here is a hard failure of the read-only rule; investigate before continuing.

- [ ] **Step 7: Commit**

```bash
cd ~/nerdjoy-pipeline
git add scripts/verify_public.py
git commit -m "feat: add public artifact verification gate"
```

---

### Task 15: Public repo sanitization and README

**Files:**
- Create: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Audit what is about to be public**

```bash
cd ~/nerdjoy-pipeline
git ls-files
```

Read every listed file. Confirm none contains a real company name, contact, resume content, credential, or tracker row. `dbt/seeds/applications_seed.csv`, `metrics.json`, `.env`, and `docs/proof/` must **not** appear. If any does, remove it from the index and add it to `.gitignore` before the first push.

```bash
git ls-files | xargs grep -l -i -E "northwind data|hubspot_token|BEGIN PRIVATE KEY" || echo "clean"
```

Expected: `clean` (HubSpot as a *tool name* in the README is fine; a *token value* is not).

- [ ] **Step 2: Write `README.md`**

No em-dashes. No company names.

```markdown
# nerdjoy // Pipeline

I run my job search like a go-to-market motion, on a real modern data stack.

Target companies are accounts. Hiring managers are leads. Referrals are warm intros.
The application tracker is the CRM. This repo is the engine that runs it, and the
dashboard is the pipeline report.

## The stack

| Layer | Tool |
|---|---|
| Sources | Postgres (application tracker), HubSpot CRM, ATS job boards |
| Ingest | Fivetran connectors |
| Warehouse | BigQuery |
| Transform | dbt Core |
| Activate | Hightouch reverse ETL into HubSpot and a daily targets sheet |
| Orchestrate | Airflow on Astronomer Astro |
| Control plane | A Claude agent that reads the marts and drafts outreach for me to approve |

Every tool listed above is genuinely wired and has run for real. Nothing here is
aspirational.

## What is in this repo

```
src/nerdjoy_pipeline/   Loaders, metrics aggregation, and the anonymization guard
dbt/                    Staging models, funnel and referral-scoring marts, dbt tests
dags/                   The Airflow DAG that runs the whole thing daily
dashboard/              The static dashboard and its guarded build step
scripts/                Seed generation and the public verification gate
```

## Privacy

The engine runs on my real data inside my own accounts. Everything published is an
aggregate. No company names, no contacts, no URLs reach the dashboard or this repo.

That rule is enforced in code, not by review. `src/nerdjoy_pipeline/guard.py` builds a
deny list from the real tracker and fails the build if any name appears in a published
artifact. It also rejects em-dashes, which are a tell of unedited AI text. The metrics
export and the dashboard build both call it, and `scripts/verify_public.py` runs it
across every public file as a final gate.

## Running it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest

cp .env.example .env    # fill in your own credentials
python3 -m nerdjoy_pipeline.metrics_extract --output metrics.json
python3 dashboard/build.py
python3 scripts/verify_public.py
```

## License

MIT
```

- [ ] **Step 3: Verify the README passes the guard**

```bash
python3 scripts/verify_public.py README.md
```

Expected: `All 1 public artifacts are clean.`

- [ ] **Step 4: HUMAN STEP — Heather creates and pushes the repo**

> 1. Create `nerdjoy-pipeline` under `github.com/heatherisland`, public, with no README (this repo has one).
> 2. `git remote add origin git@github.com:heatherisland/nerdjoy-pipeline.git`
> 3. Run `git ls-files` one last time and read the list.
> 4. `git push -u origin main`

Claude must **not** run the push. Confirm with Heather first, per the risky-actions rule.

- [ ] **Step 5: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: add public README"
```

---

### Task 16: Publish the dashboard and draft the reveal post

**Files:**
- Create: `content/reveal-post.md` (gitignored; local only)

- [ ] **Step 1: Publish the dashboard**

```bash
python3 -m nerdjoy_pipeline.metrics_extract --source bigquery --output metrics.json
python3 dashboard/build.py
python3 scripts/verify_public.py
```

Then publish `dashboard/dist/` as an Artifact, or to GitHub Pages from the `dashboard/dist` folder. Capture the live URL.

- [ ] **Step 2: Verify the live page**

Open the public URL on a phone. Confirm: it renders, numbers match, light and dark both work, and no em-dash appears.

- [ ] **Step 3: Draft the reveal post**

Write `content/reveal-post.md`. First person, no em-dashes, no company names. Use the spec §1 hook:

```markdown
GTM Engineers get hired to wire up the revenue stack and automate the funnel.

So I did exactly that, for my own job search.

Target companies are accounts. Hiring managers are leads. Referrals are warm intros.
My application tracker is the CRM. Then I wired the whole thing up the way I would
wire a real revenue stack: Fivetran into BigQuery, dbt for the models, Hightouch
pushing scored audiences back into HubSpot and a daily targets sheet, Airflow on Astro
running it every morning, and a Claude agent reading the marts to draft the outreach.

Here is the system, the integrations, and the pipeline data. Real numbers, no names.

[dashboard link]

Everything on that architecture diagram is genuinely wired. I do not pad a tool stack.
```

- [ ] **Step 4: Guard the post before Heather sees it**

```bash
python3 scripts/verify_public.py content/reveal-post.md
```

Expected: clean. Fix by rewriting, never by weakening the guard.

- [ ] **Step 5: HUMAN STEP — Heather reviews and posts**

Show her the drafted post and the live dashboard URL. She edits and posts it herself. Claude does not post.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete nerdjoy pipeline build"
```

Confirm `content/` is gitignored and the post draft is not in the commit.

---

## Verification Checklist (spec §12 and §14)

- [ ] `pytest` fully green
- [ ] `metrics_extract` output reconciles against a manual tracker sum (467 applications, 379 companies)
- [ ] `dbt test` green on both the seed source and the Fivetran source
- [ ] One full DAG run end to end, all 8 tasks green
- [ ] `scripts/verify_public.py` clean on every public artifact
- [ ] `grep -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+' metrics.json dashboard/dist/index.html README.md` returns nothing
- [ ] Dashboard renders at 375px, light and dark, zero em-dashes
- [ ] Every tool on the diagram has a proof artifact in `docs/proof/`
- [ ] `job_tracker.csv` unmodified (`git status` clean in the job-search repo)
- [ ] `git ls-files` contains no PII, no credentials, no tracker rows
- [ ] Reveal post drafted, guarded, and approved by Heather
