from pathlib import Path

import pytest

from nerdjoy_pipeline.hubspot_loader import (
    TargetCompany,
    parse_target_companies,
    to_hubspot_properties,
    upsert_companies,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_targets.md"


class FakeClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict) -> dict:
        self.calls.append((url, json))
        return {"id": str(len(self.calls))}


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


def test_upsert_posts_once_per_company():
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
