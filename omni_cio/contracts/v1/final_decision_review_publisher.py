from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import AccountReference, ContractModel
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    ObservabilityEventV1,
    ObservabilityOutcome,
)


Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]


class FinalDecisionReviewPublicationDisposition(StrEnum):
    PUBLISHED = "published"
    REPLACED = "replaced"


class FinalDecisionReviewPublicationResultV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    disposition: FinalDecisionReviewPublicationDisposition
    published_at: datetime
    expires_at: datetime
    account: AccountReference
    query_sha256: Sha256Digest
    response_sha256: Sha256Digest
    action_candidate_sha256: Sha256Digest
    instrument_count: PositiveInt
    source_replaced: bool
    registry_active_sources: PositiveInt
    registry_evicted_sources: NonNegativeInt
    observability_event: ObservabilityEventV1
    internal_only: Literal[True] = True
    http_publication_method_created: Literal[False] = False
    external_broker_called: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("published_at", "expires_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("publisher timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_publication(self) -> FinalDecisionReviewPublicationResultV1:
        if self.expires_at <= self.published_at:
            raise ValueError("publisher expiry must be after publication")
        expected_replaced = (
            self.disposition is FinalDecisionReviewPublicationDisposition.REPLACED
        )
        if self.source_replaced != expected_replaced:
            raise ValueError("publisher disposition and replacement flag must agree")

        event = self.observability_event
        if event.event_name != "final.review.publisher":
            raise ValueError("unexpected publisher observability event")
        if event.component != "final_review_publisher":
            raise ValueError("unexpected publisher observability component")
        if event.outcome is not ObservabilityOutcome.SUCCESS:
            raise ValueError("successful publication requires success observability")
        if event.account != self.account:
            raise ValueError("publisher observability account must match")
        if event.external_call is None:
            raise ValueError("publisher observability requires external-call telemetry")
        if event.external_call.status is not ExternalCallStatus.NOT_CALLED:
            raise ValueError("publisher must not report an external call")
        if event.contains_sensitive_payload or event.trading_methods:
            raise ValueError("publisher observability must remain safe and read-only")

        metrics = {metric.name: metric.value for metric in event.metrics}
        expected_metrics = {
            "registry.active.sources": self.registry_active_sources,
            "registry.evicted.sources": self.registry_evicted_sources,
            "source.replaced": int(self.source_replaced),
            "instrument.count": self.instrument_count,
        }
        if metrics != expected_metrics:
            raise ValueError("publisher observability metrics must match result")
        return self
