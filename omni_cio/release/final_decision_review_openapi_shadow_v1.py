from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from omni_cio.contracts.v1.final_decision_review import FinalDecisionReviewResponseV1
from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewActionCandidateBlocker,
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewActionCandidateWarning,
    FinalDecisionReviewGetActionCandidateV1,
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseEligibilityV1,
    FinalDecisionReviewReleaseStatus,
)
from omni_cio.contracts.v1.release import ReadOnlyActionV1, ReadOnlyReleaseManifestV1
from omni_cio.release.read_only_contract_v1 import (
    ReadOnlyReleaseError,
    build_read_only_release_manifest,
)


class FinalDecisionReviewOpenApiShadowError(ValueError):
    """The final-review Action candidate cannot be shadow-validated safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewOpenApiShadowError(
            "FINAL_DECISION_REVIEW_OPENAPI_SHADOW_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _action_key(action: ReadOnlyActionV1) -> tuple[str, str, str, bool, bool]:
    return (
        action.path,
        action.method,
        action.operation_id,
        action.public,
        action.authentication_required,
    )


def _candidate_operation(
    candidate: FinalDecisionReviewGetActionCandidateV1,
) -> dict[str, Any]:
    return {
        "summary": candidate.summary,
        "operationId": candidate.operation_id,
        "security": [{candidate.security_scheme: []}],
        "responses": {
            "200": {
                "description": "Final read-only decision review",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": (
                                "#/components/schemas/"
                                f"{candidate.response_schema_name}"
                            )
                        }
                    }
                },
            }
        },
    }


def build_final_decision_review_openapi_shadow(
    current_openapi_schema: Mapping[str, Any],
    release_eligibility: FinalDecisionReviewReleaseEligibilityV1,
    *,
    expected_app_version: str,
    approved_hosts: frozenset[str],
    validated_at: datetime | None = None,
) -> FinalDecisionReviewOpenApiShadowV1:
    """Validate a GET Action candidate on a deep-copied OpenAPI document only."""

    shadow_time = _aware_utc(validated_at)
    current_schema = deepcopy(dict(current_openapi_schema))
    current_manifest = build_read_only_release_manifest(
        current_schema,
        expected_app_version=expected_app_version,
        approved_hosts=approved_hosts,
        generated_at=shadow_time,
    )

    response_schema = FinalDecisionReviewResponseV1.model_json_schema()
    response_schema_sha256 = _canonical_sha256(response_schema)
    eligibility_sha256 = _canonical_sha256(
        release_eligibility.model_dump(mode="json")
    )
    candidate = FinalDecisionReviewGetActionCandidateV1(
        response_schema_sha256=response_schema_sha256,
        release_eligibility_sha256=eligibility_sha256,
    )

    blockers: list[FinalDecisionReviewActionCandidateBlocker] = []
    if (
        release_eligibility.status
        is not FinalDecisionReviewReleaseStatus.ELIGIBLE
        or not release_eligibility.eligible
        or not release_eligibility.get_read_only_compatible
        or release_eligibility.route_approval_granted
        or release_eligibility.public_action_created
        or release_eligibility.route_added
        or release_eligibility.openapi_changed
        or release_eligibility.trade_authorized
        or release_eligibility.order_created
        or release_eligibility.execution_ready
        or release_eligibility.trading_methods
    ):
        _append_unique(
            blockers,
            FinalDecisionReviewActionCandidateBlocker.RELEASE_NOT_ELIGIBLE,
        )

    if (
        not current_manifest.get_only
        or current_manifest.forbidden_surface_count != 0
        or current_manifest.trading_methods
        or current_manifest.entrypoint != "app:app"
    ):
        _append_unique(
            blockers,
            FinalDecisionReviewActionCandidateBlocker.CURRENT_MANIFEST_NOT_READ_ONLY,
        )

    paths_raw = current_schema.get("paths")
    paths = paths_raw if isinstance(paths_raw, dict) else {}
    if candidate.path in paths:
        _append_unique(
            blockers,
            FinalDecisionReviewActionCandidateBlocker.PATH_ALREADY_EXISTS,
        )
    if any(
        action.operation_id == candidate.operation_id
        for action in current_manifest.actions
    ):
        _append_unique(
            blockers,
            FinalDecisionReviewActionCandidateBlocker.OPERATION_ID_ALREADY_EXISTS,
        )

    response_schema_match = (
        release_eligibility.response_schema_name
        == candidate.response_contract_name
        and release_eligibility.response_schema_version
        == candidate.response_contract_version
    )
    if not response_schema_match:
        _append_unique(
            blockers,
            FinalDecisionReviewActionCandidateBlocker.RESPONSE_SCHEMA_MISMATCH,
        )

    shadow_manifest: ReadOnlyReleaseManifestV1 | None = None
    candidate_action_present = False
    existing_actions_unchanged = False
    shadow_action_count: int | None = None

    if not blockers:
        shadow_schema = deepcopy(current_schema)
        shadow_paths = shadow_schema.setdefault("paths", {})
        shadow_components = shadow_schema.setdefault("components", {})
        shadow_schemas = shadow_components.setdefault("schemas", {})
        shadow_schemas[candidate.response_schema_name] = response_schema
        shadow_paths[candidate.path] = {
            candidate.method: _candidate_operation(candidate)
        }
        try:
            shadow_manifest = build_read_only_release_manifest(
                shadow_schema,
                expected_app_version=expected_app_version,
                approved_hosts=approved_hosts,
                generated_at=shadow_time,
            )
        except ReadOnlyReleaseError:
            _append_unique(
                blockers,
                FinalDecisionReviewActionCandidateBlocker.SHADOW_MANIFEST_INVALID,
            )
        else:
            shadow_action_count = shadow_manifest.action_count
            expected_candidate_key = (
                candidate.path,
                candidate.method,
                candidate.operation_id,
                candidate.public,
                candidate.authentication_required,
            )
            shadow_keys = {_action_key(action) for action in shadow_manifest.actions}
            current_keys = {_action_key(action) for action in current_manifest.actions}
            candidate_action_present = expected_candidate_key in shadow_keys
            existing_actions_unchanged = current_keys.issubset(shadow_keys)
            if not candidate_action_present:
                _append_unique(
                    blockers,
                    FinalDecisionReviewActionCandidateBlocker.CANDIDATE_ACTION_MISSING,
                )
            if not existing_actions_unchanged:
                _append_unique(
                    blockers,
                    FinalDecisionReviewActionCandidateBlocker.EXISTING_ACTIONS_CHANGED,
                )
            if shadow_manifest.action_count != current_manifest.action_count + 1:
                _append_unique(
                    blockers,
                    FinalDecisionReviewActionCandidateBlocker.ACTION_COUNT_MISMATCH,
                )

    shadow_valid = not blockers
    return FinalDecisionReviewOpenApiShadowV1(
        validated_at=shadow_time,
        status=(
            FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
            if shadow_valid
            else FinalDecisionReviewActionCandidateStatus.SHADOW_BLOCKED
        ),
        shadow_valid=shadow_valid,
        candidate=candidate,
        release_eligibility=release_eligibility,
        current_manifest=current_manifest,
        shadow_manifest=shadow_manifest,
        current_action_count=current_manifest.action_count,
        shadow_action_count=shadow_action_count,
        candidate_action_present=candidate_action_present,
        existing_actions_unchanged=existing_actions_unchanged,
        response_schema_match=response_schema_match,
        primary_blocker=blockers[0] if blockers else None,
        blockers=tuple(blockers),
        warnings=tuple(FinalDecisionReviewActionCandidateWarning),
    )
