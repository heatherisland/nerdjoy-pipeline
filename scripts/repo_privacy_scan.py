#!/usr/bin/env python3
"""Fail if any real company name from the tracker is in a git-tracked file.

The guard in nerdjoy_pipeline.guard protects OUTGOING COPY: metrics.json, the
dashboard, the post. Nothing protected the repository itself, and real company
names reached committed source comments, test fixtures and the plan before this
existed. The repo is public, so a name in a code comment is as published as a
name on the dashboard.

Run before every push:  python scripts/repo_privacy_scan.py
Exit 0 = clean, exit 1 = names found (printed with file and term).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from nerdjoy_pipeline.guard import VENDOR_TOOL_NAMES  # noqa: E402
from nerdjoy_pipeline.tracker import (  # noqa: E402
    load_excluded_companies,
    read_tracker,
)

DEFAULT_TRACKER = os.environ.get(
    "TRACKER_PATH", ".local/tracker/job_tracker.csv"
)

# Tracker companies whose names are also ordinary English that this repo must be
# able to write. Same reasoning as VENDOR_TOOL_NAMES in the guard: the company
# IS the word, so banning the string outright would make the docs unwritable,
# and dropping it from the tracker-derived list is the only alternative. Each
# was checked by hand: every occurrence in this repo is the ordinary word.
#   "remote"    - the Location and Type column value on nearly every row.
#   "canonical" - the adjective, as in "canonical status".
#   "ready"     - the adjective, as in "drafted and ready".
#   "real"      - the adjective, as in "real data" and "real company names".
#   "locally"   - the adverb, as in "not installed locally".
ORDINARY_WORD_COMPANIES = frozenset({"remote", "canonical", "ready", "real", "locally"})

ALLOWED = VENDOR_TOOL_NAMES | ORDINARY_WORD_COMPANIES


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=REPO, check=True
    )
    return out.stdout.split()


def main() -> int:
    tracker = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TRACKER
    if not Path(tracker).exists():
        print(f"SKIP: tracker not found at {tracker}")
        return 0

    # read_tracker drops EXCLUDED_COMPANIES before returning, so a name removed
    # that way would be invisible to this scan: the one class of name most likely
    # to have been handled by hand, and so most likely to have been left in source.
    # Union them back in explicitly. This is the check that would have caught
    # a hardcoded exclusion sitting in tracker.py while the scan reported PASS.
    names = {
        a.company.strip().lower()
        for a in read_tracker(tracker)
        if len(a.company.strip()) > 3
    }
    names |= {
        c.strip().lower() for c in load_excluded_companies() if len(c.strip()) > 3
    }
    names -= ALLOWED

    files = tracked_files()
    hits: list[tuple[str, str]] = []
    for rel in files:
        path = REPO / rel
        try:
            low = path.read_text(encoding="utf-8", errors="ignore").lower()
        except (OSError, UnicodeDecodeError):
            continue
        hits.extend((rel, n) for n in names if re.search(rf"\b{re.escape(n)}\b", low))

    if hits:
        print(f"FAIL: {len(hits)} real company name(s) in git-tracked files")
        for rel, name in sorted(hits):
            print(f"   {rel}: {name!r}")
        print("\nReplace with fictional names, or move the data to a gitignored file.")
        return 1

    print(f"PASS: no real company names in {len(files)} tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
