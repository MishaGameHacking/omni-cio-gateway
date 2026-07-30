from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority


RatePercent = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("100"), allow_inf_nan=False),
]


class MacroDataStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class MacroDataErrorCode(StrEnum):
    NETWORK_ERROR = "CBR_KEY_RATE_NETWORK_ERROR"
    HTTP_ERROR = "CBR_KEY_RATE_HTTP_ERROR"
    CONTENT_TYPE_INVALID = "CBR_KEY_RATE_CONTENT_TYPE_INVALID"
    RESPONSE_TOO_LARGE = "CBR_KEY_RATE_RESPONSE_TOO_LARGE"
    XML_INVALID = "CBR_KEY_RATE_XML_INVALID"
    SOAP_FAULT = "CBR_KEY_RATE_SOAP_FAULT"
    EMPTY = "CBR_KEY_RATE_EMPTY"
    RANGE_MISMATCH = "CBR_KEY_RATE_RANGE_MISMATCH"
    DUPLICATE_CONFLICT = "CBR_KEY_RATE_DUPLICATE_CONFLICT"


class KeyRateObservationV1(ContractModel):
    effective_date: date
    rate_percent: RatePercent


class CbrKeyRateSnapshotV1(ContractModel):
    schema_name: Literal["cbr_key_rate_snapshot"] = "cbr_key_rate_snapshot"
    schema_version: Literal["1.0"] = "1.0"
    requested_from: date
    requested_to: date
    retrieved_at: datetime
    status: MacroDataStatus
    source: MarketSourceV1 | None = None
    observations: tuple[KeyRateObservationV1, ...] = ()
    current: KeyRateObservationV1 | None = None
    error_code: MacroDataErrorCode | None = None
    warnings: tuple[
        Annotated[str, Field(min_length=1, max_length=256)], ...
    ] = ()
    source_text_treated_as_data: Literal[True] = True
    external_instructions_executed: Literal[False] = False
    raw_xml_stored: Literal[False] = False
    credentials_present: Literal[False] = False
    full_account_identifier_present: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_snapshot(self) -> CbrKeyRateSnapshotV1:
        if self.requested_from > self.requested_to:
            raise ValueError("requested date range is invalid")

        dates = tuple(row.effective_date for row in self.observations)
        if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
            raise ValueError("key-rate observations must be unique and sorted")
        if any(
            row.effective_date < self.requested_from
            or row.effective_date > self.requested_to
            for row in self.observations
        ):
            raise ValueError("key-rate observation is outside requested range")

        if self.status is MacroDataStatus.AVAILABLE:
            if (
                self.source is None
                or self.source.authority is not SourceAuthority.OFFICIAL
                or not self.observations
                or self.current != self.observations[-1]
                or self.error_code is not None
            ):
                raise ValueError("available key-rate snapshot is inconsistent")
        elif (
            self.source is not None
            or self.observations
            or self.current is not None
            or self.error_code is None
        ):
            raise ValueError("unavailable key-rate snapshot is inconsistent")
        return self
