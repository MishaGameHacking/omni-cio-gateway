from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review_workflow_producer import (
    FinalDecisionReviewWorkflowProducerResultV1,
    FinalDecisionReviewWorkflowProducerStatus,
)


SafeIdentifier = Annotated[str, Field(min_length=3, max_length=128)]
SafeErrorCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]
SafeBlocker = Annotated[str, Field(min_length=1, max_length=256)]


class FinalDecisionReviewWorkflowSourceSlot(StrEnum):
    PURCHASE_GATE = "purchase_gate"
    SELL_GATE = "sell_gate"
    CURRENT_RISK = "current_risk"
    PRO_FORMA_RISK = "pro_forma_risk"


class FinalDecisionReviewWorkflowSourceStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    FAILED = "failed"


class FinalDecisionReviewWorkflowSourceEvidenceV1(ContractModel):
    schema_name: Literal["final_decision_review_workflow_source_evidence"] = (
        "final_decision_review_workflow_source_evidence"
    )
    schema_version: Literal["1.0"] = "1.0"
    slot: FinalDecisionReviewWorkflowSourceSlot
    status: FinalDecisionReviewWorkflowSourceStatus
    observed_at: datetime | None = None
    provider: SafeIdentifier | None = None
    operation: SafeIdentifier | None = None
    error_code: SafeErrorCode | None = None
    payload_logged: Literal[False] = False
    credentials_logged: Literal[False] = False
    full_account_logged: Literal[False] = False
    broker_write_called: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workflow source timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evidence(self) -> FinalDecisionReviewWorkflowSourceEvidenceV1:
        if self.status is FinalDecisionReviewWorkflowSourceStatus.AVAILABLE:
            if self.observed_at is None or self.provider is None or self.operation is None:
                raise ValueError("available workflow source requires provenance")
            if self.error_code is not None:
                raise ValueError("available workflow source cannot contain error code")
        elif self.status is FinalDecisionReviewWorkflowSourceStatus.FAILED:
            if self.error_code is None:
                raise ValueError("failed workflow source requires error code")
        elif self.error_code is not None:
            raise ValueError("missing workflow source cannot contain error code")
        return self


class FinalDecisionReviewWorkflowCoordinatorStatus(StrEnum):
    PUBLISHED = "published"
    BLOCKED = "blocked"


class FinalDecisionReviewWorkflowCoordinatorStage(StrEnum):
    SOURCE_EVIDENCE = "source_evidence"
    FRESHNESS = "freshness"
    ACCOUNT_CONTEXT = "account_context"
    PRODUCER = "producer"


class FinalDecisionReviewWorkflowCoordinatorResultV1(ContractModel):
    schema_name: Literal["final_decision_review_workflow_coordinator_result"] = (
        "final_decision_review_workflow_coordinator_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    coordinated_at: datetime
    status: FinalDecisionReviewWorkflowCoordinatorStatus
    completed_stage: FinalDecisionReviewWorkflowCoordinatorStage
    published: bool
    primary_blocker: SafeBlocker | None = None
    source_evidence: Annotated[
        tuple[FinalDecisionReviewWorkflowSourceEvidenceV1, ...],
        Field(min_length=4, max_length=4),
    ]
    producer_result: Annotated[
        FinalDecisionReviewWorkflowProducerResultV1 | None,
        SkipValidation(),
    ] = None
    available_source_count: Annotated[int, Field(ge=0, le=4)]
    missing_source_count: Annotated[int, Field(ge=0, le=4)]
    failed_source_count: Annotated[int, Field(ge=0, le=4)]
    selected_direction_count: Annotated[int, Field(ge=0, le=2)]
    source_evidence_complete: bool
    freshness_confirmed: bool
    account_context_confirmed: bool
    exact_direction_confirmed: bool
    coordinator_performed_network_calls: Literal[False] = False
    source_payloads_logged: Literal[False] = False
    credentials_logged: Literal[False] = False
    full_account_logged: Literal[False] = False
    external_broker_called: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("coordinated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workflow coordinator timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> FinalDecisionReviewWorkflowCoordinatorResultV1:
        slots = tuple(row.slot for row in self.source_evidence)
        if len(set(slots)) != len(slots):
            raise ValueError("workflow source evidence slots must be unique")
        if set(slots) != set(FinalDecisionReviewWorkflowSourceSlot):
            raise ValueError("workflow source evidence slots are incomplete")
        available = sum(
            row.status is FinalDecisionReviewWorkflowSourceStatus.AVAILABLE
            for row in self.source_evidence
        )
        missing = sum(
            row.status is FinalDecisionReviewWorkflowSourceStatus.MISSING
            for row in self.source_evidence
        )
        failed = sum(
            row.status is FinalDecisionReviewWorkflowSourceStatus.FAILED
            for row in self.source_evidence
        )
        if (
            self.available_source_count != available
            or self.missing_source_count != missing
            or self.failed_source_count != failed
        ):
            raise ValueError("workflow source counters do not reconcile")
        expected_complete = (
            self.selected_direction_count == 1
            and available == 3
            and missing == 1
            and failed == 0
        )
        if self.source_evidence_complete is not expected_complete:
            raise ValueError("workflow source completeness mirror is inconsistent")

        expected_published = (
            self.producer_result is not None
            and self.producer_result.status
            is FinalDecisionReviewWorkflowProducerStatus.PUBLISHED
            and self.producer_result.published
            and self.producer_result.primary_blocker is None
        )
        expected_status = (
            FinalDecisionReviewWorkflowCoordinatorStatus.PUBLISHED
            if expected_published
            else FinalDecisionReviewWorkflowCoordinatorStatus.BLOCKED
        )
        expected_blocker = (
            None
            if expected_published
            else (
                self.producer_result.primary_blocker
                if self.producer_result is not None
                else self.primary_blocker
            )
        )
        if self.published is not expected_published:
            raise ValueError("workflow coordinator publication mirror is inconsistent")
        if self.status is not expected_status:
            raise ValueError("workflow coordinator status mirror is inconsistent")
        if self.primary_blocker != expected_blocker:
            raise ValueError("workflow coordinator blocker mirror is inconsistent")
        if self.producer_result is not None and self.completed_stage is not FinalDecisionReviewWorkflowCoordinatorStage.PRODUCER:
            raise ValueError("producer result requires producer stage")
        return self
