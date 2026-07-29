from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.pretrade import PreviewFreshnessStatus
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
    SellPreviewPriceBasis,
)
from omni_cio.pretrade import (
    SellPreTradeOrchestratorError,
    build_sell_pretrade_preview,
)


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
KEY_REDUCE = "uid:asset-a"
KEY_ADD = "uid:asset-b"


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


def _plan(*, decision_ready: bool = True) -> ThresholdRebalancePlanV1:
    lines = (
        RebalanceLineV1(
            stable_key=KEY_REDUCE,
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
            stable_key=KEY_ADD,
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
    if decision_ready:
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
        preferred_id = "rebalance.cash_first"
    else:
        blockers = (RebalanceBlocker.DECISION_NOT_READY,)
        alternatives = (
            RebalanceAlternativeV1(
                alternative_id="rebalance.no_action",
                kind=RebalanceAlternativeKind.NO_ACTION,
                status=RebalanceAlternativeStatus.PREFERRED,
                title="Wait",
                rationale="Source decision is blocked.",
                uses_sales=False,
                available_cash=Decimal("80"),
                planned_add_value=Decimal("0"),
                planned_reduce_value=Decimal("0"),
                residual_cash=Decimal("80"),
            ),
            RebalanceAlternativeV1(
                alternative_id="rebalance.cash_first",
                kind=RebalanceAlternativeKind.CASH_FIRST,
                status=RebalanceAlternativeStatus.BLOCKED,
                title="Blocked cash deployment",
                rationale="Source decision is blocked.",
                uses_sales=False,
                available_cash=Decimal("80"),
                planned_add_value=Decimal("0"),
                planned_reduce_value=Decimal("0"),
                residual_cash=Decimal("80"),
                blockers=blockers,
            ),
            RebalanceAlternativeV1(
                alternative_id="rebalance.full_threshold",
                kind=RebalanceAlternativeKind.FULL_THRESHOLD,
                status=RebalanceAlternativeStatus.BLOCKED,
                title="Blocked full repair",
                rationale="Source decision is blocked.",
                uses_sales=False,
                available_cash=Decimal("80"),
                planned_add_value=Decimal("0"),
                planned_reduce_value=Decimal("0"),
                residual_cash=Decimal("80"),
                blockers=blockers,
            ),
        )
        preferred_id = "rebalance.no_action"
    return ThresholdRebalancePlanV1(
        metadata=_metadata(),
        source_decision_schema_version="1.0",
        lines=lines,
        alternatives=alternatives,
        preferred_alternative_id=preferred_id,
        decision_ready=decision_ready,
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
            "instrument_uid": "asset-a",
            "price_basis": "best_bid",
            "quantity_lots": 1,
            "direction": "ORDER_DIRECTION_SELL",
        },
        "instrument": {
            "uid": "asset-a",
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
            "source": "T-Invest GetMaxLots sell_limits",
            "currency": "RUB",
            "position_lots": 5,
            "sell_max_lots": 5,
            "current_position_value": _money("500"),
        },
        "open_orders": {
            "status": "ok",
            "checked": True,
            "conflicting_sell_lots": 0,
            "source": "T-Invest GetOrders",
        },
        "order_preview": {
            "status": "ok",
            "source": "T-Invest GetOrderPrice",
            "lots_requested": 1,
            "initial_order_amount": _money("98"),
            "gross_proceeds": _money("100"),
            "net_proceeds": _money("95"),
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
            "status": "ok",
            "confirmed": True,
            "source": "normalized portfolio tax evidence",
            "estimated_tax": _money("4"),
        },
        "price_freshness": {
            "status": "fresh",
            "source_time": source_time.isoformat(),
            "age_seconds": "30",
            "fresh_threshold_seconds": "120",
        },
        "quality": {
            "instrument_resolved": True,
            "position_availability_confirmed": True,
            "open_orders_checked": True,
            "tax_basis_confirmed": True,
            "commission_double_count_protected": True,
            "currency_consistent": True,
            "calculation_integrity_confirmed": True,
            "complete": True,
            "read_only": True,
            "no_order_created": True,
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


def test_fresh_complete_sell_preview_is_ready_and_reconciles() -> None:
    result = build_sell_pretrade_preview(
        _payload(),
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )

    assert result.preview_ready is True
    assert result.blockers == ()
    assert result.price_basis == SellPreviewPriceBasis.BEST_BID
    assert result.freshness_status == PreviewFreshnessStatus.FRESH
    assert result.quantity_units == 1
    assert result.remaining_position_lots == 4
    assert result.sold_position_value is not None
    assert result.sold_position_value.amount == Decimal("100")
    assert result.gross_proceeds is not None
    assert result.gross_proceeds.amount == Decimal("100")
    assert result.net_proceeds is not None
    assert result.net_proceeds.amount == Decimal("95")
    assert result.estimated_portfolio_value_before is not None
    assert result.estimated_portfolio_value_before.amount == Decimal("1000")
    assert result.estimated_portfolio_value_after is not None
    assert result.estimated_portfolio_value_after.amount == Decimal("995")
    assert result.estimated_post_sale_weight == Decimal("400") / Decimal("995")
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_missing_tax_basis_is_a_hard_blocker() -> None:
    payload = _payload()
    payload["tax_basis"] = {"status": "unavailable", "confirmed": False}
    quality = payload["quality"]
    assert isinstance(quality, dict)
    quality["tax_basis_confirmed"] = False

    result = build_sell_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )

    assert SellPreTradeBlocker.TAX_BASIS_UNAVAILABLE in result.blockers
    assert SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED in result.blockers
    assert result.preview_ready is False


def test_stale_or_manual_price_cannot_become_ready() -> None:
    stale = _payload()
    market_price = stale["market_price"]
    assert isinstance(market_price, dict)
    market_price["source_time"] = (NOW - timedelta(seconds=121)).isoformat()
    result = build_sell_pretrade_preview(
        stale,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert result.freshness_status == PreviewFreshnessStatus.STALE
    assert SellPreTradeBlocker.PRICE_STALE in result.blockers

    manual = _payload()
    request = manual["request"]
    market_price = manual["market_price"]
    assert isinstance(request, dict)
    assert isinstance(market_price, dict)
    request["price_basis"] = "manual"
    market_price["basis"] = "manual"
    market_price["source_time"] = "not_applicable"
    result = build_sell_pretrade_preview(
        manual,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert result.freshness_status == PreviewFreshnessStatus.MANUAL_INPUT
    assert SellPreTradeBlocker.MANUAL_PRICE_NOT_ALLOWED in result.blockers


def test_position_limits_and_open_orders_prevent_oversell() -> None:
    max_lots = _payload()
    position_limits = max_lots["position_limits"]
    assert isinstance(position_limits, dict)
    position_limits["sell_max_lots"] = 0
    result = build_sell_pretrade_preview(
        max_lots,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.POSITION_INSUFFICIENT in result.blockers

    conflict = _payload()
    request = conflict["request"]
    open_orders = conflict["open_orders"]
    assert isinstance(request, dict)
    assert isinstance(open_orders, dict)
    request["quantity_lots"] = 2
    open_orders["conflicting_sell_lots"] = 4
    result = build_sell_pretrade_preview(
        conflict,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert result.available_after_open_orders_lots == 1
    assert SellPreTradeBlocker.OPEN_ORDER_CONFLICT in result.blockers
    assert SellPreTradeBlocker.POSITION_INSUFFICIENT in result.blockers


def test_short_sale_is_explicitly_forbidden() -> None:
    payload = _payload()
    request = payload["request"]
    position_limits = payload["position_limits"]
    assert isinstance(request, dict)
    assert isinstance(position_limits, dict)
    request["quantity_lots"] = 6
    position_limits["sell_max_lots"] = 6

    result = build_sell_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )

    assert SellPreTradeBlocker.SHORT_SALE_FORBIDDEN in result.blockers
    assert result.remaining_position_lots is None
    assert result.no_short_sale is True


def test_target_reduction_overshoot_and_band_undershoot_are_blocked() -> None:
    payload = _payload()
    request = payload["request"]
    order_preview = payload["order_preview"]
    tax_basis = payload["tax_basis"]
    assert isinstance(request, dict)
    assert isinstance(order_preview, dict)
    assert isinstance(tax_basis, dict)
    request["quantity_lots"] = 4
    order_preview["initial_order_amount"] = _money("392")
    order_preview["gross_proceeds"] = _money("400")
    order_preview["net_proceeds"] = _money("391")
    order_preview["extra_bond"] = {"aci_value": _money("8")}
    tax_basis["estimated_tax"] = _money("8")

    result = build_sell_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )

    assert result.sold_position_value is not None
    assert result.sold_position_value.amount == Decimal("400")
    assert SellPreTradeBlocker.TARGET_REDUCTION_OVERSHOOT in result.blockers
    assert SellPreTradeBlocker.POST_SALE_BAND_UNDERSHOOT in result.blockers


def test_account_direction_plan_and_target_binding_are_fail_closed() -> None:
    wrong_account = _payload()
    wrong_account["account"] = {"masked_id": "***9999"}
    result = build_sell_pretrade_preview(
        wrong_account,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.ACCOUNT_MISMATCH in result.blockers

    wrong_direction = _payload()
    request = wrong_direction["request"]
    assert isinstance(request, dict)
    request["direction"] = "ORDER_DIRECTION_BUY"
    result = build_sell_pretrade_preview(
        wrong_direction,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.DIRECTION_MISMATCH in result.blockers

    blocked_plan = build_sell_pretrade_preview(
        _payload(),
        _plan(decision_ready=False),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.PLAN_NOT_READY in blocked_plan.blockers
    assert (
        SellPreTradeBlocker.SALE_ALTERNATIVE_NOT_AVAILABLE
        in blocked_plan.blockers
    )

    wrong_target_payload = _payload()
    position_limits = wrong_target_payload["position_limits"]
    assert isinstance(position_limits, dict)
    position_limits["current_position_value"] = _money("300")
    wrong_target = build_sell_pretrade_preview(
        wrong_target_payload,
        _plan(),
        stable_key=KEY_ADD,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.TARGET_NOT_REDUCE in wrong_target.blockers


def test_currency_position_value_and_arithmetic_mismatches_are_preserved() -> None:
    currency_mismatch = _payload()
    order_preview = currency_mismatch["order_preview"]
    assert isinstance(order_preview, dict)
    order_preview["initial_order_amount"] = _money("98", "USD")
    currency_mismatch["currency_consistency"] = {"status": "warning"}
    result = build_sell_pretrade_preview(
        currency_mismatch,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.CURRENCY_MISMATCH in result.blockers

    value_mismatch = _payload()
    position_limits = value_mismatch["position_limits"]
    assert isinstance(position_limits, dict)
    position_limits["current_position_value"] = _money("499")
    result = build_sell_pretrade_preview(
        value_mismatch,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.POSITION_VALUE_MISMATCH in result.blockers

    arithmetic = _payload()
    order_preview = arithmetic["order_preview"]
    assert isinstance(order_preview, dict)
    order_preview["net_proceeds"] = _money("96")
    result = build_sell_pretrade_preview(
        arithmetic,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    assert SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED in result.blockers


def test_incomplete_source_and_unchecked_orders_are_blocked() -> None:
    payload = _payload()
    payload["complete"] = False
    quality = payload["quality"]
    open_orders = payload["open_orders"]
    assert isinstance(quality, dict)
    assert isinstance(open_orders, dict)
    quality["complete"] = False
    quality["open_orders_checked"] = False
    open_orders["checked"] = False

    result = build_sell_pretrade_preview(
        payload,
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )

    assert SellPreTradeBlocker.SOURCE_INCOMPLETE in result.blockers
    assert SellPreTradeBlocker.OPEN_ORDERS_UNCHECKED in result.blockers


def test_builder_is_deterministic_and_does_not_mutate_inputs() -> None:
    payload = _payload()
    plan = _plan()
    payload_before = deepcopy(payload)
    plan_before = plan.model_copy(deep=True)

    first = build_sell_pretrade_preview(
        payload,
        plan,
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    second = build_sell_pretrade_preview(
        payload,
        plan,
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )

    assert first == second
    assert payload == payload_before
    assert plan == plan_before


def test_contract_rejects_tampered_financial_summary() -> None:
    result = build_sell_pretrade_preview(
        _payload(),
        _plan(),
        stable_key=KEY_REDUCE,
        evaluated_at=NOW,
    )
    payload = result.model_dump(mode="python")
    payload["net_proceeds"]["amount"] = Decimal("999")

    with pytest.raises(ValidationError, match="net sell proceeds"):
        SellPreTradePreviewV1.model_validate(payload)


def test_invalid_threshold_and_missing_line_raise_before_normalization() -> None:
    with pytest.raises(
        SellPreTradeOrchestratorError,
        match="INVALID_SELL_PRICE_FRESHNESS_THRESHOLD",
    ):
        build_sell_pretrade_preview(
            _payload(),
            _plan(),
            stable_key=KEY_REDUCE,
            evaluated_at=NOW,
            max_price_age_seconds=Decimal("0"),
        )

    with pytest.raises(
        SellPreTradeOrchestratorError,
        match="SELL_REBALANCE_LINE_NOT_FOUND_OR_DUPLICATE",
    ):
        build_sell_pretrade_preview(
            _payload(),
            _plan(),
            stable_key="uid:missing",
            evaluated_at=NOW,
        )


def test_sell_preview_has_no_network_or_execution_surface() -> None:
    source = Path("omni_cio/pretrade/sell_orchestrator_v1.py").read_text(
        encoding="utf-8"
    )
    lowered = source.casefold()
    assert "requests" not in lowered
    assert "httpx" not in lowered
    assert "grpc" not in lowered
    assert "postorder" not in lowered
    assert "trading_methods=true" not in lowered
