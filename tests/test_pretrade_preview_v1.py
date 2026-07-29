from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.pretrade import (
    PreTradeBlocker,
    PreviewFreshnessStatus,
)
from omni_cio.contracts.v1.rebalancing import (
    RebalanceAlternativeKind,
    RebalanceAlternativeStatus,
    RebalanceAlternativeV1,
    RebalanceBandStatus,
    RebalanceBlocker,
    RebalanceDirection,
    RebalanceLineV1,
    ThresholdRebalancePlanV1,
)
from omni_cio.pretrade import PreTradeOrchestratorError, build_pretrade_preview


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
KEY_A = "uid:asset-a"
KEY_B = "uid:asset-b"


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="threshold_rebalance_plan",
        retrieved_at=NOW,
        account=ACCOUNT,
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation="build_threshold_rebalance_plan",
                retrieved_at=NOW,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _plan() -> ThresholdRebalancePlanV1:
    lines = (
        RebalanceLineV1(
            stable_key=KEY_A,
            currency="RUB",
            current_value=Decimal("500"),
            current_weight=Decimal("0.5"),
            lower_weight=Decimal("0.35"),
            target_weight=Decimal("0.4"),
            upper_weight=Decimal("0.45"),
            band_status=RebalanceBandStatus.ABOVE,
            direction=RebalanceDirection.REDUCE,
            deviation_from_target=Decimal("0.1"),
            value_to_nearest_band=Decimal("50"),
            value_to_target=Decimal("100"),
            sale_required=True,
        ),
        RebalanceLineV1(
            stable_key=KEY_B,
            currency="RUB",
            current_value=Decimal("300"),
            current_weight=Decimal("0.3"),
            lower_weight=Decimal("0.35"),
            target_weight=Decimal("0.4"),
            upper_weight=Decimal("0.45"),
            band_status=RebalanceBandStatus.BELOW,
            direction=RebalanceDirection.ADD,
            deviation_from_target=Decimal("-0.1"),
            value_to_nearest_band=Decimal("50"),
            value_to_target=Decimal("100"),
            sale_required=False,
        ),
    )
    alternatives = (
        RebalanceAlternativeV1(
            alternative_id="rebalance.no_action",
            kind=RebalanceAlternativeKind.NO_ACTION,
            status=RebalanceAlternativeStatus.AVAILABLE,
            title="Keep the current portfolio",
            rationale="Holding remains available.",
            uses_sales=False,
            available_cash=Decimal("80"),
            planned_add_value=Decimal("0"),
            planned_reduce_value=Decimal("0"),
            residual_cash=Decimal("80"),
        ),
        RebalanceAlternativeV1(
            alternative_id="rebalance.cash_first",
            kind=RebalanceAlternativeKind.CASH_FIRST,
            status=RebalanceAlternativeStatus.PREFERRED,
            title="Use available cash first",
            rationale="Add cash to underweight positions without selling.",
            uses_sales=False,
            available_cash=Decimal("80"),
            planned_add_value=Decimal("80"),
            planned_reduce_value=Decimal("0"),
            residual_cash=Decimal("0"),
        ),
        RebalanceAlternativeV1(
            alternative_id="rebalance.full_threshold",
            kind=RebalanceAlternativeKind.FULL_THRESHOLD,
            status=RebalanceAlternativeStatus.BLOCKED,
            title="Review full threshold repair",
            rationale="Sales require tax basis and a live preview.",
            uses_sales=True,
            available_cash=Decimal("80"),
            planned_add_value=Decimal("100"),
            planned_reduce_value=Decimal("100"),
            residual_cash=Decimal("80"),
            blockers=(
                RebalanceBlocker.SALES_REQUIRE_TAX_BASIS,
                RebalanceBlocker.LIVE_PREVIEW_REQUIRED,
            ),
        ),
    )
    return ThresholdRebalancePlanV1(
        metadata=_metadata(),
        source_decision_schema_version="1.0",
        lines=lines,
        alternatives=alternatives,
        preferred_alternative_id="rebalance.cash_first",
        decision_ready=True,
        breach_count=2,
        below_count=1,
        above_count=1,
        inside_count=0,
    )


def _money(amount: str, currency: str = "RUB") -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def _payload() -> dict[str, object]:
    source_time = NOW - timedelta(seconds=30)
    return {
        "status": "ok",
        "version": "3.9.1",
        "retrieved_at": NOW.isoformat(),
        "account": {"masked_id": "***3118"},
        "request": {
            "instrument_uid": "asset-b",
            "price_basis": "best_ask",
            "quantity_lots": 1,
            "direction": "ORDER_DIRECTION_BUY",
        },
        "instrument": {
            "uid": "asset-b",
            "currency": "RUB",
            "lot": 1,
        },
        "instrument_resolution": {"status": "resolved"},
        "market_price": {
            "status": "ok",
            "basis": "best_ask",
            "source": "T-Invest GetOrderBook best ask",
            "price": "80",
            "currency": "RUB",
            "lot_size": 1,
            "source_time": source_time.isoformat(),
        },
        "own_funds": {
            "status": "ok",
            "source": "T-Invest GetMaxLots buy_limits",
            "currency": "RUB",
            "buy_money_amount": "200",
            "buy_max_lots": 2,
        },
        "order_preview": {
            "status": "ok",
            "source": "T-Invest GetOrderPrice",
            "lots_requested": 1,
            "initial_order_amount": _money("80"),
            "total_order_amount": _money("81"),
            "executed_commission": _money("1"),
        },
        "affordable": "yes",
        "affordability_confirmed": True,
        "remaining_cash_estimate": "119",
        "remaining_cash_currency": "RUB",
        "price_freshness": {
            "status": "fresh",
            "source_time": source_time.isoformat(),
            "age_seconds": "30",
            "fresh_threshold_seconds": "120",
        },
        "quality": {
            "instrument_resolved": True,
            "price_available": True,
            "max_lots_available": True,
            "order_price_available": True,
            "affordability_confirmed": True,
            "purchase_capacity_integrity": True,
            "commission_double_count_protected": True,
            "currency_consistent": True,
            "calculation_integrity_confirmed": True,
            "complete": True,
            "read_only": True,
            "no_order_created": True,
        },
        "commission_summary": {
            "status": "ok",
            "canonical_source": "executed_commission",
            "canonical_commission": _money("1"),
            "double_count_protection": True,
        },
        "currency_consistency": {"status": "ok"},
        "calculation_checks": {
            "overall_status": "passed",
            "integrity_confirmed": True,
        },
        "complete": True,
        "component_errors": [],
        "trading_methods": False,
    }


def test_fresh_complete_preview_is_ready() -> None:
    result = build_pretrade_preview(
        _payload(),
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert result.preview_ready is True
    assert result.blockers == ()
    assert result.freshness_status == PreviewFreshnessStatus.FRESH
    assert result.price_age_seconds == Decimal("30.0")
    assert result.total_order_amount is not None
    assert result.total_order_amount.amount == Decimal("81")
    assert result.remaining_cash is not None
    assert result.remaining_cash.amount == Decimal("119")
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_stale_price_is_a_hard_blocker() -> None:
    payload = _payload()
    market_price = payload["market_price"]
    assert isinstance(market_price, dict)
    market_price["source_time"] = (NOW - timedelta(seconds=121)).isoformat()

    result = build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert result.preview_ready is False
    assert result.freshness_status == PreviewFreshnessStatus.STALE
    assert PreTradeBlocker.PRICE_STALE in result.blockers


def test_missing_price_time_blocks_preview() -> None:
    payload = _payload()
    market_price = payload["market_price"]
    assert isinstance(market_price, dict)
    market_price["source_time"] = "unavailable"

    result = build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert result.freshness_status == PreviewFreshnessStatus.UNKNOWN
    assert PreTradeBlocker.PRICE_TIME_UNKNOWN in result.blockers


def test_manual_price_cannot_become_recommendation_ready() -> None:
    payload = _payload()
    request = payload["request"]
    market_price = payload["market_price"]
    assert isinstance(request, dict)
    assert isinstance(market_price, dict)
    request["price_basis"] = "manual"
    market_price["basis"] = "manual"
    market_price["source"] = "manual_input"
    market_price["source_time"] = "not_applicable"

    result = build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert result.freshness_status == PreviewFreshnessStatus.MANUAL_INPUT
    assert PreTradeBlocker.MANUAL_PRICE_NOT_ALLOWED in result.blockers


def test_account_binding_is_fail_closed() -> None:
    payload = _payload()
    payload["account"] = {"masked_id": "***9999"}

    result = build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert PreTradeBlocker.ACCOUNT_MISMATCH in result.blockers
    assert result.preview_ready is False


def test_incomplete_source_and_failed_integrity_are_blocked() -> None:
    payload = _payload()
    payload["complete"] = False
    quality = payload["quality"]
    checks = payload["calculation_checks"]
    assert isinstance(quality, dict)
    assert isinstance(checks, dict)
    quality["complete"] = False
    quality["calculation_integrity_confirmed"] = False
    checks["integrity_confirmed"] = False

    result = build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert PreTradeBlocker.SOURCE_INCOMPLETE in result.blockers
    assert PreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED in result.blockers


def test_unconfirmed_and_insufficient_affordability_are_distinct() -> None:
    unconfirmed = _payload()
    unconfirmed["affordability_confirmed"] = False
    unconfirmed["affordable"] = "unavailable"
    result = build_pretrade_preview(
        unconfirmed,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )
    assert PreTradeBlocker.AFFORDABILITY_UNCONFIRMED in result.blockers
    assert PreTradeBlocker.INSUFFICIENT_FUNDS not in result.blockers

    insufficient = _payload()
    insufficient["affordable"] = "no"
    result = build_pretrade_preview(
        insufficient,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )
    assert PreTradeBlocker.INSUFFICIENT_FUNDS in result.blockers


def test_currency_mismatch_is_preserved_as_blocked_evidence() -> None:
    payload = _payload()
    own_funds = payload["own_funds"]
    assert isinstance(own_funds, dict)
    own_funds["currency"] = "USD"
    payload["remaining_cash_currency"] = "USD"
    payload["currency_consistency"] = {"status": "warning"}

    result = build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert PreTradeBlocker.CURRENCY_MISMATCH in result.blockers
    assert result.own_funds is not None
    assert result.own_funds.currency == "USD"
    assert result.preview_ready is False


def test_target_value_overshoot_blocks_preview() -> None:
    payload = _payload()
    order_preview = payload["order_preview"]
    commission_summary = payload["commission_summary"]
    assert isinstance(order_preview, dict)
    assert isinstance(commission_summary, dict)
    order_preview["initial_order_amount"] = _money("100")
    order_preview["total_order_amount"] = _money("101")
    commission_summary["canonical_commission"] = _money("1")
    payload["remaining_cash_estimate"] = "99"

    result = build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )

    assert PreTradeBlocker.TARGET_BAND_OVERSHOOT in result.blockers
    assert result.preview_ready is False


def test_non_add_target_and_missing_line_fail_closed() -> None:
    result = build_pretrade_preview(
        _payload(),
        _plan(),
        stable_key=KEY_A,
        evaluated_at=NOW,
    )
    assert PreTradeBlocker.TARGET_NOT_ADD in result.blockers

    with pytest.raises(
        PreTradeOrchestratorError,
        match="REBALANCE_LINE_NOT_FOUND_OR_DUPLICATE",
    ):
        build_pretrade_preview(
            _payload(),
            _plan(),
            stable_key="uid:missing",
            evaluated_at=NOW,
        )


def test_output_contains_no_execution_identifiers() -> None:
    result = build_pretrade_preview(
        _payload(),
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )
    serialized = result.model_dump(mode="json")
    forbidden = {
        "order_id",
        "idempotency_key",
        "confirmation_id",
        "broker_method",
        "submit_order",
        "cancel_order",
        "replace_order",
    }

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert keys(serialized).isdisjoint(forbidden)
    assert serialized["execution_ready"] is False
    assert serialized["trading_methods"] is False


def test_source_payload_is_not_mutated() -> None:
    payload = _payload()
    original = deepcopy(payload)
    build_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_B,
        evaluated_at=NOW,
    )
    assert payload == original
