#!/usr/bin/env python3
"""Final gate before anything goes public.

Runs the guard across every artifact that will be published or committed,
and reports every violation at once rather than stopping at the first.
Reporting them all matters: fixing one violation and rediscovering the next
on the following run turns a single audit into several.
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
    "TRACKER_PATH", ".local/tracker/job_tracker.csv"
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


if __name__ == "__main__":
    raise SystemExit(main())
