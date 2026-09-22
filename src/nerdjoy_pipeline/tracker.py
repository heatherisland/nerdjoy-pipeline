"""Read-only reader for job_tracker.csv.

The tracker is the single source of truth and is NEVER mutated by this
pipeline. Every open() here uses mode "r".
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
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


# The tracker is maintained in a spreadsheet that writes M/D/YY, but dates
# entered or repaired by hand arrive as ISO. Both must parse: accepting only
# ISO silently returned None for every real applied_date, which emptied the
# activity chart without any error. Two-digit years resolve via %y, which maps
# 26 to 2026.
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y")


def parse_date(raw: str) -> date | None:
    """Parse the tracker's date formats, returning None if none of them fit."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS[1:]:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def normalize_apply_via(raw: str) -> str:
    """Collapse variants and strip any contact details out of the label.

    Channel labels are published verbatim in metrics.json, and the live
    tracker stores a value like "Email (person@example.com)" here, carrying a
    real address. Reduce anything holding
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


# Companies excluded from the pipeline at Heather's explicit instruction. The
# source tracker is never modified; these rows are dropped on read, so they
# reach no downstream consumer: metrics, warehouse, CRM or dashboard.
#
# The names live in a gitignored file rather than in this source, for the same
# reason as config/agency_channels.txt: an excluded company is a REAL company,
# and hardcoding it here republishes in source the very name the exclusion was
# meant to withhold. That is not hypothetical. One name sat in this file while
# repo_privacy_scan.py reported PASS, because the scan derives its deny list
# from read_tracker, which had already filtered that name out. The scan now
# unions these names back in, so this file staying empty of them is enforced.
EXCLUDED_COMPANIES_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "excluded_companies.txt"
)


@lru_cache(maxsize=1)
def load_excluded_companies(path: str | Path | None = None) -> frozenset[str]:
    """Read the local exclusion list. Missing file yields an empty set."""
    target = Path(path) if path is not None else EXCLUDED_COMPANIES_PATH
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return frozenset()
    return frozenset(
        stripped.lower()
        for line in lines
        if (stripped := line.strip()) and not stripped.startswith("#")
    )


def is_excluded(company: str, excluded: frozenset[str] | None = None) -> bool:
    """True if this company is withheld from the pipeline entirely.

    Pass `excluded` to supply the list explicitly; the default reads the
    gitignored local config, so tests never depend on private data.
    """
    known = load_excluded_companies() if excluded is None else excluded
    return (company or "").strip().lower() in known


def read_tracker(
    path: str | Path, excluded: frozenset[str] | None = None
) -> list[Application]:
    """Read the tracker into normalized Application records. Never writes.

    Pass `excluded` to supply the exclusion list explicitly; the default reads
    the gitignored local config, so tests never depend on private data.
    """
    with open(path, "r", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    known = load_excluded_companies() if excluded is None else excluded
    rows = [r for r in rows if not is_excluded(r.get("Company", ""), known)]

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


# The pipeline covers the search from this date on. Applied to data paths only:
# deny lists and the repo scan must keep reading the full tracker, or a pre-cutoff
# name would silently fall off them.
PIPELINE_START = date(2026, 7, 1)


def in_pipeline_window(apps: list[Application]) -> list[Application]:
    """Keep applications dated on or after PIPELINE_START (applied, else discovered)."""
    return [
        a for a in apps
        if (a.applied_date or a.discovered_date)
        and (a.applied_date or a.discovered_date) >= PIPELINE_START
    ]
