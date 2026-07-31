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
SafeErrorCode = Annotated[
    str,
    Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$"),
]


class AcraRatingActionsAlertKind(StrEnum):
    SOURCE_UNAVAILABLE = "source_unavailable"
    CACHE_UNAVAILABLE = "cache_unavailable"
    STALE_RECORDS_EXPOSED = "stale_records_exposed"
    REFRESH_FAILED_USING_FRESH_CACHE = "refresh_failed_using_fresh_cache"


class AcraRatingActionsAlertDisposition(StrEnum):
    IGNORED = "ignored"
    PENDING = "pending"
    FIRED = "fired"
    SUPPRESSED_COOLDOWN = "suppressed_cooldown"
    RECOVERED = "recovered"


class AcraRatingActionsAlertPolicyV1(ContractModel):
    scope: Literal["global_acra_rating_actions_feed"] = (
        "global_acra_rating_actions_feed"
    )
    source_unavailable_threshold: PositiveCount = 3
    cache_unavailable_threshold: PositiveCount = 2
    stale_records_threshold: PositiveCount = 2
    refresh_failure_threshold: PositiveCount = 3
    cooldown_seconds: NonNegativeSeconds = 900
    state_retention_seconds: Annotated[int, Field(ge=60, le=604_800)] = 86_400
    capacity: StateCapacity = 4
    issuer_identity_present: Literal[False] = False
    rating_thresholds_present: Literal[False] = False
    financial_thresholds_present: Literal[False] = False
    external_notifications_enabled: Literal[False] = False
    trading_methods: Literal[False] = False

    def threshold_for(self, kind: AcraRatingActionsAlertKind) -> int:
        if kind is AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE:
            return self.source_unavailable_threshold
        if kind is AcraRatingActionsAlertKind.CACHE_UNAVAILABLE:
            return self.cache_unavailable_threshold
        if kind is AcraRatingActionsAlertKind.STALE_RECORDS_EXPOSED:
            return self.stale_records_threshold
        return self.refresh_failure_threshold


class AcraRatingActionsAlertEvaluationV1(ContractModel):
    evaluated_at: datetime
    source_event_name: Annotated[str, Field(min_length=3, max_length=128)]
    scope: Literal["global_acra_rating_actions_feed"] = (
        "global_acra_rating_actions_feed"
    )
    disposition: AcraRatingActionsAlertDisposition
    kind: AcraRatingActionsAlertKind | None = None
    severity: ObservabilitySeverity | None = None
    consecutive_occurrences: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    threshold: Annotated[int, Field(ge=0, le=100)] = 0
    cooldown_remaining_seconds: NonNegativeSeconds = 0
    error_code: SafeErrorCode | None = None
    contains_sensitive_payload: Literal[False] = False
    issuer_identity_present: Literal[False] = False
    rating_values_present: Literal[False] = False
    rating_thresholds_present: Literal[False] = False
    financial_thresholds_present: Literal[False] = False
    external_notification_sent: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ACRA alert evaluation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evaluation(self) -> AcraRatingActionsAlertEvaluationV1:
        actionable = self.disposition is not AcraRatingActionsAlertDisposition.IGNORED
        if actionable and (self.kind is None or self.severity is None):
            raise ValueError("actionable ACRA alert requires kind and severity")
        if not actionable:
            if self.kind is not None or self.severity is not None:
                raise ValueError("ignored ACRA alert cannot carry alert identity")
            if self.consecutive_occurrences != 0 or self.threshold != 0:
                raise ValueError("ignored ACRA alert cannot carry counters")
        active = self.disposition in (
            AcraRatingActionsAlertDisposition.PENDING,
            AcraRatingActionsAlertDisposition.FIRED,
            AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN,
        )
        if active and (self.threshold < 1 or self.consecutive_occurrences < 1):
            raise ValueError("active ACRA alert requires positive counters")
        if (
            self.disposition is AcraRatingActionsAlertDisposition.PENDING
            and self.consecutive_occurrences >= self.threshold
        ):
            raise ValueError("pending ACRA alert must remain below threshold")
        if (
            self.disposition
            in (
                AcraRatingActionsAlertDisposition.FIRED,
                AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN,
            )
            and self.consecutive_occurrences < self.threshold
        ):
            raise ValueError("fired or suppressed ACRA alert must meet threshold")
        if self.disposition is AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN:
            if self.cooldown_remaining_seconds < 1:
                raise ValueError("ACRA cooldown suppression requires remaining time")
        elif self.cooldown_remaining_seconds != 0:
            raise ValueError("only ACRA cooldown suppression may carry remaining time")
        if (
            self.disposition
            in (
                AcraRatingActionsAlertDisposition.FIRED,
                AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN,
            )
            and self.error_code is None
        ):
            raise ValueError("fired or suppressed ACRA alert requires safe error code")
        return self
