from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewScenarioSourceStoreV1,
)
import omni_cio.release.final_decision_review_calculator_publication_v1 as subject


NOW = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)


def _purchase_gate(timestamp: datetime = NOW) -> CapacityPreTradeDecisionGateV1:
    return CapacityPreTradeDecisionGateV1.model_construct(assessed_at=timestamp)


def _sell_gate(timestamp: datetime = NOW) -> CapacitySellPreTradeDecisionGateV1:
    return CapacitySellPreTradeDecisionGateV1.model_construct(assessed_at=timestamp)


def _risk(timestamp: datetime = NOW) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=timestamp)
    )


def test_publisher_publishes_exact_purchase_bundle() -> None:
    store = FinalDecisionReviewScenarioSourceStoreV1()
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=store
    )
    result = publisher.publish(
        scenario_id="calculator:buy:001",
        purchase_gate=_purchase_gate(),
        pro_forma_risk=_risk(),
        published_at=NOW + timedelta(seconds=5),
    )
    bundle = store.load_bundle(
        "calculator:buy:001",
        checked_at=NOW + timedelta(seconds=5),
    )
    assert bundle is not None
    assert bundle.direction is OrderSide.BUY
    assert bundle.purchase_gate is not None
    assert bundle.sell_gate is None
    assert result.direction is OrderSide.BUY
    assert result.source_age_seconds == 5
    assert result.internal_only is True
    assert result.calculator_owned is True
    assert result.user_controlled_publication_surface is False
    assert result.http_publication_method_created is False
    assert result.broker_write_called is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_publisher_publishes_sell_and_replaces_same_scenario() -> None:
    store = FinalDecisionReviewScenarioSourceStoreV1()
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=store
    )
    publisher.publish(
        scenario_id="calculator:replace:001",
        purchase_gate=_purchase_gate(),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    result = publisher.publish(
        scenario_id="calculator:replace:001",
        sell_gate=_sell_gate(NOW + timedelta(seconds=1)),
        pro_forma_risk=_risk(NOW + timedelta(seconds=1)),
        published_at=NOW + timedelta(seconds=2),
    )
    bundle = store.load_bundle(
        "calculator:replace:001",
        checked_at=NOW + timedelta(seconds=2),
    )
    assert result.replaced is True
    assert bundle is not None
    assert bundle.direction is OrderSide.SELL


@pytest.mark.parametrize(
    ("purchase_gate", "sell_gate"),
    [
        (None, None),
        (_purchase_gate(), _sell_gate()),
    ],
)
def test_publisher_rejects_zero_or_two_directional_gates(
    purchase_gate: CapacityPreTradeDecisionGateV1 | None,
    sell_gate: CapacitySellPreTradeDecisionGateV1 | None,
) -> None:
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=FinalDecisionReviewScenarioSourceStoreV1()
    )
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorPublicationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_DIRECTION_INVALID",
    ):
        publisher.publish(
            scenario_id="calculator:invalid-direction",
            purchase_gate=purchase_gate,
            sell_gate=sell_gate,
            pro_forma_risk=_risk(),
            published_at=NOW,
        )


def test_publisher_rejects_source_skew_before_store_mutation() -> None:
    store = FinalDecisionReviewScenarioSourceStoreV1()
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=store,
        max_source_skew_seconds=10,
    )
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorPublicationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SOURCE_SKEW_EXCEEDED",
    ):
        publisher.publish(
            scenario_id="calculator:skew",
            purchase_gate=_purchase_gate(),
            pro_forma_risk=_risk(NOW + timedelta(seconds=11)),
            published_at=NOW + timedelta(seconds=11),
        )
    assert store.active_bundle_count(checked_at=NOW + timedelta(seconds=11)) == 0


def test_publisher_rejects_stale_and_future_sources() -> None:
    store = FinalDecisionReviewScenarioSourceStoreV1()
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=store,
        max_publication_delay_seconds=60,
    )
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorPublicationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SOURCE_STALE",
    ):
        publisher.publish(
            scenario_id="calculator:stale",
            purchase_gate=_purchase_gate(),
            pro_forma_risk=_risk(),
            published_at=NOW + timedelta(seconds=61),
        )
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorPublicationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_FUTURE_SOURCE",
    ):
        publisher.publish(
            scenario_id="calculator:future",
            sell_gate=_sell_gate(NOW + timedelta(seconds=1)),
            pro_forma_risk=_risk(NOW + timedelta(seconds=1)),
            published_at=NOW,
        )
    assert store.active_bundle_count(checked_at=NOW) == 0


def test_publisher_rejects_naive_source_timestamp() -> None:
    publisher = subject.FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=FinalDecisionReviewScenarioSourceStoreV1()
    )
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorPublicationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_GATE_TIMESTAMP_INVALID",
    ):
        publisher.publish(
            scenario_id="calculator:naive",
            purchase_gate=_purchase_gate(NOW.replace(tzinfo=None)),
            pro_forma_risk=_risk(),
            published_at=NOW,
        )


def test_result_contract_rejects_safety_flag_tampering() -> None:
    with pytest.raises(
        subject.FinalDecisionReviewCalculatorPublicationError,
        match="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SAFETY_INVARIANT_FAILED",
    ):
        subject.FinalDecisionReviewCalculatorPublicationResultV1(
            scenario_id="calculator:tamper",
            direction=OrderSide.BUY,
            calculated_at=NOW,
            published_at=NOW,
            source_age_seconds=0,
            replaced=False,
            evicted=False,
            active_bundle_count=1,
            trade_authorized=True,
        )


def test_module_contains_no_public_route_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_calculator_publication_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "@app.get",
        "@app.post",
        "@app.put",
        "@app.delete",
        ".post_order(",
        ".cancel_order(",
        ".replace_order(",
        "withdraw",
        "transfer",
        "logger.exception",
    )
    assert all(marker not in source for marker in forbidden)
