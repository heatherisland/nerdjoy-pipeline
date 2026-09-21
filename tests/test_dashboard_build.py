import json
from pathlib import Path

import pytest

from nerdjoy_pipeline.guard import GuardViolation

from dashboard.build import build_dashboard

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dashboard"


@pytest.fixture
def metrics_file(tmp_path: Path) -> Path:
    payload = {
        "generated_at": "2026-09-20",
        "totals": {"applications": 466, "companies": 378},
        "funnel": {"To Apply": 199, "Applied": 238, "Offer": 0},
        "referrals": {"needed": 124, "outreach_sent": 3, "got_referral": 2,
                      "conversion_pct": 0.8},
        "channels": {"LinkedIn Easy Apply": 81, "LinkedIn": 79},
        "activity": [{"month": "2026-08", "applied": 40}],
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(payload))
    return path


def test_build_writes_index_html(metrics_file: Path, tmp_path: Path, sample_tracker_path: Path):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert out.name == "index.html"
    assert out.exists()


def test_metrics_are_inlined_not_fetched(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    html = out.read_text()
    assert "466" in html
    assert "fetch(" not in html  # no runtime fetch; the page is self-contained


def test_built_html_has_no_em_dash(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert "—" not in out.read_text()


def test_built_html_has_no_denylisted_name(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert "hollowpine" not in out.read_text().lower()


def test_guard_violation_prevents_output(tmp_path: Path, sample_tracker_path: Path):
    leaky = tmp_path / "metrics.json"
    leaky.write_text(json.dumps({"totals": {"applications": 1}, "note": "Hollowpine"}))
    dist = tmp_path / "dist"
    with pytest.raises(GuardViolation):
        build_dashboard(leaky, TEMPLATE_DIR, dist, sample_tracker_path)
    assert not (dist / "index.html").exists()


def test_css_and_js_are_copied(metrics_file: Path, tmp_path: Path, sample_tracker_path: Path):
    dist = tmp_path / "dist"
    build_dashboard(metrics_file, TEMPLATE_DIR, dist, sample_tracker_path)
    assert (dist / "style.css").exists()
    assert (dist / "app.js").exists()


def test_page_declares_a_viewport_for_mobile(
    metrics_file: Path, tmp_path: Path, sample_tracker_path: Path
):
    out = build_dashboard(metrics_file, TEMPLATE_DIR, tmp_path / "dist", sample_tracker_path)
    assert 'name="viewport"' in out.read_text()
