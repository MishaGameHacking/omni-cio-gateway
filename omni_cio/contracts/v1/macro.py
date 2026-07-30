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


class MacroCacheStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class MacroCacheErrorCode(StrEnum):
    EMPTY = "CBR_KEY_RATE_CACHE_EMPTY"
    EXPIRED = "CBR_KEY_RATE_CACHE_EXPIRED"
    STALE_NOT_ALLOWED = "CBR_KEY_RATE_CACHE_STALE_NOT_ALLOWED"
    REFRESH_FAILED = "CBR_KEY_RATE_CACHE_REFRESH_FAILED"
    REFRESH_TYPE_INVALID = "CBR_KEY_RATE_CACHE_REFRESH_TYPE_INVALID"
    REFRESH_RANGE_MISMATCH = "CBR_KEY_RATE_CACHE_REFRESH_RANGE_MISMATCH"
    REFRESH_FROM_FUTURE = "CBR_KEY_RATE_CACHE_REFRESH_FROM_FUTURE"
    REFRESH_STALE = "CBR_KEY_RATE_CACHE_REFRESH_STALE"


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


class CbrKeyRateCacheResultV1(ContractModel):
    schema_name: Literal["cbr_key_rate_cache_result"] = (
        "cbr_key_rate_cache_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    requested_from: date
    requested_to: date
    checked_at: datetime
    status: MacroCacheStatus
    snapshot: CbrKeyRateSnapshotV1 | None = None
    age_seconds: Annotated[int, Field(ge=0)] | None = None
    fresh_until: datetime | None = None
    stale_until: datetime | None = None
    served_from_cache: bool
    stale_available: bool
    stale_value_exposed: bool
    refresh_attempted: bool
    refresh_succeeded: bool
    source_error_code: MacroDataErrorCode | None = None
    cache_error_code: MacroCacheErrorCode | None = None
    display_value_allowed: bool
    source_text_treated_as_data: Literal[True] = True
    external_instructions_executed: Literal[False] = False
    raw_xml_stored: Literal[False] = False
    credentials_present: Literal[False] = False
    full_account_identifier_present: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("checked_at", "fresh_until", "stale_until")
    @classmethod
    def normalize_cache_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("cache timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_cache_result(self) -> CbrKeyRateCacheResultV1:
        if self.requested_from > self.requested_to:
            raise ValueError("requested date range is invalid")
        if self.refresh_succeeded and not self.refresh_attempted:
            raise ValueError("refresh success requires an attempt")
        if self.stale_value_exposed and not self.stale_available:
            raise ValueError("stale value exposure requires stale data")
        if self.snapshot is not None and (
            self.snapshot.requested_from != self.requested_from
            or self.snapshot.requested_to != self.requested_to
            or self.snapshot.status is not MacroDataStatus.AVAILABLE
        ):
            raise ValueError("cache snapshot does not match the request")

        deadlines_present = self.fresh_until is not None and self.stale_until is not None
        if deadlines_present and self.fresh_until > self.stale_until:
            raise ValueError("cache deadlines are inconsistent")
        if (self.fresh_until is None) is not (self.stale_until is None):
            raise ValueError("cache deadlines must be present together")

        if self.status is MacroCacheStatus.FRESH:
            if (
                self.snapshot is None
                or self.age_seconds is None
                or not deadlines_present
                or self.checked_at >= self.fresh_until
                or self.stale_available
                or self.stale_value_exposed
                or not self.display_value_allowed
                or self.cache_error_code is not None
                or self.source_error_code is not None
                or (self.refresh_attempted and not self.refresh_succeeded)
            ):
                raise ValueError("fresh cache result is inconsistent")
        elif self.status is MacroCacheStatus.STALE:
            if (
                self.snapshot is None
                or self.age_seconds is None
                or not deadlines_present
                or self.checked_at < self.fresh_until
                or self.checked_at >= self.stale_until
                or not self.stale_available
                or not self.stale_value_exposed
                or not self.display_value_allowed
                or not self.refresh_attempted
                or self.refresh_succeeded
                or (
                    self.cache_error_code is None
                    and self.source_error_code is None
                )
            ):
                raise ValueError("stale cache result is inconsistent")
        elif (
            self.snapshot is not None
            or self.display_value_allowed
            or self.stale_value_exposed
            or self.refresh_succeeded
            or (
                self.cache_error_code is None
                and self.source_error_code is None
            )
        ):
            raise ValueError("unavailable cache result is inconsistent")
        return self
