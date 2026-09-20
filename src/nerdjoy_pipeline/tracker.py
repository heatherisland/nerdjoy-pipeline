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
    tracker stores "Email (petra@shovels.ai)" here. Reduce anything holding
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
# source tracker is never modified; these rows are dropped on read, so they reach
# no downstream consumer: metrics, warehouse, CRM or dashboard. Because an
# excluded company never reaches a published artifact, it is also dropped from
# the deny list, which exists only to protect names that could otherwise leak.
EXCLUDED_COMPANIES: frozenset[str] = frozenset({"apply digital"})


def is_excluded(company: str) -> bool:
    """True if this company is withheld from the pipeline entirely."""
    return (company or "").strip().lower() in EXCLUDED_COMPANIES


def read_tracker(path: str | Path) -> list[Application]:
    """Read the tracker into normalized Application records. Never writes."""
    with open(path, "r", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    rows = [r for r in rows if not is_excluded(r.get("Company", ""))]

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
