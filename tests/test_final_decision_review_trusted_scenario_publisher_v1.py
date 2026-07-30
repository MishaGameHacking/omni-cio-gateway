from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1, OrderSide
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationDisposition,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_production_registration_v1 import (
    register_final_decision_review_production_sources,
)
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewScenarioSourceStoreV1,
)
import omni_cio.release.final_decision_review_trusted_scenario_publisher_v1 as subject


NOW = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***1234", account_type="brokerage")
OTHER_ACCOUNT = AccountReference(masked_id="***9876", account_type="brokerage")


def _request(side: OrderSide, key: str = "uid:instrument-1") -> CapacityOrderRequestV1:
    return CapacityOrderRequestV1.model_construct(
        request_id=f"request:{side.value}:001",
        instrument_key=key,
        side=side,
    )


def _coverage(account: AccountReference, key: str = "uid:instrument-1") -> object:
    return SimpleNamespace(
        instrument_key=key,
        preview=SimpleNamespace(metadata=SimpleNamespace(account=account)),
    )


def _purchase_gate(
    *,
    timestamp: datetime = NOW,
    account: AccountReference = ACCOUNT,
    side: OrderSide = OrderSide.BUY,
    gate_ready: bool = True,
) -> CapacityPreTradeDecisionGateV1:
    request = _request(side)
    return CapacityPreTradeDecisionGateV1.model_construct(
        assessed_at=timestamp,
        gate_ready=gate_ready,
        base_intent_gate=SimpleNamespace(
            request=SimpleNamespace(expected_capacity_requests=(request,))
        ),
        coverage=(_coverage(account),),
        order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _sell_gate(
    *,
    timestamp: datetime = NOW,
    account: AccountReference = ACCOUNT,
) -> CapacitySellPreTradeDecisionGateV1:
    request = _request(OrderSide.SELL)
    return CapacitySellPreTradeDecisionGateV1.model_construct(
        assessed_at=timestamp,
        gate_ready=True,
        base_intent_gate=SimpleNamespace(
            request=SimpleNamespace(expected_capacity_requests=(request,))
        ),
        coverage=(_coverage(account),),
        order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _risk(
    *,
    timestamp: datetime = NOW,
    account: AccountReference = ACCOUNT,
    decision_ready: bool = True,
    allow_margin: bool = False,
) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=timestamp, account=account),
        policy=SimpleNamespace(
            allow_margin=allow_margin,
            allow_short_sales=False,
            allow_derivatives=False,
            allow_currency_operations=False,
        ),
        decision_ready=decision_ready,
    )


def _publisher(
    *,
    ttl_seconds: int = 900,
    capacity: int = 64,
) -> subject.FinalDecisionReviewTrustedScenarioPublisherV1:
    return subject.FinalDecisionReviewTrustedScenarioPublisherV1(
        source_store=FinalDecisionReviewScenarioSourceStoreV1(
            ttl_seconds=ttl_seconds,
            capacity=capacity,
        ),
        max_source_age_seconds=900,
        future_tolerance_seconds=60,
    )


def test_trusted_publisher_publishes_exact_purchase_bundle() -> None:
    publisher = _publisher()
    gate = _purchase_gate()
    risk = _risk()

    result = publisher.publish(
        scenario_id="scenario:purchase:001",
        purchase_gate=gate,
        pro_forma_risk=risk,
        provider="omni-cio",
        operation="publish-trusted-scenario",
        published_at=NOW,
    )

    bundle = publisher.source_store.load_bundle(
        "scenario:purchase:001",
        checked_at=NOW,
    )
    assert result.disposition is TrustedScenarioPublicationDisposition.PUBLISHED
    assert result.direction is OrderSide.BUY
    assert result.account == ACCOUNT
    assert result.instrument_count == 1
    assert result.gate_ready is True
    assert result.pro_forma_decision_ready is True
    assert result.source.provider == "omni-cio"
    assert result.internal_only is True
    assert result.http_route_created is False
    assert result.broker_write_called is False
    assert result.trading_methods is False
    assert bundle is not None
    assert bundle.purchase_gate is gate
    assert bundle.pro_forma_risk is risk


def test_trusted_publisher_supports_sell_and_exact_replacement() -> None:
    publisher = _publisher()
    first = publisher.publish(
        scenario_id="scenario:sell:001",
        sell_gate=_sell_gate(),
        pro_forma_risk=_risk(),
        provider="omni-cio",
        operation="publish-trusted-scenario",
        published_at=NOW,
    )
    second = publisher.publish(
        scenario_id="scenario:sell:001",
        sell_gate=_sell_gate(timestamp=NOW + timedelta(seconds=1)),
        pro_forma_risk=_risk(timestamp=NOW + timedelta(seconds=1)),
        provider="omni-cio",
        operation="replace-trusted-scenario",
        published_at=NOW + timedelta(seconds=1),
    )
    assert first.direction is OrderSide.SELL
    assert first.source_replaced is False
    assert second.disposition is TrustedScenarioPublicationDisposition.REPLACED
    assert second.source_replaced is True
    assert second.active_bundle_count == 1


@pytest.mark.parametrize(
    ("gate_time", "risk_time", "published_at", "error_code"),
    (
        (
            NOW,
            NOW + timedelta(seconds=1),
            NOW + timedelta(seconds=1),
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_TIMESTAMP_MISMATCH",
        ),
        (
            NOW,
            NOW,
            NOW + timedelta(seconds=901),
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_STALE",
        ),
        (
            NOW + timedelta(seconds=61),
            NOW + timedelta(seconds=61),
            NOW,
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_FROM_FUTURE",
        ),
    ),
)
def test_trusted_publisher_rejects_time_mismatch_stale_and_future(
    gate_time: datetime,
    risk_time: datetime,
    published_at: datetime,
    error_code: str,
) -> None:
    publisher = _publisher()
    with pytest.raises(
        subject.FinalDecisionReviewTrustedScenarioPublisherError,
        match=error_code,
    ):
        publisher.publish(
            scenario_id="scenario:time:001",
            purchase_gate=_purchase_gate(timestamp=gate_time),
            pro_forma_risk=_risk(timestamp=risk_time),
            provider="omni-cio",
            operation="publish-trusted-scenario",
            published_at=published_at,
        )
    assert publisher.source_store.active_bundle_count(checked_at=published_at) == 0


def test_trusted_publisher_rejects_account_and_direction_mismatch() -> None:
    publisher = _publisher()
    with pytest.raises(
        subject.FinalDecisionReviewTrustedScenarioPublisherError,
        match="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_RISK_ACCOUNT_MISMATCH",
    ):
        publisher.publish(
            scenario_id="scenario:account:001",
            purchase_gate=_purchase_gate(),
            pro_forma_risk=_risk(account=OTHER_ACCOUNT),
            provider="omni-cio",
            operation="publish-trusted-scenario",
            published_at=NOW,
        )
    with pytest.raises(
        subject.FinalDecisionReviewTrustedScenarioPublisherError,
        match="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_DIRECTION_MISMATCH",
    ):
        publisher.publish(
            scenario_id="scenario:direction:001",
            purchase_gate=_purchase_gate(side=OrderSide.SELL),
            pro_forma_risk=_risk(),
            provider="omni-cio",
            operation="publish-trusted-scenario",
            published_at=NOW,
        )


def test_trusted_publisher_rejects_raw_types_and_unsafe_policy() -> None:
    publisher = _publisher()
    with pytest.raises(
        subject.FinalDecisionReviewTrustedScenarioPublisherError,
        match="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_PRO_FORMA_TYPE_INVALID",
    ):
        publisher.publish(
            scenario_id="scenario:raw-risk:001",
            purchase_gate=_purchase_gate(),
            pro_forma_risk={"decision_ready": True},  # type: ignore[arg-type]
            provider="omni-cio",
            operation="publish-trusted-scenario",
            published_at=NOW,
        )
    with pytest.raises(
        subject.FinalDecisionReviewTrustedScenarioPublisherError,
        match="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_RISK_POLICY_UNSAFE",
    ):
        publisher.publish(
            scenario_id="scenario:unsafe:001",
            purchase_gate=_purchase_gate(),
            pro_forma_risk=_risk(allow_margin=True),
            provider="omni-cio",
            operation="publish-trusted-scenario",
            published_at=NOW,
        )


def test_trusted_publisher_serializes_concurrent_replacement() -> None:
    publisher = _publisher()

    def publish(_: int) -> TrustedScenarioPublicationDisposition:
        return publisher.publish(
            scenario_id="scenario:concurrent:001",
            purchase_gate=_purchase_gate(),
            pro_forma_risk=_risk(),
            provider="omni-cio",
            operation="publish-trusted-scenario",
            published_at=NOW,
        ).disposition

    with ThreadPoolExecutor(max_workers=8) as pool:
        dispositions = tuple(pool.map(publish, range(8)))

    assert dispositions.count(TrustedScenarioPublicationDisposition.PUBLISHED) == 1
    assert dispositions.count(TrustedScenarioPublicationDisposition.REPLACED) == 7
    assert publisher.source_store.active_bundle_count(checked_at=NOW) == 1


def test_production_registration_uses_one_store_for_publisher_and_wiring() -> None:
    runtime = register_final_decision_review_production_sources(
        bridge=object(),  # type: ignore[arg-type]
        portfolio_payload_loader=lambda: {},
    )
    assert runtime.scenario_publisher.source_store is runtime.source_store
    assert runtime.source_wiring.source_store is runtime.source_store
    assert runtime.internal_only is True
    assert runtime.startup_broker_call_performed is False
    assert runtime.public_source_publication_route_created is False
    assert runtime.broker_write_called is False
    assert runtime.trading_methods is False


def test_trusted_publisher_module_has_no_public_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_trusted_scenario_publisher_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "@app.post",
        "@app.put",
        "@app.delete",
        ".post_order(",
        ".replace_order(",
        ".cancel_order(",
        "withdraw",
        "request.body",
        "logger.exception",
    )
    assert all(marker not in source for marker in forbidden)
