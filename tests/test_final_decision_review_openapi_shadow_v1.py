from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewActionCandidateBlocker,
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseEligibilityV1,
    FinalDecisionReviewReleaseStatus,
)
from omni_cio.release.final_decision_review_openapi_shadow_v1 import (
    FinalDecisionReviewOpenApiShadowError,
    build_final_decision_review_openapi_shadow,
)
from omni_cio.release.read_only_contract_v1 import ReadOnlyReleaseError


NOW = datetime(2026, 7, 29, 20, 15, tzinfo=timezone.utc)
HOST = "omni-cio-gateway.onrender.com"


def _openapi() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Omni-CIO", "version": "3.9.1"},
        "servers": [{"url": f"https://{HOST}"}],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "gatewayHealth",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/portfolio": {
                "get": {
                    "operationId": "getPortfolioSnapshot",
                    "security": [{"ApiKeyAuth": []}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Gateway-Key",
                }
            }
        },
    }


def _eligibility(
    *,
    eligible: bool = True,
    schema_name: str = "final_decision_review_response",
    schema_version: str = "1.0",
) -> FinalDecisionReviewReleaseEligibilityV1:
    return FinalDecisionReviewReleaseEligibilityV1.model_construct(
        assessed_at=NOW,
        status=(
            FinalDecisionReviewReleaseStatus.ELIGIBLE
            if eligible
            else FinalDecisionReviewReleaseStatus.INELIGIBLE
        ),
        eligible=eligible,
        response_schema_name=schema_name,
        response_schema_version=schema_version,
        response_sha256="1" * 64,
        payload_size_bytes=2048,
        intent_count=1,
        source_count=1,
        intended_http_method="GET",
        get_read_only_compatible=eligible,
        route_approval_granted=False,
        public_action_created=False,
        route_added=False,
        openapi_changed=False,
        trade_authorized=False,
        order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _build(schema: dict, eligibility: FinalDecisionReviewReleaseEligibilityV1):
    return build_final_decision_review_openapi_shadow(
        schema,
        eligibility,
        expected_app_version="3.9.1",
        approved_hosts=frozenset({HOST}),
        validated_at=NOW,
    )


def test_get_candidate_passes_shadow_without_mutating_production_schema() -> None:
    schema = _openapi()
    original = deepcopy(schema)
    result = _build(schema, _eligibility())

    assert result.status is FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
    assert result.shadow_valid is True
    assert result.blockers == ()
    assert result.current_action_count == 2
    assert result.shadow_action_count == 3
    assert result.candidate_action_present is True
    assert result.existing_actions_unchanged is True
    assert result.response_schema_match is True
    assert result.shadow_manifest is not None
    candidate_action = next(
        action
        for action in result.shadow_manifest.actions
        if action.operation_id == "getFinalDecisionReview"
    )
    assert candidate_action.path == "/decision/final-review"
    assert candidate_action.method == "get"
    assert candidate_action.public is False
    assert candidate_action.authentication_required is True
    assert schema == original
    assert result.production_schema_mutated is False
    assert result.route_added is False
    assert result.openapi_changed is False
    assert result.public_action_created is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_ineligible_release_blocks_candidate_before_shadow_manifest() -> None:
    result = _build(_openapi(), _eligibility(eligible=False))

    assert result.status is FinalDecisionReviewActionCandidateStatus.SHADOW_BLOCKED
    assert result.shadow_valid is False
    assert result.shadow_manifest is None
    assert (
        FinalDecisionReviewActionCandidateBlocker.RELEASE_NOT_ELIGIBLE
        in result.blockers
    )


def test_existing_candidate_path_is_blocked() -> None:
    schema = _openapi()
    schema["paths"]["/decision/final-review"] = {
        "get": {
            "operationId": "existingFinalReview",
            "security": [{"ApiKeyAuth": []}],
            "responses": {"200": {"description": "OK"}},
        }
    }
    result = _build(schema, _eligibility())

    assert FinalDecisionReviewActionCandidateBlocker.PATH_ALREADY_EXISTS in result.blockers
    assert result.shadow_manifest is None


def test_existing_operation_id_is_blocked() -> None:
    schema = _openapi()
    schema["paths"]["/other-review"] = {
        "get": {
            "operationId": "getFinalDecisionReview",
            "security": [{"ApiKeyAuth": []}],
            "responses": {"200": {"description": "OK"}},
        }
    }
    result = _build(schema, _eligibility())

    assert (
        FinalDecisionReviewActionCandidateBlocker.OPERATION_ID_ALREADY_EXISTS
        in result.blockers
    )


def test_response_contract_substitution_is_blocked() -> None:
    result = _build(
        _openapi(),
        _eligibility(schema_version="2.0"),
    )

    assert result.response_schema_match is False
    assert (
        FinalDecisionReviewActionCandidateBlocker.RESPONSE_SCHEMA_MISMATCH
        in result.blockers
    )


def test_current_non_get_openapi_is_rejected_by_existing_release_guard() -> None:
    schema = _openapi()
    schema["paths"]["/unsafe"] = {
        "post": {
            "operationId": "unsafeMutation",
            "security": [{"ApiKeyAuth": []}],
            "responses": {"200": {"description": "unsafe"}},
        }
    }

    with pytest.raises(ReadOnlyReleaseError, match="NON_GET_ACTION_EXPOSED"):
        _build(schema, _eligibility())


def test_candidate_hashes_are_deterministic() -> None:
    first = _build(_openapi(), _eligibility())
    second = _build(_openapi(), _eligibility())

    assert first.candidate.response_schema_sha256 == second.candidate.response_schema_sha256
    assert (
        first.candidate.release_eligibility_sha256
        == second.candidate.release_eligibility_sha256
    )


def test_shadow_result_tampering_is_rejected() -> None:
    result = _build(_openapi(), _eligibility())
    payload = result.model_dump(mode="python")
    payload["shadow_valid"] = False

    with pytest.raises(ValidationError):
        FinalDecisionReviewOpenApiShadowV1.model_validate(payload)


def test_naive_shadow_timestamp_is_rejected() -> None:
    with pytest.raises(
        FinalDecisionReviewOpenApiShadowError,
        match="FINAL_DECISION_REVIEW_OPENAPI_SHADOW_TIMESTAMP_MUST_BE_AWARE",
    ):
        build_final_decision_review_openapi_shadow(
            _openapi(),
            _eligibility(),
            expected_app_version="3.9.1",
            approved_hosts=frozenset({HOST}),
            validated_at=NOW.replace(tzinfo=None),
        )
