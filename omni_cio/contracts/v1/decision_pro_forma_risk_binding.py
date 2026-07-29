from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1, OrderSide
from omni_cio.contracts.v1.common import AccountReference, ContractModel
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationEnvelopeV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def calculate_pro_forma_intent_fingerprint(
    *,
    account_masked_id: str,
    requested_option_id: str,
    direction: OrderSide,
    capacity_requests: tuple[CapacityOrderRequestV1, ...],
) -> str:
    """Return a deterministic non-secret fingerprint for one exact intent set."""

    rows = [
        {
            "request_id": row.request_id,
            "instrument_key": row.instrument_key,
            "side": row.side.value,
            "currency": row.currency,
            "quantity_lots": row.quantity_lots,
            "lot_size": row.lot_size,
            "reference_price": _decimal_text(row.reference_price),
            "intended_execution_days": row.intended_execution_days,
            "units": row.units,
            "order_notional": _decimal_text(row.order_notional),
        }
        for row in sorted(
            capacity_requests,
            key=lambda request: (request.instrument_key, request.request_id),
        )
    ]
    payload = {
        "account_masked_id": account_masked_id,
        "requested_option_id": requested_option_id,
        "direction": direction.value,
        "capacity_requests": rows,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ProFormaRiskScenarioMethod(StrEnum):
    EXACT_CAPACITY_INTENT_POST_CHANGE = "exact_capacity_intent_post_change"


class ProFormaRiskIntentBindingBlocker(StrEnum):
    BASE_EXPLANATION_NOT_READY = "base_explanation_not_ready"
    ACCOUNT_CONTEXT_MISMATCH = "account_context_mismatch"
    OPTION_ID_MISMATCH = "option_id_mismatch"
    DIRECTION_MISMATCH = "direction_mismatch"
    INTENT_INSTRUMENTS_MISMATCH = "intent_instruments_mismatch"
    INTENT_FINGERPRINT_MISMATCH = "intent_fingerprint_mismatch"
    RISK_POLICY_MISMATCH = "risk_policy_mismatch"
    PRO_FORMA_RISK_NOT_READY = "pro_forma_risk_not_ready"
    PRO_FORMA_RISK_STALE = "pro_forma_risk_stale"
    PRO_FORMA_RISK_FROM_FUTURE = "pro_forma_risk_from_future"


class ProFormaRiskIntentBindingWarning(StrEnum):
    EXACT_INTENT_FINGERPRINT_BOUND = "exact_intent_fingerprint_bound"
    CURRENT_AND_PRO_FORMA_RISK_RETAINED = "current_and_pro_forma_risk_retained"
    RISK_STATUS_DELTA_NOT_RETURN_FORECAST = "risk_status_delta_not_return_forecast"
    PRO_FORMA_RISK_NOT_RECOMPUTED_BY_BINDING = (
        "pro_forma_risk_not_recomputed_by_binding"
    )
    REVIEW_ONLY_NO_ORDER_CREATED = "review_only_no_order_created"


class ProFormaRiskIntentBindingPolicyV1(ContractModel):
    pro_forma_max_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 900
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60


class ProFormaRiskScenarioV1(ContractModel):
    schema_name: Literal["pro_forma_risk_scenario"] = "pro_forma_risk_scenario"
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: Annotated[str, Field(min_length=3, max_length=128)]
    generated_at: datetime
    account: AccountReference
    requested_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    direction: OrderSide
    capacity_requests: Annotated[
        tuple[CapacityOrderRequestV1, ...],
        Field(min_length=1),
    ]
    intent_fingerprint: Fingerprint
    risk_evaluation: Annotated[RiskPolicyEvaluationV1, SkipValidation()]
    method: Literal[
        ProFormaRiskScenarioMethod.EXACT_CAPACITY_INTENT_POST_CHANGE
    ] = ProFormaRiskScenarioMethod.EXACT_CAPACITY_INTENT_POST_CHANGE
    current_portfolio_risk: Literal[False] = False
    pro_forma_post_change: Literal[True] = True
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pro-forma scenario timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_scenario(self) -> ProFormaRiskScenarioV1:
        instrument_keys = tuple(row.instrument_key for row in self.capacity_requests)
        request_ids = tuple(row.request_id for row in self.capacity_requests)
        if len(set(instrument_keys)) != len(instrument_keys):
            raise ValueError("pro-forma scenario instruments must be unique")
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("pro-forma scenario request IDs must be unique")
        if any(row.side is not self.direction for row in self.capacity_requests):
            raise ValueError("pro-forma scenario direction must be homogeneous")
        if self.risk_evaluation.metadata.account != self.account:
            raise ValueError("pro-forma risk account does not match scenario")
        if self.risk_evaluation.metadata.retrieved_at != self.generated_at:
            raise ValueError("pro-forma risk timestamp does not match scenario")
        expected_fingerprint = calculate_pro_forma_intent_fingerprint(
            account_masked_id=self.account.masked_id,
            requested_option_id=self.requested_option_id,
            direction=self.direction,
            capacity_requests=self.capacity_requests,
        )
        if self.intent_fingerprint != expected_fingerprint:
            raise ValueError("pro-forma scenario fingerprint is invalid")
        return self


class ProFormaRiskIntentBindingV1(ContractModel):
    schema_name: Literal["pro_forma_risk_intent_binding"] = (
        "pro_forma_risk_intent_binding"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: CapacityDecisionGateStatus
    review_ready: bool
    abstain: bool
    base_explanation: Annotated[
        RiskPreTradeExplanationEnvelopeV1,
        SkipValidation(),
    ]
    scenario: Annotated[ProFormaRiskScenarioV1, SkipValidation()]
    policy: ProFormaRiskIntentBindingPolicyV1
    no_action_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    requested_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    direction: OrderSide
    account_context_confirmed: bool
    option_binding_confirmed: bool
    direction_binding_confirmed: bool
    instrument_binding_confirmed: bool
    intent_fingerprint_confirmed: bool
    risk_policy_match: bool
    base_explanation_ready: bool
    pro_forma_risk_ready: bool
    bound_instrument_count: PositiveInt
    intent_fingerprint: Fingerprint
    current_risk_status: RiskOverallStatus
    pro_forma_risk_status: RiskOverallStatus
    current_breach_count: NonNegativeInt
    pro_forma_breach_count: NonNegativeInt
    breach_count_delta: int
    current_warning_count: NonNegativeInt
    pro_forma_warning_count: NonNegativeInt
    warning_count_delta: int
    current_unknown_count: NonNegativeInt
    pro_forma_unknown_count: NonNegativeInt
    unknown_count_delta: int
    risk_status_changed: bool
    primary_blocker: ProFormaRiskIntentBindingBlocker | None = None
    blockers: tuple[ProFormaRiskIntentBindingBlocker, ...] = ()
    warnings: tuple[ProFormaRiskIntentBindingWarning, ...] = ()
    risk_change_approval_confirmed: bool
    pro_forma_risk_recomputed_by_binding: Literal[False] = False
    option_selected_by_binding: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pro-forma binding timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_binding(self) -> ProFormaRiskIntentBindingV1:
        base = self.base_explanation
        scenario = self.scenario
        current_risk = base.risk_evaluation
        pro_forma_risk = scenario.risk_evaluation
        base_intent = base.directional_review.base_intent_gate.request
        expected_requests = base_intent.expected_capacity_requests
        expected_keys = tuple(sorted(row.instrument_key for row in expected_requests))
        scenario_keys = tuple(
            sorted(row.instrument_key for row in scenario.capacity_requests)
        )
        expected_fingerprint = calculate_pro_forma_intent_fingerprint(
            account_masked_id=current_risk.metadata.account.masked_id,
            requested_option_id=base_intent.requested_option_id,
            direction=base.direction,
            capacity_requests=expected_requests,
        )
        pro_forma_age = (
            self.assessed_at - scenario.generated_at
        ).total_seconds()

        expected_states = {
            ProFormaRiskIntentBindingBlocker.BASE_EXPLANATION_NOT_READY: (
                not base.review_ready
            ),
            ProFormaRiskIntentBindingBlocker.ACCOUNT_CONTEXT_MISMATCH: (
                not base.account_context_confirmed
                or scenario.account != current_risk.metadata.account
            ),
            ProFormaRiskIntentBindingBlocker.OPTION_ID_MISMATCH: (
                scenario.requested_option_id != base_intent.requested_option_id
            ),
            ProFormaRiskIntentBindingBlocker.DIRECTION_MISMATCH: (
                scenario.direction is not base.direction
            ),
            ProFormaRiskIntentBindingBlocker.INTENT_INSTRUMENTS_MISMATCH: (
                scenario_keys != expected_keys
            ),
            ProFormaRiskIntentBindingBlocker.INTENT_FINGERPRINT_MISMATCH: (
                scenario.intent_fingerprint != expected_fingerprint
            ),
            ProFormaRiskIntentBindingBlocker.RISK_POLICY_MISMATCH: (
                pro_forma_risk.policy != current_risk.policy
            ),
            ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_NOT_READY: (
                not pro_forma_risk.decision_ready
            ),
            ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_STALE: (
                pro_forma_age > self.policy.pro_forma_max_age_seconds
            ),
            ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_FROM_FUTURE: (
                pro_forma_age < -self.policy.future_tolerance_seconds
            ),
        }
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("pro-forma binding blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("pro-forma binding warnings must be unique")
        for blocker, expected_present in expected_states.items():
            if (blocker in self.blockers) != expected_present:
                raise ValueError(f"pro-forma blocker {blocker.value} is inconsistent")

        expected_mirrors = (
            (self.requested_option_id, scenario.requested_option_id, "option"),
            (self.direction, scenario.direction, "direction"),
            (
                self.account_context_confirmed,
                not expected_states[
                    ProFormaRiskIntentBindingBlocker.ACCOUNT_CONTEXT_MISMATCH
                ],
                "account",
            ),
            (
                self.option_binding_confirmed,
                not expected_states[
                    ProFormaRiskIntentBindingBlocker.OPTION_ID_MISMATCH
                ],
                "option binding",
            ),
            (
                self.direction_binding_confirmed,
                not expected_states[
                    ProFormaRiskIntentBindingBlocker.DIRECTION_MISMATCH
                ],
                "direction binding",
            ),
            (
                self.instrument_binding_confirmed,
                not expected_states[
                    ProFormaRiskIntentBindingBlocker.INTENT_INSTRUMENTS_MISMATCH
                ],
                "instrument binding",
            ),
            (
                self.intent_fingerprint_confirmed,
                not expected_states[
                    ProFormaRiskIntentBindingBlocker.INTENT_FINGERPRINT_MISMATCH
                ],
                "fingerprint binding",
            ),
            (
                self.risk_policy_match,
                not expected_states[
                    ProFormaRiskIntentBindingBlocker.RISK_POLICY_MISMATCH
                ],
                "risk policy",
            ),
            (self.base_explanation_ready, base.review_ready, "base readiness"),
            (
                self.pro_forma_risk_ready,
                pro_forma_risk.decision_ready,
                "pro-forma readiness",
            ),
            (self.bound_instrument_count, len(scenario.capacity_requests), "count"),
            (
                self.intent_fingerprint,
                scenario.intent_fingerprint,
                "fingerprint",
            ),
            (self.current_risk_status, current_risk.overall_status, "current status"),
            (
                self.pro_forma_risk_status,
                pro_forma_risk.overall_status,
                "pro-forma status",
            ),
            (self.current_breach_count, current_risk.breach_count, "current breaches"),
            (
                self.pro_forma_breach_count,
                pro_forma_risk.breach_count,
                "pro-forma breaches",
            ),
            (self.current_warning_count, current_risk.warning_count, "current warnings"),
            (
                self.pro_forma_warning_count,
                pro_forma_risk.warning_count,
                "pro-forma warnings",
            ),
            (self.current_unknown_count, current_risk.unknown_count, "current unknowns"),
            (
                self.pro_forma_unknown_count,
                pro_forma_risk.unknown_count,
                "pro-forma unknowns",
            ),
        )
        for observed, expected, label in expected_mirrors:
            if observed != expected:
                raise ValueError(f"pro-forma {label} mirror is inconsistent")

        if self.breach_count_delta != (
            pro_forma_risk.breach_count - current_risk.breach_count
        ):
            raise ValueError("pro-forma breach delta is inconsistent")
        if self.warning_count_delta != (
            pro_forma_risk.warning_count - current_risk.warning_count
        ):
            raise ValueError("pro-forma warning delta is inconsistent")
        if self.unknown_count_delta != (
            pro_forma_risk.unknown_count - current_risk.unknown_count
        ):
            raise ValueError("pro-forma unknown delta is inconsistent")
        if self.risk_status_changed is (
            current_risk.overall_status is pro_forma_risk.overall_status
        ):
            raise ValueError("pro-forma risk-status change flag is inconsistent")

        expected_ready = not self.blockers
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        if self.review_ready is not expected_ready:
            raise ValueError("pro-forma binding readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("pro-forma binding abstain state is inconsistent")
        if self.status is not expected_status:
            raise ValueError("pro-forma binding status is inconsistent")
        if self.risk_change_approval_confirmed is not expected_ready:
            raise ValueError("pro-forma risk approval state is inconsistent")
        if expected_ready:
            if self.primary_blocker is not None:
                raise ValueError("ready pro-forma binding cannot have primary blocker")
            if self.final_option_id != base.final_option_id:
                raise ValueError("ready pro-forma binding changed final option")
            if self.final_action is not base.final_action:
                raise ValueError("ready pro-forma binding changed final action")
        else:
            if self.primary_blocker != self.blockers[0]:
                raise ValueError("primary pro-forma blocker must be first")
            if self.final_option_id != self.no_action_option_id:
                raise ValueError("blocked pro-forma binding must use no action")
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked pro-forma binding must wait for data")

        required_warnings = {
            ProFormaRiskIntentBindingWarning.EXACT_INTENT_FINGERPRINT_BOUND,
            ProFormaRiskIntentBindingWarning.CURRENT_AND_PRO_FORMA_RISK_RETAINED,
            ProFormaRiskIntentBindingWarning.RISK_STATUS_DELTA_NOT_RETURN_FORECAST,
            ProFormaRiskIntentBindingWarning.PRO_FORMA_RISK_NOT_RECOMPUTED_BY_BINDING,
            ProFormaRiskIntentBindingWarning.REVIEW_ONLY_NO_ORDER_CREATED,
        }
        if not required_warnings.issubset(self.warnings):
            raise ValueError("required pro-forma binding warnings are missing")
        return self
