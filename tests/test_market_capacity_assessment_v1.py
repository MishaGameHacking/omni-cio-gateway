from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityBlocker,
    CapacityEvidenceV1,
    CapacityOrderRequestV1,
    CapacityPolicyV1,
    CapacityStatus,
    CapacityWarning,
    OrderSide,
)
from omni_cio.contracts.v1.market import (
    MarketAssessmentStatus,
    MarketReadinessAssessmentV1,
    MarketSourceV1,
    SourceAuthority,
)
from omni_cio.market.capacity_v1 import (
    CapacityAssessmentError,
    assess_market_capacity,
)


NOW = datetime(2026, 7, 29, 16, 0, tzinfo=timezone.utc)
KEY = "uid:capacity-a"


def _source(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    retrieved_at: datetime = NOW,
) -> MarketSourceV1:
    return MarketSourceV1(
        provider="synthetic-capacity-source",
        authority=authority,
        retrieved_at=retrieved_at,
        source_id="capacity-source-v1",
    )


def _market_readiness(*, ready: bool = True) -> MarketReadinessAssessmentV1:
    if ready:
        return MarketReadinessAssessmentV1(
            assessed_at=NOW,
            status=MarketAssessmentStatus.READY,
            decision_ready=True,
            stale_components=(),
            missing_components=(),
            untrusted_components=(),
        )
    return MarketReadinessAssessmentV1(
        assessed_at=NOW,
        status=MarketAssessmentStatus.PARTIAL,
        decision_ready=False,
        stale_components=("liquidity",),
        missing_components=(),
        untrusted_components=(),
    )


def _request(
    *,
    instrument_key: str = KEY,
    currency: str = "RUB",
    quantity_lots: int = 100,
    lot_size: int = 10,
    price: Decimal = Decimal("100"),
    execution_days: int = 2,
) -> CapacityOrderRequestV1:
    units = quantity_lots * lot_size
    return CapacityOrderRequestV1(
        request_id="capacity-request-1",
        instrument_key=instrument_key,
        side=OrderSide.BUY,
        currency=currency,
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=price,
        intended_execution_days=execution_days,
        units=units,
        order_notional=Decimal(units) * price,
    )


def _evidence(
    *,
    instrument_key: str = KEY,
    currency: str = "RUB",
    lot_size: int = 10,
    price: Decimal = Decimal("100"),
    as_of: datetime = NOW,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    source_retrieved_at: datetime = NOW,
    spread_bps: Decimal = Decimal("20"),
    depth: Decimal = Decimal("1000000"),
    average_turnover: Decimal = Decimal("10000000"),
    median_turnover: Decimal = Decimal("8000000"),
    history_days: int = 30,
    volatility: Decimal = Decimal("0.02"),
) -> CapacityEvidenceV1:
    return CapacityEvidenceV1(
        instrument_key=instrument_key,
        currency=currency,
        lot_size=lot_size,
        as_of=as_of,
        source=_source(
            authority=authority,
            retrieved_at=source_retrieved_at,
        ),
        venue="MOEX",
        reference_price=price,
        spread_bps=spread_bps,
        top_of_book_depth_notional=depth,
        average_daily_turnover_notional=average_turnover,
        median_daily_turnover_notional=median_turnover,
        turnover_history_days=history_days,
        daily_return_volatility=volatility,
    )


def test_small_split_order_is_capacity_ready_with_exact_envelope() -> None:
    result = assess_market_capacity(
        _request(),
        _evidence(),
        _market_readiness(),
        assessed_at=NOW,
    )

    assert result.status is CapacityStatus.READY
    assert result.capacity_ready is True
    assert result.blockers == ()
    assert result.metrics is not None
    assert result.metrics.order_notional == Decimal("100000")
    assert result.metrics.daily_slice_notional == Decimal("50000")
    assert result.metrics.daily_turnover_participation == Decimal("0.005")
    assert result.metrics.top_of_book_participation == Decimal("0.05")
    assert result.metrics.minimum_execution_days == 1
    assert result.metrics.half_spread_bps == Decimal("10")
    assert result.metrics.estimated_impact_bps > Decimal("10")
    assert result.metrics.safe_notional_for_requested_window == Decimal("500000")
    assert result.metrics.safe_lots_for_requested_window == 500
    assert result.metrics.requested_notional_within_safe_capacity is True
    assert CapacityWarning.SQUARE_ROOT_IMPACT_PROXY in result.warnings
    assert CapacityWarning.IMPACT_IS_NOT_EXECUTION_PRICE in result.warnings
    assert result.order_created is False
    assert result.trading_methods is False


def test_oversized_one_day_order_is_rejected_by_adv_depth_and_window() -> None:
    result = assess_market_capacity(
        _request(quantity_lots=2000, execution_days=1),
        _evidence(),
        _market_readiness(),
        assessed_at=NOW,
    )

    assert result.status is CapacityStatus.REJECTED
    assert result.capacity_ready is False
    assert result.metrics is not None
    assert CapacityBlocker.DAILY_PARTICIPATION_EXCEEDED in result.blockers
    assert CapacityBlocker.TOP_OF_BOOK_PARTICIPATION_EXCEEDED in result.blockers
    assert CapacityBlocker.EXECUTION_WINDOW_TOO_SHORT in result.blockers
    assert result.metrics.minimum_execution_days == 4
    assert CapacityWarning.ORDER_SPLITTING_REQUIRED in result.warnings


def test_strict_impact_limit_blocks_even_when_adv_and_depth_pass() -> None:
    result = assess_market_capacity(
        _request(),
        _evidence(),
        _market_readiness(),
        policy=CapacityPolicyV1(maximum_estimated_impact_bps=Decimal("15")),
        assessed_at=NOW,
    )

    assert result.metrics is not None
    assert result.metrics.daily_turnover_participation <= result.policy.maximum_daily_turnover_participation
    assert result.metrics.top_of_book_participation <= result.policy.maximum_top_of_book_participation
    assert CapacityBlocker.ESTIMATED_IMPACT_EXCEEDED in result.blockers
    assert result.metrics.safe_notional_for_requested_window < result.request.order_notional


def test_market_readiness_staleness_authority_and_history_are_fail_closed() -> None:
    market_blocked = assess_market_capacity(
        _request(),
        _evidence(),
        _market_readiness(ready=False),
        assessed_at=NOW,
    )
    assert CapacityBlocker.MARKET_NOT_READY in market_blocked.blockers

    stale = assess_market_capacity(
        _request(),
        _evidence(as_of=NOW - timedelta(minutes=10)),
        _market_readiness(),
        assessed_at=NOW,
    )
    assert CapacityBlocker.EVIDENCE_STALE in stale.blockers

    future = assess_market_capacity(
        _request(),
        _evidence(
            as_of=NOW + timedelta(minutes=10),
            source_retrieved_at=NOW + timedelta(minutes=10),
        ),
        _market_readiness(),
        assessed_at=NOW,
    )
    assert CapacityBlocker.EVIDENCE_FROM_FUTURE in future.blockers

    untrusted = assess_market_capacity(
        _request(),
        _evidence(authority=SourceAuthority.SECONDARY),
        _market_readiness(),
        assessed_at=NOW,
    )
    assert CapacityBlocker.UNTRUSTED_SOURCE in untrusted.blockers

    short_history = assess_market_capacity(
        _request(),
        _evidence(history_days=5),
        _market_readiness(),
        assessed_at=NOW,
    )
    assert CapacityBlocker.INSUFFICIENT_TURNOVER_HISTORY in short_history.blockers


def test_high_spread_can_reduce_safe_capacity_to_zero() -> None:
    result = assess_market_capacity(
        _request(),
        _evidence(spread_bps=Decimal("250")),
        _market_readiness(),
        policy=CapacityPolicyV1(maximum_estimated_impact_bps=Decimal("100")),
        assessed_at=NOW,
    )

    assert result.metrics is not None
    assert result.metrics.maximum_notional_by_impact == 0
    assert result.metrics.safe_notional_for_requested_window == 0
    assert CapacityBlocker.ZERO_SAFE_CAPACITY in result.blockers
    assert CapacityBlocker.ESTIMATED_IMPACT_EXCEEDED in result.blockers
    assert CapacityWarning.HIGH_SPREAD in result.warnings


def test_turnover_variability_is_explicit_warning() -> None:
    result = assess_market_capacity(
        _request(),
        _evidence(
            average_turnover=Decimal("10000000"),
            median_turnover=Decimal("3000000"),
        ),
        _market_readiness(),
        assessed_at=NOW,
    )

    assert CapacityWarning.TURNOVER_VARIABILITY_HIGH in result.warnings


def test_identity_currency_lot_and_price_mismatch_raise_structural_error() -> None:
    with pytest.raises(CapacityAssessmentError, match="INSTRUMENT_MISMATCH"):
        assess_market_capacity(
            _request(),
            _evidence(instrument_key="uid:capacity-b"),
            _market_readiness(),
            assessed_at=NOW,
        )
    with pytest.raises(CapacityAssessmentError, match="CURRENCY_MISMATCH"):
        assess_market_capacity(
            _request(),
            _evidence(currency="USD"),
            _market_readiness(),
            assessed_at=NOW,
        )
    with pytest.raises(CapacityAssessmentError, match="LOT_SIZE_MISMATCH"):
        assess_market_capacity(
            _request(),
            _evidence(lot_size=1),
            _market_readiness(),
            assessed_at=NOW,
        )
    with pytest.raises(CapacityAssessmentError, match="REFERENCE_PRICE_MISMATCH"):
        assess_market_capacity(
            _request(),
            _evidence(price=Decimal("101")),
            _market_readiness(),
            assessed_at=NOW,
        )


def test_request_evidence_metrics_and_safety_tampering_are_rejected() -> None:
    request_payload = _request().model_dump()
    request_payload["order_notional"] = Decimal("1")
    with pytest.raises(ValidationError, match="notional does not reconcile"):
        CapacityOrderRequestV1.model_validate(request_payload)

    evidence_payload = _evidence().model_dump()
    evidence_payload["source"]["retrieved_at"] = NOW - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="retrieved before evidence"):
        CapacityEvidenceV1.model_validate(evidence_payload)

    result = assess_market_capacity(
        _request(),
        _evidence(),
        _market_readiness(),
        assessed_at=NOW,
    )
    assert result.metrics is not None
    payload = result.model_dump()
    payload["metrics"]["safe_notional_for_requested_window"] = Decimal("1")
    with pytest.raises(ValidationError, match="safe notional"):
        CapacityAssessmentV1.model_validate(payload)

    payload = result.model_dump()
    payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        CapacityAssessmentV1.model_validate(payload)


def test_zero_volatility_does_not_invent_unbounded_impact_capacity() -> None:
    result = assess_market_capacity(
        _request(),
        _evidence(volatility=Decimal("0")),
        _market_readiness(),
        assessed_at=NOW,
    )

    assert result.metrics is not None
    assert result.metrics.impact_ex_spread_bps == 0
    assert (
        result.metrics.maximum_notional_by_impact
        == result.metrics.maximum_notional_by_daily_turnover
    )


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(
        CapacityAssessmentError,
        match="CAPACITY_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE",
    ):
        assess_market_capacity(
            _request(),
            _evidence(),
            _market_readiness(),
            assessed_at=datetime(2026, 7, 29, 16, 0),
        )
