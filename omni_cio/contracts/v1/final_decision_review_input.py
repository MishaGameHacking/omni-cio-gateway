from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import AccountReference, ContractModel
from omni_cio.contracts.v1.final_decision_review import FinalDecisionReviewResponseV1
from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewOpenApiShadowV1,
)


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeIdentifier = Annotated[str, Field(min_length=3, max_length=256)]
SafeMessage = Annotated[str, Field(min_length=1, max_length=512)]
SafeObservation = Annotated[str, Field(min_length=1, max_length=1024)]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class FinalDecisionReviewInputStatus(StrEnum):
    VALID = "valid"
    BLOCKED = "blocked"


class FinalDecisionReviewInputCheckStatus(StrEnum):
    PASS = "pass"
    BLOCK = "block"


class FinalDecisionReviewInputCheckCode(StrEnum):
    ACTION_SHADOW = "action_shadow"
    RESPONSE_IDENTITY = "response_identity"
    ACTION_CANDIDATE_IDENTITY = "action_candidate_identity"
    ACCOUNT = "account"
    OPTIONS = "options"
    INTENT_FINGERPRINT = "intent_fingerprint"
    INSTRUMENTS = "instruments"
    PAYLOAD_BOUNDS = "payload_bounds"
    RESPONSE_FRESHNESS = "response_freshness"
    REQUEST_BODY = "request_body"
    CREDENTIAL_FIELDS = "credential_fields"
    EXECUTION_FIELDS = "execution_fields"
    MUTATION_FIELDS = "mutation_fields"
    FUNDS_MOVEMENT_FIELDS = "funds_movement_fields"


class FinalDecisionReviewInputWarning(StrEnum):
    INTERNAL_SHADOW_ONLY = "internal_shadow_only"
    QUERY_ONLY_NO_REQUEST_BODY = "query_only_no_request_body"
    NO_PRODUCTION_ROUTE = "no_production_route"
    OPENAPI_NOT_MODIFIED = "openapi_not_modified"
    SEPARATE_PRODUCTION_REVIEW_REQUIRED = "separate_production_review_required"
    NO_EXECUTION_AUTHORIZATION = "no_execution_authorization"


class FinalDecisionReviewInputPolicyV1(ContractModel):
    max_query_bytes: Annotated[int, Field(ge=1_024, le=65_536)] = 8_192
    max_instruments: Annotated[int, Field(ge=1, le=1_000)] = 100
    max_response_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 900
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60
    allowed_query_parameters: tuple[str, ...] = (
        "account",
        "requested_option_id",
        "final_option_id",
        "intent_fingerprint",
        "instrument_count",
        "instrument_keys",
        "response_sha256",
        "action_candidate_sha256",
    )

    @model_validator(mode="after")
    def validate_policy(self) -> FinalDecisionReviewInputPolicyV1:
        if len(set(self.allowed_query_parameters)) != len(
            self.allowed_query_parameters
        ):
            raise ValueError("read-only input parameter allowlist must be unique")
        return self


class FinalDecisionReviewReadOnlyQueryV1(ContractModel):
    schema_name: Literal["final_decision_review_read_only_query"] = (
        "final_decision_review_read_only_query"
    )
    schema_version: Literal["1.0"] = "1.0"
    account: AccountReference
    requested_option_id: SafeIdentifier
    final_option_id: SafeIdentifier
    intent_fingerprint: Sha256Digest
    instrument_count: PositiveInt
    instrument_keys: Annotated[tuple[SafeIdentifier, ...], Field(min_length=1)]
    response_sha256: Sha256Digest
    action_candidate_sha256: Sha256Digest
    request_body_present: Literal[False] = False
    credential_fields_present: Literal[False] = False
    execution_fields_present: Literal[False] = False
    mutation_fields_present: Literal[False] = False
    funds_movement_fields_present: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("requested_option_id", "final_option_id")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("read-only option identifier contains control characters")
        return value

    @field_validator("instrument_keys")
    @classmethod
    def validate_instrument_keys(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            any(ord(character) < 32 for character in value)
            for value in values
        ):
            raise ValueError("read-only instrument key contains control characters")
        if len(set(values)) != len(values):
            raise ValueError("read-only instrument keys must be unique")
        return values

    @model_validator(mode="after")
    def validate_query(self) -> FinalDecisionReviewReadOnlyQueryV1:
        if self.instrument_count != len(self.instrument_keys):
            raise ValueError("read-only input instrument count does not reconcile")
        return self


class FinalDecisionReviewInputCheckV1(ContractModel):
    code: FinalDecisionReviewInputCheckCode
    status: FinalDecisionReviewInputCheckStatus
    message: SafeMessage
    observed: SafeObservation
    expected: SafeObservation


class FinalDecisionReviewInputBindingV1(ContractModel):
    schema_name: Literal["final_decision_review_input_binding"] = (
        "final_decision_review_input_binding"
    )
    schema_version: Literal["1.0"] = "1.0"
    validated_at: datetime
    status: FinalDecisionReviewInputStatus
    input_valid: bool
    policy: FinalDecisionReviewInputPolicyV1
    query: FinalDecisionReviewReadOnlyQueryV1
    response: Annotated[FinalDecisionReviewResponseV1, SkipValidation()]
    action_shadow: Annotated[FinalDecisionReviewOpenApiShadowV1, SkipValidation()]
    query_sha256: Sha256Digest
    response_sha256: Sha256Digest
    action_candidate_sha256: Sha256Digest
    query_size_bytes: NonNegativeInt
    response_age_seconds: NonNegativeInt
    action_shadow_confirmed: bool
    response_identity_confirmed: bool
    action_candidate_identity_confirmed: bool
    account_confirmed: bool
    options_confirmed: bool
    fingerprint_confirmed: bool
    instruments_confirmed: bool
    payload_bounds_confirmed: bool
    freshness_confirmed: bool
    request_body_absent: bool
    credential_fields_absent: bool
    execution_fields_absent: bool
    mutation_fields_absent: bool
    funds_movement_fields_absent: bool
    checks: Annotated[tuple[FinalDecisionReviewInputCheckV1, ...], Field(min_length=1)]
    primary_blocker: FinalDecisionReviewInputCheckCode | None = None
    blockers: tuple[FinalDecisionReviewInputCheckCode, ...] = ()
    warnings: tuple[FinalDecisionReviewInputWarning, ...]
    internal_only: Literal[True] = True
    route_added: Literal[False] = False
    openapi_changed: Literal[False] = False
    public_action_created: Literal[False] = False
    request_body_created: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("validated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("read-only input binding timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_binding(self) -> FinalDecisionReviewInputBindingV1:
        query_payload = self.query.model_dump(mode="json")
        query_bytes = _canonical_bytes(query_payload)
        response_payload = self.response.model_dump(mode="json")
        candidate_payload = self.action_shadow.candidate.model_dump(mode="json")
        computed_query_sha = hashlib.sha256(query_bytes).hexdigest()
        computed_response_sha = _canonical_sha256(response_payload)
        computed_candidate_sha = _canonical_sha256(candidate_payload)

        if self.query_sha256 != computed_query_sha:
            raise ValueError("read-only input query digest is inconsistent")
        if self.response_sha256 != computed_response_sha:
            raise ValueError("read-only input response digest is inconsistent")
        if self.action_candidate_sha256 != computed_candidate_sha:
            raise ValueError("read-only input Action candidate digest is inconsistent")
        if self.query_size_bytes != len(query_bytes):
            raise ValueError("read-only input query size is inconsistent")

        check_codes = tuple(check.code for check in self.checks)
        if len(set(check_codes)) != len(check_codes):
            raise ValueError("read-only input checks must be unique")
        if set(check_codes) != set(FinalDecisionReviewInputCheckCode):
            raise ValueError("read-only input checks are incomplete")
        expected_blockers = tuple(
            check.code
            for check in self.checks
            if check.status is FinalDecisionReviewInputCheckStatus.BLOCK
        )
        if self.blockers != expected_blockers:
            raise ValueError("read-only input blockers do not match checks")
        expected_primary = self.blockers[0] if self.blockers else None
        if self.primary_blocker is not expected_primary:
            raise ValueError("read-only input primary blocker is inconsistent")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("read-only input blockers must be unique")
        if set(self.warnings) != set(FinalDecisionReviewInputWarning):
            raise ValueError("read-only input warnings are incomplete")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("read-only input warnings must be unique")

        expected_action_shadow = (
            self.action_shadow.status
            is FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
            and self.action_shadow.shadow_valid
            and not self.action_shadow.blockers
            and self.action_shadow.candidate.path == "/decision/final-review"
            and self.action_shadow.candidate.method == "get"
            and self.action_shadow.candidate.operation_id
            == "getFinalDecisionReview"
            and not self.action_shadow.production_schema_mutated
            and not self.action_shadow.route_added
            and not self.action_shadow.openapi_changed
            and not self.action_shadow.public_action_created
            and not self.action_shadow.trade_authorized
            and not self.action_shadow.order_created
            and not self.action_shadow.execution_ready
            and not self.action_shadow.trading_methods
        )
        if self.action_shadow_confirmed is not expected_action_shadow:
            raise ValueError("read-only input Action shadow mirror is inconsistent")

        expected_response_identity = (
            self.query.response_sha256 == self.response_sha256
            and self.action_shadow.release_eligibility.response_sha256
            == self.response_sha256
        )
        if self.response_identity_confirmed is not expected_response_identity:
            raise ValueError("read-only input response identity mirror is inconsistent")
        expected_candidate_identity = (
            self.query.action_candidate_sha256 == self.action_candidate_sha256
        )
        if (
            self.action_candidate_identity_confirmed
            is not expected_candidate_identity
        ):
            raise ValueError("read-only input candidate identity mirror is inconsistent")

        if self.account_confirmed is not (self.query.account == self.response.account):
            raise ValueError("read-only input account mirror is inconsistent")
        expected_options = (
            self.query.requested_option_id == self.response.requested_option_id
            and self.query.final_option_id == self.response.final_option_id
        )
        if self.options_confirmed is not expected_options:
            raise ValueError("read-only input option mirror is inconsistent")
        expected_fingerprint = (
            self.query.intent_fingerprint == self.response.intent_fingerprint
        )
        if self.fingerprint_confirmed is not expected_fingerprint:
            raise ValueError("read-only input fingerprint mirror is inconsistent")
        expected_instruments = (
            self.query.instrument_count == self.response.instrument_count
            and self.query.instrument_keys
            == tuple(row.instrument_key for row in self.response.intents)
            and self.query.instrument_count <= self.policy.max_instruments
        )
        if self.instruments_confirmed is not expected_instruments:
            raise ValueError("read-only input instruments mirror is inconsistent")

        expected_payload_bounds = (
            self.query_size_bytes <= self.policy.max_query_bytes
            and self.query.instrument_count <= self.policy.max_instruments
            and set(self.query.model_fields_set).issubset(
                self.policy.allowed_query_parameters
            )
        )
        if self.payload_bounds_confirmed is not expected_payload_bounds:
            raise ValueError("read-only input bounds mirror is inconsistent")

        response_delta = self.validated_at - self.response.generated_at
        expected_age_seconds = max(0, int(response_delta.total_seconds()))
        if self.response_age_seconds != expected_age_seconds:
            raise ValueError("read-only input response age is inconsistent")
        expected_freshness = (
            expected_age_seconds <= self.policy.max_response_age_seconds
            and self.response.generated_at
            <= self.validated_at
            + timedelta(seconds=self.policy.future_tolerance_seconds)
        )
        if self.freshness_confirmed is not expected_freshness:
            raise ValueError("read-only input freshness mirror is inconsistent")

        if self.request_body_absent is not (not self.query.request_body_present):
            raise ValueError("read-only input request-body mirror is inconsistent")
        if self.credential_fields_absent is not (
            not self.query.credential_fields_present
        ):
            raise ValueError("read-only input credential mirror is inconsistent")
        expected_execution_absent = (
            not self.query.execution_fields_present
            and not self.query.trade_authorized
            and not self.query.order_created
            and not self.query.execution_ready
            and not self.query.trading_methods
        )
        if self.execution_fields_absent is not expected_execution_absent:
            raise ValueError("read-only input execution mirror is inconsistent")
        if self.mutation_fields_absent is not (
            not self.query.mutation_fields_present
        ):
            raise ValueError("read-only input mutation mirror is inconsistent")
        if self.funds_movement_fields_absent is not (
            not self.query.funds_movement_fields_present
        ):
            raise ValueError("read-only input funds-movement mirror is inconsistent")

        flags = (
            self.action_shadow_confirmed,
            self.response_identity_confirmed,
            self.action_candidate_identity_confirmed,
            self.account_confirmed,
            self.options_confirmed,
            self.fingerprint_confirmed,
            self.instruments_confirmed,
            self.payload_bounds_confirmed,
            self.freshness_confirmed,
            self.request_body_absent,
            self.credential_fields_absent,
            self.execution_fields_absent,
            self.mutation_fields_absent,
            self.funds_movement_fields_absent,
        )
        expected_valid = all(flags) and not self.blockers
        if self.input_valid is not expected_valid:
            raise ValueError("read-only input decision is inconsistent")
        expected_status = (
            FinalDecisionReviewInputStatus.VALID
            if expected_valid
            else FinalDecisionReviewInputStatus.BLOCKED
        )
        if self.status is not expected_status:
            raise ValueError("read-only input status is inconsistent")
        return self
