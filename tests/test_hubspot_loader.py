from pathlib import Path

import pytest

from nerdjoy_pipeline.hubspot_loader import (
    TargetCompany,
    parse_target_companies,
    to_hubspot_properties,
    upsert_companies,
    web_domain,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_targets.md"


class FakeClient:
    """Models a HubSpot portal: search finds existing records, post creates.

    `existing` maps a lowercased domain or name to a record id. A search for a
    known key returns that record, which is what makes the second run of an
    idempotent loader update instead of create.
    """

    def __init__(self, existing: dict[str, str] | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.patches: list[tuple[str, dict]] = []
        self.existing = dict(existing or {})
        self._next_id = 1000

    def post(self, url: str, json: dict) -> dict:
        if url.endswith("/search"):
            value = json["filterGroups"][0]["filters"][0]["value"].strip().lower()
            found = self.existing.get(value)
            return {"results": [{"id": found}] if found else []}
        self.calls.append((url, json))
        self._next_id += 1
        new_id = str(self._next_id)
        props = json.get("properties", {})
        for key in ("domain", "name"):
            if props.get(key):
                self.existing[props[key].strip().lower()] = new_id
        return {"id": new_id}

    def patch(self, url: str, json: dict) -> dict:
        self.patches.append((url, json))
        return {"id": url.rsplit("/", 1)[-1]}


def test_parses_every_table_row():
    companies = parse_target_companies(FIXTURE)
    assert len(companies) == 3
    assert {c.name for c in companies} == {"Acme Data Co", "Borealis Systems", "Cindergrid"}


def test_skips_header_and_separator_rows():
    companies = parse_target_companies(FIXTURE)
    assert all(c.name not in {"Company", "---"} for c in companies)


def test_captures_every_column():
    company = next(c for c in parse_target_companies(FIXTURE) if c.name == "Acme Data Co")
    assert company.why_fit == "Reverse ETL and warehouse activation"
    assert company.stage_size == "Series C, ~250"
    assert company.ats == "Greenhouse"
    assert company.slug == "acmedata"
    assert company.board_url == "https://example.invalid/acmedata"


def test_captures_the_domain_section():
    companies = parse_target_companies(FIXTURE)
    acme = next(c for c in companies if c.name == "Acme Data Co")
    cinder = next(c for c in companies if c.name == "Cindergrid")
    assert acme.domain == "Domain 1 - MarTech Data Infrastructure & Integrations"
    assert cinder.domain == "Domain 2 - Customer Data Platforms"


def test_domain_labels_carry_no_em_dash():
    # Section headings in the source use an em-dash; parsing must strip it so
    # the value is safe if it ever reaches an outgoing surface.
    for company in parse_target_companies(FIXTURE):
        assert "—" not in company.domain


def test_hubspot_properties_shape():
    company = TargetCompany(
        name="Acme Data Co",
        why_fit="Reverse ETL",
        stage_size="Series C, ~250",
        ats="Greenhouse",
        slug="acmedata",
        board_url="https://example.invalid/acmedata",
        domain="Domain 1 - MarTech",
    )
    props = to_hubspot_properties(company)
    assert props["name"] == "Acme Data Co"
    assert props["ats_platform"] == "Greenhouse"
    assert props["target_domain"] == "Domain 1 - MarTech"
    assert all(isinstance(v, str) for v in props.values())


def test_upsert_creates_once_per_company_on_empty_portal():
    companies = parse_target_companies(FIXTURE)
    client = FakeClient()
    count = upsert_companies(companies, client)
    assert count == 3
    assert len(client.calls) == 3


def test_upsert_targets_the_companies_endpoint():
    client = FakeClient()
    upsert_companies(parse_target_companies(FIXTURE), client)
    url, payload = client.calls[0]
    assert url.endswith("/crm/v3/objects/companies")
    assert "properties" in payload


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_target_companies(Path("/nonexistent/targets.md"))


def test_upsert_is_idempotent_against_a_populated_portal():
    """Re-running must update, never duplicate.

    This is the defect that mattered: the loader was named upsert_companies
    but only ever POSTed, so a second run against a real portal would have
    created a second copy of every target company.
    """
    companies = parse_target_companies(FIXTURE)
    client = FakeClient()

    first = upsert_companies(companies, client)
    created_first = len(client.calls)

    second = upsert_companies(companies, client)

    assert first == second == len(companies)
    assert created_first == len(companies)
    assert len(client.calls) == created_first, "second run created new records"
    assert len(client.patches) == len(companies), "second run did not update"


def test_upsert_matches_an_existing_record_by_domain():
    """A company already in the portal under its domain is updated, not added."""
    companies = parse_target_companies(FIXTURE)
    target = companies[0]
    client = FakeClient(existing={web_domain(target): "55"})

    upsert_companies([target], client)

    assert client.calls == [], "created a duplicate of an existing company"
    assert len(client.patches) == 1
    assert client.patches[0][0].endswith("/55")


def test_properties_include_domain_for_matching():
    """Without a domain property HubSpot cannot dedupe, which caused the bug."""
    company = parse_target_companies(FIXTURE)[0]
    props = to_hubspot_properties(company)
    assert props.get("domain"), "no domain emitted, so dedupe is impossible"
