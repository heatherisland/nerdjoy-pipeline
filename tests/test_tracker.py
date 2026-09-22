import os
from datetime import date
from pathlib import Path

import pytest

from nerdjoy_pipeline.tracker import (
    VALID_PRIORITIES,
    VALID_REFERRAL_STATUSES,
    VALID_STATUSES,
    PIPELINE_START,
    Application,
    in_pipeline_window,
    is_excluded,
    normalize_apply_via,
    parse_date,
    read_tracker,
)


def test_reads_every_row(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert len(apps) == 10
    assert all(isinstance(a, Application) for a in apps)


def test_does_not_mutate_the_tracker(sample_tracker_path: Path):
    before_bytes = sample_tracker_path.read_bytes()
    before_mtime = os.stat(sample_tracker_path).st_mtime_ns
    read_tracker(sample_tracker_path)
    assert sample_tracker_path.read_bytes() == before_bytes
    assert os.stat(sample_tracker_path).st_mtime_ns == before_mtime


def test_every_status_is_canonical(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert {a.status for a in apps} <= VALID_STATUSES


def test_every_priority_is_canonical(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert {a.priority for a in apps} <= VALID_PRIORITIES


def test_dirty_referral_needed_date_becomes_false(sample_tracker_path: Path):
    # Everwake Labs has the literal string "2026-08-01" in Referral Needed.
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Everwake Labs")
    assert app.referral_needed is False


def test_dirty_referral_status_falls_back_to_not_needed(sample_tracker_path: Path):
    # Foxglove AI has the out-of-domain value "NO" in Referral Status.
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Foxglove AI")
    assert app.referral_status == "Not Needed"
    assert app.referral_status in VALID_REFERRAL_STATUSES


def test_referral_needed_yes_parses_true(sample_tracker_path: Path):
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Acme Data Co")
    assert app.referral_needed is True


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Company Site", "Company Site"),
        ("Company site", "Company Site"),
        ("Company Website", "Company Site"),
        ("Company", "Company Site"),
        ("LinkedIn Easy Apply", "LinkedIn Easy Apply"),
        ("Greenhouse", "Greenhouse"),
        ("", "Unknown"),
        ("   ", "Unknown"),
        # The live tracker embeds a real address in this column.
        ("Email (dana@northwind.invalid)", "Email"),
        ("dana@northwind.invalid", "Email"),
    ],
)
def test_normalize_apply_via(raw: str, expected: str):
    assert normalize_apply_via(raw) == expected


def test_normalize_apply_via_never_returns_an_address():
    for raw in ("Email (dana@northwind.invalid)", "someone@example.com", "Referral (a@b.co)"):
        assert "@" not in normalize_apply_via(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-08-01", date(2026, 8, 1)),
        ("", None),
        ("   ", None),
        ("not a date", None),
    ],
)
def test_parse_date(raw: str, expected):
    assert parse_date(raw) == expected


def test_applied_date_parsed(sample_tracker_path: Path):
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Acme Data Co")
    assert app.applied_date == date(2026, 8, 1)


def test_missing_applied_date_is_none(sample_tracker_path: Path):
    app = next(a for a in read_tracker(sample_tracker_path) if a.company == "Cindergrid")
    assert app.applied_date is None


def test_excluded_company_never_enters_the_pipeline(tmp_path):
    """Excluded rows are dropped on read; the source file is never modified."""
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "Company,Role,Status,Priority,Referral Needed,Referral Status,"
        "Apply Via,Applied Date,Discovered Date\n"
        "Vantablack Labs,Architect,Offer,HIGH,NO,Not Needed,Company Site,,\n"
        "Hollowpine,Engineer,Applied,HIGH,NO,Not Needed,Greenhouse,,\n",
        encoding="utf-8",
    )
    before = csv_path.read_bytes()
    apps = read_tracker(csv_path, excluded=frozenset({"vantablack labs"}))
    assert [a.company for a in apps] == ["Hollowpine"]
    assert csv_path.read_bytes() == before


def test_is_excluded_is_case_insensitive():
    excluded = frozenset({"vantablack labs"})
    assert is_excluded("VANTABLACK LABS", excluded)
    assert is_excluded("  Vantablack Labs  ", excluded)
    assert not is_excluded("Vantablack Labs Systems", excluded)


def test_parse_date_accepts_the_us_slash_format_the_tracker_actually_writes():
    """The live tracker stores M/D/YY, not ISO. Parsing only ISO silently
    dropped all 252 applied dates and left the activity chart empty."""
    from datetime import date

    from nerdjoy_pipeline.tracker import parse_date

    assert parse_date("9/7/26") == date(2026, 9, 7)
    assert parse_date("12/25/26") == date(2026, 12, 25)
    assert parse_date("7/9/26") == date(2026, 7, 9)


def test_parse_date_still_accepts_iso():
    from datetime import date

    from nerdjoy_pipeline.tracker import parse_date

    assert parse_date("2026-09-07") == date(2026, 9, 7)


def test_parse_date_rejects_junk():
    from nerdjoy_pipeline.tracker import parse_date

    assert parse_date("") is None
    assert parse_date("not a date") is None
    assert parse_date("13/45/99") is None


def test_activity_timeseries_is_populated_from_the_real_tracker_format():
    from nerdjoy_pipeline.metrics import activity_timeseries
    from nerdjoy_pipeline.tracker import Application, parse_date

    apps = [
        Application(
            company="Acme", role="r", status="Applied", priority="HIGH",
            referral_needed=False, referral_status="", apply_via="LinkedIn",
            applied_date=parse_date("9/7/26"), discovered_date=None,
        ),
        Application(
            company="Beta", role="r", status="Applied", priority="HIGH",
            referral_needed=False, referral_status="", apply_via="LinkedIn",
            applied_date=parse_date("8/14/26"), discovered_date=None,
        ),
    ]
    series = activity_timeseries(apps)
    assert series == [{"month": "2026-08", "applied": 1}, {"month": "2026-09", "applied": 1}]


def _app(applied, discovered):
    return Application(
        company="Example Corp", role="Engineer", status="Applied", priority="LOW",
        referral_needed=False, referral_status="Not Needed", apply_via="Unknown",
        applied_date=applied, discovered_date=discovered,
    )


def test_pipeline_window_uses_applied_then_discovered_date():
    kept = in_pipeline_window([
        _app(date(2026, 7, 1), date(2026, 6, 1)),   # applied on the cutoff: kept
        _app(date(2026, 6, 30), date(2026, 7, 5)),  # applied before: dropped
        _app(None, date(2026, 7, 2)),               # no applied, discovered after: kept
        _app(None, date(2026, 6, 2)),               # no applied, discovered before: dropped
        _app(None, None),                           # undated: dropped
    ])
    assert [(a.applied_date, a.discovered_date) for a in kept] == [
        (date(2026, 7, 1), date(2026, 6, 1)),
        (None, date(2026, 7, 2)),
    ]
    assert PIPELINE_START == date(2026, 7, 1)
