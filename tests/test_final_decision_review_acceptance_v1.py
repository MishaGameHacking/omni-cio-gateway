from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.final_decision_review_acceptance import (
    FinalDecisionReviewAcceptanceCase,
    FinalDecisionReviewAcceptanceDossierV1,
    FinalDecisionReviewAcceptanceEvidenceSource,
    FinalDecisionReviewAcceptanceEvidenceStatus,
    FinalDecisionReviewAcceptanceEvidenceV1,
    FinalDecisionReviewAcceptanceOverallStatus,
)
from omni_cio.contracts.v1.observability import SafeCountMetricV1
from omni_cio.release.final_decision_review_acceptance_v1 import (
    FinalDecisionReviewAcceptanceError,
    collect_final_decision_review_acceptance_evidence,
    record_final_decision_review_acceptance_evidence,
)


NOW = datetime(2026, 7, 30, 5, 30, tzinfo=timezone.utc)
COMMIT_SHA = "ae4ca2429b1c1d6e7a2991daa9aab211d51a8048"
APP_VERSION = "3.10.0"
BASE_URL = "https://omni-cio-gateway.onrender.com"

_SOURCE_BY_CASE = {
    FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT: (
        FinalDecisionReviewAcceptanceEvidenceSource.RENDER
    ),
    FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT: (
        FinalDecisionReviewAcceptanceEvidenceSource.GATEWAY
    ),
    FinalDecisionReviewAcceptanceCase.PRIVATE_AUTH_NEGATIVE: (
        FinalDecisionReviewAcceptanceEvidenceSource.GATEWAY
    ),
    FinalDecisionReviewAcceptanceCase.EXACT_ROUTE_POSITIVE: (
        FinalDecisionReviewAcceptanceEvidenceSource.GATEWAY
    ),
    FinalDecisionReviewAcceptanceCase.GPT_SCHEMA_IMPORT: (
        FinalDecisionReviewAcceptanceEvidenceSource.GPT_EDITOR
    ),
    FinalDecisionReviewAcceptanceCase.GPT_AUTHENTICATED_PREVIEW: (
        FinalDecisionReviewAcceptanceEvidenceSource.GPT_EDITOR
    ),
    FinalDecisionReviewAcceptanceCase.GPT_ACTION_LIST: (
        FinalDecisionReviewAcceptanceEvidenceSource.GPT_EDITOR
    ),
    FinalDecisionReviewAcceptanceCase.ROLLBACK_RESTORE: (
        FinalDecisionReviewAcceptanceEvidenceSource.ROLLBACK_RUNBOOK
    ),
}


def _reference(case: FinalDecisionReviewAcceptanceCase) -> str:
    if case is FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT:
        return COMMIT_SHA
    return f"evidence:{case.value}:v1"


def _record(
    case: FinalDecisionReviewAcceptanceCase,
    *,
    status: FinalDecisionReviewAcceptanceEvidenceStatus = (
        FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
    ),
    error_code: str | None = None,
):
    source = _SOURCE_BY_CASE[case]
    if status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_APPLICABLE:
        source = FinalDecisionReviewAcceptanceEvidenceSource.MANUAL_REVIEW
    return record_final_decision_review_acceptance_evidence(
        case=case,
        status=status,
        observed_at=NOW,
        source=source,
        reference=_reference(case),
        summary=f"Acceptance observation for {case.value}",
        error_code=error_code,
        metrics=(SafeCountMetricV1(name="checks.passed", value=1),),
    )


def _collect(*rows: FinalDecisionReviewAcceptanceEvidenceV1):
    return collect_final_decision_review_acceptance_evidence(
        expected_commit_sha=COMMIT_SHA,
        expected_app_version=APP_VERSION,
        base_url=BASE_URL,
        evidence=tuple(rows),
        collected_at=NOW + timedelta(minutes=1),
    )


def test_empty_collector_is_explicitly_not_executed() -> None:
    result = _collect()

    assert result.overall_status is FinalDecisionReviewAcceptanceOverallStatus.NOT_EXECUTED
    assert result.required_case_count == 8
    assert result.not_executed_count == 8
    assert result.executed_count == 0
    assert result.passed_count == 0
    assert result.failed_count == 0
    assert result.acceptance_completed is False
    assert result.actual_deployment_verified is False
    assert result.gpt_preview_verified is False
    assert result.rollback_verified is False
    assert all(
        row.status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED
        for row in result.evidence
    )
    assert result.collector_performed_network_calls is False
    assert result.collector_changed_deployment is False
    assert result.collector_changed_gpt_editor is False
    assert result.trading_methods is False


def test_passed_evidence_is_dated_digest_bound_and_immutable() -> None:
    row = _record(FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT)

    assert row.status is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
    assert row.observed_at == NOW
    assert row.reference == COMMIT_SHA
    assert row.evidence_sha256 is not None
    assert len(row.evidence_sha256) == 64
    assert row.contains_sensitive_material is False
    assert row.contains_account_context is False
    assert row.deployment_change_performed is False
    assert row.gpt_editor_change_performed is False
    assert row.trade_authorized is False
    assert row.trading_methods is False

    with pytest.raises(ValidationError):
        row.status = FinalDecisionReviewAcceptanceEvidenceStatus.FAILED  # type: ignore[misc]


def test_failed_evidence_requires_error_code() -> None:
    with pytest.raises(
        FinalDecisionReviewAcceptanceError,
        match="FINAL_DECISION_REVIEW_ACCEPTANCE_ERROR_CODE_REQUIRED",
    ):
        _record(
            FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT,
            status=FinalDecisionReviewAcceptanceEvidenceStatus.FAILED,
        )

    failed = _record(
        FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT,
        status=FinalDecisionReviewAcceptanceEvidenceStatus.FAILED,
        error_code="HEALTH_VERSION_MISMATCH",
    )
    assert failed.error_code == "HEALTH_VERSION_MISMATCH"


def test_evidence_digest_tampering_is_rejected() -> None:
    row = _record(FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT)
    payload = row.model_dump(mode="python")
    payload["evidence_sha256"] = "f" * 64

    with pytest.raises(ValidationError, match="digest is inconsistent"):
        FinalDecisionReviewAcceptanceEvidenceV1.model_validate(payload)


def test_sensitive_evidence_text_is_rejected() -> None:
    with pytest.raises(ValidationError, match="sensitive material"):
        record_final_decision_review_acceptance_evidence(
            case=FinalDecisionReviewAcceptanceCase.PRIVATE_AUTH_NEGATIVE,
            status=FinalDecisionReviewAcceptanceEvidenceStatus.PASSED,
            observed_at=NOW,
            source=FinalDecisionReviewAcceptanceEvidenceSource.GATEWAY,
            reference="evidence:auth:v1",
            summary="Bearer value was inspected",
        )


def test_complete_evidence_set_passes_only_after_all_eight_cases() -> None:
    rows = tuple(_record(case) for case in FinalDecisionReviewAcceptanceCase)
    result = _collect(*rows)

    assert result.overall_status is FinalDecisionReviewAcceptanceOverallStatus.PASSED
    assert result.passed_count == 8
    assert result.executed_count == 8
    assert result.not_executed_count == 0
    assert result.not_applicable_count == 0
    assert result.actual_deployment_verified is True
    assert result.gpt_preview_verified is True
    assert result.rollback_verified is True
    assert result.all_executed_evidence_dated is True
    assert result.acceptance_completed is True
    assert result.primary_failed_case is None
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_partial_deployment_evidence_remains_in_progress() -> None:
    deployment_cases = tuple(FinalDecisionReviewAcceptanceCase)[:4]
    result = _collect(*(_record(case) for case in deployment_cases))

    assert result.overall_status is FinalDecisionReviewAcceptanceOverallStatus.IN_PROGRESS
    assert result.passed_count == 4
    assert result.not_executed_count == 4
    assert result.actual_deployment_verified is True
    assert result.gpt_preview_verified is False
    assert result.rollback_verified is False
    assert result.acceptance_completed is False


def test_failure_dominates_and_identifies_primary_case() -> None:
    render = _record(FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT)
    health = _record(
        FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT,
        status=FinalDecisionReviewAcceptanceEvidenceStatus.FAILED,
        error_code="HEALTH_VERSION_MISMATCH",
    )
    result = _collect(render, health)

    assert result.overall_status is FinalDecisionReviewAcceptanceOverallStatus.FAILED
    assert result.failed_count == 1
    assert result.primary_failed_case is FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT
    assert result.acceptance_completed is False


def test_passed_downstream_case_without_prerequisites_is_rejected() -> None:
    preview = _record(
        FinalDecisionReviewAcceptanceCase.GPT_AUTHENTICATED_PREVIEW,
    )

    with pytest.raises(ValidationError, match="violates dependency order"):
        _collect(preview)


def test_not_applicable_is_dated_but_never_completes_acceptance() -> None:
    rows = [
        _record(case)
        for case in FinalDecisionReviewAcceptanceCase
        if case is not FinalDecisionReviewAcceptanceCase.ROLLBACK_RESTORE
    ]
    rows.append(
        _record(
            FinalDecisionReviewAcceptanceCase.ROLLBACK_RESTORE,
            status=FinalDecisionReviewAcceptanceEvidenceStatus.NOT_APPLICABLE,
        )
    )
    result = _collect(*rows)

    assert result.overall_status is FinalDecisionReviewAcceptanceOverallStatus.IN_PROGRESS
    assert result.not_applicable_count == 1
    assert result.all_executed_evidence_dated is True
    assert result.acceptance_completed is False
    assert result.rollback_verified is False


def test_duplicate_and_future_evidence_fail_closed() -> None:
    row = _record(FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT)
    with pytest.raises(
        FinalDecisionReviewAcceptanceError,
        match="FINAL_DECISION_REVIEW_ACCEPTANCE_DUPLICATE_CASE",
    ):
        _collect(row, row)

    future = record_final_decision_review_acceptance_evidence(
        case=FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT,
        status=FinalDecisionReviewAcceptanceEvidenceStatus.PASSED,
        observed_at=NOW + timedelta(days=1),
        source=FinalDecisionReviewAcceptanceEvidenceSource.RENDER,
        reference=COMMIT_SHA,
        summary="Future-dated source commit observation",
    )
    with pytest.raises(
        FinalDecisionReviewAcceptanceError,
        match="FINAL_DECISION_REVIEW_ACCEPTANCE_FUTURE_EVIDENCE",
    ):
        _collect(future)


def test_naive_timestamps_and_unsafe_base_url_are_rejected() -> None:
    with pytest.raises(
        FinalDecisionReviewAcceptanceError,
        match="FINAL_DECISION_REVIEW_ACCEPTANCE_TIMESTAMP_MUST_BE_AWARE",
    ):
        collect_final_decision_review_acceptance_evidence(
            expected_commit_sha=COMMIT_SHA,
            expected_app_version=APP_VERSION,
            base_url=BASE_URL,
            collected_at=NOW.replace(tzinfo=None),
        )

    with pytest.raises(
        FinalDecisionReviewAcceptanceError,
        match="FINAL_DECISION_REVIEW_ACCEPTANCE_BASE_URL_INVALID",
    ):
        collect_final_decision_review_acceptance_evidence(
            expected_commit_sha=COMMIT_SHA,
            expected_app_version=APP_VERSION,
            base_url="https://omni-cio-gateway.onrender.com/health",
            collected_at=NOW,
        )


def test_dossier_mirror_tampering_is_rejected() -> None:
    result = _collect()
    payload = result.model_dump(mode="python")
    payload["acceptance_completed"] = True

    with pytest.raises(ValidationError, match="completion mirror is inconsistent"):
        FinalDecisionReviewAcceptanceDossierV1.model_validate(payload)


def test_acceptance_collector_has_no_network_or_broker_imports() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_acceptance_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "http.client",
        "urllib.request",
        "requests",
        "tinkoff.invest",
        "t_tech.invest",
        "import grpc",
    )
    assert all(marker not in source for marker in forbidden)
