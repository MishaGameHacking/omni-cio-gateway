from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1, OrderSide
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_directional_pretrade import (
    CapacityDirectionalPreTradeReviewV1,
)
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingBlocker,
    ProFormaRiskIntentBindingV1,
    ProFormaRiskIntentBindingWarning,
    ProFormaRiskScenarioV1,
)
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationEnvelopeV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1
from omni_cio.decision.pro_forma_risk_binding_v1 import (
    ProFormaRiskIntentBindingError,
    bind_pro_forma_risk_to_intent,
    build_pro_forma_risk_scenario,
)
from omni_cio.risk.policy_v1 import default_conservative_risk_policy


NOW = datetime(2026, 7, 29, 22, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")
OTHER_ACCOUNT = AccountReference(masked_id="****9876")
KEY = "uid:pro-forma-a"
OTHER_KEY = "uid:pro-forma-b"
OPTION = "option.limited_change"
NO_ACTION = "option.no_action"


def _metadata(
    *,
    retrieved_at: datetime = NOW,
    account: AccountReference = ACCOUNT,
) -> ContractMetadata:
    return ContractMetadata(
        schema_name="risk_policy_evaluation",
        retrieved_at=retrieved_at,
        account=account,
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation="pro-forma-risk-binding-test",
                retrieved_at=retrieved_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _risk(
    *,
    retrieved_at: datetime = NOW,
    account: AccountReference = ACCOUNT,
    ready: bool = True,
    status: RiskOverallStatus = RiskOverallStatus.PASS,
    breaches: int = 0,
    warnings: int = 0,
    unknowns: int = 0,
    policy=None,
) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=_metadata(retrieved_at=retrieved_at, account=account),
        policy=policy or default_conservative_risk_policy(),
        overall_status=status,
        decision_ready=ready,
        checks=(),
        breach_count=breaches,
        warning_count=warnings,
        unknown_count=unknowns,
        no_cross_currency_aggregation=True,
    )


def _request(
    instrument_key: str = KEY,
    *,
    side: OrderSide = OrderSide.BUY,
    quantity_lots: int = 2,
) -> CapacityOrderRequestV1:
    lot_size = 10
    reference_price = Decimal("100")
    units = quantity_lots * lot_size
    return CapacityOrderRequestV1(
        request_id=f"request-{instrument_key}-{quantity_lots}",
        instrument_key=instrument_key,
        side=side,
        currency="RUB",
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=reference_price,
        intended_execution_days=2,
        units=units,
        order_notional=Decimal(units) * reference_price,
    )


def _base_explanation(
    *,
    requests: tuple[CapacityOrderRequestV1, ...] | None = None,
    current_risk: RiskPolicyEvaluationV1 | None = None,
    ready: bool = True,
) -> RiskPreTradeExplanationEnvelopeV1:
    intent_requests = requests or (_request(),)
    intent_request = CapacityIntentDecisionGateRequestV1(
        gate_id="pro-forma-binding-gate",
        requested_option_id=OPTION,
        expected_capacity_requests=intent_requests,
    )
    intent_gate = CapacityIntentDecisionGateV1.model_construct(
        request=intent_request,
        gate_ready=ready,
    )
    directional_review = CapacityDirectionalPreTradeReviewV1.model_construct(
        direction=intent_requests[0].side,
        base_intent_gate=intent_gate,
    )
    risk = current_risk or _risk()
    return RiskPreTradeExplanationEnvelopeV1.model_construct(
        assessed_at=NOW,
        status=(
            CapacityDecisionGateStatus.READY
            if ready
            else CapacityDecisionGateStatus.ABSTAIN
        ),
        review_ready=ready,
        abstain=not ready,
        direction=intent_requests[0].side,
        risk_evaluation=risk,
        directional_review=directional_review,
        no_action_option_id=NO_ACTION,
        final_option_id=OPTION if ready else NO_ACTION,
        final_action=(
            DecisionAction.REVIEW_LIMITED_CHANGE
            if ready
            else DecisionAction.WAIT_FOR_DATA
        ),
        account_context_confirmed=ready,
    )


def _scenario(
    base: RiskPreTradeExplanationEnvelopeV1,
    *,
    risk: RiskPolicyEvaluationV1 | None = None,
    account: AccountReference | None = None,
    option: str | None = None,
    direction: OrderSide | None = None,
    requests: tuple[CapacityOrderRequestV1, ...] | None = None,
) -> ProFormaRiskScenarioV1:
    base_intent = base.directional_review.base_intent_gate.request
    active_risk = risk or _risk()
    return build_pro_forma_risk_scenario(
        scenario_id="scenario-pro-forma-1",
        account=account or active_risk.metadata.account,
        requested_option_id=option or base_intent.requested_option_id,
        direction=direction or base.direction,
        capacity_requests=requests or base_intent.expected_capacity_requests,
        risk_evaluation=active_risk,
    )


def test_ready_pro_forma_risk_is_bound_without_trade_authorization() -> None:
    base = _base_explanation()
    pro_forma = _risk(
        status=RiskOverallStatus.WARNING,
        warnings=1,
    )
    scenario = _scenario(base, risk=pro_forma)

    result = bind_pro_forma_risk_to_intent(
        base,
        scenario,
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.READY
    assert result.review_ready is True
    assert result.abstain is False
    assert result.final_option_id == OPTION
    assert result.final_action is DecisionAction.REVIEW_LIMITED_CHANGE
    assert result.risk_change_approval_confirmed is True
    assert result.account_context_confirmed is True
    assert result.option_binding_confirmed is True
    assert result.direction_binding_confirmed is True
    assert result.instrument_binding_confirmed is True
    assert result.intent_fingerprint_confirmed is True
    assert result.risk_policy_match is True
    assert result.current_risk_status is RiskOverallStatus.PASS
    assert result.pro_forma_risk_status is RiskOverallStatus.WARNING
    assert result.warning_count_delta == 1
    assert result.risk_status_changed is True
    assert result.pro_forma_risk_recomputed_by_binding is False
    assert result.option_selected_by_binding is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False
    assert (
        ProFormaRiskIntentBindingWarning.EXACT_INTENT_FINGERPRINT_BOUND
        in result.warnings
    )


def test_account_option_and_direction_mismatches_fail_closed() -> None:
    base = _base_explanation()
    other_risk = _risk(account=OTHER_ACCOUNT)
    account_result = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, risk=other_risk, account=OTHER_ACCOUNT),
        assessed_at=NOW,
    )
    assert (
        ProFormaRiskIntentBindingBlocker.ACCOUNT_CONTEXT_MISMATCH
        in account_result.blockers
    )
    assert account_result.final_action is DecisionAction.WAIT_FOR_DATA

    option_result = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, option="option.strategic_rebalance"),
        assessed_at=NOW,
    )
    assert (
        ProFormaRiskIntentBindingBlocker.OPTION_ID_MISMATCH
        in option_result.blockers
    )

    sell_request = _request(side=OrderSide.SELL)
    direction_result = bind_pro_forma_risk_to_intent(
        base,
        _scenario(
            base,
            direction=OrderSide.SELL,
            requests=(sell_request,),
        ),
        assessed_at=NOW,
    )
    assert (
        ProFormaRiskIntentBindingBlocker.DIRECTION_MISMATCH
        in direction_result.blockers
    )
    assert direction_result.risk_change_approval_confirmed is False


def test_exact_request_substitution_breaks_fingerprint_binding() -> None:
    base = _base_explanation()
    changed_quantity = _request(quantity_lots=3)
    result = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, requests=(changed_quantity,)),
        assessed_at=NOW,
    )

    assert result.instrument_binding_confirmed is True
    assert result.intent_fingerprint_confirmed is False
    assert (
        ProFormaRiskIntentBindingBlocker.INTENT_FINGERPRINT_MISMATCH
        in result.blockers
    )
    assert result.status is CapacityDecisionGateStatus.ABSTAIN
    assert result.final_option_id == NO_ACTION

    other_instrument = _request(OTHER_KEY)
    instrument_result = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, requests=(other_instrument,)),
        assessed_at=NOW,
    )
    assert (
        ProFormaRiskIntentBindingBlocker.INTENT_INSTRUMENTS_MISMATCH
        in instrument_result.blockers
    )


def test_blocked_stale_and_future_pro_forma_risk_are_explicit() -> None:
    base = _base_explanation()
    blocked_risk = _risk(
        ready=False,
        status=RiskOverallStatus.UNKNOWN,
        unknowns=1,
    )
    blocked = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, risk=blocked_risk),
        assessed_at=NOW,
    )
    assert (
        ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_NOT_READY
        in blocked.blockers
    )

    stale_risk = _risk(retrieved_at=NOW - timedelta(hours=1))
    stale = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, risk=stale_risk),
        assessed_at=NOW,
    )
    assert ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_STALE in stale.blockers

    future_risk = _risk(retrieved_at=NOW + timedelta(minutes=10))
    future = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, risk=future_risk),
        assessed_at=NOW,
    )
    assert (
        ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_FROM_FUTURE
        in future.blockers
    )


def test_risk_policy_must_match_current_portfolio_policy() -> None:
    base = _base_explanation()
    changed_policy = default_conservative_risk_policy().model_copy(
        update={"max_position_weight": Decimal("0.15")}
    )
    pro_forma = _risk(policy=changed_policy)
    result = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base, risk=pro_forma),
        assessed_at=NOW,
    )

    assert result.risk_policy_match is False
    assert (
        ProFormaRiskIntentBindingBlocker.RISK_POLICY_MISMATCH
        in result.blockers
    )
    assert result.abstain is True


def test_blocked_base_explanation_cannot_be_upgraded() -> None:
    base = _base_explanation(ready=False)
    result = bind_pro_forma_risk_to_intent(
        base,
        _scenario(base),
        assessed_at=NOW,
    )

    assert (
        ProFormaRiskIntentBindingBlocker.BASE_EXPLANATION_NOT_READY
        in result.blockers
    )
    assert result.risk_change_approval_confirmed is False
    assert result.final_action is DecisionAction.WAIT_FOR_DATA


def test_scenario_and_result_tampering_are_rejected() -> None:
    base = _base_explanation()
    scenario = _scenario(base)
    scenario_payload = dict(scenario.__dict__)
    scenario_payload["intent_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ProFormaRiskScenarioV1.model_validate(scenario_payload)

    result = bind_pro_forma_risk_to_intent(
        base,
        scenario,
        assessed_at=NOW,
    )
    payload = dict(result.__dict__)
    payload["risk_change_approval_confirmed"] = False
    with pytest.raises(ValidationError):
        ProFormaRiskIntentBindingV1.model_validate(payload)

    payload = dict(result.__dict__)
    payload["trade_authorized"] = True
    with pytest.raises(ValidationError):
        ProFormaRiskIntentBindingV1.model_validate(payload)


def test_naive_binding_timestamp_is_rejected() -> None:
    base = _base_explanation()
    with pytest.raises(
        ProFormaRiskIntentBindingError,
        match="PRO_FORMA_RISK_BINDING_TIMESTAMP_MUST_BE_AWARE",
    ):
        bind_pro_forma_risk_to_intent(
            base,
            _scenario(base),
            assessed_at=NOW.replace(tzinfo=None),
        )
