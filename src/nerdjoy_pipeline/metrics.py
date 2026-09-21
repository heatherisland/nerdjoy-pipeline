"""Aggregate a list of Applications into anonymized public metrics.

No network. Output contains counts, rates, and time buckets. It never
contains a company or person name.

One exception to purity: the staffing-agency name list is read from a
gitignored local config, because those names are real companies and cannot
be committed to a public repo. The read is cached and tolerates a missing
file, so callers stay deterministic.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path

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


# Staffing agencies are both a channel and an employer in the tracker, so
# publishing them verbatim would disclose real companies applied to. They are
# generalized to one descriptor, which keeps the aggregate and the funnel total
# honest while removing the names. Matched case-insensitively.
#
# The list itself is real company names, so it CANNOT live in this file: the
# repo is public and committing it would leak exactly what the generalization
# exists to hide. It is read from a gitignored local config instead. When the
# file is absent (CI, a fresh clone) the set is empty, which is safe: an
# unrecognized channel is published under its own name only if it reached the
# tracker, and CI runs on the fictional fixture.
AGENCY_CHANNELS_PATH = Path(__file__).resolve().parents[2] / "config" / "agency_channels.txt"
AGENCY_CHANNEL_LABEL = "Staffing Agency"


@lru_cache(maxsize=1)
def load_agency_channels(path: str | Path | None = None) -> frozenset[str]:
    """Read the local agency name list. Missing file yields an empty set."""
    target = Path(path) if path is not None else AGENCY_CHANNELS_PATH
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return frozenset()
    return frozenset(
        stripped.lower()
        for line in lines
        if (stripped := line.strip()) and not stripped.startswith("#")
    )


def generalize_channel(label: str, agencies: frozenset[str] | None = None) -> str:
    """Collapse agency channel names to a generic descriptor."""
    known = load_agency_channels() if agencies is None else agencies
    return AGENCY_CHANNEL_LABEL if label.strip().lower() in known else label


def channel_counts(
    apps: list[Application], agencies: frozenset[str] | None = None
) -> dict[str, int]:
    """Applications per normalized apply channel, descending by count.

    Re-normalizes the label rather than trusting the field. Channel labels are
    published verbatim in metrics.json, and an Application can be built without
    passing through read_tracker, so the scrub is repeated here. Agency names are
    then generalized so no real company is published as a channel. Pass
    `agencies` to supply that list explicitly; the default reads the gitignored
    local config, so tests never depend on private data.
    """
    known = load_agency_channels() if agencies is None else agencies
    counts = Counter(
        generalize_channel(normalize_apply_via(a.apply_via), known) for a in apps
    )
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
