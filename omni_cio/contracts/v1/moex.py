from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import MarketQuoteV1, MarketSourceV1, SourceAuthority


class MoexIssQuoteStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class MoexIssQuoteErrorCode(StrEnum):
    NETWORK_ERROR = "MOEX_ISS_QUOTE_NETWORK_ERROR"
    HTTP_ERROR = "MOEX_ISS_QUOTE_HTTP_ERROR"
    CONTENT_TYPE_INVALID = "MOEX_ISS_QUOTE_CONTENT_TYPE_INVALID"
    RESPONSE_TOO_LARGE = "MOEX_ISS_QUOTE_RESPONSE_TOO_LARGE"
    JSON_INVALID = "MOEX_ISS_QUOTE_JSON_INVALID"
    SCHEMA_INVALID = "MOEX_ISS_QUOTE_SCHEMA_INVALID"
    EMPTY = "MOEX_ISS_QUOTE_EMPTY"
    IDENTITY_MISMATCH = "MOEX_ISS_QUOTE_IDENTITY_MISMATCH"
    DUPLICATE_CONFLICT = "MOEX_ISS_QUOTE_DUPLICATE_CONFLICT"
    TIMESTAMP_INVALID = "MOEX_ISS_QUOTE_TIMESTAMP_INVALID"
    CURRENCY_INVALID = "MOEX_ISS_QUOTE_CURRENCY_INVALID"
    PRICE_INVALID = "MOEX_ISS_QUOTE_PRICE_INVALID"


class MoexIssTqbrQuoteSnapshotV1(ContractModel):
    schema_name: Literal["moex_iss_tqbr_quote_snapshot"] = (
        "moex_iss_tqbr_quote_snapshot"
    )
    schema_version: Literal["1.0"] = "1.0"
    secid: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{0,35}$")]
    board_id: Literal["TQBR"] = "TQBR"
    retrieved_at: datetime
    status: MoexIssQuoteStatus
    source: MarketSourceV1 | None = None
    quote: MarketQuoteV1 | None = None
    short_name: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    lot_size: Annotated[int | None, Field(ge=1, le=1_000_000_000)] = None
    decimals: Annotated[int | None, Field(ge=0, le=12)] = None
    error_code: MoexIssQuoteErrorCode | None = None
    warnings: tuple[
        Annotated[str, Field(min_length=1, max_length=256)], ...
    ] = ()
    delayed_data_possible: Literal[True] = True
    realtime_guaranteed: Literal[False] = False
    source_text_treated_as_data: Literal[True] = True
    external_instructions_executed: Literal[False] = False
    raw_json_stored: Literal[False] = False
    credentials_present: Literal[False] = False
    full_account_identifier_present: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("secid", mode="before")
    @classmethod
    def normalize_secid(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_snapshot(self) -> MoexIssTqbrQuoteSnapshotV1:
        expected_key = f"MOEX:{self.board_id}:{self.secid}"
        if self.status is MoexIssQuoteStatus.AVAILABLE:
            if (
                self.source is None
                or self.source.authority is not SourceAuthority.OFFICIAL
                or self.quote is None
                or self.quote.instrument_key != expected_key
                or self.quote.source != self.source
                or self.short_name is None
                or self.lot_size is None
                or self.decimals is None
                or self.error_code is not None
            ):
                raise ValueError("available MOEX quote snapshot is inconsistent")
        elif (
            self.source is not None
            or self.quote is not None
            or self.short_name is not None
            or self.lot_size is not None
            or self.decimals is not None
            or self.error_code is None
        ):
            raise ValueError("unavailable MOEX quote snapshot is inconsistent")
        return self
