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
    "TRACKER_PATH", ".local/tracker/job_tracker.csv"
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
