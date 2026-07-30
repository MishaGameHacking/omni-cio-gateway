from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority


class CreditRatingSourceStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CreditRatingSourceErrorCode(StrEnum):
    NETWORK_ERROR = "CREDIT_RATING_SOURCE_NETWORK_ERROR"
    HTTP_ERROR = "CREDIT_RATING_SOURCE_HTTP_ERROR"
    CONTENT_TYPE_INVALID = "CREDIT_RATING_SOURCE_CONTENT_TYPE_INVALID"
    RESPONSE_TOO_LARGE = "CREDIT_RATING_SOURCE_RESPONSE_TOO_LARGE"
    HTML_INVALID = "CREDIT_RATING_SOURCE_HTML_INVALID"
    SCHEMA_INVALID = "CREDIT_RATING_SOURCE_SCHEMA_INVALID"
    EMPTY = "CREDIT_RATING_SOURCE_EMPTY"
    DUPLICATE_CONFLICT = "CREDIT_RATING_SOURCE_DUPLICATE_CONFLICT"
    TIMESTAMP_INVALID = "CREDIT_RATING_SOURCE_TIMESTAMP_INVALID"
    IDENTITY_INVALID = "CREDIT_RATING_SOURCE_IDENTITY_INVALID"
    RATING_INVALID = "CREDIT_RATING_SOURCE_RATING_INVALID"
    OUTLOOK_INVALID = "CREDIT_RATING_SOURCE_OUTLOOK_INVALID"
    URL_INVALID = "CREDIT_RATING_SOURCE_URL_INVALID"


class CreditRatingOutlook(StrEnum):
    STABLE = "stable"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    DEVELOPING = "developing"
    UNDER_REVISION = "under_revision"


class AcraIssuerRatingActionV1(ContractModel):
    schema_name: Literal["acra_issuer_rating_action"] = "acra_issuer_rating_action"
    schema_version: Literal["1.0"] = "1.0"
    subject_name: Annotated[str, Field(min_length=1, max_length=256)]
    scope: Literal["issuer"] = "issuer"
    agency: Literal["ACRA"] = "ACRA"
    agency_legal_name: Literal[
        "Analytical Credit Rating Agency (Joint-Stock Company)"
    ] = "Analytical Credit Rating Agency (Joint-Stock Company)"
    recognized_by_bank_of_russia: Literal[True] = True
    rating_scale: Literal["national_russia"] = "national_russia"
    rating: Annotated[str | None, Field(max_length=32)] = None
    action: RatingAction
    outlook: CreditRatingOutlook | None = None
    published_on: date
    release_url: Annotated[str, Field(min_length=1, max_length=512)]
    source: MarketSourceV1
    source_language: Literal["en"] = "en"
    raw_title_stored: Literal[False] = False
    raw_html_stored: Literal[False] = False
    source_text_treated_as_data: Literal[True] = True
    external_instructions_executed: Literal[False] = False
    credentials_present: Literal[False] = False
    full_account_identifier_present: Literal[False] = False
    broker_write_called: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("subject_name")
    @classmethod
    def normalize_subject_name(cls, value: str) -> str:
        result = " ".join(value.split())
        if not result:
            raise ValueError("rating subject name cannot be empty")
        return result

    @field_validator("rating")
    @classmethod
    def normalize_rating(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        if not result:
            raise ValueError("rating cannot be blank")
        return result

    @model_validator(mode="after")
    def validate_action(self) -> AcraIssuerRatingActionV1:
        if self.source.authority is not SourceAuthority.OFFICIAL:
            raise ValueError("ACRA rating action requires an official source")
        if (
            self.source.provider != "ACRA"
            or self.source.source_id != "ACRA.press_releases.issuer_rating_actions"
        ):
            raise ValueError("ACRA source identity is inconsistent")
        if not self.release_url.startswith(
            "https://www.acra-ratings.ru/press-releases/"
        ):
            raise ValueError("ACRA release URL is outside the fixed source scope")
        if self.action is RatingAction.WITHDRAWN:
            if self.rating is not None or self.outlook is not None:
                raise ValueError(
                    "withdrawn rating action cannot claim a current rating"
                )
        elif self.rating is None:
            raise ValueError("non-withdrawn rating action requires a rating")
        return self


class AcraIssuerRatingActionsSnapshotV1(ContractModel):
    schema_name: Literal["acra_issuer_rating_actions_snapshot"] = (
        "acra_issuer_rating_actions_snapshot"
    )
    schema_version: Literal["1.0"] = "1.0"
    retrieved_at: datetime
    status: CreditRatingSourceStatus
    source: MarketSourceV1 | None = None
    records: tuple[AcraIssuerRatingActionV1, ...] = ()
    error_code: CreditRatingSourceErrorCode | None = None
    warnings: tuple[
        Annotated[str, Field(min_length=1, max_length=256)],
        ...,
    ] = ()
    fixed_official_source: Literal[True] = True
    issuer_scope_only: Literal[True] = True
    raw_html_stored: Literal[False] = False
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
            raise ValueError("rating snapshot retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_snapshot(self) -> AcraIssuerRatingActionsSnapshotV1:
        if self.status is CreditRatingSourceStatus.AVAILABLE:
            if self.source is None or not self.records or self.error_code is not None:
                raise ValueError("available rating snapshot is inconsistent")
            if any(record.source != self.source for record in self.records):
                raise ValueError("rating records must share the snapshot source")
        elif self.source is not None or self.records or self.error_code is None:
            raise ValueError("unavailable rating snapshot is inconsistent")
        return self
