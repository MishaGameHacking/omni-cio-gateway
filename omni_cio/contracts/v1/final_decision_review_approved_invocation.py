from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationResultV1,
)


SafeIdentifier = Annotated[
    str,
    Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,127}$"),
]
PositiveInt = Annotated[int, Field(gt=0)]


class ApprovedCalculatorOperation(StrEnum):
    PURCHASE_REVIEW = "purchase_review"
    SELL_REVIEW = "sell_review"


class ApprovedCalculatorInvocationRequestV1(ContractModel):
    schema_name: Literal["approved_calculator_invocation_request"] = (
        "approved_calculator_invocation_request"
    )
    schema_version: Literal["1.0"] = "1.0"
    invocation_id: SafeIdentifier
    scenario_id: SafeIdentifier
    correlation_id: SafeIdentifier
    operation: ApprovedCalculatorOperation
    invoked_at: datetime

    @field_validator("invoked_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved invocation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class ApprovedCalculatorInvocationResultV1(ContractModel):
    schema_name: Literal["approved_calculator_invocation_result"] = (
        "approved_calculator_invocation_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    request: ApprovedCalculatorInvocationRequestV1
    completed_at: datetime
    publication: TrustedScenarioPublicationResultV1
    decision_count: Literal[1] = 1
    capacity_assessment_count: PositiveInt
    preview_count: PositiveInt
    replay_checked: Literal[True] = True
    replay_detected: Literal[False] = False
    invoked_once: Literal[True] = True
    internal_only: Literal[True] = True
    raw_payload_accepted: Literal[False] = False
    credentials_accepted: Literal[False] = False
    full_account_accepted: Literal[False] = False
    request_body_accepted: Literal[False] = False
    http_route_created: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("completed_at")
    @classmethod
    def require_aware_completed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved invocation completion must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> ApprovedCalculatorInvocationResultV1:
        if self.completed_at < self.request.invoked_at:
            raise ValueError("approved invocation completion precedes invocation")
        if self.publication.scenario_id != self.request.scenario_id:
            raise ValueError("approved invocation scenario does not reconcile")
        if self.publication.published_at != self.request.invoked_at:
            raise ValueError("approved invocation publication timestamp does not reconcile")
        expected_operation = (
            ApprovedCalculatorOperation.PURCHASE_REVIEW
            if self.publication.direction.value == "buy"
            else ApprovedCalculatorOperation.SELL_REVIEW
        )
        if self.request.operation is not expected_operation:
            raise ValueError("approved invocation operation does not match direction")
        return self
