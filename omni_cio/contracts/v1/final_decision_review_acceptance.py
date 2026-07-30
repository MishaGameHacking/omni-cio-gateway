from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.observability import SafeCountMetricV1


CommitSha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
SemVer = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeReference = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/#-]{2,255}$"),
]
SafeSummary = Annotated[str, Field(min_length=1, max_length=512)]
ErrorCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]

_SENSITIVE_FRAGMENTS = (
    "authorization",
    "bearer ",
    "api_key",
    "apikey",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "tinvest_token",
    "account_id",
    "broker_account",
    "full_account",
    "portfolio_value",
    "positions",
    "order_id",
    "confirmation_id",
)


class FinalDecisionReviewAcceptanceEvidenceStatus(StrEnum):
    NOT_EXECUTED = "not_executed"
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class FinalDecisionReviewAcceptanceCase(StrEnum):
    RENDER_SOURCE_COMMIT = "render_source_commit"
    HEALTH_CONTRACT = "health_contract"
    PRIVATE_AUTH_NEGATIVE = "private_auth_negative"
    EXACT_ROUTE_POSITIVE = "exact_route_positive"
    GPT_SCHEMA_IMPORT = "gpt_schema_import"
    GPT_AUTHENTICATED_PREVIEW = "gpt_authenticated_preview"
    GPT_ACTION_LIST = "gpt_action_list"
    ROLLBACK_RESTORE = "rollback_restore"


class FinalDecisionReviewAcceptanceEvidenceSource(StrEnum):
    NONE = "none"
    RENDER = "render"
    GATEWAY = "gateway"
    GPT_EDITOR = "gpt_editor"
    ROLLBACK_RUNBOOK = "rollback_runbook"
    MANUAL_REVIEW = "manual_review"


class FinalDecisionReviewAcceptanceOverallStatus(StrEnum):
    NOT_EXECUTED = "not_executed"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"


class FinalDecisionReviewAcceptanceWarning(StrEnum):
    ACTUAL_DEPLOYMENT_EVIDENCE_REQUIRED = "actual_deployment_evidence_required"
    GPT_EDITOR_EVIDENCE_REQUIRED = "gpt_editor_evidence_required"
    ROLLBACK_EVIDENCE_REQUIRED = "rollback_evidence_required"
    CONTRACT_DOES_NOT_EXECUTE_ACCEPTANCE = "contract_does_not_execute_acceptance"
    NO_EXECUTION_AUTHORIZATION = "no_execution_authorization"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _evidence_payload(
    *,
    case: FinalDecisionReviewAcceptanceCase,
    status: FinalDecisionReviewAcceptanceEvidenceStatus,
    observed_at: datetime | None,
    source: FinalDecisionReviewAcceptanceEvidenceSource,
    reference: str | None,
    summary: str | None,
    error_code: str | None,
    metrics: tuple[SafeCountMetricV1, ...],
) -> dict[str, object]:
    return {
        "case": case.value,
        "status": status.value,
        "observed_at": (
            observed_at.astimezone(timezone.utc).isoformat()
            if observed_at is not None
            else None
        ),
        "source": source.value,
        "reference": reference,
        "summary": summary,
        "error_code": error_code,
        "metrics": [metric.model_dump(mode="json") for metric in metrics],
    }


def calculate_final_decision_review_acceptance_evidence_sha256(
    *,
    case: FinalDecisionReviewAcceptanceCase,
    status: FinalDecisionReviewAcceptanceEvidenceStatus,
    observed_at: datetime,
    source: FinalDecisionReviewAcceptanceEvidenceSource,
    reference: str,
    summary: str,
    error_code: str | None = None,
    metrics: tuple[SafeCountMetricV1, ...] = (),
) -> str:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("acceptance evidence timestamp must be timezone-aware")
    return _canonical_sha256(
        _evidence_payload(
            case=case,
            status=status,
            observed_at=observed_at,
            source=source,
            reference=reference,
            summary=summary,
            error_code=error_code,
            metrics=metrics,
        )
    )


class FinalDecisionReviewAcceptanceEvidenceV1(ContractModel):
    schema_name: Literal["final_decision_review_acceptance_evidence"] = (
        "final_decision_review_acceptance_evidence"
    )
    schema_version: Literal["1.0"] = "1.0"
    case: FinalDecisionReviewAcceptanceCase
    status: FinalDecisionReviewAcceptanceEvidenceStatus
    observed_at: datetime | None = None
    source: FinalDecisionReviewAcceptanceEvidenceSource = (
        FinalDecisionReviewAcceptanceEvidenceSource.NONE
    )
    reference: SafeReference | None = None
    summary: SafeSummary | None = None
    evidence_sha256: Sha256Digest | None = None
    error_code: ErrorCode | None = None
    metrics: tuple[SafeCountMetricV1, ...] = ()
    contains_sensitive_material: Literal[False] = False
    contains_account_context: Literal[False] = False
    deployment_change_performed: Literal[False] = False
    gpt_editor_change_performed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("acceptance evidence timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("reference", "summary")
    @classmethod
    def reject_sensitive_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.lower()
        if any(fragment in lowered for fragment in _SENSITIVE_FRAGMENTS):
            raise ValueError("acceptance evidence must not contain sensitive material")
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> FinalDecisionReviewAcceptanceEvidenceV1:
        metric_names = tuple(metric.name for metric in self.metrics)
        if len(set(metric_names)) != len(metric_names):
            raise ValueError("acceptance evidence metric names must be unique")

        if self.status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED:
            if (
                self.observed_at is not None
                or self.source is not FinalDecisionReviewAcceptanceEvidenceSource.NONE
                or self.reference is not None
                or self.summary is not None
                or self.evidence_sha256 is not None
                or self.error_code is not None
                or self.metrics
            ):
                raise ValueError("not-executed evidence cannot contain an observation")
            return self

        if self.observed_at is None:
            raise ValueError("executed acceptance evidence requires observed_at")
        if self.source is FinalDecisionReviewAcceptanceEvidenceSource.NONE:
            raise ValueError("executed acceptance evidence requires a source")
        if self.reference is None or self.summary is None or self.evidence_sha256 is None:
            raise ValueError("executed acceptance evidence requires proof fields")

        if self.status is FinalDecisionReviewAcceptanceEvidenceStatus.FAILED:
            if self.error_code is None:
                raise ValueError("failed acceptance evidence requires error_code")
        elif self.error_code is not None:
            raise ValueError("only failed acceptance evidence may contain error_code")

        if (
            self.status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_APPLICABLE
            and self.source
            is not FinalDecisionReviewAcceptanceEvidenceSource.MANUAL_REVIEW
        ):
            raise ValueError("not-applicable evidence requires manual review")

        expected_digest = _canonical_sha256(
            _evidence_payload(
                case=self.case,
                status=self.status,
                observed_at=self.observed_at,
                source=self.source,
                reference=self.reference,
                summary=self.summary,
                error_code=self.error_code,
                metrics=self.metrics,
            )
        )
        if self.evidence_sha256 != expected_digest:
            raise ValueError("acceptance evidence digest is inconsistent")
        return self


class FinalDecisionReviewAcceptanceDossierV1(ContractModel):
    schema_name: Literal["final_decision_review_acceptance_dossier"] = (
        "final_decision_review_acceptance_dossier"
    )
    schema_version: Literal["1.0"] = "1.0"
    collected_at: datetime
    expected_commit_sha: CommitSha
    expected_app_version: SemVer
    base_url: Annotated[str, Field(pattern=r"^https://[A-Za-z0-9.-]+$")]
    evidence: Annotated[
        tuple[FinalDecisionReviewAcceptanceEvidenceV1, ...],
        Field(min_length=1),
    ]
    overall_status: FinalDecisionReviewAcceptanceOverallStatus
    required_case_count: Annotated[int, Field(gt=0)]
    passed_count: Annotated[int, Field(ge=0)]
    failed_count: Annotated[int, Field(ge=0)]
    not_executed_count: Annotated[int, Field(ge=0)]
    not_applicable_count: Annotated[int, Field(ge=0)]
    executed_count: Annotated[int, Field(ge=0)]
    primary_failed_case: FinalDecisionReviewAcceptanceCase | None = None
    actual_deployment_verified: bool
    gpt_preview_verified: bool
    rollback_verified: bool
    all_executed_evidence_dated: bool
    acceptance_completed: bool
    warnings: tuple[FinalDecisionReviewAcceptanceWarning, ...]
    collector_performed_network_calls: Literal[False] = False
    collector_changed_deployment: Literal[False] = False
    collector_changed_gpt_editor: Literal[False] = False
    contains_sensitive_material: Literal[False] = False
    contains_account_context: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("collected_at")
    @classmethod
    def normalize_collected_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("acceptance dossier timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_dossier(self) -> FinalDecisionReviewAcceptanceDossierV1:
        cases = tuple(row.case for row in self.evidence)
        if len(set(cases)) != len(cases):
            raise ValueError("acceptance evidence cases must be unique")
        if set(cases) != set(FinalDecisionReviewAcceptanceCase):
            raise ValueError("acceptance evidence cases are incomplete")
        if self.required_case_count != len(FinalDecisionReviewAcceptanceCase):
            raise ValueError("required acceptance case count is inconsistent")

        passed = tuple(
            row
            for row in self.evidence
            if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
        )
        failed = tuple(
            row
            for row in self.evidence
            if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.FAILED
        )
        not_executed = tuple(
            row
            for row in self.evidence
            if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED
        )
        not_applicable = tuple(
            row
            for row in self.evidence
            if row.status is FinalDecisionReviewAcceptanceEvidenceStatus.NOT_APPLICABLE
        )
        executed_count = len(self.evidence) - len(not_executed)
        if (
            self.passed_count != len(passed)
            or self.failed_count != len(failed)
            or self.not_executed_count != len(not_executed)
            or self.not_applicable_count != len(not_applicable)
            or self.executed_count != executed_count
        ):
            raise ValueError("acceptance evidence counters do not reconcile")

        expected_primary = failed[0].case if failed else None
        if self.primary_failed_case is not expected_primary:
            raise ValueError("primary failed acceptance case is inconsistent")

        by_case = {row.case: row for row in self.evidence}
        dependency_order = (
            FinalDecisionReviewAcceptanceCase.RENDER_SOURCE_COMMIT,
            FinalDecisionReviewAcceptanceCase.HEALTH_CONTRACT,
            FinalDecisionReviewAcceptanceCase.PRIVATE_AUTH_NEGATIVE,
            FinalDecisionReviewAcceptanceCase.EXACT_ROUTE_POSITIVE,
            FinalDecisionReviewAcceptanceCase.GPT_SCHEMA_IMPORT,
            FinalDecisionReviewAcceptanceCase.GPT_AUTHENTICATED_PREVIEW,
            FinalDecisionReviewAcceptanceCase.GPT_ACTION_LIST,
        )
        for index, case in enumerate(dependency_order[1:], start=1):
            if (
                by_case[case].status
                is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
                and any(
                    by_case[prior].status
                    is not FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
                    for prior in dependency_order[:index]
                )
            ):
                raise ValueError("passed acceptance evidence violates dependency order")

        deployment_cases = dependency_order[:4]
        expected_deployment = all(
            by_case[case].status
            is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
            for case in deployment_cases
        )
        expected_gpt = all(
            by_case[case].status
            is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
            for case in dependency_order[4:]
        )
        expected_rollback = (
            by_case[FinalDecisionReviewAcceptanceCase.ROLLBACK_RESTORE].status
            is FinalDecisionReviewAcceptanceEvidenceStatus.PASSED
        )
        expected_dated = all(
            row.observed_at is not None
            for row in self.evidence
            if row.status
            is not FinalDecisionReviewAcceptanceEvidenceStatus.NOT_EXECUTED
        )
        expected_complete = len(passed) == len(self.evidence)
        expected_status = (
            FinalDecisionReviewAcceptanceOverallStatus.FAILED
            if failed
            else FinalDecisionReviewAcceptanceOverallStatus.PASSED
            if expected_complete
            else FinalDecisionReviewAcceptanceOverallStatus.NOT_EXECUTED
            if executed_count == 0
            else FinalDecisionReviewAcceptanceOverallStatus.IN_PROGRESS
        )
        if self.overall_status is not expected_status:
            raise ValueError("acceptance overall status is inconsistent")
        if self.actual_deployment_verified is not expected_deployment:
            raise ValueError("deployment verification mirror is inconsistent")
        if self.gpt_preview_verified is not expected_gpt:
            raise ValueError("GPT verification mirror is inconsistent")
        if self.rollback_verified is not expected_rollback:
            raise ValueError("rollback verification mirror is inconsistent")
        if self.all_executed_evidence_dated is not expected_dated:
            raise ValueError("acceptance evidence date mirror is inconsistent")
        if self.acceptance_completed is not expected_complete:
            raise ValueError("acceptance completion mirror is inconsistent")
        if set(self.warnings) != set(FinalDecisionReviewAcceptanceWarning):
            raise ValueError("acceptance dossier warnings are incomplete")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("acceptance dossier warnings must be unique")
        return self
