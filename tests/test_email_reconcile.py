"""Tests for email_reconcile. Only synthetic example data: never real names.

The reconcile fixture tracker below is written to tmp_path per test, never
the real tracker.
"""
from pathlib import Path

from nerdjoy_pipeline.email_reconcile import (
    TRACKER_FIELDS,
    format_as_csv_rows,
    parse_application_email,
    reconcile,
)

FIXTURE_HEADER = (
    "Priority,Company,Role,Location,Type,Salary,Status,Applied Date,"
    "Next Action,URL,Notes,Discovered Date,Referral Needed,Referral Status,"
    "Referral Deadline,Apply Via\n"
)


def _write_tracker(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "job_tracker.csv"
    path.write_text(FIXTURE_HEADER + rows, encoding="utf-8")
    return path


# --- parse_application_email: one ATS pattern per test -----------------


def test_greenhouse_pattern_extracts_company_and_applied_signal():
    result = parse_application_email(
        sender="careers@greenhouse-mail.io",
        subject="Thank you for applying to Example Corp!",
        snippet_or_body="Thank you for applying to Example Corp. We have received your application.",
        date="2026-09-01",
    )
    assert result == {
        "company": "Example Corp",
        "role": None,
        "status_signal": "Applied",
        "date": "2026-09-01",
        "apply_via": "Greenhouse",
    }


def test_greenhouse_io_domain_variant_also_matches():
    result = parse_application_email(
        sender="no-reply@boards.greenhouse.io",
        subject="Your application to Example Corp",
        snippet_or_body="We have received your application.",
        date="2026-09-01",
    )
    assert result is not None
    assert result["company"] == "Example Corp"
    assert result["apply_via"] == "Greenhouse"


def test_lever_pattern_extracts_company_and_applied_signal():
    result = parse_application_email(
        sender="no-reply@hire.lever.co",
        subject="Thank you for applying to Acme Inc!",
        snippet_or_body="Thanks for applying! We'll be in touch.",
        date="2026-09-02",
    )
    assert result["company"] == "Acme Inc"
    assert result["status_signal"] == "Applied"
    assert result["apply_via"] == "Lever"


def test_ashby_pattern_extracts_company():
    result = parse_application_email(
        sender="notify@ashbyhq.com",
        subject="Your application to Widget Co",
        snippet_or_body="We have received your application.",
        date="2026-09-03",
    )
    assert result["company"] == "Widget Co"
    assert result["apply_via"] == "Ashby"
    assert result["status_signal"] == "Applied"


def test_workday_pattern_extracts_company_and_rejected_signal():
    result = parse_application_email(
        sender="noreply@myworkday.com",
        subject="Update on your application to Northwind Systems",
        snippet_or_body=(
            "After careful review, we have decided not to move forward "
            "with your application at this time."
        ),
        date="2026-09-04",
    )
    assert result["company"] == "Northwind Systems"
    assert result["apply_via"] == "Workday"
    assert result["status_signal"] == "Rejected"


def test_generic_for_role_at_company_pattern_extracts_both():
    result = parse_application_email(
        sender="jobs@example.com",
        subject="Your application for Data Analyst at Quillmoor Labs",
        snippet_or_body="Thank you for applying.",
        date="2026-09-05",
    )
    assert result["company"] == "Quillmoor Labs"
    assert result["role"] == "Data Analyst"
    assert result["status_signal"] == "Applied"
    assert "apply_via" not in result


def test_generic_for_role_dash_company_pattern_extracts_both():
    result = parse_application_email(
        sender="jobs@example.com",
        subject="Your application for Software Engineer - Cascade Robotics",
        snippet_or_body="We have decided to move forward with other candidates.",
        date="2026-09-06",
    )
    assert result["company"] == "Cascade Robotics"
    assert result["role"] == "Software Engineer"
    assert result["status_signal"] == "Rejected"


def test_em_dash_variant_of_generic_pattern_also_matches():
    result = parse_application_email(
        sender="jobs@example.com",
        subject="Your application for Support Engineer — Fictional Co",
        snippet_or_body="Application received.",
        date="2026-09-06",
    )
    assert result["company"] == "Fictional Co"
    assert result["role"] == "Support Engineer"


def test_rejection_language_variants_are_detected():
    for phrase in (
        "we are not moving forward with your application",
        "we have decided not to proceed with your candidacy",
        "we will not be moving forward at this time",
    ):
        result = parse_application_email(
            sender="jobs@example.com",
            subject="Your application to Sample Holdings",
            snippet_or_body=phrase,
            date="2026-09-06",
        )
        assert result["status_signal"] == "Rejected", phrase


# --- no confident match --------------------------------------------------


def test_unrelated_email_returns_none():
    result = parse_application_email(
        sender="newsletter@random.example.com",
        subject="Check out our new features!",
        snippet_or_body="Nothing relevant here.",
        date="2026-09-07",
    )
    assert result is None


def test_ats_domain_with_unparseable_subject_returns_none():
    """A recognized ATS domain alone is not confident enough without a
    company name; the pipeline must not guess one from thin air."""
    result = parse_application_email(
        sender="careers@greenhouse-mail.io",
        subject="Hello there",
        snippet_or_body="Some unrelated text.",
        date="2026-09-08",
    )
    assert result is None


def test_ambiguous_status_language_yields_none_not_a_guess():
    """Confirmation email whose body doesn't confidently signal applied or
    rejected must not be force-guessed into Interview/Offer territory."""
    result = parse_application_email(
        sender="jobs@example.com",
        subject="Your application to Ferngrove Systems",
        snippet_or_body="We wanted to give you an update on your candidacy.",
        date="2026-09-09",
    )
    assert result is not None
    assert result["status_signal"] is None


# --- reconcile: dedup and diff against the tracker ------------------------


def test_reconcile_returns_only_rows_missing_from_tracker(tmp_path):
    tracker_path = _write_tracker(
        tmp_path,
        "HIGH,Example Corp,Analytics Engineer,Remote,Remote,,Applied,2026-08-01,,,,"
        "2026-07-25,NO,Not Needed,,Greenhouse\n",
    )
    matches = [
        {
            "company": "Example Corp",
            "role": "Analytics Engineer",
            "status_signal": "Applied",
            "date": "2026-08-01",
        },
        {
            "company": "New Company",
            "role": "Data Engineer",
            "status_signal": "Applied",
            "date": "2026-09-01",
        },
    ]
    missing = reconcile(matches, str(tracker_path))
    assert len(missing) == 1
    assert missing[0]["Company"] == "New Company"
    assert missing[0]["Role"] == "Data Engineer"
    assert missing[0]["Status"] == "Applied"
    assert missing[0]["Applied Date"] == "2026-09-01"
    assert missing[0]["Discovered Date"] == "2026-09-01"
    assert missing[0]["Priority"] == "LOW"


def test_reconcile_matches_are_case_and_whitespace_insensitive(tmp_path):
    tracker_path = _write_tracker(
        tmp_path,
        "HIGH,Example Corp,Analytics Engineer,Remote,Remote,,Applied,2026-08-01,,,,"
        "2026-07-25,NO,Not Needed,,Greenhouse\n",
    )
    matches = [
        {
            "company": "  EXAMPLE CORP  ",
            "role": " analytics engineer ",
            "status_signal": "Applied",
            "date": "2026-08-01",
        },
    ]
    missing = reconcile(matches, str(tracker_path))
    assert missing == []


def test_reconcile_dedupes_same_key_preferring_known_status(tmp_path):
    tracker_path = _write_tracker(tmp_path, "")
    matches = [
        {
            "company": "New Company",
            "role": "Data Engineer",
            "status_signal": None,
            "date": "2026-09-01",
        },
        {
            "company": "new company",
            "role": "data engineer",
            "status_signal": "Rejected",
            "date": "2026-09-03",
        },
    ]
    missing = reconcile(matches, str(tracker_path))
    assert len(missing) == 1
    assert missing[0]["Status"] == "Rejected"
    assert missing[0]["Applied Date"] == "2026-09-03"


def test_reconcile_never_reads_role_as_empty_string_key_collision(tmp_path):
    """Two different companies with no role parsed must not collide."""
    tracker_path = _write_tracker(tmp_path, "")
    matches = [
        {"company": "Company A", "role": None, "status_signal": "Applied", "date": "2026-09-01"},
        {"company": "Company B", "role": None, "status_signal": "Applied", "date": "2026-09-02"},
    ]
    missing = reconcile(matches, str(tracker_path))
    assert {row["Company"] for row in missing} == {"Company A", "Company B"}


def test_reconcile_roleless_match_falls_back_to_company_only(tmp_path):
    tracker_path = _write_tracker(
        tmp_path,
        "HIGH,Example Corp,Analytics Engineer,Remote,Remote,,Applied,2026-08-01,,,,"
        "2026-07-25,NO,Not Needed,,Greenhouse\n",
    )
    matches = [
        {"company": " example corp ", "role": None, "status_signal": "Applied", "date": "2026-08-01"},
        {"company": "Other Co", "role": None, "status_signal": "Applied", "date": "2026-09-01"},
    ]
    missing = reconcile(matches, str(tracker_path))
    assert [row["Company"] for row in missing] == ["Other Co"]


def test_reconcile_does_not_mutate_the_tracker_file(tmp_path):
    tracker_path = _write_tracker(
        tmp_path,
        "HIGH,Example Corp,Analytics Engineer,Remote,Remote,,Applied,2026-08-01,,,,"
        "2026-07-25,NO,Not Needed,,Greenhouse\n",
    )
    before = tracker_path.read_bytes()
    reconcile([{"company": "New Co", "role": "Eng", "status_signal": None, "date": ""}], str(tracker_path))
    assert tracker_path.read_bytes() == before


# --- format_as_csv_rows ----------------------------------------------------


def test_format_as_csv_rows_header_matches_tracker_exactly():
    csv_text = format_as_csv_rows([])
    header_line = csv_text.splitlines()[0]
    assert header_line == ",".join(TRACKER_FIELDS)


def test_format_as_csv_rows_renders_expected_columns():
    missing = [
        {
            "Priority": "LOW",
            "Company": "New Company",
            "Role": "Data Engineer",
            "Location": "",
            "Type": "",
            "Salary": "",
            "Status": "Applied",
            "Applied Date": "2026-09-01",
            "Next Action": "",
            "URL": "",
            "Notes": "",
            "Discovered Date": "2026-09-01",
            "Referral Needed": "",
            "Referral Status": "",
            "Referral Deadline": "",
            "Apply Via": "Greenhouse",
        }
    ]
    csv_text = format_as_csv_rows(missing)
    lines = csv_text.strip().splitlines()
    assert lines[0] == ",".join(TRACKER_FIELDS)
    assert "New Company" in lines[1]
    assert "Data Engineer" in lines[1]
    assert "Greenhouse" in lines[1]


def test_format_as_csv_rows_handles_missing_optional_fields_as_blank():
    missing = [{"Company": "New Company", "Role": "Data Engineer", "Status": "Applied"}]
    csv_text = format_as_csv_rows(missing)
    lines = csv_text.strip().splitlines()
    assert len(lines[1].split(",")) == len(TRACKER_FIELDS)
