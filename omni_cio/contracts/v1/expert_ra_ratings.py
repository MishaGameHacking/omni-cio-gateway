from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)


_EXPERT_RA_RATINGS = frozenset(
    {
        "ruAAA",
        "ruAA+",
        "ruAA",
        "ruAA-",
        "ruA+",
        "ruA",
        "ruA-",
        "ruBBB+",
        "ruBBB",
        "ruBBB-",
        "ruBB+",
        "ruBB",
        "ruBB-",
        "ruB+",
        "ruB",
        "ruB-",
        "ruCCC",
        "ruCC",
        "ruC",
        "ruRD",
        "ruD",
    }
)
_EXPERT_RA_RELEASE_URL_PATTERN = (
    r"^https://raexpert\.ru/releases/20[0-9]{2}/"
    r"[a-z]{3}(?:0[1-9]|[12][0-9]|3[01])[a-z]?$"
)


class ExpertRaIssuerRatingActionV1(ContractModel):
    schema_name: Literal["expert_ra_issuer_rating_action"] = (
        "expert_ra_issuer_rating_action"
    )
    schema_version: Literal["1.0"] = "1.0"
    subject_name: Annotated[str, Field(min_length=1, max_length=256)]
    scope: Literal["issuer"] = "issuer"
    agency: Literal["EXPERT_RA"] = "EXPERT_RA"
    agency_legal_name: Literal["АО «Эксперт РА»"] = "АО «Эксперт РА»"
    recognized_by_bank_of_russia: Literal[True] = True
    rating_scale: Literal["national_russia"] = "national_russia"
    rating: Annotated[str | None, Field(max_length=16)] = None
    action: RatingAction
    outlook: CreditRatingOutlook | None = None
    published_on: date
    release_url: Annotated[
        str,
        Field(
            min_length=1,
            max_length=512,
            pattern=_EXPERT_RA_RELEASE_URL_PATTERN,
        ),
    ]
    source: MarketSourceV1
    source_language: Literal["ru"] = "ru"
    informational_use_only: Literal[True] = True
    redistribution_authorized: Literal[False] = False
    investment_recommendation: Literal[False] = False
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
        result = " ".join(value.replace("\xa0", " ").split()).strip(" ,.;")
        if not result:
            raise ValueError("Expert RA rating subject cannot be empty")
        return result

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        if result not in _EXPERT_RA_RATINGS:
            raise ValueError("Expert RA rating is outside the fixed national scale")
        return result

    @model_validator(mode="after")
    def validate_action(self) -> ExpertRaIssuerRatingActionV1:
        if self.source.authority is not SourceAuthority.OFFICIAL:
            raise ValueError("Expert RA rating action requires an official source")
        if (
            self.source.provider != "Expert RA"
            or self.source.source_id != "EXPERT_RA.home.rating_actions"
        ):
            raise ValueError("Expert RA source identity is inconsistent")
        if self.action is RatingAction.WITHDRAWN:
            if self.rating is not None or self.outlook is not None:
                raise ValueError(
                    "withdrawn Expert RA action cannot claim current rating"
                )
        elif self.rating is None:
            raise ValueError("non-withdrawn Expert RA action requires rating")
        return self


class ExpertRaIssuerRatingActionsSnapshotV1(ContractModel):
    schema_name: Literal["expert_ra_issuer_rating_actions_snapshot"] = (
        "expert_ra_issuer_rating_actions_snapshot"
    )
    schema_version: Literal["1.0"] = "1.0"
    retrieved_at: datetime
    status: CreditRatingSourceStatus
    source: MarketSourceV1 | None = None
    records: tuple[ExpertRaIssuerRatingActionV1, ...] = ()
    error_code: CreditRatingSourceErrorCode | None = None
    warnings: tuple[
        Annotated[str, Field(min_length=1, max_length=256)],
        ...,
    ] = ()
    fixed_official_source: Literal[True] = True
    issuer_scope_only: Literal[True] = True
    agency_specific_scale_only: Literal[True] = True
    informational_use_only: Literal[True] = True
    redistribution_authorized: Literal[False] = False
    investment_recommendation: Literal[False] = False
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
            raise ValueError("Expert RA snapshot timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_snapshot(self) -> ExpertRaIssuerRatingActionsSnapshotV1:
        if self.status is CreditRatingSourceStatus.AVAILABLE:
            if self.source is None or not self.records or self.error_code is not None:
                raise ValueError("available Expert RA snapshot is inconsistent")
            if any(record.source != self.source for record in self.records):
                raise ValueError("Expert RA records must share snapshot source")
            release_urls = tuple(record.release_url for record in self.records)
            if len(set(release_urls)) != len(release_urls):
                raise ValueError("Expert RA release URLs must be unique")
        elif self.source is not None or self.records or self.error_code is None:
            raise ValueError("unavailable Expert RA snapshot is inconsistent")
        return self
