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
from omni_cio.contracts.v1.sell_pretrade import (
    SellPreTradeBlocker,
    SellPreTradePreviewV1,
)
from omni_cio.pretrade import (
    LiveSellPreTradeIntegrationError,
    build_live_sell_pretrade_preview,
)


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
STABLE_KEY = "uid:asset-a"
INSTRUMENT_UID = "asset-a"


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
            stable_key=STABLE_KEY,
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
            rationale="Add cash without selling.",
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
            rationale="Sale needs tax evidence and live preview.",
            uses_sales=True,
            available_cash=Decimal("80"),
            planned_add_value=Decimal("100"),
            planned_reduce_value=Decimal("100"),
            residual_cash=Decimal("80"),
            blockers=(
                RebalanceBlocker.LIVE_PREVIEW_REQUIRED,
                RebalanceBlocker.SALES_REQUIRE_TAX_BASIS,
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
        breach_count=1,
        below_count=0,
        above_count=1,
        inside_count=0,
    )


def _money(amount: str, currency: str = "RUB") -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def _payload() -> dict[str, object]:
    source_time = NOW - timedelta(seconds=20)
    return {
        "status": "ok",
        "version": "3.9.1",
        "retrieved_at": NOW.isoformat(),
        "account": {"masked_id": "***3118"},
        "request": {
            "instrument_uid": INSTRUMENT_UID,
            "price_basis": "best_bid",
            "quantity_lots": 1,
            "direction": "ORDER_DIRECTION_SELL",
        },
        "instrument": {
            "uid": INSTRUMENT_UID,
            "currency": "RUB",
            "lot": 1,
        },
        "instrument_resolution": {"status": "resolved"},
        "market_price": {
            "status": "ok",
            "basis": "best_bid",
            "source": "T-Invest GetOrderBook best bid",
            "price": "98",
            "currency": "RUB",
            "lot_size": 1,
            "source_time": source_time.isoformat(),
        },
        "position_limits": {
            "status": "ok",
            "currency": "RUB",
            "position_lots": 5,
            "sell_max_lots": 5,
        },
        "open_orders": {
            "status": "ok",
            "checked": True,
            "conflicting_sell_lots": 0,
        },
        "order_preview": {
            "status": "ok",
            "lots_requested": 1,
            "initial_order_amount": _money("98"),
            "gross_proceeds": _money("100"),
            "executed_commission": _money("1"),
            "extra_bond": {"aci_value": _money("2")},
        },
        "commission_summary": {
            "status": "ok",
            "canonical_source": "executed_commission",
            "canonical_commission": _money("1"),
            "double_count_protection": True,
        },
        "tax_basis": {
            "status": "unavailable",
            "confirmed": False,
            "estimated_tax": {
                "amount": "unavailable",
                "currency": "RUB",
            },
        },
        "price_freshness": {
            "status": "fresh",
            "source_time": source_time.isoformat(),
            "age_seconds": "20",
            "fresh_threshold_seconds": "120",
        },
        "currency_consistency": {"status": "ok"},
        "calculation_checks": {
            "overall_status": "partial",
            "integrity_confirmed": False,
        },
        "quality": {
            "instrument_resolved": True,
            "position_availability_confirmed": True,
            "open_orders_checked": True,
            "tax_basis_confirmed": False,
            "commission_double_count_protected": True,
            "currency_consistent": True,
            "calculation_integrity_confirmed": False,
            "complete": True,
            "read_only": True,
            "no_order_created": True,
        },
        "complete": True,
        "component_errors": [],
        "trading_methods": False,
    }


def _build(loader):
    return build_live_sell_pretrade_preview(
        sale_capacity_loader=loader,
        rebalance_plan=_plan(),
        stable_key=STABLE_KEY,
        instrument_uid=INSTRUMENT_UID,
        price_basis="best_bid",
        quantity_lots=1,
        evaluated_at=NOW,
    )


def test_live_payload_builds_typed_fail_closed_preview_once() -> None:
    payload = _payload()
    original = deepcopy(payload)
    calls: list[tuple[str, str, int]] = []

    def loader(uid: str, basis: str, lots: int) -> dict[str, object]:
        calls.append((uid, basis, lots))
        return payload

    result = _build(loader)

    assert isinstance(result, SellPreTradePreviewV1)
    assert calls == [(INSTRUMENT_UID, "best_bid", 1)]
    assert payload == original
    assert result.source_complete is True
    assert result.tax_basis_confirmed is False
    assert SellPreTradeBlocker.TAX_BASIS_UNAVAILABLE in result.blockers
    assert SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED in result.blockers
    assert result.preview_ready is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_account_mismatch_is_preserved_as_typed_blocker() -> None:
    payload = _payload()
    payload["account"] = {"masked_id": "***9999"}

    result = _build(lambda uid, basis, lots: payload)

    assert SellPreTradeBlocker.ACCOUNT_MISMATCH in result.blockers
    assert result.preview_ready is False


def test_stale_price_remains_blocked_after_live_integration() -> None:
    payload = _payload()
    market_price = payload["market_price"]
    assert isinstance(market_price, dict)
    market_price["source_time"] = (NOW - timedelta(seconds=121)).isoformat()

    result = _build(lambda uid, basis, lots: payload)

    assert SellPreTradeBlocker.PRICE_STALE in result.blockers
    assert result.preview_ready is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("instrument_uid", "asset-b", "LIVE_SELL_INSTRUMENT_MISMATCH"),
        ("price_basis", "last_price", "LIVE_SELL_PRICE_BASIS_MISMATCH"),
        ("quantity_lots", 2, "LIVE_SELL_QUANTITY_MISMATCH"),
        ("direction", "ORDER_DIRECTION_BUY", "LIVE_SELL_DIRECTION_MISMATCH"),
    ),
)
def test_request_parameter_tampering_is_rejected(
    field: str,
    value: object,
    message: str,
) -> None:
    payload = _payload()
    request = payload["request"]
    assert isinstance(request, dict)
    request[field] = value

    with pytest.raises(LiveSellPreTradeIntegrationError, match=message):
        _build(lambda uid, basis, lots: payload)


@pytest.mark.parametrize("trading_value", (True, None, "false"))
def test_source_must_explicitly_preserve_trading_methods_false(
    trading_value: object,
) -> None:
    payload = _payload()
    payload["trading_methods"] = trading_value

    with pytest.raises(
        LiveSellPreTradeIntegrationError,
        match="LIVE_SELL_SOURCE_TRADING_ENABLED",
    ):
        _build(lambda uid, basis, lots: payload)


def test_non_mapping_loader_result_is_rejected() -> None:
    with pytest.raises(
        LiveSellPreTradeIntegrationError,
        match="LIVE_SELL_PAYLOAD_NOT_MAPPING",
    ):
        _build(lambda uid, basis, lots: None)  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("stable_key", "instrument_uid", "price_basis", "quantity_lots", "message"),
    (
        ("", INSTRUMENT_UID, "best_bid", 1, "LIVE_SELL_STABLE_KEY_REQUIRED"),
        (STABLE_KEY, "", "best_bid", 1, "LIVE_SELL_INSTRUMENT_UID_REQUIRED"),
        (STABLE_KEY, INSTRUMENT_UID, "manual", 1, "LIVE_SELL_PRICE_BASIS_INVALID"),
        (STABLE_KEY, INSTRUMENT_UID, "best_bid", 0, "LIVE_SELL_QUANTITY_INVALID"),
    ),
)
def test_invalid_input_is_rejected_before_collector_call(
    stable_key: str,
    instrument_uid: str,
    price_basis: str,
    quantity_lots: int,
    message: str,
) -> None:
    calls = 0

    def loader(uid: str, basis: str, lots: int) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _payload()

    with pytest.raises(LiveSellPreTradeIntegrationError, match=message):
        build_live_sell_pretrade_preview(
            sale_capacity_loader=loader,
            rebalance_plan=_plan(),
            stable_key=stable_key,
            instrument_uid=instrument_uid,
            price_basis=price_basis,
            quantity_lots=quantity_lots,
            evaluated_at=NOW,
        )

    assert calls == 0
