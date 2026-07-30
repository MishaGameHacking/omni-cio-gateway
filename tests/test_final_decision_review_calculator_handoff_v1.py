from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1, OrderSide
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.pretrade import (
    PreTradeBlocker,
    PreTradePreviewV1,
    PreviewFreshnessStatus,
    PreviewPriceBasis,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import (
    SellPreTradePreviewV1,
    SellPreviewPriceBasis,
)
from omni_cio.release.final_decision_review_calculator_handoff_v1 import (
    FinalDecisionReviewCalculatorScenarioHandoffError,
    FinalDecisionReviewCalculatorScenarioHandoffV1,
)
from omni_cio.release.final_decision_review_production_registration_v1 import (
    register_final_decision_review_production_sources,
)
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewScenarioSourceStoreV1,
)
from omni_cio.release.final_decision_review_trusted_scenario_publisher_v1 import (
    FinalDecisionReviewTrustedScenarioPublisherV1,
)


NOW = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")
KEY = "uid:handoff-a"


def _metadata(schema_name: str, *, retrieved_at: datetime = NOW) -> ContractMetadata:
    return ContractMetadata(
        schema_name=schema_name,
        retrieved_at=retrieved_at,
        account=ACCOUNT,
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation="calculator-handoff-test",
                retrieved_at=retrieved_at,
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _request(side: OrderSide) -> CapacityOrderRequestV1:
    lot_size = 1 if side is OrderSide.SELL else 10
    quantity_lots = 1 if side is OrderSide.SELL else 10
    reference_price = Decimal("98") if side is OrderSide.SELL else Decimal("100")
    units = lot_size * quantity_lots
    return CapacityOrderRequestV1(
        request_id=f"handoff-{side.value}-request",
        instrument_key=KEY,
        side=side,
        currency="RUB",
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=reference_price,
        intended_execution_days=2,
        units=units,
        order_notional=Decimal(units) * reference_price,
    )


def _intent(side: OrderSide) -> CapacityIntentDecisionGateV1:
    return CapacityIntentDecisionGateV1.model_construct(
        gate_ready=True,
        request=SimpleNamespace(expected_capacity_requests=(_request(side),)),
        no_action_option_id="option.no_action",
        final_option_id="option.limited_change",
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
    )


def _purchase_preview(*, ready: bool = True) -> PreTradePreviewV1:
    initial_amount = Decimal("10000")
    commission = Decimal("10")
    total = initial_amount + commission
    own_funds = Decimal("200000")
    blockers = () if ready else (PreTradeBlocker.AFFORDABILITY_UNCONFIRMED,)
    return PreTradePreviewV1(
        metadata=_metadata("pretrade_preview"),
        stable_key=KEY,
        instrument_uid="handoff-a",
        currency="RUB",
        price_basis=PreviewPriceBasis.BEST_ASK,
        price_source="t-invest-best-ask",
        price_time=NOW,
        evaluated_at=NOW,
        price_age_seconds=Decimal("0"),
        max_price_age_seconds=Decimal("120"),
        freshness_status=PreviewFreshnessStatus.FRESH,
        unit_price=Decimal("100"),
        lot_size=10,
        quantity_lots=10,
        initial_order_amount=Money(amount=initial_amount, currency="RUB"),
        canonical_commission=Money(amount=commission, currency="RUB"),
        accrued_interest=None,
        total_order_amount=Money(amount=total, currency="RUB"),
        own_funds=Money(amount=own_funds, currency="RUB"),
        remaining_cash=Money(amount=own_funds - total, currency="RUB"),
        target_value_limit=Money(amount=Decimal("150000"), currency="RUB"),
        affordable=ready,
        source_complete=True,
        integrity_confirmed=True,
        blockers=blockers,
        preview_ready=ready,
    )


def _sell_preview() -> SellPreTradePreviewV1:
    return SellPreTradePreviewV1(
        metadata=_metadata("sell_pretrade_preview"),
        stable_key=KEY,
        instrument_uid="handoff-a",
        currency="RUB",
        price_basis=SellPreviewPriceBasis.BEST_BID,
        price_source="t-invest-best-bid",
        price_time=NOW,
        evaluated_at=NOW,
        price_age_seconds=Decimal("0"),
        max_price_age_seconds=Decimal("120"),
        freshness_status=PreviewFreshnessStatus.FRESH,
        unit_price=Decimal("98"),
        lot_size=1,
        quantity_lots=1,
        quantity_units=1,
        position_lots=5,
        sell_max_lots=5,
        conflicting_open_sell_lots=0,
        available_after_open_orders_lots=5,
        remaining_position_lots=4,
        current_position_value=Money(amount=Decimal("500"), currency="RUB"),
        sold_position_value=Money(amount=Decimal("100"), currency="RUB"),
        gross_security_proceeds=Money(amount=Decimal("98"), currency="RUB"),
        accrued_interest_proceeds=Money(amount=Decimal("2"), currency="RUB"),
        gross_proceeds=Money(amount=Decimal("100"), currency="RUB"),
        canonical_commission=Money(amount=Decimal("1"), currency="RUB"),
        estimated_tax=Money(amount=Decimal("4"), currency="RUB"),
        net_proceeds=Money(amount=Decimal("95"), currency="RUB"),
        estimated_post_sale_position_value=Money(
            amount=Decimal("400"),
            currency="RUB",
        ),
        estimated_portfolio_value_before=Money(
            amount=Decimal("1000"),
            currency="RUB",
        ),
        estimated_portfolio_value_after=Money(
            amount=Decimal("995"),
            currency="RUB",
        ),
        current_weight=Decimal("0.5"),
        lower_weight=Decimal("0.35"),
        target_weight=Decimal("0.4"),
        upper_weight=Decimal("0.45"),
        estimated_post_sale_weight=Decimal("400") / Decimal("995"),
        reduction_value_limit=Money(amount=Decimal("100"), currency="RUB"),
        tax_basis_confirmed=True,
        open_orders_checked=True,
        position_availability_confirmed=True,
        source_complete=True,
        integrity_confirmed=True,
        blockers=(),
        preview_ready=True,
    )


def _risk(*, timestamp: datetime = NOW) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=timestamp, account=ACCOUNT),
        policy=SimpleNamespace(
            allow_margin=False,
            allow_short_sales=False,
            allow_derivatives=False,
            allow_currency_operations=False,
        ),
        decision_ready=True,
    )


def _handoff() -> FinalDecisionReviewCalculatorScenarioHandoffV1:
    publisher = FinalDecisionReviewTrustedScenarioPublisherV1(
        source_store=FinalDecisionReviewScenarioSourceStoreV1(),
    )
    return FinalDecisionReviewCalculatorScenarioHandoffV1(publisher=publisher)


def test_purchase_handoff_builds_gate_and_publishes_exact_bundle() -> None:
    handoff = _handoff()
    result = handoff.publish_purchase(
        scenario_id="scenario:handoff:purchase",
        base_intent_gate=_intent(OrderSide.BUY),
        previews=(_purchase_preview(),),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    bundle = handoff.publisher.source_store.load_bundle(
        "scenario:handoff:purchase",
        checked_at=NOW,
    )
    assert result.direction is OrderSide.BUY
    assert result.gate_ready is True
    assert result.source.operation == "purchase-gate-pro-forma-handoff"
    assert bundle is not None
    assert isinstance(bundle.purchase_gate, CapacityPreTradeDecisionGateV1)
    assert bundle.purchase_gate.assessed_at == NOW
    assert bundle.purchase_gate.order_created is False
    assert bundle.purchase_gate.trading_methods is False


def test_sell_handoff_builds_gate_and_publishes_exact_bundle() -> None:
    handoff = _handoff()
    result = handoff.publish_sell(
        scenario_id="scenario:handoff:sell",
        base_intent_gate=_intent(OrderSide.SELL),
        previews=(_sell_preview(),),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    bundle = handoff.publisher.source_store.load_bundle(
        "scenario:handoff:sell",
        checked_at=NOW,
    )
    assert result.direction is OrderSide.SELL
    assert result.gate_ready is True
    assert result.source.operation == "sell-gate-pro-forma-handoff"
    assert bundle is not None
    assert isinstance(bundle.sell_gate, CapacitySellPreTradeDecisionGateV1)
    assert bundle.sell_gate.assessed_at == NOW
    assert bundle.sell_gate.order_created is False
    assert bundle.sell_gate.trading_methods is False


def test_blocked_preview_is_published_only_as_blocked_review_source() -> None:
    handoff = _handoff()
    result = handoff.publish_purchase(
        scenario_id="scenario:handoff:blocked",
        base_intent_gate=_intent(OrderSide.BUY),
        previews=(_purchase_preview(ready=False),),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    assert result.gate_ready is False
    assert result.trade_authorized is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_handoff_rejects_raw_preview_without_mutating_store() -> None:
    handoff = _handoff()
    with pytest.raises(
        FinalDecisionReviewCalculatorScenarioHandoffError,
        match="FINAL_DECISION_REVIEW_HANDOFF_PURCHASE_PREVIEWS_INVALID",
    ):
        handoff.publish_purchase(
            scenario_id="scenario:handoff:raw",
            base_intent_gate=_intent(OrderSide.BUY),
            previews=({"stable_key": KEY},),  # type: ignore[arg-type]
            pro_forma_risk=_risk(),
            published_at=NOW,
        )
    assert handoff.publisher.source_store.active_bundle_count(checked_at=NOW) == 0


def test_handoff_preserves_risk_time_and_rejects_stale_publication() -> None:
    handoff = _handoff()
    with pytest.raises(
        FinalDecisionReviewCalculatorScenarioHandoffError,
        match="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_STALE",
    ):
        handoff.publish_purchase(
            scenario_id="scenario:handoff:stale",
            base_intent_gate=_intent(OrderSide.BUY),
            previews=(_purchase_preview(),),
            pro_forma_risk=_risk(),
            published_at=NOW + timedelta(seconds=901),
        )
    assert handoff.publisher.source_store.active_bundle_count(
        checked_at=NOW + timedelta(seconds=901)
    ) == 0


def test_runtime_handoff_uses_registered_publisher_and_store() -> None:
    runtime = register_final_decision_review_production_sources(
        bridge=object(),  # type: ignore[arg-type]
        portfolio_payload_loader=lambda: {},
    )
    assert runtime.calculator_handoff.publisher is runtime.scenario_publisher
    assert runtime.calculator_handoff.publisher.source_store is runtime.source_store
    assert runtime.public_source_publication_route_created is False
    assert runtime.broker_write_called is False
    assert runtime.trading_methods is False


def test_handoff_module_has_no_http_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_calculator_handoff_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "@app.post",
        "@app.put",
        "@app.delete",
        ".post_order(",
        ".replace_order(",
        ".cancel_order(",
        "request.body",
        "logger.exception",
    )
    assert all(marker not in source for marker in forbidden)
