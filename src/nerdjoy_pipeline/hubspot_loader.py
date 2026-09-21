"""Load target companies from the markdown table into HubSpot's free CRM.

The source file lives in the job-search repo and is never copied here.
HubSpot becomes the CRM of record and a Fivetran source.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HUBSPOT_BASE = "https://api.hubapi.com"
COMPANIES_ENDPOINT = f"{HUBSPOT_BASE}/crm/v3/objects/companies"

_SECTION_RE = re.compile(r"^##\s+(.*)$")
_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")


@dataclass(frozen=True)
class TargetCompany:
    name: str
    why_fit: str
    stage_size: str
    ats: str
    slug: str
    board_url: str
    domain: str


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_target_companies(path: str | Path) -> list[TargetCompany]:
    """Parse the markdown tables under each Domain heading."""
    text = Path(path).read_text(encoding="utf-8")
    companies: list[TargetCompany] = []
    current_domain = ""

    for line in text.splitlines():
        section = _SECTION_RE.match(line)
        if section:
            # Headings use an em-dash; normalize so the value is safe downstream.
            current_domain = section.group(1).replace("—", "-").strip()
            continue

        if not line.startswith("|") or _SEPARATOR_RE.match(line):
            continue

        cells = _split_row(line)
        if len(cells) < 6 or cells[0].lower() == "company":
            continue

        companies.append(
            TargetCompany(
                name=cells[0],
                why_fit=cells[1],
                stage_size=cells[2],
                ats=cells[3],
                slug=cells[4],
                board_url=cells[5],
                domain=current_domain,
            )
        )

    return companies


def web_domain(company: TargetCompany) -> str:
    """Best-effort web domain for a target company, used to dedupe in HubSpot.

    TargetCompany.domain is NOT a web domain: it holds the markdown section
    heading ("Domain 1 - MarTech ..."), and board_url is an ATS host shared by
    every company on that platform (jobs.ashbyhq.com, boards.greenhouse.io), so
    neither can identify a company. The ATS slug is the only per-company handle
    available, so the domain is derived from it. A slug that already contains a
    dot is treated as domain-like and used as is, because appending ".com" to
    "customer.io" would yield the wrong "customerio.com".
    """
    slug = company.slug.strip().lower()
    if not slug:
        return ""
    return slug if "." in slug else f"{slug}.com"


def to_hubspot_properties(company: TargetCompany) -> dict[str, str]:
    return {
        "name": company.name,
        "description": company.why_fit,
        "lifecyclestage": "opportunity",
        "ats_platform": company.ats,
        "ats_slug": company.slug,
        "target_domain": company.domain,
        "stage_size": company.stage_size,
        # HubSpot dedupes on domain. Without it a second run creates a second
        # copy of every company, which is exactly what the original POST-only
        # loader did.
        "domain": web_domain(company),
    }


def _find_company_id(client, prop: str, value: str) -> str | None:
    """Search HubSpot for one company whose `prop` equals `value`."""
    if not value:
        return None
    payload = {
        "filterGroups": [
            {"filters": [{"propertyName": prop, "operator": "EQ", "value": value}]}
        ],
        "limit": 1,
    }
    results = client.post(f"{COMPANIES_ENDPOINT}/search", payload).get("results") or []
    return results[0]["id"] if results else None


def upsert_companies(companies: list[TargetCompany], client) -> int:
    """Create or update each company. Safe to run repeatedly.

    Heather's portal already holds real companies, so this must never blindly
    create: it searches by domain, then by name, and PATCHes a match instead of
    POSTing a duplicate. `client` needs post(url, json) and patch(url, json).

    Returns the number of companies processed, not the number created.
    """
    for company in companies:
        properties = to_hubspot_properties(company)
        existing = _find_company_id(client, "domain", properties.get("domain", ""))
        if existing is None:
            existing = _find_company_id(client, "name", company.name)

        if existing is None:
            client.post(COMPANIES_ENDPOINT, {"properties": properties})
        else:
            client.patch(f"{COMPANIES_ENDPOINT}/{existing}", {"properties": properties})
    return len(companies)


class _RequestsClient:
    def __init__(self, token: str):
        import requests

        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def post(self, url: str, json: dict) -> dict:
        response = self._session.post(url, json=json, timeout=30)
        response.raise_for_status()
        return response.json()

    def patch(self, url: str, json: dict) -> dict:
        response = self._session.patch(url, json=json, timeout=30)
        response.raise_for_status()
        return response.json()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load target companies into HubSpot")
    parser.add_argument(
        "--targets",
        default=os.environ.get(
            "TARGET_COMPANIES_PATH",
            "../claude-linkedin-assistant/resumes/target_companies.md",
        ),
    )
    args = parser.parse_args(argv)

    token = os.environ.get("HUBSPOT_TOKEN")
    if not token:
        print(
            "HUBSPOT_TOKEN is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1

    companies = parse_target_companies(args.targets)
    count = upsert_companies(companies, _RequestsClient(token))
    print(f"Upserted {count} companies into HubSpot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
