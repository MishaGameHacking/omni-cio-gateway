from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from omni_cio.contracts.v1.final_decision_review import FinalDecisionReviewResponseV1
from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputCheckCode,
    FinalDecisionReviewInputCheckStatus,
    FinalDecisionReviewInputCheckV1,
    FinalDecisionReviewInputPolicyV1,
    FinalDecisionReviewInputStatus,
    FinalDecisionReviewInputWarning,
    FinalDecisionReviewReadOnlyQueryV1,
)


class FinalDecisionReviewInputError(ValueError):
    """The final-review read-only input cannot be validated safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewInputError(
            "FINAL_DECISION_REVIEW_INPUT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _check(
    code: FinalDecisionReviewInputCheckCode,
    passed: bool,
    *,
    message: str,
    observed: str,
    expected: str,
) -> FinalDecisionReviewInputCheckV1:
    return FinalDecisionReviewInputCheckV1(
        code=code,
        status=(
            FinalDecisionReviewInputCheckStatus.PASS
            if passed
            else FinalDecisionReviewInputCheckStatus.BLOCK
        ),
        message=message,
        observed=observed,
        expected=expected,
    )


def build_final_decision_review_read_only_query(
    response: FinalDecisionReviewResponseV1,
    action_shadow: FinalDecisionReviewOpenApiShadowV1,
) -> FinalDecisionReviewReadOnlyQueryV1:
    """Build the minimal exact query context from reviewed source objects."""

    response_sha256 = _canonical_sha256(response.model_dump(mode="json"))
    candidate_sha256 = _canonical_sha256(
        action_shadow.candidate.model_dump(mode="json")
    )
    return FinalDecisionReviewReadOnlyQueryV1(
        account=response.account,
        requested_option_id=response.requested_option_id,
        final_option_id=response.final_option_id,
        intent_fingerprint=response.intent_fingerprint,
        instrument_count=response.instrument_count,
        instrument_keys=tuple(row.instrument_key for row in response.intents),
        response_sha256=response_sha256,
        action_candidate_sha256=candidate_sha256,
    )


def bind_final_decision_review_read_only_input(
    query: FinalDecisionReviewReadOnlyQueryV1,
    response: FinalDecisionReviewResponseV1,
    action_shadow: FinalDecisionReviewOpenApiShadowV1,
    *,
    policy: FinalDecisionReviewInputPolicyV1 | None = None,
    validated_at: datetime | None = None,
) -> FinalDecisionReviewInputBindingV1:
    """Bind query-only inputs to the exact response and PR-55 Action shadow."""

    input_policy = policy or FinalDecisionReviewInputPolicyV1()
    validation_time = _aware_utc(validated_at)
    query_payload = query.model_dump(mode="json")
    response_payload = response.model_dump(mode="json")
    candidate_payload = action_shadow.candidate.model_dump(mode="json")
    query_bytes = _canonical_bytes(query_payload)
    query_sha256 = hashlib.sha256(query_bytes).hexdigest()
    response_sha256 = _canonical_sha256(response_payload)
    candidate_sha256 = _canonical_sha256(candidate_payload)

    response_delta = validation_time - response.generated_at
    response_age_seconds = max(0, int(response_delta.total_seconds()))
    response_not_too_old = (
        response_age_seconds <= input_policy.max_response_age_seconds
    )
    response_not_too_far_future = (
        response.generated_at
        <= validation_time
        + timedelta(seconds=input_policy.future_tolerance_seconds)
    )

    action_shadow_confirmed = (
        action_shadow.status
        is FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
        and action_shadow.shadow_valid
        and not action_shadow.blockers
        and action_shadow.candidate.path == "/decision/final-review"
        and action_shadow.candidate.method == "get"
        and action_shadow.candidate.operation_id == "getFinalDecisionReview"
        and not action_shadow.production_schema_mutated
        and not action_shadow.route_added
        and not action_shadow.openapi_changed
        and not action_shadow.public_action_created
        and not action_shadow.trade_authorized
        and not action_shadow.order_created
        and not action_shadow.execution_ready
        and not action_shadow.trading_methods
    )
    response_identity_confirmed = (
        query.response_sha256 == response_sha256
        and action_shadow.release_eligibility.response_sha256 == response_sha256
    )
    action_candidate_identity_confirmed = (
        query.action_candidate_sha256 == candidate_sha256
    )
    account_confirmed = query.account == response.account
    options_confirmed = (
        query.requested_option_id == response.requested_option_id
        and query.final_option_id == response.final_option_id
    )
    fingerprint_confirmed = (
        query.intent_fingerprint == response.intent_fingerprint
    )
    expected_instruments = tuple(row.instrument_key for row in response.intents)
    instruments_confirmed = (
        query.instrument_count == response.instrument_count
        and query.instrument_keys == expected_instruments
        and query.instrument_count <= input_policy.max_instruments
    )
    allowed_fields = set(input_policy.allowed_query_parameters)
    payload_bounds_confirmed = (
        len(query_bytes) <= input_policy.max_query_bytes
        and query.instrument_count <= input_policy.max_instruments
        and set(query.model_fields_set).issubset(allowed_fields)
    )
    freshness_confirmed = response_not_too_old and response_not_too_far_future
    request_body_absent = not query.request_body_present
    credential_fields_absent = not query.credential_fields_present
    execution_fields_absent = (
        not query.execution_fields_present
        and not query.trade_authorized
        and not query.order_created
        and not query.execution_ready
        and not query.trading_methods
    )
    mutation_fields_absent = not query.mutation_fields_present
    funds_movement_fields_absent = not query.funds_movement_fields_present

    checks = (
        _check(
            FinalDecisionReviewInputCheckCode.ACTION_SHADOW,
            action_shadow_confirmed,
            message="PR-55 Action shadow must be exact, valid and read-only",
            observed=str(action_shadow.status.value),
            expected="shadow_valid",
        ),
        _check(
            FinalDecisionReviewInputCheckCode.RESPONSE_IDENTITY,
            response_identity_confirmed,
            message="Query must identify the exact PR-53 response",
            observed=query.response_sha256,
            expected=response_sha256,
        ),
        _check(
            FinalDecisionReviewInputCheckCode.ACTION_CANDIDATE_IDENTITY,
            action_candidate_identity_confirmed,
            message="Query must identify the exact PR-55 Action candidate",
            observed=query.action_candidate_sha256,
            expected=candidate_sha256,
        ),
        _check(
            FinalDecisionReviewInputCheckCode.ACCOUNT,
            account_confirmed,
            message="Masked account context must match the reviewed response",
            observed=query.account.masked_id,
            expected=response.account.masked_id,
        ),
        _check(
            FinalDecisionReviewInputCheckCode.OPTIONS,
            options_confirmed,
            message="Requested and final options must match exactly",
            observed=f"{query.requested_option_id}|{query.final_option_id}",
            expected=(
                f"{response.requested_option_id}|{response.final_option_id}"
            ),
        ),
        _check(
            FinalDecisionReviewInputCheckCode.INTENT_FINGERPRINT,
            fingerprint_confirmed,
            message="Intent fingerprint must match the reviewed response",
            observed=query.intent_fingerprint,
            expected=response.intent_fingerprint,
        ),
        _check(
            FinalDecisionReviewInputCheckCode.INSTRUMENTS,
            instruments_confirmed,
            message="Instrument set and order must match exactly",
            observed=str(query.instrument_count),
            expected=str(response.instrument_count),
        ),
        _check(
            FinalDecisionReviewInputCheckCode.PAYLOAD_BOUNDS,
            payload_bounds_confirmed,
            message="Query payload and instrument count must stay bounded",
            observed=f"{len(query_bytes)} bytes/{query.instrument_count}",
            expected=(
                f"<={input_policy.max_query_bytes} bytes/"
                f"<={input_policy.max_instruments}"
            ),
        ),
        _check(
            FinalDecisionReviewInputCheckCode.RESPONSE_FRESHNESS,
            freshness_confirmed,
            message="Reviewed response must be fresh and not future-dated",
            observed=f"{response_age_seconds}s",
            expected=f"<={input_policy.max_response_age_seconds}s",
        ),
        _check(
            FinalDecisionReviewInputCheckCode.REQUEST_BODY,
            request_body_absent,
            message="Final-review retrieval must not use a request body",
            observed=str(query.request_body_present).lower(),
            expected="false",
        ),
        _check(
            FinalDecisionReviewInputCheckCode.CREDENTIAL_FIELDS,
            credential_fields_absent,
            message="Query must not carry credentials or secrets",
            observed=str(query.credential_fields_present).lower(),
            expected="false",
        ),
        _check(
            FinalDecisionReviewInputCheckCode.EXECUTION_FIELDS,
            execution_fields_absent,
            message="Query must not contain execution controls",
            observed=str(query.execution_fields_present).lower(),
            expected="false",
        ),
        _check(
            FinalDecisionReviewInputCheckCode.MUTATION_FIELDS,
            mutation_fields_absent,
            message="Query must not contain mutation controls",
            observed=str(query.mutation_fields_present).lower(),
            expected="false",
        ),
        _check(
            FinalDecisionReviewInputCheckCode.FUNDS_MOVEMENT_FIELDS,
            funds_movement_fields_absent,
            message="Query must not contain funds movement controls",
            observed=str(query.funds_movement_fields_present).lower(),
            expected="false",
        ),
    )
    blockers = tuple(
        check.code
        for check in checks
        if check.status is FinalDecisionReviewInputCheckStatus.BLOCK
    )
    input_valid = not blockers
    return FinalDecisionReviewInputBindingV1(
        validated_at=validation_time,
        status=(
            FinalDecisionReviewInputStatus.VALID
            if input_valid
            else FinalDecisionReviewInputStatus.BLOCKED
        ),
        input_valid=input_valid,
        policy=input_policy,
        query=query,
        response=response,
        action_shadow=action_shadow,
        query_sha256=query_sha256,
        response_sha256=response_sha256,
        action_candidate_sha256=candidate_sha256,
        query_size_bytes=len(query_bytes),
        response_age_seconds=response_age_seconds,
        action_shadow_confirmed=action_shadow_confirmed,
        response_identity_confirmed=response_identity_confirmed,
        action_candidate_identity_confirmed=action_candidate_identity_confirmed,
        account_confirmed=account_confirmed,
        options_confirmed=options_confirmed,
        fingerprint_confirmed=fingerprint_confirmed,
        instruments_confirmed=instruments_confirmed,
        payload_bounds_confirmed=payload_bounds_confirmed,
        freshness_confirmed=freshness_confirmed,
        request_body_absent=request_body_absent,
        credential_fields_absent=credential_fields_absent,
        execution_fields_absent=execution_fields_absent,
        mutation_fields_absent=mutation_fields_absent,
        funds_movement_fields_absent=funds_movement_fields_absent,
        checks=checks,
        primary_blocker=blockers[0] if blockers else None,
        blockers=blockers,
        warnings=tuple(FinalDecisionReviewInputWarning),
    )
