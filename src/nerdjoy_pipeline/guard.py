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
# its own. Splitting a name like "Northwind Data" or "Acme (a Hollowpine Company)"
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
    # public artifacts need. The full name always stays on the deny list, so the
    # real company is still blocked; only the reusable fragment is dropped. The
    # names themselves are deliberately not listed here: this file is committed,
    # and naming them would leak exactly what the deny list protects.
    "analytics", "aria", "code", "list", "main", "privacy", "search", "revenue",
    "blend", "infinite", "motion", "staffing", "distinct", "family", "from",
    "workday", "brand", "center", "outcome", "right", "short", "space", "unit",
    "customer", "edge", "answer", "half", "model", "pivot",
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
    "outreach", "revenue", "revenue.io", "real", "locally", "one", "ready",
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
    from stays on the list, so "Northwind Data" is still blocked while the word
    "data" stays usable in ordinary prose.
    """
    terms: set[str] = set()
    for app in read_tracker(tracker_path):
        name = app.company.strip()
        if len(name) < _MIN_TERM_LENGTH:
            continue
        terms.add(name.lower())
        # A parenthetical is a descriptor, not identity: "Undisclosed (LinkedIn
        # partner)" is already anonymized, and "Quillmoor Search (Staffing)" is
        # identified by "Quillmoor Search". Indexing their qualifier words would
        # protect nothing while banning ordinary vocabulary. The full name stays
        # on the list; only the parenthetical is skipped when splitting words.
        name = re.sub(r"\([^)]*\)", " ", name)
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
            if not re.search(rf"(?<!\w){re.escape(term)}(?!\w)", haystack):
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
