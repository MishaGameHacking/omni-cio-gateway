"""Synthetic provider observations; no live broker/model/trading calls."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.credit_evidence import (
    BROKER_RATING_URL, Rating, Source, broker_bond_ratings, credit_assessment,
)

NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)


def raw_rating(**changes):
    return {"agencyName": "АКРА", "ratingLevel": "BBB(RU)",
            "ratingDate": "2026-10-01T00:00:00Z", "forecast": "Стабильный",
            "isUnderWatch": False, **changes}


def normalize(rows, **changes):
    meta = {"uid": "bond-uid", "instrumentType": "bond", "ratings": rows, **changes}
    return broker_bond_ratings(meta, instrument_id="bond-uid", observed_at=NOW.isoformat(), at=NOW)


@pytest.mark.parametrize("agency,grade", [
    ("АКРА", "BBB(RU)"), ("ACRA", "AAA(RU)"), ("Эксперт РА", "ruBBB"),
    ("EXPERT_RA", "ruAA+"), ("НКР", "BBB.ru"), ("NCR", "AA-.ru"),
    ("НРА", "BBB|ru|"), ("NRA", "A+|ru|"),
])
def test_accredited_national_ratings_retain_dated_provider_provenance(agency, grade):
    rows, errors = normalize([raw_rating(agencyName=agency, ratingLevel=grade)])
    assert not errors
    assert len(rows) == 1
    rating = rows[0]
    assert rating.evidence_basis == "t_invest_bond_rating"
    assert rating.subject_kind == "issue" and rating.subject_id == "bond-uid"
    assert rating.source.url == BROKER_RATING_URL
    assert rating.source.published_at != rating.source.checked_at
    assert rating.source.valid(NOW)
    result = credit_assessment(rows, issuer_id=None, instrument_id="bond-uid", at=NOW, bond=True)
    assert result["within_rating_floor"]
    assert result["default_probability"] is None
    assert {row["subject_kind"] for row in result["ratings"]} == {"issue"}


@pytest.mark.parametrize("change", [
    {"agencyName": "Unknown agency"}, {"ratingLevel": "BBB"},
    {"ratingLevel": "ruBBB"}, {"ratingDate": "2027-01-01T00:00:00Z"},
    {"ratingDate": "2024-01-01T00:00:00Z"}, {"ratingDate": "2026-10-01"},
    {"isUnderWatch": "false"}, {"forecast": "unknown"}, {"ratingDate": None},
])
def test_ambiguous_or_stale_provider_facts_fail_closed(change):
    rows, errors = normalize([raw_rating(**change)])
    assert not rows and errors


def test_broker_risk_level_is_not_a_credit_rating():
    rows, errors = broker_bond_ratings({"uid": "bond-uid", "riskLevel": "RISK_LEVEL_LOW"},
        instrument_id="bond-uid", observed_at=NOW.isoformat(), at=NOW)
    assert rows == [] and errors == []
    assert not credit_assessment(rows, issuer_id=None, instrument_id="bond-uid", at=NOW,
                                 bond=True)["has_required_rating"]


def test_bbb_minus_is_observed_but_never_eligible():
    rows, errors = normalize([raw_rating(ratingLevel="BBB-(RU)")])
    assert not errors and rows[0].level() == 9
    result = credit_assessment(rows, issuer_id=None, instrument_id="bond-uid", at=NOW, bond=True)
    assert result["has_required_rating"]
    assert not result["within_rating_floor"]


def test_provider_conflicts_are_order_independent_and_not_averaged():
    rows, _ = normalize([raw_rating(), raw_rating(ratingLevel="AAA(RU)")])
    left = credit_assessment(rows, issuer_id=None, instrument_id="bond-uid", at=NOW, bond=True)
    right = credit_assessment(reversed(rows), issuer_id=None, instrument_id="bond-uid", at=NOW, bond=True)
    assert left == right
    assert not left["has_required_rating"]
    assert not left["within_rating_floor"]


def test_broker_cannot_resurrect_a_primary_source_withdrawal():
    rows, _ = normalize([raw_rating(ratingLevel="AAA(RU)")])
    withdrawn = Rating("ACRA", "RU_NATIONAL_LONG_TERM", "AAA(RU)", "issue", "bond-uid",
        "withdrawn", "stable", Source("withdrawal", "https://acra-ratings.ru/ratings/issue",
        "2026-10-01T00:00:00Z", "2026-10-28T00:00:00Z", "2026-11-01T00:00:00Z", "review"))
    result = credit_assessment([*rows, withdrawn], issuer_id=None, instrument_id="bond-uid", at=NOW, bond=True)
    assert result["warnings"]
    assert not result["within_rating_floor"]


def test_old_provider_observation_cannot_be_refreshed_by_a_new_assessment():
    meta = {"uid": "bond-uid", "ratings": [raw_rating()]}
    for age in (-1, 24 * 3600):
        rows, errors = broker_bond_ratings(meta, instrument_id="bond-uid",
            observed_at=(NOW - timedelta(seconds=age)).isoformat(), at=NOW)
        assert not rows and errors


def test_provider_origin_cannot_be_used_for_an_issuer_or_a_fake_source():
    rows, _ = normalize([raw_rating()])
    assert replace(rows[0], subject_kind="issuer").level() is None
    assert replace(rows[0], source=replace(rows[0].source,
        url="https://developer.tbank.ru.attacker.invalid/rating")).level() is None


def test_rating_section_consumes_official_bond_ratings(monkeypatch):
    from backend import volume_market as market
    monkeypatch.setattr(market.research_store, "latest_verified", lambda *_: None)
    monkeypatch.setattr(market.research_store, "records", lambda *_, **__: [])
    now = datetime.now(timezone.utc)
    meta = {"uid": "bond-uid", "instrumentType": "bond", "ratings": [raw_rating(ratingDate=now.isoformat())],
            "_source": {"observed_at": now.isoformat()}}
    result = market.rating_section("bond-uid", meta)
    assert result["state"] == "available"
    assert result["data"]["items"][0]["evidence_basis"] == "t_invest_bond_rating"
    assert result["sources"][0]["provider"] == "T-Invest / ACRA"
    assert result["data"]["issuer_id"] is None


def test_purchase_credit_consumes_broker_data_but_does_not_invent_issuer_rating(monkeypatch):
    from backend import volume_purchases as purchases, purchase_policy
    monkeypatch.setattr(purchases.research_store, "latest_verified", lambda *_: None)
    monkeypatch.setattr(purchases.research_store, "records", lambda *_, **__: [])
    identity, assessment = purchases.reviewed_credit("bond-uid", "bond", NOW,
        {"uid": "bond-uid", "ratings": [raw_rating()], "_ratings_observed_at": NOW.isoformat()})
    assert not identity
    assert "issuer_rating_required" in purchase_policy.credit_reasons(assessment, "bond")
    assert "issue_rating_required" not in purchase_policy.credit_reasons(assessment, "bond")


def test_purchase_assessment_does_not_redate_cached_broker_rating(monkeypatch):
    from backend import volume_purchases as purchases
    monkeypatch.setattr(purchases.research_store, "latest_verified", lambda *_: None)
    monkeypatch.setattr(purchases.research_store, "records", lambda *_, **__: [])
    _, assessment = purchases.reviewed_credit("bond-uid", "bond", NOW,
        {"uid": "bond-uid", "ratings": [raw_rating()],
         "_ratings_observed_at": (NOW - timedelta(days=2)).isoformat()})
    assert not assessment["has_required_rating"]
    assert "broker_rating_observation_stale_or_future" in assessment["warnings"]


def test_metadata_preserves_missing_empty_and_observed_ratings():
    from backend.volume_workspace import _position_metadata
    position = {"instrumentType": "bond"}
    assert "broker_ratings" not in _position_metadata({}, position)
    empty = _position_metadata({"ratings": [], "_source": {"observed_at": NOW.isoformat()}}, position)
    assert empty["broker_ratings"] == []
    assert empty["broker_ratings_observed_at"] == NOW.isoformat()


def test_monitor_marks_bbb_minus_and_watch_as_critical():
    from backend.volume_credit import critical
    rows, _ = normalize([raw_rating(ratingLevel="BBB-(RU)")])
    row = {**asdict(rows[0]), "level_within_agency": rows[0].level()}
    assert critical({"data": {"items": [row]}})
    assert critical({"data": {"items": [{**row, "level_within_agency": 0, "is_under_watch": True}]}})
