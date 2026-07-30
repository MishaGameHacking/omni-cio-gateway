from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.observability import ObservabilitySeverity


PositiveCount = Annotated[int, Field(ge=1, le=100)]
NonNegativeSeconds = Annotated[int, Field(ge=0, le=604_800)]
StateCapacity = Annotated[int, Field(ge=4, le=64)]


class CbrKeyRateAlertKind(StrEnum):
    SOURCE_UNAVAILABLE = "source_unavailable"
    CACHE_UNAVAILABLE = "cache_unavailable"
    STALE_VALUE_EXPOSED = "stale_value_exposed"
    REFRESH_FAILED_USING_FRESH_CACHE = "refresh_failed_using_fresh_cache"


class CbrKeyRateAlertDisposition(StrEnum):
    IGNORED = "ignored"
    PENDING = "pending"
    FIRED = "fired"
    SUPPRESSED_COOLDOWN = "suppressed_cooldown"
    RECOVERED = "recovered"


class CbrKeyRateAlertPolicyV1(ContractModel):
    source_unavailable_threshold: PositiveCount = 3
    cache_unavailable_threshold: PositiveCount = 2
    stale_value_threshold: PositiveCount = 2
    refresh_failure_threshold: PositiveCount = 3
    cooldown_seconds: NonNegativeSeconds = 900
    state_retention_seconds: Annotated[int, Field(ge=60, le=604_800)] = 86_400
    capacity: StateCapacity = 4

    def threshold_for(self, kind: CbrKeyRateAlertKind) -> int:
        if kind is CbrKeyRateAlertKind.SOURCE_UNAVAILABLE:
            return self.source_unavailable_threshold
        if kind is CbrKeyRateAlertKind.CACHE_UNAVAILABLE:
            return self.cache_unavailable_threshold
        if kind is CbrKeyRateAlertKind.STALE_VALUE_EXPOSED:
            return self.stale_value_threshold
        return self.refresh_failure_threshold


class CbrKeyRateAlertEvaluationV1(ContractModel):
    evaluated_at: datetime
    source_event_name: Annotated[str, Field(min_length=3, max_length=128)]
    disposition: CbrKeyRateAlertDisposition
    kind: CbrKeyRateAlertKind | None = None
    severity: ObservabilitySeverity | None = None
    consecutive_occurrences: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    threshold: Annotated[int, Field(ge=0, le=100)] = 0
    cooldown_remaining_seconds: NonNegativeSeconds = 0
    error_code: Annotated[
        str | None,
        Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$"),
    ] = None
    contains_sensitive_payload: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("alert evaluation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evaluation(self) -> CbrKeyRateAlertEvaluationV1:
        actionable = self.disposition is not CbrKeyRateAlertDisposition.IGNORED
        if actionable and (self.kind is None or self.severity is None):
            raise ValueError("actionable alert evaluation requires kind and severity")
        if not actionable:
            if self.kind is not None or self.severity is not None:
                raise ValueError("ignored alert evaluation cannot carry alert identity")
            if self.consecutive_occurrences != 0 or self.threshold != 0:
                raise ValueError("ignored alert evaluation cannot carry counters")
        if self.disposition in (
            CbrKeyRateAlertDisposition.PENDING,
            CbrKeyRateAlertDisposition.FIRED,
            CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN,
        ):
            if self.threshold < 1 or self.consecutive_occurrences < 1:
                raise ValueError("active alert evaluation requires positive counters")
        if self.disposition is CbrKeyRateAlertDisposition.PENDING:
            if self.consecutive_occurrences >= self.threshold:
                raise ValueError("pending alert must remain below threshold")
        if self.disposition in (
            CbrKeyRateAlertDisposition.FIRED,
            CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN,
        ) and self.consecutive_occurrences < self.threshold:
            raise ValueError("fired or suppressed alert must meet threshold")
        if self.disposition is CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN:
            if self.cooldown_remaining_seconds < 1:
                raise ValueError("cooldown suppression requires remaining time")
        elif self.cooldown_remaining_seconds != 0:
            raise ValueError("only cooldown suppression may carry remaining time")
        if self.disposition in (
            CbrKeyRateAlertDisposition.FIRED,
            CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN,
        ) and self.error_code is None:
            raise ValueError("fired or suppressed alert requires safe error code")
        return self
