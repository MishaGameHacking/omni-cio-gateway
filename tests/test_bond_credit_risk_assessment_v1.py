from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.bond_credit import (
    BondCreditBlocker,
    BondCreditRiskAssessmentV1,
    BondCreditRiskPolicyV1,
    BondCreditWarning,
    BondYieldBasis,
)
from omni_cio.contracts.v1.common import (
    Completeness,
    DataQuality,
    QualityMetadata,
)
from omni_cio.contracts.v1.market import (
    BondMetricsV1,
    ComponentStateV1,
    ComponentStatus,
    CreditRatingV1,
    InstrumentReferenceV1,
    MarketAssessmentStatus,
    MarketResearchBundleV1,
    MarketResearchMetadataV1,
    MarketSourceV1,
    RatingAction,
    RatingScope,
    SourceAuthority,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.market import assess_bond_credit_risk


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
KEY = "uid:bond-a"


def _source(
    provider: str = "ACRA fixture",
    authority: SourceAuthority = SourceAuthority.REGULATED,
    *,
    retrieved_at: datetime = NOW,
) -> MarketSourceV1:
    return MarketSourceV1(
        provider=provider,
        authority=authority,
        retrieved_at=retrieved_at,
        source_id=provider.casefold().replace(" ", "-"),
    )


def _rating(
    scope: RatingScope,
    *,
    agency: str = "ACRA",
    rating: str = "AAA(RU)",
    action: RatingAction = RatingAction.AFFIRMED,
    effective_at: datetime | None = None,
    authority: SourceAuthority = SourceAuthority.REGULATED,
    outlook: str | None = "stable",
) -> CreditRatingV1:
    timestamp = effective_at or NOW - timedelta(days=30)
    return CreditRatingV1(
        instrument_key=KEY,
        scope=scope,
        agency=agency,
        rating=rating,
        action=action,
        effective_at=timestamp,
        source=_source(agency, authority, retrieved_at=timestamp),
        outlook=outlook,
        previous_rating="AA+(RU)" if action == RatingAction.UPGRADED else None,
    )


def _metrics(
    *,
    as_of: datetime = NOW - timedelta(hours=1),
    maturity_date: date = date(2029, 7, 29),
    duration_years: str = "3.2",
    offer_date: date | None = None,
    yield_to_maturity: str | None = "0.145",
    yield_to_offer: str | None = None,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
) -> BondMetricsV1:
    return BondMetricsV1(
        instrument_key=KEY,
        currency="RUB",
        as_of=as_of,
        source=_source("MOEX", authority, retrieved_at=as_of),
        maturity_date=maturity_date,
        duration_years=Decimal(duration_years),
        accrued_interest=Decimal("12.34"),
        yield_to_maturity=(
            Decimal(yield_to_maturity) if yield_to_maturity is not None else None
        ),
        yield_to_offer=(
            Decimal(yield_to_offer) if yield_to_offer is not None else None
        ),
        offer_date=offer_date,
    )


def _state(
    status: ComponentStatus,
    *,
    count: int,
    source: MarketSourceV1 | None = None,
    checked_at: datetime | None = None,
) -> ComponentStateV1:
    return ComponentStateV1(
        status=status,
        source=source,
        checked_at=checked_at,
        record_count=count,
    )


def _bundle(
    *,
    ratings: tuple[CreditRatingV1, ...] | None = None,
    metrics: BondMetricsV1 | None = None,
    instrument_type: InstrumentType = InstrumentType.BOND,
    reference_authority: SourceAuthority = SourceAuthority.OFFICIAL,
) -> MarketResearchBundleV1:
    active_ratings = ratings or (
        _rating(RatingScope.ISSUER),
        _rating(RatingScope.ISSUE),
    )
    active_metrics = metrics or _metrics()
    reference_source = _source("T-Invest", reference_authority)
    rating_state_source = _source("Ratings registry")
    event_source = _source("MOEX events", SourceAuthority.OFFICIAL)
    return MarketResearchBundleV1(
        metadata=MarketResearchMetadataV1(
            retrieved_at=NOW,
            quality=QualityMetadata(
                quality=DataQuality.VERIFIED,
                completeness=Completeness.COMPLETE,
            ),
        ),
        instrument_key=KEY,
        reference_state=_state(
            ComponentStatus.OK,
            count=1,
            source=reference_source,
            checked_at=NOW,
        ),
        quote_state=_state(ComponentStatus.UNAVAILABLE, count=0),
        liquidity_state=_state(ComponentStatus.UNAVAILABLE, count=0),
        ratings_state=_state(
            ComponentStatus.OK,
            count=len(active_ratings),
            source=rating_state_source,
            checked_at=NOW,
        ),
        bond_metrics_state=_state(
            ComponentStatus.OK if active_metrics is not None else ComponentStatus.UNAVAILABLE,
            count=int(active_metrics is not None),
            source=active_metrics.source if active_metrics is not None else None,
            checked_at=active_metrics.as_of if active_metrics is not None else None,
        ),
        events_state=_state(
            ComponentStatus.OK,
            count=0,
            source=event_source,
            checked_at=NOW,
        ),
        reference=InstrumentReferenceV1(
            stable_key=KEY,
            name="Тестовая облигация",
            instrument_type=instrument_type,
            currency="RUB",
            lot=1,
            source=reference_source,
            ticker="BOND1",
            isin="RU000A000001",
            uid="bond-a",
            issuer_id="issuer-a",
        ),
        ratings=active_ratings,
        bond_metrics=active_metrics,
        events=(),
        trading_methods=False,
    )


def test_ready_bond_requires_current_issuer_and_issue_ratings() -> None:
    result = assess_bond_credit_risk(_bundle(), assessed_at=NOW)

    assert result.status == MarketAssessmentStatus.READY
    assert result.decision_ready is True
    assert result.current_issuer_rating_count == 1
    assert result.current_issue_rating_count == 1
    assert result.stale_rating_count == 0
    assert result.yield_basis == BondYieldBasis.TO_MATURITY
    assert result.selected_yield == Decimal("0.145")
    assert result.effective_exit_date == date(2029, 7, 29)
    assert result.cross_agency_scale_normalized is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_future_offer_selects_yield_to_offer_and_earlier_exit() -> None:
    metrics = _metrics(
        offer_date=date(2027, 7, 29),
        yield_to_offer="0.132",
    )
    result = assess_bond_credit_risk(_bundle(metrics=metrics), assessed_at=NOW)

    assert result.decision_ready is True
    assert result.yield_basis == BondYieldBasis.TO_OFFER
    assert result.selected_yield == Decimal("0.132")
    assert result.effective_exit_date == date(2027, 7, 29)
    assert result.days_to_offer == 365


def test_missing_or_stale_required_scope_blocks_readiness() -> None:
    missing_issue = assess_bond_credit_risk(
        _bundle(ratings=(_rating(RatingScope.ISSUER),)),
        assessed_at=NOW,
    )
    assert missing_issue.status == MarketAssessmentStatus.PARTIAL
    assert BondCreditBlocker.ISSUE_RATING_MISSING in missing_issue.blockers

    stale_issue = assess_bond_credit_risk(
        _bundle(
            ratings=(
                _rating(RatingScope.ISSUER),
                _rating(
                    RatingScope.ISSUE,
                    effective_at=NOW - timedelta(days=500),
                ),
            )
        ),
        assessed_at=NOW,
    )
    assert BondCreditBlocker.ISSUE_RATING_STALE in stale_issue.blockers
    assert stale_issue.current_issue_rating_count == 0


def test_latest_withdrawal_removes_scope_coverage() -> None:
    ratings = (
        _rating(RatingScope.ISSUER),
        _rating(
            RatingScope.ISSUE,
            action=RatingAction.AFFIRMED,
            effective_at=NOW - timedelta(days=60),
        ),
        _rating(
            RatingScope.ISSUE,
            action=RatingAction.WITHDRAWN,
            effective_at=NOW - timedelta(days=10),
        ),
    )
    result = assess_bond_credit_risk(_bundle(ratings=ratings), assessed_at=NOW)

    assert BondCreditBlocker.ISSUE_RATING_MISSING in result.blockers
    assert BondCreditWarning.WITHDRAWN_RATING_PRESENT in result.warnings
    assert result.withdrawn_rating_count == 1


def test_contradictory_latest_records_are_rejected() -> None:
    timestamp = NOW - timedelta(days=10)
    ratings = (
        _rating(RatingScope.ISSUER),
        _rating(RatingScope.ISSUE, rating="AAA(RU)", effective_at=timestamp),
        _rating(RatingScope.ISSUE, rating="AA+(RU)", effective_at=timestamp),
    )
    result = assess_bond_credit_risk(_bundle(ratings=ratings), assessed_at=NOW)

    assert result.status == MarketAssessmentStatus.REJECTED
    assert BondCreditBlocker.RATING_RECORD_CONTRADICTION in result.blockers


def test_cross_agency_label_divergence_is_visible_but_not_normalized() -> None:
    ratings = (
        _rating(RatingScope.ISSUER, agency="ACRA", rating="AAA(RU)"),
        _rating(RatingScope.ISSUE, agency="ACRA", rating="AAA(RU)"),
        _rating(RatingScope.ISSUER, agency="Expert RA", rating="ruAAA"),
        _rating(RatingScope.ISSUE, agency="Expert RA", rating="ruAAA"),
    )
    result = assess_bond_credit_risk(_bundle(ratings=ratings), assessed_at=NOW)

    assert result.decision_ready is True
    assert set(result.divergent_scopes) == {RatingScope.ISSUER, RatingScope.ISSUE}
    assert BondCreditWarning.RATING_LABELS_DIVERGE in result.warnings
    assert BondCreditWarning.CROSS_AGENCY_SCALE_NOT_NORMALIZED in result.warnings
    assert result.cross_agency_scale_normalized is False


def test_recent_downgrade_and_untrusted_source_are_exposed() -> None:
    downgraded = _rating(
        RatingScope.ISSUE,
        rating="A(RU)",
        action=RatingAction.DOWNGRADED,
        effective_at=NOW - timedelta(days=20),
    )
    result = assess_bond_credit_risk(
        _bundle(ratings=(_rating(RatingScope.ISSUER), downgraded)),
        assessed_at=NOW,
    )
    assert BondCreditWarning.RECENT_DOWNGRADE in result.warnings
    assert result.latest_downgrade_at == downgraded.effective_at

    untrusted = assess_bond_credit_risk(
        _bundle(
            ratings=(
                _rating(RatingScope.ISSUER),
                _rating(
                    RatingScope.ISSUE,
                    authority=SourceAuthority.SECONDARY,
                ),
            )
        ),
        assessed_at=NOW,
    )
    assert untrusted.status == MarketAssessmentStatus.REJECTED
    assert BondCreditBlocker.UNTRUSTED_SOURCE in untrusted.blockers


def test_metrics_freshness_duration_and_required_yield_are_fail_closed() -> None:
    policy = BondCreditRiskPolicyV1(max_duration_years=Decimal("4"))
    metrics = _metrics(
        as_of=NOW - timedelta(days=2),
        duration_years="6",
        yield_to_maturity=None,
    )
    result = assess_bond_credit_risk(
        _bundle(metrics=metrics),
        assessed_at=NOW,
        policy=policy,
    )

    assert result.status == MarketAssessmentStatus.PARTIAL
    assert BondCreditBlocker.BOND_METRICS_STALE in result.blockers
    assert BondCreditBlocker.DURATION_LIMIT_BREACH in result.blockers
    assert BondCreditBlocker.YIELD_TO_MATURITY_MISSING in result.blockers


def test_past_offer_uses_maturity_but_past_maturity_is_rejected() -> None:
    past_offer = assess_bond_credit_risk(
        _bundle(metrics=_metrics(offer_date=date(2026, 1, 1))),
        assessed_at=NOW,
    )
    assert past_offer.yield_basis == BondYieldBasis.TO_MATURITY
    assert BondCreditWarning.OFFER_ALREADY_PASSED in past_offer.warnings

    matured = assess_bond_credit_risk(
        _bundle(metrics=_metrics(maturity_date=date(2026, 1, 1))),
        assessed_at=NOW,
    )
    assert matured.status == MarketAssessmentStatus.REJECTED
    assert BondCreditBlocker.MATURITY_PASSED in matured.blockers


def test_non_bond_and_missing_metrics_are_blocked() -> None:
    non_bond = assess_bond_credit_risk(
        _bundle(instrument_type=InstrumentType.SHARE),
        assessed_at=NOW,
    )
    assert non_bond.status == MarketAssessmentStatus.REJECTED
    assert BondCreditBlocker.NOT_A_BOND in non_bond.blockers

    missing_metrics = assess_bond_credit_risk(
        _bundle(metrics=None),
        assessed_at=NOW,
    )
    assert missing_metrics.status == MarketAssessmentStatus.PARTIAL
    assert BondCreditBlocker.BOND_METRICS_MISSING in missing_metrics.blockers
    assert missing_metrics.yield_basis == BondYieldBasis.UNAVAILABLE


def test_contract_rejects_tampered_counts_and_status() -> None:
    result = assess_bond_credit_risk(_bundle(), assessed_at=NOW)
    payload = result.model_dump(mode="python")
    payload["current_issue_rating_count"] = 99

    with pytest.raises(ValidationError, match="issue rating count"):
        BondCreditRiskAssessmentV1.model_validate(payload)

    payload = result.model_dump(mode="python")
    payload["decision_ready"] = False
    with pytest.raises(ValidationError, match="decision_ready"):
        BondCreditRiskAssessmentV1.model_validate(payload)


def test_bond_credit_module_has_no_network_or_broker_imports() -> None:
    source = Path("omni_cio/market/bond_credit_v1.py").read_text(encoding="utf-8")
    forbidden = (
        "import grpc",
        "import requests",
        "import httpx",
        "http.client",
        "urllib.request",
        "from t_tech",
        "from tinkoff",
        "post_order",
    )
    assert all(marker not in source for marker in forbidden)
