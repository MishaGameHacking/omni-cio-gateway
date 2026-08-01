from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.observability import ObservabilitySeverity


PositiveCount = Annotated[int, Field(ge=1, le=100)]
NonNegativeSeconds = Annotated[int, Field(ge=0, le=604_800)]
StateCapacity = Annotated[int, Field(ge=4, le=4)]
SafeErrorCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]
OpaqueEvidenceIdentifier = Annotated[
    str,
    Field(pattern=r"^expert-ra-evidence:[a-p]{64}$"),
]
ExpertRaSourceEventName = Literal[
    "market.expert_ra_rating_actions.source",
    "market.expert_ra_rating_actions.cache",
]


class ExpertRaRatingActionsAlertKind(StrEnum):
    SOURCE_UNAVAILABLE = "source_unavailable"
    CACHE_UNAVAILABLE = "cache_unavailable"
    STALE_RECORDS_EXPOSED = "stale_records_exposed"
    REFRESH_FAILED_USING_FRESH_CACHE = "refresh_failed_using_fresh_cache"


class ExpertRaRatingActionsAlertDisposition(StrEnum):
    IGNORED = "ignored"
    PENDING = "pending"
    FIRED = "fired"
    SUPPRESSED_COOLDOWN = "suppressed_cooldown"
    RECOVERED = "recovered"


class ExpertRaRatingActionsAlertPolicyV1(ContractModel):
    scope: Literal["global_expert_ra_rating_actions_feed"] = (
        "global_expert_ra_rating_actions_feed"
    )
    source_unavailable_threshold: PositiveCount = 3
    cache_unavailable_threshold: PositiveCount = 2
    stale_records_threshold: PositiveCount = 2
    refresh_failure_threshold: PositiveCount = 3
    cooldown_seconds: NonNegativeSeconds = 900
    state_retention_seconds: Annotated[int, Field(ge=60, le=604_800)] = 86_400
    capacity: StateCapacity = 4
    issuer_identity_present: Literal[False] = False
    rating_values_present: Literal[False] = False
    action_identity_present: Literal[False] = False
    rating_thresholds_present: Literal[False] = False
    financial_thresholds_present: Literal[False] = False
    external_notifications_enabled: Literal[False] = False
    broker_write_called: Literal[False] = False
    trading_methods: Literal[False] = False

    def threshold_for(self, kind: ExpertRaRatingActionsAlertKind) -> int:
        if kind is ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE:
            return self.source_unavailable_threshold
        if kind is ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE:
            return self.cache_unavailable_threshold
        if kind is ExpertRaRatingActionsAlertKind.STALE_RECORDS_EXPOSED:
            return self.stale_records_threshold
        return self.refresh_failure_threshold


class ExpertRaRatingActionsAlertEvaluationV1(ContractModel):
    evaluated_at: datetime
    source_event_name: Annotated[str, Field(min_length=3, max_length=128)]
    scope: Literal["global_expert_ra_rating_actions_feed"] = (
        "global_expert_ra_rating_actions_feed"
    )
    disposition: ExpertRaRatingActionsAlertDisposition
    kind: ExpertRaRatingActionsAlertKind | None = None
    severity: ObservabilitySeverity | None = None
    consecutive_occurrences: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    threshold: Annotated[int, Field(ge=0, le=100)] = 0
    cooldown_remaining_seconds: NonNegativeSeconds = 0
    error_code: SafeErrorCode | None = None
    contains_sensitive_payload: Literal[False] = False
    issuer_identity_present: Literal[False] = False
    rating_values_present: Literal[False] = False
    action_identity_present: Literal[False] = False
    rating_thresholds_present: Literal[False] = False
    financial_thresholds_present: Literal[False] = False
    external_notification_sent: Literal[False] = False
    broker_write_called: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Expert RA alert evaluation timestamp must be timezone-aware"
            )
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evaluation(self) -> ExpertRaRatingActionsAlertEvaluationV1:
        actionable = (
            self.disposition is not ExpertRaRatingActionsAlertDisposition.IGNORED
        )
        if actionable and (self.kind is None or self.severity is None):
            raise ValueError(
                "actionable Expert RA alert requires kind and severity"
            )
        if not actionable:
            if self.kind is not None or self.severity is not None:
                raise ValueError(
                    "ignored Expert RA alert cannot carry alert identity"
                )
            if self.consecutive_occurrences != 0 or self.threshold != 0:
                raise ValueError(
                    "ignored Expert RA alert cannot carry counters"
                )
            if self.error_code is not None:
                raise ValueError(
                    "ignored Expert RA alert cannot carry error code"
                )

        active = self.disposition in (
            ExpertRaRatingActionsAlertDisposition.PENDING,
            ExpertRaRatingActionsAlertDisposition.FIRED,
            ExpertRaRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN,
        )
        if active and (self.threshold < 1 or self.consecutive_occurrences < 1):
            raise ValueError(
                "active Expert RA alert requires positive counters"
            )
        if (
            self.disposition is ExpertRaRatingActionsAlertDisposition.PENDING
            and self.consecutive_occurrences >= self.threshold
        ):
            raise ValueError(
                "pending Expert RA alert must remain below threshold"
            )
        if (
            self.disposition
            in (
                ExpertRaRatingActionsAlertDisposition.FIRED,
                ExpertRaRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN,
            )
            and self.consecutive_occurrences < self.threshold
        ):
            raise ValueError(
                "fired or suppressed Expert RA alert must meet threshold"
            )
        if (
            self.disposition
            is ExpertRaRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN
        ):
            if self.cooldown_remaining_seconds < 1:
                raise ValueError(
                    "Expert RA cooldown suppression requires remaining time"
                )
        elif self.cooldown_remaining_seconds != 0:
            raise ValueError(
                "only Expert RA cooldown suppression may carry remaining time"
            )
        if (
            self.disposition
            in (
                ExpertRaRatingActionsAlertDisposition.FIRED,
                ExpertRaRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN,
            )
            and self.error_code is None
        ):
            raise ValueError(
                "fired or suppressed Expert RA alert requires safe error code"
            )
        if (
            self.disposition is ExpertRaRatingActionsAlertDisposition.RECOVERED
            and self.error_code is not None
        ):
            raise ValueError(
                "recovered Expert RA alert cannot retain an error code"
            )
        return self


class ExpertRaRatingActionsAlertEvidenceV1(ContractModel):
    evidence_id: OpaqueEvidenceIdentifier
    recorded_at: datetime
    source_event_name: ExpertRaSourceEventName
    scope: Literal["global_expert_ra_rating_actions_feed"] = (
        "global_expert_ra_rating_actions_feed"
    )
    disposition: ExpertRaRatingActionsAlertDisposition
    kind: ExpertRaRatingActionsAlertKind
    severity: ObservabilitySeverity
    consecutive_occurrences: Annotated[int, Field(ge=1, le=1_000_000)]
    threshold: PositiveCount
    error_code: SafeErrorCode | None = None
    contains_sensitive_payload: Literal[False] = False
    correlation_id_present: Literal[False] = False
    issuer_identity_present: Literal[False] = False
    rating_values_present: Literal[False] = False
    action_identity_present: Literal[False] = False
    release_identity_present: Literal[False] = False
    publication_date_present: Literal[False] = False
    financial_values_present: Literal[False] = False
    raw_source_payload_present: Literal[False] = False
    rating_thresholds_present: Literal[False] = False
    financial_thresholds_present: Literal[False] = False
    external_notification_sent: Literal[False] = False
    broker_write_called: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("recorded_at")
    @classmethod
    def require_aware_recorded_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Expert RA alert evidence timestamp must be timezone-aware"
            )
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evidence(self) -> ExpertRaRatingActionsAlertEvidenceV1:
        if self.disposition not in (
            ExpertRaRatingActionsAlertDisposition.FIRED,
            ExpertRaRatingActionsAlertDisposition.RECOVERED,
        ):
            raise ValueError(
                "Expert RA evidence stores only fired or recovered state"
            )
        expected_source = (
            "market.expert_ra_rating_actions.source"
            if self.kind is ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE
            else "market.expert_ra_rating_actions.cache"
        )
        if self.source_event_name != expected_source:
            raise ValueError(
                "Expert RA evidence source event and alert kind must agree"
            )
        expected_severity = (
            ObservabilitySeverity.ERROR
            if self.kind
            in (
                ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE,
                ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE,
            )
            else ObservabilitySeverity.WARNING
        )
        if self.severity is not expected_severity:
            raise ValueError(
                "Expert RA evidence severity and alert kind must agree"
            )
        if self.consecutive_occurrences < self.threshold:
            raise ValueError(
                "terminal Expert RA evidence must meet its threshold"
            )
        if (
            self.disposition is ExpertRaRatingActionsAlertDisposition.FIRED
            and self.error_code is None
        ):
            raise ValueError(
                "fired Expert RA evidence requires a safe error code"
            )
        if (
            self.disposition is ExpertRaRatingActionsAlertDisposition.RECOVERED
            and self.error_code is not None
        ):
            raise ValueError(
                "recovered Expert RA evidence cannot retain an error code"
            )
        return self
