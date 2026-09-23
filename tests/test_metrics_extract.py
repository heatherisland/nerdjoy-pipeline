import json
from pathlib import Path

import pytest

from nerdjoy_pipeline.guard import GuardViolation
from nerdjoy_pipeline.metrics_extract import export_metrics, main


def test_writes_valid_json(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    export_metrics(sample_tracker_path, out)
    payload = json.loads(out.read_text())
    assert payload["totals"]["applications"] == 10


def test_output_has_required_top_level_keys(sample_tracker_path: Path, tmp_path: Path):
    payload = export_metrics(sample_tracker_path, tmp_path / "m.json")
    assert set(payload) == {"generated_at", "totals", "funnel", "referrals", "channels", "activity"}


def test_generated_at_is_timezone_aware_iso_timestamp(sample_tracker_path: Path, tmp_path: Path):
    from datetime import datetime

    payload = export_metrics(sample_tracker_path, tmp_path / "m.json")
    # A bare date parses as UTC midnight in browsers and shows the previous
    # evening in US time zones, so the offset must be explicit.
    assert datetime.fromisoformat(payload["generated_at"]).tzinfo is not None


def test_output_contains_no_company_names(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    export_metrics(sample_tracker_path, out)
    text = out.read_text().lower()
    for name in ("acme", "hollowpine", "borealis", "foxglove", "junipergate"):
        assert name not in text


def test_output_contains_no_em_dash(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    export_metrics(sample_tracker_path, out)
    assert "—" not in out.read_text()


def test_guard_violation_prevents_writing_the_file(
    sample_tracker_path: Path, tmp_path: Path, monkeypatch
):
    out = tmp_path / "metrics.json"

    def leaky_summary(_apps):
        return {"totals": {"applications": 1, "companies": 1}, "leak": "Hollowpine"}

    monkeypatch.setattr("nerdjoy_pipeline.metrics_extract.summary", leaky_summary)
    with pytest.raises(GuardViolation):
        export_metrics(sample_tracker_path, out)
    assert not out.exists()


def test_does_not_mutate_the_tracker(sample_tracker_path: Path, tmp_path: Path):
    before = sample_tracker_path.read_bytes()
    export_metrics(sample_tracker_path, tmp_path / "m.json")
    assert sample_tracker_path.read_bytes() == before


def test_main_returns_zero_on_success(sample_tracker_path: Path, tmp_path: Path):
    out = tmp_path / "metrics.json"
    code = main(["--tracker", str(sample_tracker_path), "--output", str(out)])
    assert code == 0
    assert out.exists()


def test_main_returns_one_on_guard_violation(
    sample_tracker_path: Path, tmp_path: Path, monkeypatch
):
    def leaky_summary(_apps):
        return {"totals": {"applications": 1, "companies": 1}, "leak": "Hollowpine"}

    monkeypatch.setattr("nerdjoy_pipeline.metrics_extract.summary", leaky_summary)
    code = main(["--tracker", str(sample_tracker_path), "--output", str(tmp_path / "m.json")])
    assert code == 1


def test_payload_from_bigquery_rows_matches_the_tracker_shape():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 467},
        {"metric_name": "companies_total", "metric_value": 379},
        {"metric_name": "funnel_applied", "metric_value": 238},
        {"metric_name": "funnel_to_apply", "metric_value": 199},
        {"metric_name": "referrals_needed", "metric_value": 124},
        {"metric_name": "referrals_got", "metric_value": 2},
        {"metric_name": "referral_conversion_pct", "metric_value": 1.6},
    ]
    payload = payload_from_bigquery_rows(rows)
    assert payload["totals"]["applications"] == 467
    assert payload["totals"]["companies"] == 379
    assert payload["funnel"]["Applied"] == 238
    assert payload["funnel"]["To Apply"] == 199
    assert payload["referrals"]["needed"] == 124
    assert payload["referrals"]["conversion_pct"] == 1.6


def test_bigquery_payload_has_no_names():
    import json

    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 1},
        {"metric_name": "companies_total", "metric_value": 1},
    ]
    text = json.dumps(payload_from_bigquery_rows(rows))
    assert "hollowpine" not in text.lower()


def test_unknown_metric_names_are_ignored():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 5},
        {"metric_name": "companies_total", "metric_value": 5},
        {"metric_name": "some_future_metric", "metric_value": 9},
    ]
    payload = payload_from_bigquery_rows(rows)
    assert payload["totals"]["applications"] == 5
    assert "some_future_metric" not in str(payload["funnel"])


def test_crm_metrics_reach_the_payload_with_their_denominator():
    """The CRM loop only earns its place on the diagram if it reaches the page.

    coverage_pct must travel with opportunity_pct: the rate is over known
    companies only, and publishing it alone would imply it describes them all.
    """
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 460},
        {"metric_name": "companies_total", "metric_value": 378},
        {"metric_name": "crm_known_companies", "metric_value": 128},
        {"metric_name": "crm_coverage_pct", "metric_value": 33.9},
        {"metric_name": "crm_opportunity_pct", "metric_value": 16.4},
    ]
    payload = payload_from_bigquery_rows(rows)
    assert payload["crm"]["known_companies"] == 128
    assert payload["crm"]["coverage_pct"] == 33.9
    assert payload["crm"]["opportunity_pct"] == 16.4


def test_crm_block_is_absent_when_the_mart_has_no_crm_metrics():
    """The tracker source has no CRM data, so the block must not appear empty."""
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 5},
        {"metric_name": "companies_total", "metric_value": 5},
    ]
    payload = payload_from_bigquery_rows(rows)
    assert "crm" not in payload


def test_channel_rows_populate_the_channels_block():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 460},
        {"metric_name": "companies_total", "metric_value": 378},
    ]
    channels = [
        {"channel": "Company Site", "application_count": 127},
        {"channel": "LinkedIn", "application_count": 79},
        {"channel": "Staffing Agency", "application_count": 24},
    ]
    payload = payload_from_bigquery_rows(rows, channel_rows=channels)
    assert payload["channels"]["Company Site"] == 127
    assert payload["channels"]["Staffing Agency"] == 24
    assert list(payload["channels"])[0] == "Company Site"


def test_channels_block_is_empty_when_no_channel_rows_are_supplied():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    payload = payload_from_bigquery_rows(
        [{"metric_name": "applications_total", "metric_value": 1}]
    )
    assert payload["channels"] == {}


def test_outreach_sent_comes_through_the_mart():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [
        {"metric_name": "applications_total", "metric_value": 460},
        {"metric_name": "referrals_needed", "metric_value": 122},
        {"metric_name": "referrals_outreach_sent", "metric_value": 4},
    ]
    payload = payload_from_bigquery_rows(rows)
    assert payload["referrals"]["outreach_sent"] == 4


def test_activity_rows_populate_the_activity_block():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    rows = [{"metric_name": "applications_total", "metric_value": 460}]
    activity = [
        {"month": "2026-07", "applied_count": 47},
        {"month": "2026-08", "applied_count": 3},
        {"month": "2026-09", "applied_count": 199},
    ]
    payload = payload_from_bigquery_rows(rows, activity_rows=activity)
    assert payload["activity"] == [
        {"month": "2026-07", "applied": 47},
        {"month": "2026-08", "applied": 3},
        {"month": "2026-09", "applied": 199},
    ]


def test_activity_block_is_empty_when_no_activity_rows_are_supplied():
    from nerdjoy_pipeline.metrics_extract import payload_from_bigquery_rows

    payload = payload_from_bigquery_rows(
        [{"metric_name": "applications_total", "metric_value": 1}]
    )
    assert payload["activity"] == []
