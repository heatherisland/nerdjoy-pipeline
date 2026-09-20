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
