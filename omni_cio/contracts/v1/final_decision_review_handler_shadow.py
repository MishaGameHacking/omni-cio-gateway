from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review import FinalDecisionReviewResponseV1
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.contracts.v1.observability import ObservabilityEventV1


Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeText = Annotated[str, Field(min_length=1, max_length=512)]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class FinalDecisionReviewHandlerShadowStatus(StrEnum):
    SUCCESS = "success"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class FinalDecisionReviewHandlerErrorCode(StrEnum):
    INVALID_REQUEST = "FINAL_REVIEW_INVALID_REQUEST"
    AUTHENTICATION_REQUIRED = "FINAL_REVIEW_AUTHENTICATION_REQUIRED"
    SOURCE_CONFLICT = "FINAL_REVIEW_SOURCE_CONFLICT"
    SCHEMA_VALIDATION = "FINAL_REVIEW_SCHEMA_VALIDATION"
    SOURCE_UNAVAILABLE = "FINAL_REVIEW_SOURCE_UNAVAILABLE"


class FinalDecisionReviewHandlerHttpStatus(IntEnum):
    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    SERVICE_UNAVAILABLE = 503


class FinalDecisionReviewHandlerErrorMappingV1(ContractModel):
    error_code: FinalDecisionReviewHandlerErrorCode
    http_status: FinalDecisionReviewHandlerHttpStatus
    description: SafeText


class FinalDecisionReviewHandlerShadowResultV1(ContractModel):
    schema_name: Literal["final_decision_review_handler_shadow_result"] = (
        "final_decision_review_handler_shadow_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    handled_at: datetime
    status: FinalDecisionReviewHandlerShadowStatus
    http_status: FinalDecisionReviewHandlerHttpStatus
    response: Annotated[FinalDecisionReviewResponseV1, SkipValidation()] | None = None
    error_code: FinalDecisionReviewHandlerErrorCode | None = None
    error_message: SafeText | None = None
    route_plan: Annotated[
        FinalDecisionReviewRouteImplementationPlanV1,
        SkipValidation(),
    ]
    input_binding: Annotated[FinalDecisionReviewInputBindingV1, SkipValidation()]
    route_plan_sha256: Sha256Digest
    input_binding_sha256: Sha256Digest
    response_sha256: Sha256Digest | None = None
    authentication_confirmed: bool
    route_plan_confirmed: bool
    input_binding_confirmed: bool
    source_identity_confirmed: bool
    source_available: bool
    error_mapping: Annotated[
        tuple[FinalDecisionReviewHandlerErrorMappingV1, ...],
        Field(min_length=1),
    ]
    observability_event: ObservabilityEventV1
    shadow_only: Literal[True] = True
    route_registered: Literal[False] = False
    production_openapi_changed: Literal[False] = False
    public_action_created: Literal[False] = False
    external_broker_called: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("handled_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("handler shadow timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> FinalDecisionReviewHandlerShadowResultV1:
        plan_sha = _canonical_sha256(self.route_plan.model_dump(mode="json"))
        binding_sha = _canonical_sha256(self.input_binding.model_dump(mode="json"))
        if self.route_plan_sha256 != plan_sha:
            raise ValueError("handler shadow route-plan digest is inconsistent")
        if self.input_binding_sha256 != binding_sha:
            raise ValueError("handler shadow input-binding digest is inconsistent")

        mapping_codes = tuple(row.error_code for row in self.error_mapping)
        if len(set(mapping_codes)) != len(mapping_codes):
            raise ValueError("handler shadow error mappings must be unique")
        if set(mapping_codes) != set(FinalDecisionReviewHandlerErrorCode):
            raise ValueError("handler shadow error mapping is incomplete")
        expected_statuses = {
            FinalDecisionReviewHandlerErrorCode.INVALID_REQUEST: (
                FinalDecisionReviewHandlerHttpStatus.BAD_REQUEST
            ),
            FinalDecisionReviewHandlerErrorCode.AUTHENTICATION_REQUIRED: (
                FinalDecisionReviewHandlerHttpStatus.UNAUTHORIZED
            ),
            FinalDecisionReviewHandlerErrorCode.SOURCE_CONFLICT: (
                FinalDecisionReviewHandlerHttpStatus.CONFLICT
            ),
            FinalDecisionReviewHandlerErrorCode.SCHEMA_VALIDATION: (
                FinalDecisionReviewHandlerHttpStatus.UNPROCESSABLE_ENTITY
            ),
            FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE: (
                FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
            ),
        }
        for row in self.error_mapping:
            if row.http_status is not expected_statuses[row.error_code]:
                raise ValueError("handler shadow error mapping status is inconsistent")

        expected_plan = (
            self.route_plan.status
            is FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW
            and self.route_plan.ready_for_implementation_review
            and not self.route_plan.blockers
        )
        if self.route_plan_confirmed is not expected_plan:
            raise ValueError("handler shadow route-plan mirror is inconsistent")
        expected_binding = (
            self.input_binding.status is FinalDecisionReviewInputStatus.VALID
            and self.input_binding.input_valid
            and not self.input_binding.blockers
        )
        if self.input_binding_confirmed is not expected_binding:
            raise ValueError("handler shadow input-binding mirror is inconsistent")

        plan_binding = self.route_plan.readiness_dossier.input_binding
        expected_identity = (
            self.input_binding.query_sha256 == plan_binding.query_sha256
            and self.input_binding.response_sha256 == plan_binding.response_sha256
            and self.input_binding.action_candidate_sha256
            == plan_binding.action_candidate_sha256
            and self.input_binding.query == plan_binding.query
        )
        if self.source_identity_confirmed is not expected_identity:
            raise ValueError("handler shadow source identity mirror is inconsistent")

        source_response = self.route_plan.readiness_dossier.response
        expected_response_sha = _canonical_sha256(
            source_response.model_dump(mode="json")
        )
        success = (
            self.authentication_confirmed
            and self.route_plan_confirmed
            and self.input_binding_confirmed
            and self.source_identity_confirmed
            and self.source_available
        )
        if success:
            if self.status is not FinalDecisionReviewHandlerShadowStatus.SUCCESS:
                raise ValueError("handler shadow successful status is inconsistent")
            if self.http_status is not FinalDecisionReviewHandlerHttpStatus.OK:
                raise ValueError("handler shadow successful HTTP status is inconsistent")
            if self.response != source_response:
                raise ValueError("handler shadow response does not match source")
            if self.response_sha256 != expected_response_sha:
                raise ValueError("handler shadow response digest is inconsistent")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("handler shadow success cannot contain an error")
        else:
            if self.response is not None or self.response_sha256 is not None:
                raise ValueError("handler shadow blocked result cannot contain response data")
            if self.error_code is None or self.error_message is None:
                raise ValueError("handler shadow blocked result requires an error")
            expected_http = expected_statuses[self.error_code]
            if self.http_status is not expected_http:
                raise ValueError("handler shadow blocked HTTP status is inconsistent")
            expected_shadow_status = (
                FinalDecisionReviewHandlerShadowStatus.UNAVAILABLE
                if self.error_code
                is FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
                else FinalDecisionReviewHandlerShadowStatus.REJECTED
            )
            if self.status is not expected_shadow_status:
                raise ValueError("handler shadow blocked status is inconsistent")

        if self.observability_event.occurred_at != self.handled_at:
            raise ValueError("handler shadow observability timestamp is inconsistent")
        if self.observability_event.account != source_response.account:
            raise ValueError("handler shadow observability account is inconsistent")
        if self.observability_event.contains_sensitive_payload:
            raise ValueError("handler shadow observability cannot contain private payload")
        if self.observability_event.trading_methods:
            raise ValueError("handler shadow observability cannot enable trading")
        return self
