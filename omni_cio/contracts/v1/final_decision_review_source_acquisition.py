from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review_workflow_coordinator import (
    FinalDecisionReviewWorkflowCoordinatorResultV1,
    FinalDecisionReviewWorkflowCoordinatorStatus,
    FinalDecisionReviewWorkflowSourceSlot,
)


SafeIdentifier = Annotated[str, Field(min_length=3, max_length=128)]
SafeErrorCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]
SafeBlocker = Annotated[str, Field(min_length=1, max_length=256)]


class FinalDecisionReviewSourceAcquisitionStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    FAILED = "failed"


class FinalDecisionReviewSourceAcquisitionOutcomeV1(ContractModel):
    schema_name: Literal["final_decision_review_source_acquisition_outcome"] = (
        "final_decision_review_source_acquisition_outcome"
    )
    schema_version: Literal["1.0"] = "1.0"
    slot: FinalDecisionReviewWorkflowSourceSlot
    status: FinalDecisionReviewSourceAcquisitionStatus
    attempted: bool
    observed_at: datetime | None = None
    provider: SafeIdentifier
    operation: SafeIdentifier
    error_code: SafeErrorCode | None = None
    artifact_present: bool
    payload_logged: Literal[False] = False
    credentials_logged: Literal[False] = False
    full_account_logged: Literal[False] = False
    exception_text_logged: Literal[False] = False
    broker_write_called: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source acquisition timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_outcome(self) -> FinalDecisionReviewSourceAcquisitionOutcomeV1:
        if self.status is FinalDecisionReviewSourceAcquisitionStatus.AVAILABLE:
            if not self.attempted or not self.artifact_present or self.observed_at is None:
                raise ValueError("available acquisition requires an observed artifact")
            if self.error_code is not None:
                raise ValueError("available acquisition cannot contain error code")
        elif self.status is FinalDecisionReviewSourceAcquisitionStatus.MISSING:
            if self.artifact_present or self.observed_at is not None:
                raise ValueError("missing acquisition cannot contain an artifact")
            if self.error_code is not None:
                raise ValueError("missing acquisition cannot contain error code")
        else:
            if not self.attempted or self.artifact_present or self.observed_at is not None:
                raise ValueError("failed acquisition cannot contain an artifact")
            if self.error_code is None:
                raise ValueError("failed acquisition requires error code")
        return self


class FinalDecisionReviewSourceAcquisitionResultV1(ContractModel):
    schema_name: Literal["final_decision_review_source_acquisition_result"] = (
        "final_decision_review_source_acquisition_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    acquired_at: datetime
    published: bool
    primary_blocker: SafeBlocker | None = None
    outcomes: Annotated[
        tuple[FinalDecisionReviewSourceAcquisitionOutcomeV1, ...],
        Field(min_length=4, max_length=4),
    ]
    coordinator_result: Annotated[
        FinalDecisionReviewWorkflowCoordinatorResultV1,
        SkipValidation(),
    ]
    selected_direction_count: Annotated[int, Field(ge=0, le=1)]
    attempted_source_count: Annotated[int, Field(ge=0, le=3)]
    available_source_count: Annotated[int, Field(ge=0, le=3)]
    missing_source_count: Annotated[int, Field(ge=0, le=4)]
    failed_source_count: Annotated[int, Field(ge=0, le=3)]
    timeout_source_count: Annotated[int, Field(ge=0, le=3)]
    exact_slot_set_confirmed: bool
    evidence_artifact_correspondence_confirmed: bool
    adapter_registered: Literal[True] = True
    user_controlled_publication_surface: Literal[False] = False
    request_body_created: Literal[False] = False
    payload_logged: Literal[False] = False
    credentials_logged: Literal[False] = False
    full_account_logged: Literal[False] = False
    exception_text_logged: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("acquired_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source acquisition result timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> FinalDecisionReviewSourceAcquisitionResultV1:
        slots = tuple(row.slot for row in self.outcomes)
        if len(set(slots)) != len(slots):
            raise ValueError("source acquisition outcome slots must be unique")
        expected_slot_set = set(FinalDecisionReviewWorkflowSourceSlot)
        actual_slot_set = set(slots)
        expected_exact_slots = actual_slot_set == expected_slot_set
        if self.exact_slot_set_confirmed is not expected_exact_slots:
            raise ValueError("source acquisition slot-set mirror is inconsistent")
        if not expected_exact_slots:
            raise ValueError("source acquisition outcomes are incomplete")

        attempted = sum(row.attempted for row in self.outcomes)
        available = sum(
            row.status is FinalDecisionReviewSourceAcquisitionStatus.AVAILABLE
            for row in self.outcomes
        )
        missing = sum(
            row.status is FinalDecisionReviewSourceAcquisitionStatus.MISSING
            for row in self.outcomes
        )
        failed = sum(
            row.status is FinalDecisionReviewSourceAcquisitionStatus.FAILED
            for row in self.outcomes
        )
        timed_out = sum(row.error_code == "SOURCE_TIMEOUT" for row in self.outcomes)
        if (
            self.attempted_source_count != attempted
            or self.available_source_count != available
            or self.missing_source_count != missing
            or self.failed_source_count != failed
            or self.timeout_source_count != timed_out
        ):
            raise ValueError("source acquisition counters do not reconcile")

        expected_published = (
            self.coordinator_result.status
            is FinalDecisionReviewWorkflowCoordinatorStatus.PUBLISHED
            and self.coordinator_result.published
            and self.coordinator_result.primary_blocker is None
        )
        if self.published is not expected_published:
            raise ValueError("source acquisition publication mirror is inconsistent")
        expected_blocker = None if expected_published else self.coordinator_result.primary_blocker
        if self.primary_blocker != expected_blocker:
            raise ValueError("source acquisition blocker mirror is inconsistent")
        return self
