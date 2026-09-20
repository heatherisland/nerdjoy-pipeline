from pathlib import Path

import pytest

from nerdjoy_pipeline.guard import (
    GuardViolation,
    build_denylist,
    check_no_contact_details,
    check_no_denylisted_terms,
    check_no_em_dashes,
    guard_text,
)


def test_denylist_includes_every_company(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    assert "acme data co" in denylist
    assert "hollowpine" in denylist


def test_denylist_excludes_short_generic_tokens(sample_tracker_path: Path):
    # Two-character and shorter tokens would false-positive on ordinary prose.
    denylist = build_denylist(sample_tracker_path)
    assert all(len(term) > 2 for term in denylist)


def test_em_dash_raises():
    with pytest.raises(GuardViolation, match="em-dash"):
        check_no_em_dashes("This is the pipeline — it works.")


def test_clean_text_passes_em_dash_check():
    check_no_em_dashes("This is the pipeline. It works.")


def test_hyphen_and_en_dash_are_allowed():
    # Only U+2014 is banned. Hyphens and en-dashes are ordinary punctuation.
    check_no_em_dashes("well-wired stack, 2026-09-20, pages 3–5")


def test_denylisted_company_raises(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation, match="Hollowpine"):
        check_no_denylisted_terms("We interviewed at Hollowpine last week.", denylist)


def test_denylist_match_is_case_insensitive(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation):
        check_no_denylisted_terms("we interviewed at HOLLOWPINE", denylist)


def test_denylist_match_respects_word_boundaries(sample_tracker_path: Path):
    # "Merge" style substrings must not fire inside unrelated words.
    denylist = {"merge"}
    check_no_denylisted_terms("The models were merged and remerged.", denylist)


def test_generic_corporate_words_are_not_denylisted(sample_tracker_path: Path):
    # Company names contain ordinary English. If "data", "company" and "solutions"
    # land on the deny list, the README of a GTM DATA stack cannot be written.
    denylist = build_denylist(sample_tracker_path)
    for word in ("data", "company", "solutions", "software", "group", "cloud"):
        assert word not in denylist


def test_generic_words_pass_the_guard_in_prose(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    check_no_denylisted_terms(
        "A modern data stack: ingestion, a cloud warehouse, and analytics. "
        "No company names appear anywhere in this repo.",
        denylist,
    )


def test_full_company_name_still_blocked_despite_generic_word(tmp_path: Path):
    # Dropping the token "data" must NOT unprotect "Simon Data" itself.
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "Priority,Company,Role,Location,Type,Salary,Status,Applied Date,Next Action,"
        "URL,Notes,Discovered Date,Referral Needed,Referral Status,Referral Deadline,"
        "Apply Via\n"
        "HIGH,Simon Data,Analyst,Remote,Full-time,,Applied,2026-09-01,,http://x,,"
        "2026-09-01,NO,Not Needed,,Greenhouse\n",
        encoding="utf-8",
    )
    denylist = build_denylist(csv_path)
    assert "data" not in denylist
    assert "simon" in denylist
    with pytest.raises(GuardViolation):
        check_no_denylisted_terms("We spoke with Simon Data.", denylist)


def test_gtm_vocabulary_allowed_but_company_still_protected():
    # "Outreach" and "Revenue.io" are real companies in the tracker AND ordinary
    # GTM words. They stay on the deny list and are separated by context only.
    denylist = {"outreach", "revenue", "revenue.io"}
    check_no_denylisted_terms(
        "The control plane drafts outreach for me. "
        "GTM Engineers wire up the revenue stack.",
        denylist,
    )
    with pytest.raises(GuardViolation):
        check_no_denylisted_terms("Outreach rejected my application.", denylist)


def test_vendor_name_allowed_as_stack_tooling():
    # Hightouch, Fivetran, Airbyte and Greenhouse are companies in the tracker AND
    # tools on the public diagram. The honesty principle requires naming them.
    denylist = {"hightouch", "fivetran", "airbyte"}
    check_no_denylisted_terms(
        "Fivetran lands Postgres into BigQuery. Hightouch syncs the mart to "
        "HubSpot and a Google Sheet. Airbyte is the documented fallback.",
        denylist,
    )


def test_vendor_name_still_blocked_in_application_context():
    # The carve-out must not become a hole. A status word in the same sentence
    # turns a tool mention back into a disclosure about a real application.
    denylist = {"fivetran"}
    with pytest.raises(GuardViolation, match="fivetran"):
        check_no_denylisted_terms(
            "Applied to Fivetran for a Senior Solutions Architect role.", denylist
        )


def test_vendor_carveout_is_per_sentence():
    # A clean tooling sentence must not launder a leak elsewhere in the text.
    denylist = {"hightouch"}
    with pytest.raises(GuardViolation, match="hightouch"):
        check_no_denylisted_terms(
            "Hightouch syncs the mart to HubSpot.\nHightouch rejected me in August.",
            denylist,
        )


def test_non_vendor_company_has_no_carveout():
    # Only the four stack vendors are exempt. Every other tracker name is
    # rejected even in a sentence with no application words at all.
    denylist = {"hollowpine"}
    with pytest.raises(GuardViolation, match="hollowpine"):
        check_no_denylisted_terms("Hollowpine builds data tooling.", denylist)


def test_anonymized_aggregate_text_passes(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    clean = "467 applications, 124 needing referrals. Series C, ~250 employees, martech."
    guard_text(clean, denylist)


def test_guard_text_reports_the_label(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation, match="metrics.json"):
        guard_text("Acme Data Co", denylist, label="metrics.json")


def test_email_address_raises():
    # The live tracker stores "Email (petra@shovels.ai)" in Apply Via, and
    # Apply Via values reach metrics.json through channel_counts.
    with pytest.raises(GuardViolation, match="email"):
        check_no_contact_details("Email (petra@shovels.ai)")


def test_bare_email_raises():
    with pytest.raises(GuardViolation, match="email"):
        check_no_contact_details("reach me at someone@example.com")


def test_phone_number_raises():
    with pytest.raises(GuardViolation, match="phone"):
        check_no_contact_details("call 415-555-0142")


def test_aggregate_text_has_no_contact_details():
    check_no_contact_details("467 applications across 379 companies, 1.6% conversion")


def test_dates_and_versions_are_not_phone_numbers():
    # Guards against a naive digit-run regex firing on ordinary content.
    check_no_contact_details("2026-09-20, version 1.8.2, 100-250 employees")


def test_guard_text_runs_the_contact_check(sample_tracker_path: Path):
    denylist = build_denylist(sample_tracker_path)
    with pytest.raises(GuardViolation, match="email"):
        guard_text("Email (petra@shovels.ai)", denylist, label="metrics.json")
