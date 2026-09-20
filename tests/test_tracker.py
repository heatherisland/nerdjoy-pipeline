import os
from datetime import date
from pathlib import Path

import pytest

from nerdjoy_pipeline.tracker import (
    VALID_PRIORITIES,
    VALID_REFERRAL_STATUSES,
    VALID_STATUSES,
    Application,
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
        ("Email (petra@shovels.ai)", "Email"),
        ("petra@shovels.ai", "Email"),
    ],
)
def test_normalize_apply_via(raw: str, expected: str):
    assert normalize_apply_via(raw) == expected


def test_normalize_apply_via_never_returns_an_address():
    for raw in ("Email (petra@shovels.ai)", "someone@example.com", "Referral (a@b.co)"):
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
