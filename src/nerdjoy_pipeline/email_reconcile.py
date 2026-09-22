"""Reconcile ATS confirmation/rejection emails against the tracker.

This module never touches Gmail or any network API. It takes ALREADY-FETCHED
email metadata (sender, subject, snippet/body, date) as plain dicts, extracts
a best-guess {company, role, status_signal, date} per message using
sender-domain and subject-line heuristics for common ATS platforms, and diffs
the result against the tracker to find applications that exist in the user's
inbox but are missing from job_tracker.csv.

Like every other reader in this package, the tracker is opened read-only.
Nothing here writes to job_tracker.csv, ever. The CSV this module produces is
for the user to review and hand-paste into the tracker themselves.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from nerdjoy_pipeline.tracker import read_tracker

# Exact column order the tracker CSV uses. Confirmed by reading the real
# job_tracker.csv header row (read-only), not guessed.
TRACKER_FIELDS = [
    "Priority",
    "Company",
    "Role",
    "Location",
    "Type",
    "Salary",
    "Status",
    "Applied Date",
    "Next Action",
    "URL",
    "Notes",
    "Discovered Date",
    "Referral Needed",
    "Referral Status",
    "Referral Deadline",
    "Apply Via",
]

_APPLIED_PHRASES = (
    "thank you for applying",
    "thanks for applying",
    "application received",
    "we have received your application",
    "we've received your application",
)

_REJECTED_PHRASES = (
    "not moving forward",
    "not to move forward",
    "decided not to proceed",
    "decided to move forward with other candidates",
    "other candidates",
    "will not be moving forward",
    "not be moving forward",
    "unable to move forward",
    "pursue other candidates",
)


def _domain_of(sender: str) -> str:
    match = re.search(r"@([\w.-]+)", sender or "")
    return match.group(1).lower() if match else (sender or "").lower()


def _status_signal(text: str) -> str | None:
    low = text.lower()
    if any(p in low for p in _REJECTED_PHRASES):
        return "Rejected"
    if any(p in low for p in _APPLIED_PHRASES):
        return "Applied"
    return None


def _clean_company(raw: str) -> str:
    return raw.strip().strip(".!,\"' ").strip()


# Subject patterns tried in order. Each yields a company (required) and,
# optionally, a role. Patterns are intentionally strict: a subject that does
# not match any of these returns no company, and the caller treats that as
# no confident match rather than guessing.
_SUBJECT_PATTERNS: list[re.Pattern] = [
    # "Your application for {Role} at {Company}"
    re.compile(r"application for (?P<role>.+?) at (?P<company>.+?)$", re.I),
    # "Your application for {Role} — {Company}" / "- {Company}"
    re.compile(r"application for (?P<role>.+?)\s*[—\-]\s*(?P<company>.+?)$", re.I),
    # "Thank you for applying to {Company}" / "Your application to {Company}"
    re.compile(r"appl(?:y|ying|ication) (?:to|at) (?P<company>.+?)$", re.I),
    # "Update on your application to {Company}"
    re.compile(r"update on your application (?:to|at) (?P<company>.+?)$", re.I),
    # "Thank you for applying to {Company}!" already covered above; this
    # catches a bare "{Company} Application Received" shape.
    re.compile(r"^(?P<company>.+?) application received$", re.I),
]


def _extract_from_subject(subject: str) -> tuple[str | None, str | None]:
    subject = (subject or "").strip()
    for pattern in _SUBJECT_PATTERNS:
        m = pattern.search(subject)
        if not m:
            continue
        groups = m.groupdict()
        company = groups.get("company")
        role = groups.get("role")
        if company:
            company = _clean_company(company)
        if role:
            role = _clean_company(role)
        if company:
            return company, (role or None)
    return None, None


# Sender domain fragments recognized as ATS platforms, mapped to a friendly
# apply-via label. Presence of one of these is a strong signal the message is
# ATS-generated, even when the subject alone would be ambiguous.
_ATS_DOMAINS = {
    "greenhouse-mail.io": "Greenhouse",
    "greenhouse.io": "Greenhouse",
    "hire.lever.co": "Lever",
    "lever.co": "Lever",
    "ashbyhq.com": "Ashby",
    "myworkday.com": "Workday",
}


def _apply_via_for_domain(domain: str) -> str | None:
    for fragment, label in _ATS_DOMAINS.items():
        if fragment in domain:
            return label
    return None


def parse_application_email(
    sender: str, subject: str, snippet_or_body: str, date: str
) -> dict | None:
    """Extract {company, role, status_signal, date} from one email.

    Returns None when no pattern matches confidently. status_signal is one
    of "Applied", "Rejected", or None (recognized email, unclear status; the
    user reviews manually rather than the pipeline guessing Interview/Offer).
    """
    domain = _domain_of(sender)
    apply_via = _apply_via_for_domain(domain)

    company, role = _extract_from_subject(subject)

    # Without a company we have nothing worth surfacing. A recognized ATS
    # domain alone, with a subject we can't parse, is still not confident
    # enough: the company name is the load-bearing field for the tracker key.
    if not company:
        return None

    text = f"{subject}\n{snippet_or_body or ''}"
    status_signal = _status_signal(text)

    result = {
        "company": company,
        "role": role,
        "status_signal": status_signal,
        "date": date,
    }
    if apply_via:
        result["apply_via"] = apply_via
    return result


def _raw_key(company: str, role: str) -> str:
    """Same normalization as pg_loader.application_key, for raw strings.

    Duplicated rather than imported because application_key() takes an
    Application dataclass, not bare strings, and email matches never become
    Application instances (they may be missing status/priority/etc).
    """
    raw = f"{(company or '').strip().lower()}|{(role or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dedupe_matches(matches: list[dict]) -> dict[str, dict]:
    """Collapse matches resolving to the same key, preferring a known status."""
    best: dict[str, dict] = {}
    for match in matches:
        key = _raw_key(match.get("company", ""), match.get("role") or "")
        current = best.get(key)
        if current is None:
            best[key] = match
            continue
        # Prefer the one with a known status_signal over an unknown one.
        if current.get("status_signal") is None and match.get("status_signal"):
            best[key] = match
    return best


def reconcile(email_matches: list[dict], tracker_path: str) -> list[dict]:
    """Return email matches whose (company, role) key is missing from the tracker.

    Reads job_tracker.csv read-only via read_tracker(). Never writes to it.
    """
    apps = read_tracker(tracker_path)
    tracker_keys = {_raw_key(a.company, a.role) for a in apps}
    tracker_companies = {(a.company or "").strip().lower() for a in apps}

    deduped = _dedupe_matches(email_matches)

    missing: list[dict] = []
    for key, match in deduped.items():
        if key in tracker_keys:
            continue
        # Most ATS subjects carry no role, and a blank-role key can never equal
        # a tracker key that has one, so fall back to company-only presence.
        if not match.get("role") and (match.get("company") or "").strip().lower() in tracker_companies:
            continue
        role = match.get("role") or ""
        applied_date = match.get("date") or ""
        status = match.get("status_signal") or "Applied"
        missing.append(
            {
                "Priority": "LOW",
                "Company": match.get("company", ""),
                "Role": role,
                "Location": "",
                "Type": "",
                "Salary": "",
                "Status": status,
                "Applied Date": applied_date,
                "Next Action": "",
                "URL": "",
                "Notes": "",
                "Discovered Date": applied_date,
                "Referral Needed": "",
                "Referral Status": "",
                "Referral Deadline": "",
                "Apply Via": match.get("apply_via", ""),
            }
        )
    return missing


def format_as_csv_rows(missing: list[dict]) -> str:
    """Render missing rows as CSV text matching the tracker's exact header.

    Returned as a string; the caller decides whether to print it or write it
    to a gitignored local path. This function never touches job_tracker.csv.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TRACKER_FIELDS)
    writer.writeheader()
    for row in missing:
        writer.writerow({field: row.get(field, "") for field in TRACKER_FIELDS})
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile ATS confirmation/rejection emails against job_tracker.csv. "
            "Never writes to the tracker; prints or writes a review CSV instead."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a JSON file: a list of {sender, subject, snippet, date} objects.",
    )
    parser.add_argument(
        "--tracker",
        default=".local/tracker/job_tracker.csv",
        help="Path to job_tracker.csv. Opened read-only; never written.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Path to write the review CSV, e.g. .local/email_reconcile_output.csv. "
            "If omitted, the CSV is printed to stdout."
        ),
    )
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as fh:
        raw_emails = json.load(fh)

    matches: list[dict] = []
    for email in raw_emails:
        parsed = parse_application_email(
            sender=email.get("sender", ""),
            subject=email.get("subject", ""),
            snippet_or_body=email.get("snippet", ""),
            date=email.get("date", ""),
        )
        if parsed is not None:
            matches.append(parsed)

    missing = reconcile(matches, args.tracker)
    csv_text = format_as_csv_rows(missing)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(csv_text, encoding="utf-8")
        print(
            f"Parsed {len(raw_emails)} email(s), matched {len(matches)}, "
            f"found {len(missing)} row(s) missing from the tracker.",
            file=sys.stderr,
        )
        print(f"Wrote review CSV to {out_path}", file=sys.stderr)
    else:
        print(
            f"Parsed {len(raw_emails)} email(s), matched {len(matches)}, "
            f"found {len(missing)} row(s) missing from the tracker.",
            file=sys.stderr,
        )
        print(csv_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
