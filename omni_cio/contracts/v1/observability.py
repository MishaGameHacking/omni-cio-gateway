from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractModel,
    DataQuality,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
TraceIdentifier = Annotated[
    str,
    Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{7,127}$"),
]


class ObservabilitySeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ObservabilityOutcome(StrEnum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    REJECTED = "rejected"
    FAILURE = "failure"


class ExternalCallStatus(StrEnum):
    NOT_CALLED = "not_called"
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


class CircuitBreakerState(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FreshnessTelemetry(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ExternalCallTelemetryV1(ContractModel):
    provider: Annotated[str, Field(min_length=1, max_length=128)]
    operation: Annotated[str, Field(min_length=1, max_length=128)]
    status: ExternalCallStatus
    latency_ms: NonNegativeDecimal | None = None
    retry_count: NonNegativeInt = 0
    rate_limit_remaining: NonNegativeInt | None = None
    circuit_breaker_state: CircuitBreakerState = CircuitBreakerState.NOT_APPLICABLE
    freshness: FreshnessTelemetry = FreshnessTelemetry.NOT_APPLICABLE

    @model_validator(mode="after")
    def validate_external_call(self) -> ExternalCallTelemetryV1:
        if self.status == ExternalCallStatus.NOT_CALLED:
            if self.latency_ms is not None or self.retry_count != 0:
                raise ValueError("not-called external telemetry cannot have activity")
            if self.rate_limit_remaining is not None:
                raise ValueError("not-called telemetry cannot have a rate-limit balance")
        return self


class SafeCountMetricV1(ContractModel):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,63}$")]
    value: NonNegativeInt


class ObservabilityEventV1(ContractModel):
    occurred_at: datetime
    event_name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,127}$")]
    severity: ObservabilitySeverity
    component: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{2,127}$")]
    outcome: ObservabilityOutcome
    correlation_id: TraceIdentifier
    request_id: TraceIdentifier | None = None
    action_id: TraceIdentifier | None = None
    account: AccountReference | None = None
    duration_ms: NonNegativeDecimal | None = None
    external_call: ExternalCallTelemetryV1 | None = None
    quality: DataQuality | None = None
    completeness: Completeness | None = None
    error_code: Annotated[
        str | None,
        Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$"),
    ] = None
    exception_type: Annotated[
        str | None,
        Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$"),
    ] = None
    metrics: tuple[SafeCountMetricV1, ...] = ()
    contains_sensitive_payload: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("occurred_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observability timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_event(self) -> ObservabilityEventV1:
        metric_names = [metric.name for metric in self.metrics]
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("observability metric names must be unique")
        if self.outcome in (
            ObservabilityOutcome.REJECTED,
            ObservabilityOutcome.FAILURE,
        ) and self.error_code is None:
            raise ValueError("rejected or failed event requires an error code")
        if self.severity == ObservabilitySeverity.ERROR and self.error_code is None:
            raise ValueError("error event requires an error code")
        if self.exception_type is not None and self.error_code is None:
            raise ValueError("exception type requires an error code")
        return self
