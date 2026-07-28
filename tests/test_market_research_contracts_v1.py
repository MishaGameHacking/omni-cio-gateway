from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1 import (
    BondMetricsV1,
    Completeness,
    ComponentStateV1,
    ComponentStatus,
    CreditRatingV1,
    DataQuality,
    InstrumentReferenceV1,
    InstrumentType,
    MarketAssessmentStatus,
    MarketFreshnessPolicyV1,
    MarketLiquidityV1,
    MarketQuoteV1,
    MarketResearchBundleV1,
    MarketResearchMetadataV1,
    MarketSourceV1,
    QualityMetadata,
    RatingAction,
    RatingScope,
    SourceAuthority,
)
from omni_cio.market import (
    MarketResearchAssessmentError,
    assess_market_research_bundle,
)


NOW = datetime(2026, 7, 28, 20, 0, tzinfo=timezone.utc)
KEY = "uid:synthetic-instrument"


def _source(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    retrieved_at: datetime = NOW,
) -> MarketSourceV1:
    return MarketSourceV1(
        provider="synthetic-official-source",
        authority=authority,
        retrieved_at=retrieved_at,
        source_id="source-record-1",
    )


def _state(
    *,
    count: int,
    status: ComponentStatus = ComponentStatus.OK,
    source: MarketSourceV1 | None = None,
    checked_at: datetime | None = NOW,
) -> ComponentStateV1:
    active_source = source
    if active_source is None and status in (
        ComponentStatus.OK,
        ComponentStatus.DEGRADED,
    ):
        active_source = _source()
    return ComponentStateV1(
        status=status,
        source=active_source,
        checked_at=checked_at,
        record_count=count,
    )


def _reference(
    instrument_type: InstrumentType = InstrumentType.SHARE,
) -> InstrumentReferenceV1:
    return InstrumentReferenceV1(
        stable_key=KEY,
        name="Synthetic instrument",
        ticker="SYNTH",
        uid="synthetic-instrument",
        instrument_type=instrument_type,
        currency="RUB",
        lot=10,
        issuer_id="issuer-1",
        sector="technology",
        source=_source(authority=SourceAuthority.PRIMARY),
    )


def _quote(
    *,
    as_of: datetime = NOW,
    source: MarketSourceV1 | None = None,
    currency: str = "RUB",
    instrument_key: str = KEY,
) -> MarketQuoteV1:
    return MarketQuoteV1(
        instrument_key=instrument_key,
        currency=currency,
        as_of=as_of,
        source=source or _source(),
        last_price=Decimal("100"),
        best_bid=Decimal("99"),
        best_ask=Decimal("101"),
    )


def _liquidity(
    *,
    as_of: datetime = NOW,
    currency: str = "RUB",
    instrument_key: str = KEY,
) -> MarketLiquidityV1:
    return MarketLiquidityV1(
        instrument_key=instrument_key,
        currency=currency,
        as_of=as_of,
        source=_source(),
        best_bid=Decimal("99"),
        best_ask=Decimal("101"),
        spread_absolute=Decimal("2"),
        spread_bps=Decimal("200"),
        bid_depth=Decimal("100000"),
        ask_depth=Decimal("120000"),
        turnover_24h=Decimal("5000000"),
    )


def _rating(
    scope: RatingScope,
    *,
    action: RatingAction = RatingAction.AFFIRMED,
) -> CreditRatingV1:
    return CreditRatingV1(
        instrument_key=KEY,
        scope=scope,
        agency="Synthetic regulated agency",
        rating="AA(RU)",
        action=action,
        effective_at=NOW - timedelta(days=30),
        source=_source(authority=SourceAuthority.REGULATED),
        outlook="stable",
    )


def _bond_metrics() -> BondMetricsV1:
    return BondMetricsV1(
        instrument_key=KEY,
        currency="RUB",
        as_of=NOW,
        source=_source(),
        maturity_date=date(2029, 7, 28),
        duration_years=Decimal("2.4"),
        accrued_interest=Decimal("15.25"),
        yield_to_maturity=Decimal("0.145"),
    )


def _bundle(
    *,
    instrument_type: InstrumentType = InstrumentType.SHARE,
    quote: MarketQuoteV1 | None = None,
    liquidity: MarketLiquidityV1 | None = None,
    quote_state: ComponentStateV1 | None = None,
    ratings: tuple[CreditRatingV1, ...] = (),
    ratings_state: ComponentStateV1 | None = None,
    bond_metrics: BondMetricsV1 | None = None,
    bond_metrics_state: ComponentStateV1 | None = None,
) -> MarketResearchBundleV1:
    is_bond = instrument_type == InstrumentType.BOND
    actual_ratings_state = ratings_state or (
        _state(count=len(ratings))
        if is_bond
        else _state(
            count=0,
            status=ComponentStatus.NOT_APPLICABLE,
            checked_at=None,
        )
    )
    actual_bond_state = bond_metrics_state or (
        _state(count=int(bond_metrics is not None))
        if is_bond
        else _state(
            count=0,
            status=ComponentStatus.NOT_APPLICABLE,
            checked_at=None,
        )
    )
    return MarketResearchBundleV1(
        metadata=MarketResearchMetadataV1(
            retrieved_at=NOW,
            quality=QualityMetadata(
                quality=DataQuality.VERIFIED,
                completeness=Completeness.COMPLETE,
            ),
        ),
        instrument_key=KEY,
        reference_state=_state(count=1),
        quote_state=quote_state or _state(count=1),
        liquidity_state=_state(count=1),
        ratings_state=actual_ratings_state,
        bond_metrics_state=actual_bond_state,
        events_state=_state(count=0),
        reference=_reference(instrument_type),
        quote=quote or _quote(),
        liquidity=liquidity or _liquidity(),
        ratings=ratings,
        bond_metrics=bond_metrics,
        events=(),
        trading_methods=False,
    )


def test_fresh_share_bundle_is_decision_ready() -> None:
    result = assess_market_research_bundle(_bundle(), assessed_at=NOW)

    assert result.status == MarketAssessmentStatus.READY
    assert result.decision_ready is True
    assert result.stale_components == ()
    assert result.missing_components == ()
    assert result.untrusted_components == ()


def test_fresh_empty_events_check_is_valid() -> None:
    bundle = _bundle()

    assert bundle.events == ()
    assert bundle.events_state.status == ComponentStatus.OK
    assert bundle.events_state.record_count == 0
    assert assess_market_research_bundle(bundle, assessed_at=NOW).decision_ready


def test_complete_bond_requires_issue_and_issuer_ratings() -> None:
    bundle = _bundle(
        instrument_type=InstrumentType.BOND,
        ratings=(
            _rating(RatingScope.ISSUER),
            _rating(RatingScope.ISSUE),
        ),
        bond_metrics=_bond_metrics(),
    )

    result = assess_market_research_bundle(bundle, assessed_at=NOW)

    assert result.status == MarketAssessmentStatus.READY
    assert result.decision_ready is True


def test_stale_quote_blocks_readiness_using_value_timestamp() -> None:
    bundle = _bundle(quote=_quote(as_of=NOW - timedelta(minutes=6)))

    result = assess_market_research_bundle(bundle, assessed_at=NOW)

    assert result.status == MarketAssessmentStatus.PARTIAL
    assert result.decision_ready is False
    assert result.stale_components == ("quote",)


def test_secondary_quote_source_is_rejected_for_primary_fact() -> None:
    secondary = _source(authority=SourceAuthority.SECONDARY)
    bundle = _bundle(quote=_quote(source=secondary))

    result = assess_market_research_bundle(bundle, assessed_at=NOW)

    assert result.status == MarketAssessmentStatus.REJECTED
    assert result.untrusted_components == ("quote",)
    assert result.decision_ready is False


def test_degraded_component_is_missing_even_with_data() -> None:
    bundle = _bundle(
        quote_state=_state(
            count=1,
            status=ComponentStatus.DEGRADED,
        )
    )

    result = assess_market_research_bundle(bundle, assessed_at=NOW)

    assert "quote" in result.missing_components
    assert result.decision_ready is False


def test_withdrawn_issue_rating_does_not_satisfy_bond_gate() -> None:
    bundle = _bundle(
        instrument_type=InstrumentType.BOND,
        ratings=(
            _rating(RatingScope.ISSUER),
            _rating(RatingScope.ISSUE, action=RatingAction.WITHDRAWN),
        ),
        bond_metrics=_bond_metrics(),
    )

    result = assess_market_research_bundle(bundle, assessed_at=NOW)

    assert "ratings" in result.missing_components
    assert result.decision_ready is False


def test_future_quote_beyond_tolerance_is_blocked() -> None:
    bundle = _bundle(quote=_quote(as_of=NOW + timedelta(minutes=2)))

    result = assess_market_research_bundle(bundle, assessed_at=NOW)

    assert "quote" in result.stale_components
    assert any("future tolerance" in warning for warning in result.warnings)


def test_spread_arithmetic_is_fail_closed() -> None:
    with pytest.raises(ValidationError, match="spread_absolute"):
        MarketLiquidityV1(
            instrument_key=KEY,
            currency="RUB",
            as_of=NOW,
            source=_source(),
            best_bid=Decimal("99"),
            best_ask=Decimal("101"),
            spread_absolute=Decimal("3"),
            spread_bps=Decimal("200"),
        )


def test_bundle_rejects_identity_and_currency_mismatch() -> None:
    with pytest.raises(ValidationError, match="instrument identity mismatch"):
        _bundle(quote=_quote(instrument_key="uid:other"))

    with pytest.raises(ValidationError, match="currency mismatch"):
        _bundle(liquidity=_liquidity(currency="USD"))


def test_unavailable_state_cannot_hide_records() -> None:
    with pytest.raises(ValidationError, match="cannot contain records"):
        ComponentStateV1(
            status=ComponentStatus.UNAVAILABLE,
            record_count=1,
        )


def test_trading_methods_and_naive_assessment_time_are_rejected() -> None:
    payload = _bundle().model_dump()
    payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        MarketResearchBundleV1.model_validate(payload)

    with pytest.raises(
        MarketResearchAssessmentError,
        match="MARKET_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE",
    ):
        assess_market_research_bundle(
            _bundle(),
            assessed_at=datetime(2026, 7, 28, 20, 0),
        )


def test_custom_freshness_policy_is_enforced() -> None:
    bundle = _bundle(quote=_quote(as_of=NOW - timedelta(seconds=31)))
    policy = MarketFreshnessPolicyV1(quote_max_age_seconds=30)

    result = assess_market_research_bundle(
        bundle,
        policy=policy,
        assessed_at=NOW,
    )

    assert result.stale_components == ("quote",)
