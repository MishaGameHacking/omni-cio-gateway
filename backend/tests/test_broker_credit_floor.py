"""Synthetic provider observations; no live broker/model/trading calls."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.credit_evidence import (
    BROKER_RATING_URL, BROKER_RATINGS_EMPTY, Rating, Source, broker_bond_ratings, credit_assessment,
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
    assert rating.subject_kind == "issue"
    assert rating.subject_id == "bond-uid"
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
    assert not rows
    assert errors


def test_broker_risk_level_is_not_a_credit_rating():
    rows, errors = broker_bond_ratings({"uid": "bond-uid", "riskLevel": "RISK_LEVEL_LOW"},
        instrument_id="bond-uid", observed_at=NOW.isoformat(), at=NOW)
    assert rows == []
    assert errors == []
    assert not credit_assessment(rows, issuer_id=None, instrument_id="bond-uid", at=NOW,
                                 bond=True)["has_required_rating"]


def test_bbb_minus_is_observed_but_never_eligible():
    rows, errors = normalize([raw_rating(ratingLevel="BBB-(RU)")])
    assert not errors
    assert rows[0].level() == 9
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
        assert not rows
        assert errors


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


def test_explicit_empty_ratings_are_different_from_missing_legacy_field():
    rows, errors = normalize([])
    assert rows == []
    assert errors == [BROKER_RATINGS_EMPTY]
    missing_rows, missing_errors = broker_bond_ratings({"uid": "bond-uid"},
        instrument_id="bond-uid", observed_at=NOW.isoformat(), at=NOW)
    assert missing_rows == []
    assert missing_errors == []


def primary_records(at):
    proof = Source("primary-issue", "https://acra-ratings.ru/ratings/issue",
        (at - timedelta(days=10)).isoformat(), (at - timedelta(days=1)).isoformat(),
        (at + timedelta(days=10)).isoformat(), "primary-review")
    issue = Rating("ACRA", "RU_NATIONAL_LONG_TERM", "AAA(RU)", "issue", "bond-uid",
                   "active", "stable", proof)
    issuer = replace(issue, subject_kind="issuer", subject_id="issuer-uid",
                     source=replace(proof, id="primary-issuer"))
    return {"bond-uid": [asdict(issue)], "issuer-uid": [asdict(issuer)]}


def test_empty_current_observation_blocks_previously_positive_credit_check(monkeypatch):
    from backend import volume_purchases as purchases, purchase_policy
    records = primary_records(NOW)
    monkeypatch.setattr(purchases.research_store, "latest_verified", lambda *_: {"issuer_id": "issuer-uid"})
    monkeypatch.setattr(purchases.research_store, "records",
                        lambda _connect, _kind, subject, **_kwargs: records.get(subject, []).copy())
    _, before = purchases.reviewed_credit("bond-uid", "bond", NOW)
    assert purchase_policy.credit_reasons(before, "bond") == []
    _, after = purchases.reviewed_credit("bond-uid", "bond", NOW,
        {"uid": "bond-uid", "ratings": [], "_ratings_observed_at": NOW.isoformat()})
    assert after["ratings"] == before["ratings"]  # Retain history, deny new use.
    assert BROKER_RATINGS_EMPTY in after["warnings"]
    assert not after["within_rating_floor"]
    assert "rating_evidence_incomplete_or_conflicting" in purchase_policy.credit_reasons(after, "bond")


def test_empty_current_observation_is_visible_with_source_and_flags_monitor(monkeypatch):
    from backend import volume_market as market, volume_credit as monitor
    now = datetime.now(timezone.utc)
    records = primary_records(now)
    monkeypatch.setattr(market.research_store, "latest_verified", lambda *_: {"issuer_id": "issuer-uid"})
    monkeypatch.setattr(market.research_store, "records",
                        lambda _connect, _kind, subject, **_kwargs: records.get(subject, []).copy())
    meta = {"uid": "bond-uid", "instrumentType": "bond", "ratings": [],
            "_source": {"observed_at": now.isoformat()}}
    current = market.rating_section("bond-uid", meta)
    assert current["state"] == "partial"
    assert BROKER_RATINGS_EMPTY in current["data"]["warnings"]
    assert not current["data"]["within_rating_floor"]
    assert monitor.critical(current)
    provider_source = next(row for row in current["sources"] if row["provider"] == "T-Invest")
    assert provider_source["observed_at"] == now.isoformat()
    assert provider_source["method"] == "BondBy"


def test_empty_current_observation_emits_unresolved_evidence_event(monkeypatch):
    from backend import volume_credit as monitor, volume_state as state, volume_notifications as notifications
    events, notices = [], []
    def record_event(_db, _user, kind, _snapshot, payload, _key):
        events.append({"kind": kind, **payload})
        return {"id": "event-id", **payload}
    monkeypatch.setattr(state, "event", record_event)
    monkeypatch.setattr(notifications, "enqueue_in", lambda *args, **kwargs: notices.append(kwargs))
    source = {"id": "old-source"}
    row = {"agency": "ACRA", "grade": "AAA(RU)", "level_within_agency": 0}
    previous = {"state": "available", "data": {"items": [row], "warnings": []}, "sources": [source]}
    current = {"state": "partial", "data": {"items": [row], "warnings": [BROKER_RATINGS_EMPTY]},
               "sources": [source, {"id": "current-empty-observation"}]}
    monitor.record_changes_in(None, 1, {"snapshot_id": "new", "rating_observations": {"bond-uid": current}},
                              {"rating_observations": {"bond-uid": previous}})
    assert len(events) == 1
    assert events[0]["kind"] == "risk_rating_data_stale"
    assert events[0]["details"]["critical"]
    assert events[0]["details"]["missing_is_not_resolved"]
    assert len(notices) == 1
