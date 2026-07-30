from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityMetricsV1,
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionSetV1,
)
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
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
    FinalDecisionReviewCalculatorScenarioHandoffV1,
)
from omni_cio.release.final_decision_review_calculator_intent_workflow_v1 import (
    FinalDecisionReviewCalculatorIntentWorkflowError,
    FinalDecisionReviewCalculatorIntentWorkflowV1,
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
KEY = "uid:intent-workflow-a"


def _metadata(schema_name: str) -> ContractMetadata:
    return ContractMetadata(
        schema_name=schema_name,
        retrieved_at=NOW,
        account=ACCOUNT,
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation="intent-workflow-test",
                retrieved_at=NOW,
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _request(side: OrderSide, *, quantity_lots: int | None = None) -> CapacityOrderRequestV1:
    lot_size = 1 if side is OrderSide.SELL else 10
    lots = quantity_lots if quantity_lots is not None else (1 if side is OrderSide.SELL else 10)
    price = Decimal("98") if side is OrderSide.SELL else Decimal("100")
    units = lot_size * lots
    return CapacityOrderRequestV1(
        request_id=f"intent-workflow-{side.value}-request",
        instrument_key=KEY,
        side=side,
        currency="RUB",
        quantity_lots=lots,
        lot_size=lot_size,
        reference_price=price,
        intended_execution_days=2,
        units=units,
        order_notional=Decimal(units) * price,
    )


def _decision() -> DecisionSetV1:
    return DecisionSetV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=NOW),
        recommendation_ready=True,
        abstain=False,
        preferred_option_id="option.limited_change",
        options=(
            SimpleNamespace(
                option_id="option.no_action",
                kind=DecisionOptionKind.NO_ACTION,
                status=DecisionOptionStatus.AVAILABLE,
                action=DecisionAction.HOLD,
            ),
            SimpleNamespace(
                option_id="option.limited_change",
                kind=DecisionOptionKind.LIMITED_CHANGE,
                status=DecisionOptionStatus.PREFERRED,
                action=DecisionAction.REVIEW_LIMITED_CHANGE,
            ),
        ),
    )


def _intent_request(side: OrderSide) -> CapacityIntentDecisionGateRequestV1:
    return CapacityIntentDecisionGateRequestV1(
        gate_id=f"intent-workflow-{side.value}-gate",
        requested_option_id="option.limited_change",
        expected_capacity_requests=(_request(side),),
    )


def _assessment(side: OrderSide, *, exact: bool = True) -> CapacityAssessmentV1:
    request = _request(side, quantity_lots=None if exact else 2)
    metrics = CapacityMetricsV1.model_construct(
        safe_notional_for_requested_window=request.order_notional,
        safe_lots_for_requested_window=request.quantity_lots,
    )
    return CapacityAssessmentV1.model_construct(
        assessed_at=NOW,
        capacity_ready=True,
        request=request,
        metrics=metrics,
        blockers=(),
    )


def _purchase_preview() -> PreTradePreviewV1:
    initial = Decimal("10000")
    commission = Decimal("10")
    own_funds = Decimal("200000")
    total = initial + commission
    return PreTradePreviewV1(
        metadata=_metadata("pretrade_preview"),
        stable_key=KEY,
        instrument_uid="intent-workflow-a",
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
        initial_order_amount=Money(amount=initial, currency="RUB"),
        canonical_commission=Money(amount=commission, currency="RUB"),
        accrued_interest=None,
        total_order_amount=Money(amount=total, currency="RUB"),
        own_funds=Money(amount=own_funds, currency="RUB"),
        remaining_cash=Money(amount=own_funds - total, currency="RUB"),
        target_value_limit=Money(amount=Decimal("150000"), currency="RUB"),
        affordable=True,
        source_complete=True,
        integrity_confirmed=True,
        blockers=(),
        preview_ready=True,
    )


def _sell_preview() -> SellPreTradePreviewV1:
    return SellPreTradePreviewV1(
        metadata=_metadata("sell_pretrade_preview"),
        stable_key=KEY,
        instrument_uid="intent-workflow-a",
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
        estimated_post_sale_position_value=Money(amount=Decimal("400"), currency="RUB"),
        estimated_portfolio_value_before=Money(amount=Decimal("1000"), currency="RUB"),
        estimated_portfolio_value_after=Money(amount=Decimal("995"), currency="RUB"),
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


def _risk() -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=NOW, account=ACCOUNT),
        policy=SimpleNamespace(
            allow_margin=False,
            allow_short_sales=False,
            allow_derivatives=False,
            allow_currency_operations=False,
        ),
        decision_ready=True,
    )


def _workflow() -> FinalDecisionReviewCalculatorIntentWorkflowV1:
    publisher = FinalDecisionReviewTrustedScenarioPublisherV1(
        source_store=FinalDecisionReviewScenarioSourceStoreV1(),
    )
    handoff = FinalDecisionReviewCalculatorScenarioHandoffV1(publisher=publisher)
    return FinalDecisionReviewCalculatorIntentWorkflowV1(handoff=handoff)


def test_purchase_workflow_builds_exact_intent_and_publishes() -> None:
    workflow = _workflow()
    result = workflow.publish_purchase(
        scenario_id="scenario:intent-workflow:purchase",
        decision=_decision(),
        intent_request=_intent_request(OrderSide.BUY),
        capacity_assessments=(_assessment(OrderSide.BUY),),
        previews=(_purchase_preview(),),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    bundle = workflow.handoff.publisher.source_store.load_bundle(
        "scenario:intent-workflow:purchase",
        checked_at=NOW,
    )
    assert result.direction is OrderSide.BUY
    assert result.gate_ready is True
    assert bundle is not None
    assert bundle.purchase_gate is not None
    assert bundle.purchase_gate.base_intent_gate.gate_ready is True
    assert bundle.purchase_gate.assessed_at == NOW


def test_sell_workflow_builds_exact_intent_and_publishes() -> None:
    workflow = _workflow()
    result = workflow.publish_sell(
        scenario_id="scenario:intent-workflow:sell",
        decision=_decision(),
        intent_request=_intent_request(OrderSide.SELL),
        capacity_assessments=(_assessment(OrderSide.SELL),),
        previews=(_sell_preview(),),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    assert result.direction is OrderSide.SELL
    assert result.gate_ready is True


def test_capacity_intent_mismatch_can_only_publish_blocked_source() -> None:
    workflow = _workflow()
    result = workflow.publish_purchase(
        scenario_id="scenario:intent-workflow:blocked",
        decision=_decision(),
        intent_request=_intent_request(OrderSide.BUY),
        capacity_assessments=(_assessment(OrderSide.BUY, exact=False),),
        previews=(_purchase_preview(),),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    assert result.gate_ready is False
    assert result.trade_authorized is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_workflow_rejects_raw_assessments_before_store_mutation() -> None:
    workflow = _workflow()
    with pytest.raises(
        FinalDecisionReviewCalculatorIntentWorkflowError,
        match="FINAL_DECISION_REVIEW_INTENT_WORKFLOW_ASSESSMENTS_INVALID",
    ):
        workflow.publish_purchase(
            scenario_id="scenario:intent-workflow:raw",
            decision=_decision(),
            intent_request=_intent_request(OrderSide.BUY),
            capacity_assessments=({"capacity_ready": True},),  # type: ignore[arg-type]
            previews=(_purchase_preview(),),
            pro_forma_risk=_risk(),
            published_at=NOW,
        )
    assert workflow.handoff.publisher.source_store.active_bundle_count(checked_at=NOW) == 0


def test_runtime_workflow_reuses_exact_registered_handoff() -> None:
    runtime = register_final_decision_review_production_sources(
        bridge=object(),  # type: ignore[arg-type]
        portfolio_payload_loader=lambda: {},
    )
    assert runtime.calculator_intent_workflow.handoff is runtime.calculator_handoff
    assert runtime.calculator_intent_workflow.handoff.publisher is runtime.scenario_publisher
    assert runtime.public_source_publication_route_created is False
    assert runtime.broker_write_called is False
    assert runtime.trading_methods is False


def test_intent_workflow_module_has_no_http_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_calculator_intent_workflow_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "@app.get",
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
