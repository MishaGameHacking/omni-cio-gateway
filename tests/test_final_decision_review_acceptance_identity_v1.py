from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from omni_cio.contracts.v1.final_decision_review_acceptance import (
    FinalDecisionReviewAcceptanceCase,
    FinalDecisionReviewAcceptanceEvidenceSource,
    FinalDecisionReviewAcceptanceEvidenceStatus,
)
from omni_cio.release.final_decision_review_acceptance_v1 import (
    FinalDecisionReviewAcceptanceError,
    collect_final_decision_review_acceptance_evidence,
    record_final_decision_review_acceptance_evidence,
)


NOW = datetime(2026, 7, 30, 5, 45, tzinfo=timezone.utc)
EXPECTED_COMMIT = "a" * 40
BASE_URL = "https://omni-cio-gateway.onrender.com"


def test_case_rejects_wrong_evidence_source() -> None:
    with pytest.raises(
        FinalDecisionReviewAcceptanceError,
        match="FINAL_DECISION_REVIEW_ACCEPTANCE_SOURCE_MISMATCH",
    ):
        record_final_decision_review_acceptance_evidence(
            case=FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT,
            status=FinalDecisionReviewAcceptanceEvidenceStatus.PASSED,
            observed_at=NOW,
            source=FinalDecisionReviewAcceptanceEvidenceSource.RENDER,
            reference="evidence:health:v1",
            summary="Health contract observation",
        )


def test_passed_render_evidence_must_match_expected_commit() -> None:
    row = record_final_decision_review_acceptance_evidence(
        case=FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT,
        status=FinalDecisionReviewAcceptanceEvidenceStatus.PASSED,
        observed_at=NOW,
        source=FinalDecisionReviewAcceptanceEvidenceSource.RENDER,
        reference="b" * 40,
        summary="Render source commit observation",
    )

    with pytest.raises(
        FinalDecisionReviewAcceptanceError,
        match="FINAL_DECISION_REVIEW_ACCEPTANCE_COMMIT_MISMATCH",
    ):
        collect_final_decision_review_acceptance_evidence(
            expected_commit_sha=EXPECTED_COMMIT,
            expected_app_version="3.10.0",
            base_url=BASE_URL,
            evidence=(row,),
            collected_at=NOW + timedelta(minutes=1),
        )
