from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import OrderSide
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
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationBlocker,
    RiskPreTradeExplanationEnvelopeV1,
    RiskPreTradeExplanationLayer,
    RiskPreTradeExplanationLayerState,
    RiskPreTradeExplanationWarning,
)
from omni_cio.contracts.v1.risk import (
    RiskOverallStatus,
    RiskPolicyEvaluationV1,
)
from omni_cio.decision.risk_pretrade_explanation_v1 import (
    RiskPreTradeExplanationError,
    compose_risk_pretrade_explanation,
)
from omni_cio.risk.policy_v1 import default_conservative_risk_policy


NOW = datetime(2026, 7, 29, 21, 30, tzinfo=timezone.utc)
ACCOUNT = "****1234"
OTHER_ACCOUNT = "****9876"


def _metadata(
    schema_name: str,
    *,
    retrieved_at: datetime = NOW,
    account: str = ACCOUNT,
) -> ContractMetadata:
    return ContractMetadata(
        schema_name=schema_name,
        retrieved_at=retrieved_at,
        account=AccountReference(masked_id=account),
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation="risk-pretrade-explanation-test",
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
    ready: bool = True,
    warning_count: int = 0,
    unknown_count: int = 0,
    account: str = ACCOUNT,
) -> RiskPolicyEvaluationV1:
    overall = (
        RiskOverallStatus.PASS
        if ready and warning_count == 0 and unknown_count == 0
        else RiskOverallStatus.WARNING
        if ready
        else RiskOverallStatus.UNKNOWN
    )
    return RiskPolicyEvaluationV1.model_construct(
        metadata=_metadata(
            "risk_policy_evaluation",
            retrieved_at=retrieved_at,
            account=account,
        ),
        policy=default_conservative_risk_policy(),
        overall_status=overall,
        decision_ready=ready,
        checks=(),
        breach_count=0,
        warning_count=warning_count,
        unknown_count=unknown_count,
        no_cross_currency_aggregation=True,
    )


def _directional_review(
    *,
    assessed_at: datetime = NOW,
    ready: bool = True,
    capacity_ready: bool = True,
    broker_ready: bool = True,
    account: str | None = ACCOUNT,
) -> CapacityDirectionalPreTradeReviewV1:
    base_intent = CapacityIntentDecisionGateV1.model_construct(
        gate_ready=capacity_ready,
    )
    coverage = ()
    if account is not None:
        preview = SimpleNamespace(
            metadata=_metadata(
                "pretrade_preview",
                retrieved_at=assessed_at,
                account=account,
            )
        )
        coverage = (SimpleNamespace(preview=preview),)
    source_gate = CapacityPreTradeDecisionGateV1.model_construct(
        base_intent_gate=base_intent,
        coverage=coverage,
    )
    return CapacityDirectionalPreTradeReviewV1.model_construct(
        assessed_at=assessed_at,
        direction=OrderSide.BUY,
        gate_ready=ready,
        base_intent_gate=base_intent,
        source_gate=source_gate,
        no_action_option_id="option.no_action",
        final_option_id=(
            "option.limited_change" if ready else "option.no_action"
        ),
        final_action=(
            DecisionAction.REVIEW_LIMITED_CHANGE
            if ready
            else DecisionAction.WAIT_FOR_DATA
        ),
        source_gate_ready=broker_ready,
        source_coverage_complete=broker_ready,
        exact_intent_binding_confirmed=broker_ready,
    )


def test_ready_sources_produce_explainable_review_without_execution() -> None:
    result = compose_risk_pretrade_explanation(
        _risk(),
        _directional_review(),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.READY
    assert result.review_ready is True
    assert result.abstain is False
    assert result.final_option_id == "option.limited_change"
    assert result.final_action is DecisionAction.REVIEW_LIMITED_CHANGE
    assert result.account_context_confirmed is True
    assert result.source_account_count == 1
    assert result.primary_blocking_layer is None
    assert all(layer.ready for layer in result.layers)
    assert result.risk_change_approval_confirmed is False
    assert result.option_selected_by_envelope is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False
    assert (
        RiskPreTradeExplanationWarning.RISK_EVALUATION_NOT_PRO_FORMA_BOUND
        in result.warnings
    )


def test_account_mismatch_is_explicit_and_fail_closed() -> None:
    result = compose_risk_pretrade_explanation(
        _risk(account=ACCOUNT),
        _directional_review(account=OTHER_ACCOUNT),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.ABSTAIN
    assert (
        RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_MISMATCH
        in result.blockers
    )
    assert result.primary_blocking_layer is RiskPreTradeExplanationLayer.ACCOUNT_CONTEXT
    assert result.layers[0].state is RiskPreTradeExplanationLayerState.BLOCKED
    assert result.final_option_id == "option.no_action"
    assert result.final_action is DecisionAction.WAIT_FOR_DATA


def test_missing_preview_account_context_is_not_assumed() -> None:
    result = compose_risk_pretrade_explanation(
        _risk(),
        _directional_review(account=None),
        assessed_at=NOW,
    )

    assert (
        RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_UNCONFIRMED
        in result.blockers
    )
    assert result.source_account_count == 0
    assert result.account_context_confirmed is False
    assert result.abstain is True


def test_blocking_risk_and_risk_warnings_remain_visible() -> None:
    blocked = compose_risk_pretrade_explanation(
        _risk(ready=False, unknown_count=1),
        _directional_review(),
        assessed_at=NOW,
    )
    assert (
        RiskPreTradeExplanationBlocker.RISK_EVALUATION_NOT_READY
        in blocked.blockers
    )
    assert blocked.primary_blocking_layer is RiskPreTradeExplanationLayer.PORTFOLIO_RISK
    assert blocked.abstain is True
    assert RiskPreTradeExplanationWarning.RISK_UNKNOWN_PRESENT in blocked.warnings

    warning = compose_risk_pretrade_explanation(
        _risk(warning_count=2),
        _directional_review(),
        assessed_at=NOW,
    )
    assert warning.review_ready is True
    assert warning.layers[1].state is RiskPreTradeExplanationLayerState.WARNING
    assert RiskPreTradeExplanationWarning.RISK_WARNING_PRESENT in warning.warnings


def test_stale_and_future_sources_force_wait_for_data() -> None:
    stale_risk = compose_risk_pretrade_explanation(
        _risk(retrieved_at=NOW - timedelta(hours=1)),
        _directional_review(),
        assessed_at=NOW,
    )
    assert RiskPreTradeExplanationBlocker.RISK_EVALUATION_STALE in stale_risk.blockers

    future_review = compose_risk_pretrade_explanation(
        _risk(),
        _directional_review(assessed_at=NOW + timedelta(minutes=10)),
        assessed_at=NOW,
    )
    assert (
        RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_FROM_FUTURE
        in future_review.blockers
    )
    assert future_review.final_action is DecisionAction.WAIT_FOR_DATA


def test_capacity_broker_and_directional_layers_identify_the_first_failure() -> None:
    capacity = compose_risk_pretrade_explanation(
        _risk(),
        _directional_review(ready=False, capacity_ready=False),
        assessed_at=NOW,
    )
    assert capacity.primary_blocking_layer is RiskPreTradeExplanationLayer.CAPACITY_INTENT
    assert capacity.layers[2].state is RiskPreTradeExplanationLayerState.BLOCKED

    broker = compose_risk_pretrade_explanation(
        _risk(),
        _directional_review(ready=False, broker_ready=False),
        assessed_at=NOW,
    )
    assert broker.primary_blocking_layer is RiskPreTradeExplanationLayer.BROKER_PREVIEW
    assert broker.layers[3].state is RiskPreTradeExplanationLayerState.BLOCKED

    directional = compose_risk_pretrade_explanation(
        _risk(),
        _directional_review(ready=False),
        assessed_at=NOW,
    )
    assert directional.primary_blocking_layer is RiskPreTradeExplanationLayer.DIRECTIONAL_REVIEW


def test_naive_timestamp_and_contract_tampering_are_rejected() -> None:
    with pytest.raises(
        RiskPreTradeExplanationError,
        match="RISK_PRETRADE_EXPLANATION_TIMESTAMP_MUST_BE_AWARE",
    ):
        compose_risk_pretrade_explanation(
            _risk(),
            _directional_review(),
            assessed_at=NOW.replace(tzinfo=None),
        )

    result = compose_risk_pretrade_explanation(
        _risk(),
        _directional_review(),
        assessed_at=NOW,
    )
    payload = dict(result.__dict__)
    payload["risk_change_approval_confirmed"] = True
    with pytest.raises(ValidationError):
        RiskPreTradeExplanationEnvelopeV1.model_validate(payload)
