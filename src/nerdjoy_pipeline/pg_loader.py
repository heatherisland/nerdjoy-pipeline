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

from nerdjoy_pipeline.metrics import generalize_channel
from nerdjoy_pipeline.tracker import Application, in_pipeline_window, read_tracker

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
    screened        BOOLEAN NOT NULL DEFAULT false,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

# CREATE TABLE IF NOT EXISTS never adds columns to an existing table.
ADD_SCREENED_SQL = (
    "ALTER TABLE applications ADD COLUMN IF NOT EXISTS screened BOOLEAN NOT NULL DEFAULT false"
)

UPSERT_SQL = """
INSERT INTO applications (
    application_key, company, role, status, priority,
    referral_needed, referral_status, apply_via, applied_date, discovered_date,
    screened
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (application_key) DO UPDATE SET
    status          = EXCLUDED.status,
    priority        = EXCLUDED.priority,
    referral_needed = EXCLUDED.referral_needed,
    referral_status = EXCLUDED.referral_status,
    apply_via       = EXCLUDED.apply_via,
    applied_date    = EXCLUDED.applied_date,
    discovered_date = EXCLUDED.discovered_date,
    screened        = EXCLUDED.screened,
    loaded_at       = now()
"""


def application_key(app: Application) -> str:
    """Stable identity for an application: company plus role."""
    raw = f"{app.company.strip().lower()}|{app.role.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def to_row(app: Application, agencies: frozenset[str] | None = None) -> tuple:
    """Build the Postgres row.

    apply_via is generalized HERE, at the boundary, rather than downstream:
    staffing agency names are real companies, and collapsing them only at
    publish time would still have replicated them into BigQuery via Fivetran.
    Everything past this function is cloud infrastructure, so the name must
    not survive the call.
    """
    return (
        application_key(app),
        app.company,
        app.role,
        app.status,
        app.priority,
        app.referral_needed,
        app.referral_status,
        generalize_channel(app.apply_via, agencies),
        app.applied_date,
        app.discovered_date,
        app.screened,
    )


def load_applications(apps: list[Application], conn) -> int:
    """Create the table if needed and upsert every application. Idempotent."""
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.execute(ADD_SCREENED_SQL)
    cur.executemany(UPSERT_SQL, [to_row(a) for a in apps])
    conn.commit()
    return len(apps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the tracker into Postgres")
    parser.add_argument(
        "--tracker",
        default=os.environ.get(
            "TRACKER_PATH", ".local/tracker/job_tracker.csv"
        ),
    )
    args = parser.parse_args(argv)

    # DATABASE_URL is what .env and .env.example define, and what Supabase and
    # most hosts hand you. PG_CONNECTION_STRING is accepted as an alias so an
    # existing environment keeps working.
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("PG_CONNECTION_STRING")
    if not dsn:
        print(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1

    import psycopg  # imported here so the tests never need the driver

    apps = in_pipeline_window(read_tracker(args.tracker))
    with psycopg.connect(dsn) as conn:
        count = load_applications(apps, conn)
    print(f"Upserted {count} applications into Postgres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
