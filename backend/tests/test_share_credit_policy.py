"""New-share AAA policy uses dated issuer evidence; no broker/model calls."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.credit_evidence import Rating, Source, credit_assessment
from backend import purchase_policy as policy
from backend.portfolio_mandate import mandate_purchase_reasons
from backend.tests.test_purchase_policy import inputs


NOW = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)


def rating(grade="AAA(RU)", *, agency="ACRA", subject="issuer-a",
           kind="issuer", at=NOW, status="active", scale="RU_NATIONAL_LONG_TERM"):
    hosts = {"ACRA": "acra-ratings.ru", "EXPERT_RA": "raexpert.ru",
             "NKR": "ratings.ru", "NRA": "ra-national.ru"}
    proof = Source("synthetic-rating", "https://" + hosts[agency] + "/synthetic-review",
                   (at - timedelta(days=1)).isoformat(), at.isoformat(),
                   (at + timedelta(days=1)).isoformat(), "synthetic-review")
    return Rating(agency, scale, grade, kind, subject, status, "stable", proof)


def assessed(rows, *, kind="share", issuer="issuer-a", at=NOW):
    return credit_assessment(rows, issuer_id=issuer, instrument_id="new", at=at,
                             bond=kind == "bond")


@pytest.mark.parametrize("agency,grade", [
    ("ACRA", "AAA(RU)"), ("EXPERT_RA", "ruAAA"),
    ("NKR", "AAA.ru"), ("NRA", "AAA|ru|"),
])
def test_verified_current_national_aaa_is_admitted_as_credit_constraint(agency, grade):
    credit = assessed([rating(grade, agency=agency)])
    assert not policy.credit_reasons(credit, "share")


@pytest.mark.parametrize("grade", ["AA+(RU)", "AA(RU)", "A(RU)", "BBB(RU)"])
def test_share_grade_below_aaa_is_blocked_even_above_bond_floor(grade):
    assert "share_issuer_aaa_required" in policy.credit_reasons(
        assessed([rating(grade)]), "share")


def test_another_agencys_lower_rating_cannot_be_averaged_away():
    credit = assessed([rating(), rating("ruAA+", agency="EXPERT_RA")])
    assert "share_issuer_aaa_required" in policy.credit_reasons(credit, "share")


@pytest.mark.parametrize("change", ["expired", "withdrawn", "wrong_issuer", "wrong_scale", "issue_only"])
def test_unusable_aaa_never_substitutes_for_a_current_issuer_rating(change):
    value = rating()
    if change == "expired":
        value = replace(value, source=replace(value.source, expires_at=NOW.isoformat()))
    elif change == "withdrawn":
        value = replace(value, status="withdrawn")
    elif change == "wrong_issuer":
        value = replace(value, subject_id="different-issuer")
    elif change == "wrong_scale":
        value = replace(value, scale="GLOBAL_LONG_TERM")
    else:
        value = replace(value, subject_kind="issue", subject_id="new")
    reasons = policy.credit_reasons(assessed([value]), "share")
    assert "issuer_rating_required" in reasons
    assert "share_issuer_aaa_required" in reasons


def test_latest_downgrade_or_withdrawal_cannot_resurrect_previous_aaa():
    old = rating(at=NOW - timedelta(hours=1))
    for latest in (rating("AA+(RU)"), rating(status="withdrawn")):
        reasons = policy.credit_reasons(assessed([old, latest]), "share")
        assert "share_issuer_aaa_required" in reasons


def test_simultaneous_conflicting_agency_records_block_new_stock():
    reasons = policy.credit_reasons(assessed([rating(), rating("AA+(RU)")]), "share")
    assert "rating_evidence_incomplete_or_conflicting" in reasons
    assert "share_issuer_aaa_required" in reasons


def test_new_share_check_applies_to_legacy_config_without_rewriting_mandate():
    data = inputs()
    data["credit"] = assessed([rating(at=data["now"])], at=data["now"])
    result = policy.assess_purchase(**data)
    assert result["constraints_passed"]
    assert not result["automatic_order"]
    assert result["expected_return"] is None
    assert result["rating_rule"]["share_issuer_minimum_grade"] == "AAA"
    data["credit"] = assessed([rating("BBB(RU)", at=data["now"])], at=data["now"])
    rejected = policy.assess_purchase(**data)
    assert "share_issuer_aaa_required" in rejected["reasons"]
    assert not rejected["constraints_passed"]
    assert "mandate" not in data["config"]


def test_bond_bbb_floor_and_stricter_saved_mandate_remain_independent():
    credit = assessed([rating("BBB(RU)"), rating("BBB(RU)", kind="issue", subject="new")], kind="bond")
    assert not policy.credit_reasons(credit, "bond")
    config = {"mandate": {"asset_mode": "bonds", "account_id": "owned-a",
                          "loss_capacity_percent": "10", "minimum_rating_level": 3}}
    assert "rating_below_owner_mandate" in mandate_purchase_reasons(config, "bond", "owned-a", credit)
    assert config["mandate"]["minimum_rating_level"] == 3
    below = assessed([rating("BBB-(RU)"), rating("BBB-(RU)", kind="issue", subject="new")], kind="bond")
    assert "rating_below_bbb_or_unknown" in policy.credit_reasons(below, "bond")
    assert "share_issuer_aaa_required" not in policy.credit_reasons(below, "bond")


def test_aaa_still_requires_fresh_verified_identity_and_other_purchase_constraints():
    data = inputs()
    data["credit"] = assessed([rating(at=data["now"])], at=data["now"])
    data["identity"]["source"]["expires_at"] = data["now"].isoformat()
    result = policy.assess_purchase(**data)
    assert "candidate_identity_unverified" in result["reasons"]
    assert not result["constraints_passed"]
