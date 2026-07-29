from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.capacity import (
    CapacityBlocker,
    CapacityOrderRequestV1,
)
from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import (
    CapacityDecisionGatePolicyV1,
    CapacityDecisionGateStatus,
    CapacityDecisionGateV1,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class CapacityIntentMismatch(StrEnum):
    REQUEST_ID = "request_id"
    SIDE = "side"
    CURRENCY = "currency"
    QUANTITY_LOTS = "quantity_lots"
    LOT_SIZE = "lot_size"
    REFERENCE_PRICE = "reference_price"
    INTENDED_EXECUTION_DAYS = "intended_execution_days"
    UNITS = "units"
    ORDER_NOTIONAL = "order_notional"


class CapacityIntentDecisionGateBlocker(StrEnum):
    BASE_CAPACITY_GATE_NOT_READY = "base_capacity_gate_not_ready"
    INTENT_COVERAGE_INCOMPLETE = "intent_coverage_incomplete"
    CAPACITY_INTENT_MISMATCH = "capacity_intent_mismatch"


class CapacityIntentDecisionGateWarning(StrEnum):
    EXACT_INTENT_BINDING_ONLY = "exact_intent_binding_only"
    AFFORDABILITY_NOT_CHECKED = "affordability_not_checked"
    BROKER_PREVIEW_NOT_CHECKED = "broker_preview_not_checked"
    REVIEW_ONLY_NO_ORDER_CREATED = "review_only_no_order_created"


class CapacityIntentDecisionGateRequestV1(ContractModel):
    gate_id: Annotated[str, Field(min_length=1, max_length=128)]
    requested_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    expected_capacity_requests: tuple[CapacityOrderRequestV1, ...]
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("expected_capacity_requests")
    @classmethod
    def validate_expected_requests(
        cls,
        value: tuple[CapacityOrderRequestV1, ...],
    ) -> tuple[CapacityOrderRequestV1, ...]:
        if not value:
            raise ValueError("capacity intent gate requires expected requests")
        instrument_keys = tuple(row.instrument_key for row in value)
        if len(set(instrument_keys)) != len(instrument_keys):
            raise ValueError("capacity intent instruments must be unique")
        request_ids = tuple(row.request_id for row in value)
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("capacity intent request IDs must be unique")
        return value


class CapacityIntentBindingV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    expected_request: CapacityOrderRequestV1
    actual_request: CapacityOrderRequestV1
    mismatch_fields: tuple[CapacityIntentMismatch, ...] = ()
    exact_match: bool
    capacity_ready: bool
    capacity_assessed_at: datetime
    safe_notional: NonNegativeDecimal
    safe_lots: NonNegativeInt
    capacity_blockers: tuple[CapacityBlocker, ...] = ()

    @field_validator("capacity_assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity intent timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_binding(self) -> CapacityIntentBindingV1:
        if self.expected_request.instrument_key != self.instrument_key:
            raise ValueError("expected capacity intent instrument mismatch")
        if self.actual_request.instrument_key != self.instrument_key:
            raise ValueError("actual capacity intent instrument mismatch")
        if len(set(self.mismatch_fields)) != len(self.mismatch_fields):
            raise ValueError("capacity intent mismatch fields must be unique")
        if self.exact_match is bool(self.mismatch_fields):
            raise ValueError("capacity intent exact-match state is inconsistent")
        if self.capacity_ready == bool(self.capacity_blockers):
            raise ValueError("capacity intent readiness is inconsistent")
        return self


class CapacityIntentDecisionGateV1(ContractModel):
    schema_name: Literal["capacity_intent_decision_gate"] = (
        "capacity_intent_decision_gate"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: CapacityDecisionGateStatus
    gate_ready: bool
    abstain: bool
    request: CapacityIntentDecisionGateRequestV1
    policy: CapacityDecisionGatePolicyV1
    base_gate: CapacityDecisionGateV1
    no_action_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    required_intent_count: PositiveInt
    matched_intent_count: NonNegativeInt
    exact_match_count: NonNegativeInt
    coverage: tuple[CapacityIntentBindingV1, ...]
    blockers: tuple[CapacityIntentDecisionGateBlocker, ...] = ()
    warnings: tuple[CapacityIntentDecisionGateWarning, ...] = ()
    intent_binding_only: Literal[True] = True
    affordability_checked: Literal[False] = False
    broker_preview_checked: Literal[False] = False
    option_selected_by_gate: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity intent gate timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_gate(self) -> CapacityIntentDecisionGateV1:
        expected_keys = tuple(
            row.instrument_key for row in self.request.expected_capacity_requests
        )
        if self.base_gate.request.gate_id != self.request.gate_id:
            raise ValueError("capacity intent gate ID does not match base gate")
        if (
            self.base_gate.request.requested_option_id
            != self.request.requested_option_id
        ):
            raise ValueError("capacity intent option does not match base gate")
        if self.base_gate.request.required_instrument_keys != expected_keys:
            raise ValueError("capacity intent instruments do not match base gate")
        if self.base_gate.policy != self.policy:
            raise ValueError("capacity intent policy does not match base gate")
        if self.required_intent_count != len(expected_keys):
            raise ValueError("required capacity intent count does not reconcile")
        if self.matched_intent_count != len(self.coverage):
            raise ValueError("matched capacity intent count does not reconcile")
        if self.exact_match_count != sum(row.exact_match for row in self.coverage):
            raise ValueError("exact capacity intent count does not reconcile")

        coverage_keys = tuple(row.instrument_key for row in self.coverage)
        if len(set(coverage_keys)) != len(coverage_keys):
            raise ValueError("capacity intent coverage instruments must be unique")
        if any(key not in expected_keys for key in coverage_keys):
            raise ValueError("capacity intent coverage contains unexpected instrument")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("capacity intent blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("capacity intent warnings must be unique")

        base_blocked = not self.base_gate.gate_ready
        if (
            CapacityIntentDecisionGateBlocker.BASE_CAPACITY_GATE_NOT_READY
            in self.blockers
        ) is not base_blocked:
            raise ValueError("capacity intent base-gate blocker is inconsistent")
        coverage_incomplete = self.matched_intent_count != self.required_intent_count
        if (
            CapacityIntentDecisionGateBlocker.INTENT_COVERAGE_INCOMPLETE
            in self.blockers
        ) is not coverage_incomplete:
            raise ValueError("capacity intent coverage blocker is inconsistent")
        mismatch_present = any(not row.exact_match for row in self.coverage)
        if (
            CapacityIntentDecisionGateBlocker.CAPACITY_INTENT_MISMATCH
            in self.blockers
        ) is not mismatch_present:
            raise ValueError("capacity intent mismatch blocker is inconsistent")

        expected_ready = not self.blockers
        if self.gate_ready is not expected_ready:
            raise ValueError("capacity intent readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("capacity intent abstain state is inconsistent")
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        if self.status is not expected_status:
            raise ValueError("capacity intent status is inconsistent")

        if expected_ready:
            if not self.base_gate.gate_ready:
                raise ValueError("ready capacity intent requires ready base gate")
            if self.matched_intent_count != self.required_intent_count:
                raise ValueError("ready capacity intent requires complete coverage")
            if self.exact_match_count != self.required_intent_count:
                raise ValueError("ready capacity intent requires exact request binding")
            if self.final_option_id != self.request.requested_option_id:
                raise ValueError("ready capacity intent changed requested option")
            if self.final_action is not self.base_gate.final_action:
                raise ValueError("ready capacity intent changed base-gate action")
        else:
            if self.final_option_id != self.no_action_option_id:
                raise ValueError("blocked capacity intent must select no action")
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked capacity intent must wait for data")
        return self
