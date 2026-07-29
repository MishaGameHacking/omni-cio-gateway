from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewShadowStatus,
)


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
HttpMethod = Annotated[str, Field(pattern=r"^[A-Z]{3,10}$")]
SafeText = Annotated[str, Field(min_length=1, max_length=512)]


class FinalDecisionReviewReleaseStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class FinalDecisionReviewReleaseScope(StrEnum):
    GET_READ_ONLY_CONTRACT_REVIEW = "get_read_only_contract_review"


class FinalDecisionReviewReleaseCheckStatus(StrEnum):
    PASS = "pass"
    BLOCK = "block"


class FinalDecisionReviewReleaseCheckCode(StrEnum):
    SHADOW_PARITY = "shadow_parity"
    SCHEMA_NAME = "schema_name"
    SCHEMA_VERSION = "schema_version"
    ACCOUNT_MASKING = "account_masking"
    PAYLOAD_SIZE = "payload_size"
    INTENT_COUNT = "intent_count"
    SOURCE_COUNT = "source_count"
    PROVENANCE = "provenance"
    SENSITIVE_DATA = "sensitive_data"
    EXECUTION_SURFACE = "execution_surface"
    MUTATION_SURFACE = "mutation_surface"
    HTTP_METHOD = "http_method"


class FinalDecisionReviewReleaseWarning(StrEnum):
    ELIGIBILITY_IS_NOT_ROUTE_APPROVAL = "eligibility_is_not_route_approval"
    GET_READ_ONLY_SCOPE_ONLY = "get_read_only_scope_only"
    RESPONSE_READINESS_IS_NOT_EXECUTION_AUTHORIZATION = (
        "response_readiness_is_not_execution_authorization"
    )
    SEPARATE_ACTION_CONTRACT_REVIEW_REQUIRED = (
        "separate_action_contract_review_required"
    )


class FinalDecisionReviewReleasePolicyV1(ContractModel):
    supported_schema_name: Literal["final_decision_review_response"] = (
        "final_decision_review_response"
    )
    supported_schema_version: Literal["1.0"] = "1.0"
    max_payload_bytes: Annotated[int, Field(ge=1_024, le=1_048_576)] = 65_536
    max_intents: Annotated[int, Field(ge=1, le=1_000)] = 100
    max_sources: Annotated[int, Field(ge=1, le=1_000)] = 50
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60
    allowed_http_method: Literal["GET"] = "GET"


class FinalDecisionReviewReleaseCheckV1(ContractModel):
    code: FinalDecisionReviewReleaseCheckCode
    status: FinalDecisionReviewReleaseCheckStatus
    message: SafeText
    observed: Annotated[str, Field(min_length=1, max_length=256)]
    expected: Annotated[str, Field(min_length=1, max_length=256)]


class FinalDecisionReviewReleaseEligibilityV1(ContractModel):
    schema_name: Literal["final_decision_review_release_eligibility"] = (
        "final_decision_review_release_eligibility"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: FinalDecisionReviewReleaseStatus
    scope: Literal[
        FinalDecisionReviewReleaseScope.GET_READ_ONLY_CONTRACT_REVIEW
    ] = FinalDecisionReviewReleaseScope.GET_READ_ONLY_CONTRACT_REVIEW
    eligible: bool
    policy: FinalDecisionReviewReleasePolicyV1
    response_schema_name: Annotated[str, Field(min_length=3, max_length=128)]
    response_schema_version: Annotated[str, Field(min_length=1, max_length=32)]
    response_sha256: Sha256Digest
    payload_size_bytes: NonNegativeInt
    intent_count: PositiveInt
    source_count: PositiveInt
    intended_http_method: HttpMethod
    shadow_status: FinalDecisionReviewShadowStatus
    shadow_parity_confirmed: bool
    schema_compatible: bool
    account_masking_confirmed: bool
    payload_bounds_confirmed: bool
    provenance_confirmed: bool
    sensitive_data_absent: bool
    execution_surface_absent: bool
    mutation_surface_absent: bool
    get_read_only_compatible: bool
    checks: Annotated[tuple[FinalDecisionReviewReleaseCheckV1, ...], Field(min_length=1)]
    primary_blocker: FinalDecisionReviewReleaseCheckCode | None = None
    blockers: tuple[FinalDecisionReviewReleaseCheckCode, ...] = ()
    warnings: tuple[FinalDecisionReviewReleaseWarning, ...]
    route_approval_granted: Literal[False] = False
    public_action_created: Literal[False] = False
    route_added: Literal[False] = False
    openapi_changed: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("release eligibility timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_eligibility(self) -> FinalDecisionReviewReleaseEligibilityV1:
        check_codes = tuple(check.code for check in self.checks)
        if len(set(check_codes)) != len(check_codes):
            raise ValueError("release eligibility checks must be unique")
        if set(check_codes) != set(FinalDecisionReviewReleaseCheckCode):
            raise ValueError("release eligibility checks are incomplete")

        expected_blockers = tuple(
            check.code
            for check in self.checks
            if check.status is FinalDecisionReviewReleaseCheckStatus.BLOCK
        )
        if self.blockers != expected_blockers:
            raise ValueError("release eligibility blockers do not match checks")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("release eligibility blockers must be unique")
        expected_primary = self.blockers[0] if self.blockers else None
        if self.primary_blocker is not expected_primary:
            raise ValueError("release eligibility primary blocker is inconsistent")

        required_warnings = set(FinalDecisionReviewReleaseWarning)
        if set(self.warnings) != required_warnings:
            raise ValueError("release eligibility warnings are incomplete")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("release eligibility warnings must be unique")

        expected_flags = (
            self.shadow_parity_confirmed,
            self.schema_compatible,
            self.account_masking_confirmed,
            self.payload_bounds_confirmed,
            self.provenance_confirmed,
            self.sensitive_data_absent,
            self.execution_surface_absent,
            self.mutation_surface_absent,
            self.get_read_only_compatible,
        )
        expected_eligible = not self.blockers and all(expected_flags)
        if self.eligible is not expected_eligible:
            raise ValueError("release eligibility decision is inconsistent")
        expected_status = (
            FinalDecisionReviewReleaseStatus.ELIGIBLE
            if expected_eligible
            else FinalDecisionReviewReleaseStatus.INELIGIBLE
        )
        if self.status is not expected_status:
            raise ValueError("release eligibility status is inconsistent")
        if self.get_read_only_compatible is (
            self.intended_http_method != self.policy.allowed_http_method
        ):
            raise ValueError("GET read-only compatibility is inconsistent")
        if self.shadow_parity_confirmed is (
            self.shadow_status is not FinalDecisionReviewShadowStatus.MATCH
        ):
            raise ValueError("shadow parity status is inconsistent")
        return self
