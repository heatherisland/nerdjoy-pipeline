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


def test_generated_at_is_iso_date(sample_tracker_path: Path, tmp_path: Path):
    from datetime import date

    payload = export_metrics(sample_tracker_path, tmp_path / "m.json")
    date.fromisoformat(payload["generated_at"])  # raises if malformed


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
