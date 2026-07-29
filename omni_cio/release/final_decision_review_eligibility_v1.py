from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewResponseV1,
    FinalDecisionReviewShadowStatus,
    FinalDecisionReviewShadowValidationV1,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseCheckCode,
    FinalDecisionReviewReleaseCheckStatus,
    FinalDecisionReviewReleaseCheckV1,
    FinalDecisionReviewReleaseEligibilityV1,
    FinalDecisionReviewReleasePolicyV1,
    FinalDecisionReviewReleaseStatus,
    FinalDecisionReviewReleaseWarning,
)


_SENSITIVE_KEYS = {
    "access_token",
    "account_id",
    "api_key",
    "authorization",
    "broker_account_id",
    "full_account_id",
    "password",
    "secret",
    "source_binding",
    "source_id",
}
_MUTATION_KEY_FRAGMENTS = (
    "cancel_order",
    "create_order",
    "execute_order",
    "post_order",
    "replace_order",
    "submit_order",
    "transfer",
    "withdraw",
)
_MASK_CHARACTERS = {"*", "•", "…", "x", "X"}


class FinalDecisionReviewReleaseEligibilityError(ValueError):
    """A release eligibility assessment cannot be produced safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewReleaseEligibilityError(
            "FINAL_DECISION_REVIEW_RELEASE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_payload(response: FinalDecisionReviewResponseV1) -> bytes:
    payload = response.model_dump(mode="json")
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _walk_payload(value: Any, *, path: tuple[str, ...] = ()) -> tuple[tuple[str, Any], ...]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = (*path, key_text)
            rows.append((".".join(child_path), child))
            rows.extend(_walk_payload(child, path=child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            child_path = (*path, str(index))
            rows.extend(_walk_payload(child, path=child_path))
    return tuple(rows)


def _truthy_mutation_surface(rows: tuple[tuple[str, Any], ...]) -> bool:
    for path, value in rows:
        key = path.rsplit(".", 1)[-1].lower()
        if any(fragment in key for fragment in _MUTATION_KEY_FRAGMENTS) and bool(value):
            return True
    return False


def _sensitive_key_present(rows: tuple[tuple[str, Any], ...]) -> bool:
    return any(path.rsplit(".", 1)[-1].lower() in _SENSITIVE_KEYS for path, _ in rows)


def _check(
    code: FinalDecisionReviewReleaseCheckCode,
    passed: bool,
    *,
    message: str,
    observed: str,
    expected: str,
) -> FinalDecisionReviewReleaseCheckV1:
    return FinalDecisionReviewReleaseCheckV1(
        code=code,
        status=(
            FinalDecisionReviewReleaseCheckStatus.PASS
            if passed
            else FinalDecisionReviewReleaseCheckStatus.BLOCK
        ),
        message=message,
        observed=observed,
        expected=expected,
    )


def assess_final_decision_review_release_eligibility(
    response: FinalDecisionReviewResponseV1,
    shadow: FinalDecisionReviewShadowValidationV1,
    *,
    policy: FinalDecisionReviewReleasePolicyV1 | None = None,
    intended_http_method: str = "GET",
    assessed_at: datetime | None = None,
) -> FinalDecisionReviewReleaseEligibilityV1:
    """Assess GET/read-only contract eligibility without adding a public route."""

    active_policy = policy or FinalDecisionReviewReleasePolicyV1()
    assessment_time = _aware_utc(assessed_at)
    method = intended_http_method.upper()
    canonical = _canonical_payload(response)
    digest = hashlib.sha256(canonical).hexdigest()
    payload = response.model_dump(mode="json")
    rows = _walk_payload(payload)

    shadow_parity_confirmed = (
        shadow.status is FinalDecisionReviewShadowStatus.MATCH
        and shadow.shadow_valid
        and not shadow.mismatches
        and shadow.response == response
        and not shadow.route_added
        and not shadow.trade_authorized
        and not shadow.order_created
        and not shadow.execution_ready
        and not shadow.trading_methods
    )
    schema_name_match = response.schema_name == active_policy.supported_schema_name
    schema_version_match = (
        response.schema_version == active_policy.supported_schema_version
    )
    schema_compatible = schema_name_match and schema_version_match
    account_masking_confirmed = any(
        character in response.account.masked_id for character in _MASK_CHARACTERS
    )
    payload_size_ok = len(canonical) <= active_policy.max_payload_bytes
    intent_count_ok = (
        response.instrument_count == len(response.intents)
        and response.instrument_count <= active_policy.max_intents
    )
    source_count_ok = (
        response.source_count == len(response.provenance)
        and response.source_count <= active_policy.max_sources
    )

    provenance_keys = tuple(
        (source.provider, source.operation, source.retrieved_at)
        for source in response.provenance
    )
    future_limit = assessment_time.timestamp() + active_policy.future_tolerance_seconds
    provenance_confirmed = (
        bool(provenance_keys)
        and len(set(provenance_keys)) == len(provenance_keys)
        and all(source.retrieved_at.timestamp() <= future_limit for source in response.provenance)
    )
    sensitive_data_absent = (
        not response.full_account_identifier_present
        and not response.source_contracts_exposed
        and not _sensitive_key_present(rows)
    )
    execution_surface_absent = (
        not response.public_action_exposed
        and not response.trade_authorized
        and not response.order_created
        and not response.execution_ready
        and not response.trading_methods
    )
    mutation_surface_absent = not _truthy_mutation_surface(rows)
    get_read_only_compatible = method == active_policy.allowed_http_method
    payload_bounds_confirmed = payload_size_ok and intent_count_ok and source_count_ok

    checks = (
        _check(
            FinalDecisionReviewReleaseCheckCode.SHADOW_PARITY,
            shadow_parity_confirmed,
            message="Final response matches the completed internal shadow validation.",
            observed=shadow.status.value,
            expected=FinalDecisionReviewShadowStatus.MATCH.value,
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.SCHEMA_NAME,
            schema_name_match,
            message="Response schema name is the reviewed final-response contract.",
            observed=response.schema_name,
            expected=active_policy.supported_schema_name,
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.SCHEMA_VERSION,
            schema_version_match,
            message="Response schema version is explicitly supported.",
            observed=response.schema_version,
            expected=active_policy.supported_schema_version,
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.ACCOUNT_MASKING,
            account_masking_confirmed,
            message="Only a masked account reference may cross the user-safe boundary.",
            observed="masked" if account_masking_confirmed else "unmasked",
            expected="masked",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.PAYLOAD_SIZE,
            payload_size_ok,
            message="Canonical JSON payload stays within the reviewed byte bound.",
            observed=str(len(canonical)),
            expected=f"<= {active_policy.max_payload_bytes}",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.INTENT_COUNT,
            intent_count_ok,
            message="Intent rows reconcile and stay within the reviewed count bound.",
            observed=str(response.instrument_count),
            expected=f"1..{active_policy.max_intents}",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.SOURCE_COUNT,
            source_count_ok,
            message="Provenance rows reconcile and stay within the reviewed count bound.",
            observed=str(response.source_count),
            expected=f"1..{active_policy.max_sources}",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.PROVENANCE,
            provenance_confirmed,
            message="Sanitized provenance is present, unique and not future-dated.",
            observed="valid" if provenance_confirmed else "invalid",
            expected="valid",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.SENSITIVE_DATA,
            sensitive_data_absent,
            message="No full account, source contract or sensitive field is present.",
            observed="absent" if sensitive_data_absent else "present",
            expected="absent",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.EXECUTION_SURFACE,
            execution_surface_absent,
            message="All order, execution and trading flags remain disabled.",
            observed="absent" if execution_surface_absent else "present",
            expected="absent",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.MUTATION_SURFACE,
            mutation_surface_absent,
            message="No truthy order, transfer or withdrawal mutation surface exists.",
            observed="absent" if mutation_surface_absent else "present",
            expected="absent",
        ),
        _check(
            FinalDecisionReviewReleaseCheckCode.HTTP_METHOD,
            get_read_only_compatible,
            message="Eligibility is limited to a future GET/read-only contract review.",
            observed=method,
            expected=active_policy.allowed_http_method,
        ),
    )
    blockers = tuple(
        check.code
        for check in checks
        if check.status is FinalDecisionReviewReleaseCheckStatus.BLOCK
    )
    eligible = not blockers

    return FinalDecisionReviewReleaseEligibilityV1(
        assessed_at=assessment_time,
        status=(
            FinalDecisionReviewReleaseStatus.ELIGIBLE
            if eligible
            else FinalDecisionReviewReleaseStatus.INELIGIBLE
        ),
        eligible=eligible,
        policy=active_policy,
        response_schema_name=response.schema_name,
        response_schema_version=response.schema_version,
        response_sha256=digest,
        payload_size_bytes=len(canonical),
        intent_count=response.instrument_count,
        source_count=response.source_count,
        intended_http_method=method,
        shadow_status=shadow.status,
        shadow_parity_confirmed=shadow_parity_confirmed,
        schema_compatible=schema_compatible,
        account_masking_confirmed=account_masking_confirmed,
        payload_bounds_confirmed=payload_bounds_confirmed,
        provenance_confirmed=provenance_confirmed,
        sensitive_data_absent=sensitive_data_absent,
        execution_surface_absent=execution_surface_absent,
        mutation_surface_absent=mutation_surface_absent,
        get_read_only_compatible=get_read_only_compatible,
        checks=checks,
        primary_blocker=blockers[0] if blockers else None,
        blockers=blockers,
        warnings=tuple(FinalDecisionReviewReleaseWarning),
    )
