from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import (
    AccountReference,
    ContractModel,
    SourceReference,
)


PositiveInt = Annotated[int, Field(gt=0)]


class TrustedScenarioPublicationDisposition(StrEnum):
    PUBLISHED = "published"
    REPLACED = "replaced"


class TrustedScenarioPublicationResultV1(ContractModel):
    schema_name: Literal["trusted_scenario_publication"] = (
        "trusted_scenario_publication"
    )
    schema_version: Literal["1.0"] = "1.0"
    disposition: TrustedScenarioPublicationDisposition
    scenario_id: Annotated[
        str,
        Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,127}$"),
    ]
    direction: OrderSide
    account: AccountReference
    gate_assessed_at: datetime
    pro_forma_retrieved_at: datetime
    published_at: datetime
    expires_at: datetime
    source: SourceReference
    instrument_count: PositiveInt
    gate_ready: bool
    pro_forma_decision_ready: bool
    source_replaced: bool
    source_evicted: bool
    active_bundle_count: PositiveInt
    internal_only: Literal[True] = True
    raw_payload_accepted: Literal[False] = False
    credentials_accepted: Literal[False] = False
    full_account_accepted: Literal[False] = False
    request_body_accepted: Literal[False] = False
    http_route_created: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator(
        "gate_assessed_at",
        "pro_forma_retrieved_at",
        "published_at",
        "expires_at",
    )
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trusted scenario timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> TrustedScenarioPublicationResultV1:
        if self.gate_assessed_at != self.pro_forma_retrieved_at:
            raise ValueError("trusted scenario source timestamps must match exactly")
        if self.source.retrieved_at != self.gate_assessed_at:
            raise ValueError("trusted scenario provenance timestamp must match source")
        if self.source.source_id is not None:
            raise ValueError("trusted scenario provenance must not expose source IDs")
        if self.expires_at <= self.published_at:
            raise ValueError("trusted scenario expiry must be after publication")
        expected_replaced = (
            self.disposition is TrustedScenarioPublicationDisposition.REPLACED
        )
        if self.source_replaced is not expected_replaced:
            raise ValueError("trusted scenario disposition and replacement must agree")
        return self
