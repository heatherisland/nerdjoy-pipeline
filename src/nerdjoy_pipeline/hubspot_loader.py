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


def to_hubspot_properties(company: TargetCompany) -> dict[str, str]:
    return {
        "name": company.name,
        "description": company.why_fit,
        "lifecyclestage": "opportunity",
        "ats_platform": company.ats,
        "ats_slug": company.slug,
        "target_domain": company.domain,
        "stage_size": company.stage_size,
    }


def upsert_companies(companies: list[TargetCompany], client) -> int:
    """POST each company. `client` needs a post(url, json) -> dict method."""
    for company in companies:
        client.post(COMPANIES_ENDPOINT, {"properties": to_hubspot_properties(company)})
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load target companies into HubSpot")
    parser.add_argument(
        "--targets",
        default=os.environ.get(
            "TARGET_COMPANIES_PATH",
            "/Users/heatherbarry/claude-linkedin-assistant/resumes/target_companies.md",
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
