from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from omni_cio.contracts.v1.final_decision_review_acceptance import (
    FinalDecisionReviewAcceptanceCase,
    FinalDecisionReviewAcceptanceDossierV1,
    FinalDecisionReviewAcceptanceEvidenceSource,
    FinalDecisionReviewAcceptanceEvidenceStatus,
    FinalDecisionReviewAcceptanceEvidenceV1,
    FinalDecisionReviewAcceptanceOverallStatus,
    FinalDecisionReviewAcceptanceWarning,
    calculate_final_decision_review_acceptance_evidence_sha256,
)
from omni_cio.contracts.v1.observability import SafeCountMetricV1


class FinalDecisionReviewAcceptanceError(ValueError):
    """Production acceptance evidence cannot be recorded safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_base_url(base_url: str) -> str:
    candidate = base_url.strip().rstrip("/")
    parsed = urlparse(candidate)
    try:
        port = parsed.port
    except ValueError as exc:
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_BASE_URL_INVALID"
        ) from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_BASE_URL_INVALID"
        )
    return f"https://{parsed.hostname}"


def not_executed_final_decision_review_acceptance_evidence(
    case: FinalDecisionReviewAcceptanceCase,
) -> FinalDecisionReviewAcceptanceEvidenceV1:
    return FinalDecisionReviewAcceptanceEvidenceV1(
        case=case,
        status=FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED,
    )


def record_final_decision_review_acceptance_evidence(
    *,
    case: FinalDecisionReviewAcceptanceCase,
    status: FinalDecisionReviewAcceptanceEvidenceStatus,
    observed_at: datetime | None = None,
    source: FinalDecisionReviewAcceptanceEvidenceSource = (
        FinalDecisionReviewAcceptanceEvidenceSource.NONE
    ),
    reference: str | None = None,
    summary: str | None = None,
    error_code: str | None = None,
    metrics: tuple[SafeCountMetricV1, ...] = (),
) -> FinalDecisionReviewAcceptanceEvidenceV1:
    """Create one immutable evidence row without performing the acceptance action."""

    if status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED:
        if any(
            value is not None
            for value in (observed_at, reference, summary, error_code)
        ) or source is not FinalDecisionReviewAcceptanceEvidenceSource.NONE or metrics:
            raise FinalDecisionReviewAcceptanceError(
                "FINAL_DECISION_REVIEW_ACCEPTANCE_NOT_EXECUTED_HAS_OBSERVATION"
            )
        return not_executed_final_decision_review_acceptance_evidence(case)

    timestamp = _aware_utc(observed_at)
    if source is FinalDecisionReviewAcceptanceEvidenceSource.NONE:
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_SOURCE_REQUIRED"
        )
    if reference is None or summary is None:
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_PROOF_REQUIRED"
        )
    if (
        status is FinalDecisionReviewAcceptanceEvidenceStatus.FAILED
        and error_code is None
    ):
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_ERROR_CODE_REQUIRED"
        )
    if (
        status is not FinalDecisionReviewAcceptanceEvidenceStatus.FAILED
        and error_code is not None
    ):
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_ERROR_CODE_FORBIDDEN"
        )
    if (
        status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_APPLICABLE
        and source is not FinalDecisionReviewAcceptanceEvidenceSource.MANUAL_REVIEW
    ):
        raise FinalDecisionReviewAcceptanceError(
            "FINAL_DECISION_REVIEW_ACCEPTANCE_MANUAL_REVIEW_REQUIRED"
        )

    digest = calculate_final_decision_review_acceptance_evidence_sha256(
        case=case,
        status=status,
        observed_at=timestamp,
        source=source,
        reference=reference,
        summary=summary,
        error_code=error_code,
        metrics=metrics,
    )
    return FinalDecisionReviewAcceptanceEvidenceV1(
        case=case,
        status=status,
        observed_at=timestamp,
        source=source,
        reference=reference,
        summary=summary,
        evidence_sha256=digest,
        error_code=error_code,
        metrics=metrics,
    )


def collect_final_decision_review_acceptance_evidence(
    *,
    expected_commit_sha: str,
    expected_app_version: str,
    base_url: str,
    evidence: tuple[FinalDecisionReviewAcceptanceEvidenceV1, ...] = (),
    collected_at: datetime | None = None,
) -> FinalDecisionReviewAcceptanceDossierV1:
    """Build a complete evidence dossier without network or configuration changes."""

    timestamp = _aware_utc(collected_at)
    canonical_base_url = _canonical_base_url(base_url)
    by_case: dict[
        FinalDecisionReviewAcceptanceCase,
        FinalDecisionReviewAcceptanceEvidenceV1,
    ] = {}
    for row in evidence:
        if row.case in by_case:
            raise FinalDecisionReviewAcceptanceError(
                "FINAL_DECISION_REVIEW_ACCEPTANCE_DUPLICATE_CASE"
            )
        if row.observed_at is not None and row.observed_at > timestamp:
            raise FinalDecisionReviewAcceptanceError(
                "FINAL_DECISION_REVIEW_ACCEPTANCE_FUTURE_EVIDENCE"
            )
        by_case[row.case] = row

    ordered = tuple(
        by_case.get(
            case,
            not_executed_final_decision_review_acceptance_evidence(case),
        )
        for case in FinalDecisionReviewAcceptanceCase
    )
    passed = tuple(
        row
        for row in ordered
        if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
    )
    failed = tuple(
        row
        for row in ordered
        if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.FAILED
    )
    not_executed = tuple(
        row
        for row in ordered
        if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED
    )
    not_applicable = tuple(
        row
        for row in ordered
        if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_APPLICABLE
    )
    executed_count = len(ordered) - len(not_executed)
    completed = len(passed) == len(ordered)
    overall_status = (
        FinalDecisionReviewAcceptanceOverallStatus.FAILED
        if failed
        else FinalDecisionReviewAcceptanceOverallStatus.PASSED
        if completed
        else FinalDecisionReviewAcceptanceOverallStatus.NOT_EXECUTED
        if executed_count == 0
        else FinalDecisionReviewAcceptanceOverallStatus.IN_PROGRESS
    )
    status_by_case = {row.case: row.status for row in ordered}
    deployment_cases = (
        FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT,
        FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT,
        FinalDecisionReviewAcceptanceCase.PRIVATE_AUTH_NEGATIVE,
        FinalDecisionReviewAcceptanceCase.EXACT_ROUTE_POSITIVE,
    )
    gpt_cases = (
        FinalDecisionReviewAcceptanceCase.GPT_SCHEMA_IMPORT,
        FinalDecisionReviewAcceptanceCase.GPT_AUTHENTICATED_PREVIEW,
        FinalDecisionReviewAcceptanceCase.GPT_ACTION_LIST,
    )

    return FinalDecisionReviewAcceptanceDossierV1(
        collected_at=timestamp,
        expected_commit_sha=expected_commit_sha,
        expected_app_version=expected_app_version,
        base_url=canonical_base_url,
        evidence=ordered,
        overall_status=overall_status,
        required_case_count=len(FinalDecisionReviewAcceptanceCase),
        passed_count=len(passed),
        failed_count=len(failed),
        not_executed_count=len(not_executed),
        not_applicable_count=len(not_applicable),
        executed_count=executed_count,
        primary_failed_case=failed[0].case if failed else None,
        actual_deployment_verified=all(
            status_by_case[case]
            is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
            for case in deployment_cases
        ),
        gpt_preview_verified=all(
            status_by_case[case]
            is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
            for case in gpt_cases
        ),
        rollback_verified=(
            status_by_case[FinalDecisionReviewAcceptanceCase.ROLLBACK_RESTORE]
            is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
        ),
        all_executed_evidence_dated=all(
            row.observed_at is not None
            for row in ordered
            if row.status
            is not FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED
        ),
        acceptance_completed=completed,
        warnings=tuple(FinalDecisionReviewAcceptanceWarning),
    )
