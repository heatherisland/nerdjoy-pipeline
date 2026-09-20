from pathlib import Path

from nerdjoy_pipeline.metrics import (
    FUNNEL_ORDER,
    activity_timeseries,
    channel_counts,
    funnel_counts,
    referral_metrics,
    summary,
)
from nerdjoy_pipeline.tracker import Application, read_tracker


def _apps(path: Path):
    return read_tracker(path)


def test_funnel_counts_match_the_fixture(sample_tracker_path: Path):
    counts = funnel_counts(_apps(sample_tracker_path))
    assert counts["To Apply"] == 2
    assert counts["Applied"] == 3
    assert counts["Recruiter Call"] == 1
    assert counts["Phone Screen"] == 1
    assert counts["Offer"] == 1
    assert counts["Rejected"] == 1
    assert counts["Withdrew"] == 1


def test_funnel_counts_include_every_status_zero_filled(sample_tracker_path: Path):
    counts = funnel_counts(_apps(sample_tracker_path))
    assert set(counts) == set(FUNNEL_ORDER)
    assert counts["Onsite"] == 0


def test_funnel_counts_are_in_funnel_order(sample_tracker_path: Path):
    counts = funnel_counts(_apps(sample_tracker_path))
    assert tuple(counts) == FUNNEL_ORDER


def test_funnel_total_reconciles_with_row_count(sample_tracker_path: Path):
    apps = _apps(sample_tracker_path)
    assert sum(funnel_counts(apps).values()) == len(apps)


def test_referral_metrics(sample_tracker_path: Path):
    m = referral_metrics(_apps(sample_tracker_path))
    # Acme, Borealis, Hollowpine, Ironvale carry a literal YES.
    assert m["needed"] == 4
    assert m["outreach_sent"] == 1
    assert m["got_referral"] == 2
    assert m["conversion_pct"] == 50.0


def test_referral_conversion_is_zero_when_none_needed():
    assert referral_metrics([])["conversion_pct"] == 0.0


def test_channel_counts_collapse_case_variants(sample_tracker_path: Path):
    counts = channel_counts(_apps(sample_tracker_path))
    # Company Site + Company site + Company Website all collapse to one key.
    assert counts["Company Site"] == 3


def test_channel_counts_are_descending(sample_tracker_path: Path):
    values = list(channel_counts(_apps(sample_tracker_path)).values())
    assert values == sorted(values, reverse=True)


def test_channel_labels_never_carry_contact_details():
    # The live tracker has "Email (petra@shovels.ai)" in Apply Via, and channel
    # labels are published verbatim in metrics.json. Bucket anything with an
    # address in it rather than letting the guard fail the whole build.
    from nerdjoy_pipeline.tracker import Application

    apps = [
        Application(
            company="Acme Data Co",
            role="Analytics Engineer",
            status="Applied",
            priority="HIGH",
            referral_needed=False,
            referral_status="Not Needed",
            apply_via="Email (petra@shovels.ai)",
            applied_date=None,
            discovered_date=None,
        )
    ]
    counts = channel_counts(apps)
    assert counts == {"Email": 1}
    assert "@" not in "".join(counts)


def test_activity_timeseries_is_ascending_by_month(sample_tracker_path: Path):
    series = activity_timeseries(_apps(sample_tracker_path))
    months = [e["month"] for e in series]
    assert months == sorted(months)
    assert all(len(str(m)) == 7 for m in months)


def test_activity_timeseries_counts_only_applied_dates(sample_tracker_path: Path):
    series = activity_timeseries(_apps(sample_tracker_path))
    # 8 of 10 fixture rows carry an Applied Date.
    assert sum(int(e["applied"]) for e in series) == 8


def test_summary_has_no_company_names(sample_tracker_path: Path):
    import json

    payload = json.dumps(summary(_apps(sample_tracker_path)))
    for name in ("Acme", "Hollowpine", "Borealis", "Foxglove"):
        assert name.lower() not in payload.lower()


def test_summary_reports_totals(sample_tracker_path: Path):
    s = summary(_apps(sample_tracker_path))
    assert s["totals"]["applications"] == 10
    assert s["totals"]["companies"] == 10


def _chan(apply_via: str) -> Application:
    return Application(
        company="X", role="Y", status="Applied", priority="LOW",
        referral_needed=False, referral_status="Not Needed",
        apply_via=apply_via, applied_date=None, discovered_date=None,
    )


def test_agency_channels_are_generalized():
    """Staffing agencies are employers too; publishing them leaks company names."""
    apps = [
        _chan("Aquent"),
        _chan("Robert Half"),
        _chan("Onward Search"),
        _chan("LinkedIn"),
    ]
    assert channel_counts(apps) == {"Staffing Agency": 3, "LinkedIn": 1}


def test_non_agency_channels_are_untouched():
    apps = [_chan("Greenhouse"), _chan("Company Site")]
    assert channel_counts(apps) == {"Company Site": 1, "Greenhouse": 1}
