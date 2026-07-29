from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.capacity import CapacityBlocker
from omni_cio.contracts.v1.common import ContractModel, CurrencyCode
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionOptionKind,
    DecisionOptionStatus,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
InstrumentKey = Annotated[str, Field(min_length=3, max_length=256)]


class CapacityDecisionGateStatus(StrEnum):
    READY = "ready"
    ABSTAIN = "abstain"


class CapacityDecisionGateBlocker(StrEnum):
    BASE_DECISION_NOT_READY = "base_decision_not_ready"
    BASE_DECISION_STALE = "base_decision_stale"
    BASE_DECISION_FROM_FUTURE = "base_decision_from_future"
    REQUESTED_OPTION_NOT_FOUND = "requested_option_not_found"
    REQUESTED_OPTION_NO_ACTION = "requested_option_no_action"
    REQUESTED_OPTION_BLOCKED = "requested_option_blocked"
    CAPACITY_COVERAGE_INCOMPLETE = "capacity_coverage_incomplete"
    CAPACITY_NOT_READY = "capacity_not_ready"
    CAPACITY_STALE = "capacity_stale"
    CAPACITY_FROM_FUTURE = "capacity_from_future"


class CapacityDecisionGateWarning(StrEnum):
    CAPACITY_GATE_DOES_NOT_SELECT_OPTION = "capacity_gate_does_not_select_option"
    CAPACITY_IS_POINT_IN_TIME = "capacity_is_point_in_time"
    REVIEW_ONLY_NO_ORDER_CREATED = "review_only_no_order_created"


class CapacityDecisionGatePolicyV1(ContractModel):
    base_decision_max_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 300
    capacity_max_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 300
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60


class CapacityDecisionGateRequestV1(ContractModel):
    gate_id: Annotated[str, Field(min_length=1, max_length=128)]
    requested_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    required_instrument_keys: tuple[InstrumentKey, ...]
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("required_instrument_keys")
    @classmethod
    def validate_keys(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("capacity decision gate requires instruments")
        if len(set(value)) != len(value):
            raise ValueError("capacity decision gate instruments must be unique")
        return value


class CapacityDecisionCoverageV1(ContractModel):
    instrument_key: InstrumentKey
    capacity_request_id: Annotated[str, Field(min_length=1, max_length=128)]
    currency: CurrencyCode
    order_notional: NonNegativeDecimal
    safe_notional: NonNegativeDecimal
    safe_lots: NonNegativeInt
    capacity_ready: bool
    capacity_assessed_at: datetime
    capacity_blockers: tuple[CapacityBlocker, ...] = ()

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("capacity_assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity coverage timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_coverage(self) -> CapacityDecisionCoverageV1:
        if self.capacity_ready == bool(self.capacity_blockers):
            raise ValueError("capacity coverage readiness is inconsistent")
        return self


class CapacityDecisionGateV1(ContractModel):
    schema_name: Literal["capacity_decision_gate"] = "capacity_decision_gate"
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: CapacityDecisionGateStatus
    gate_ready: bool
    abstain: bool
    request: CapacityDecisionGateRequestV1
    policy: CapacityDecisionGatePolicyV1
    base_decision_recommendation_ready: bool
    base_preferred_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    requested_option_kind: DecisionOptionKind | None = None
    requested_option_status: DecisionOptionStatus | None = None
    requested_action: DecisionAction | None = None
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    required_capacity_count: PositiveInt
    capacity_coverage_count: NonNegativeInt
    capacity_ready_count: NonNegativeInt
    coverage: tuple[CapacityDecisionCoverageV1, ...]
    blockers: tuple[CapacityDecisionGateBlocker, ...] = ()
    warnings: tuple[CapacityDecisionGateWarning, ...] = ()
    capacity_gate_only: Literal[True] = True
    option_selected_by_gate: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity decision gate timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_gate(self) -> CapacityDecisionGateV1:
        if self.required_capacity_count != len(self.request.required_instrument_keys):
            raise ValueError("required capacity count does not reconcile")
        if self.capacity_coverage_count != len(self.coverage):
            raise ValueError("capacity coverage count does not reconcile")
        if self.capacity_ready_count != sum(row.capacity_ready for row in self.coverage):
            raise ValueError("capacity ready count does not reconcile")
        coverage_keys = tuple(row.instrument_key for row in self.coverage)
        if len(set(coverage_keys)) != len(coverage_keys):
            raise ValueError("capacity coverage instruments must be unique")
        if any(key not in self.request.required_instrument_keys for key in coverage_keys):
            raise ValueError("capacity coverage contains an unrequested instrument")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("capacity decision blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("capacity decision warnings must be unique")

        option_fields = (
            self.requested_option_kind,
            self.requested_option_status,
            self.requested_action,
        )
        if any(value is None for value in option_fields) and not all(
            value is None for value in option_fields
        ):
            raise ValueError("requested option metadata is partial")

        expected_ready = not self.blockers
        if self.gate_ready is not expected_ready:
            raise ValueError("capacity decision readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("capacity decision abstain status is inconsistent")
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        if self.status is not expected_status:
            raise ValueError("capacity decision status is inconsistent")
        if expected_ready:
            if self.requested_action is None:
                raise ValueError("ready capacity decision requires requested action")
            if self.final_option_id != self.request.requested_option_id:
                raise ValueError("ready capacity decision changed requested option")
            if self.final_action is not self.requested_action:
                raise ValueError("ready capacity decision changed requested action")
            if self.capacity_coverage_count != self.required_capacity_count:
                raise ValueError("ready capacity decision requires full coverage")
            if self.capacity_ready_count != self.required_capacity_count:
                raise ValueError("ready capacity decision requires ready capacity")
        else:
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("abstain capacity decision must wait for data")
            retained_change_option = (
                self.final_option_id == self.request.requested_option_id
                and self.requested_option_kind is not DecisionOptionKind.NO_ACTION
            )
            if retained_change_option:
                raise ValueError("abstain capacity decision cannot retain change option")
        return self
