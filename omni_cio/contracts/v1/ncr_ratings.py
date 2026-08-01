from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)


_NCR_RATINGS = frozenset(
    {
        "AAA.ru",
        "AA+.ru",
        "AA.ru",
        "AA-.ru",
        "A+.ru",
        "A.ru",
        "A-.ru",
        "BBB+.ru",
        "BBB.ru",
        "BBB-.ru",
        "BB+.ru",
        "BB.ru",
        "BB-.ru",
        "B+.ru",
        "B.ru",
        "B-.ru",
        "CCC.ru",
        "CC.ru",
        "C.ru",
        "D",
    }
)
_NCR_RELEASE_SLUG = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,126}[A-Za-z0-9])?"
_NCR_RELEASE_URL_PATTERN = (
    r"^https://ratings\.ru/ratings/press-releases/"
    rf"{_NCR_RELEASE_SLUG}-RA-"
    r"(?:0[1-9]|[12][0-9]|3[01])"
    r"(?:0[1-9]|1[0-2])[0-9]{2}/$"
)
_NCR_RELEASE_URL_RE = re.compile(
    r"^https://ratings\.ru/ratings/press-releases/"
    rf"(?P<slug>{_NCR_RELEASE_SLUG})-RA-"
    r"(?P<day>0[1-9]|[12][0-9]|3[01])"
    r"(?P<month>0[1-9]|1[0-2])(?P<year>[0-9]{2})/$"
)
_NCR_PUBLICATION_FUTURE_TOLERANCE = timedelta(days=1)
_MAX_NCR_SNAPSHOT_RECORDS = 30


class NcrIssuerRatingActionV1(ContractModel):
    schema_name: Literal["ncr_issuer_rating_action"] = "ncr_issuer_rating_action"
    schema_version: Literal["1.0"] = "1.0"
    subject_name: Annotated[str, Field(min_length=1, max_length=256)]
    scope: Literal["issuer"] = "issuer"
    agency: Literal["NCR"] = "NCR"
    agency_legal_name: Literal[
        "Общество с ограниченной ответственностью «Национальные Кредитные Рейтинги»"
    ] = "Общество с ограниченной ответственностью «Национальные Кредитные Рейтинги»"
    recognized_by_bank_of_russia: Literal[True] = True
    rating_scale: Literal["national_russia"] = "national_russia"
    subject_identity_resolved: Literal[False] = False
    stable_subject_id_present: Literal[False] = False
    subject_name_is_source_text: Literal[True] = True
    identity_resolution_required: Literal[True] = True
    rating: Annotated[str | None, Field(max_length=16)] = None
    action: RatingAction
    outlook: CreditRatingOutlook | None = None
    published_on: date
    release_url: Annotated[
        str,
        Field(
            min_length=1,
            max_length=512,
            pattern=_NCR_RELEASE_URL_PATTERN,
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
            raise ValueError("NCR rating subject cannot be empty")
        return result

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        if result not in _NCR_RATINGS:
            raise ValueError("NCR rating is outside the fixed national scale")
        return result

    @model_validator(mode="after")
    def validate_action(self) -> NcrIssuerRatingActionV1:
        if self.source.authority is not SourceAuthority.OFFICIAL:
            raise ValueError("NCR rating action requires an official source")
        if (
            self.source.provider != "NCR"
            or self.source.source_id != "NCR.press_releases.issuer_rating_actions"
        ):
            raise ValueError("NCR source identity is inconsistent")
        if (
            self.published_on
            > (self.source.retrieved_at + _NCR_PUBLICATION_FUTURE_TOLERANCE).date()
        ):
            raise ValueError("NCR publication date cannot be after source retrieval")

        release_match = _NCR_RELEASE_URL_RE.fullmatch(self.release_url)
        if release_match is None:
            raise ValueError("NCR release URL identity is inconsistent")
        try:
            release_date = date(
                2000 + int(release_match.group("year")),
                int(release_match.group("month")),
                int(release_match.group("day")),
            )
        except ValueError as exc:
            raise ValueError("NCR release URL date is invalid") from exc
        if release_date != self.published_on:
            raise ValueError("NCR release URL date must match publication date")

        if self.action is RatingAction.WITHDRAWN:
            if self.rating is not None or self.outlook is not None:
                raise ValueError("withdrawn NCR action cannot claim current rating")
        elif self.rating is None:
            raise ValueError("non-withdrawn NCR action requires rating")
        return self


class NcrIssuerRatingActionsSnapshotV1(ContractModel):
    schema_name: Literal["ncr_issuer_rating_actions_snapshot"] = (
        "ncr_issuer_rating_actions_snapshot"
    )
    schema_version: Literal["1.0"] = "1.0"
    retrieved_at: datetime
    status: CreditRatingSourceStatus
    source: MarketSourceV1 | None = None
    records: Annotated[
        tuple[NcrIssuerRatingActionV1, ...],
        Field(max_length=_MAX_NCR_SNAPSHOT_RECORDS),
    ] = ()
    error_code: CreditRatingSourceErrorCode | None = None
    warnings: tuple[
        Annotated[str, Field(min_length=1, max_length=256)],
        ...,
    ] = ()
    fixed_official_source: Literal[True] = True
    issuer_scope_only: Literal[True] = True
    agency_specific_scale_only: Literal[True] = True
    subject_identity_resolution_required: Literal[True] = True
    cross_agency_identity_merged: Literal[False] = False
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
            raise ValueError("NCR snapshot timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_snapshot(self) -> NcrIssuerRatingActionsSnapshotV1:
        if self.status is CreditRatingSourceStatus.AVAILABLE:
            if self.source is None or not self.records or self.error_code is not None:
                raise ValueError("available NCR snapshot is inconsistent")
            if self.source.retrieved_at != self.retrieved_at:
                raise ValueError(
                    "NCR snapshot and source retrieval timestamps must match"
                )
            if any(record.source != self.source for record in self.records):
                raise ValueError("NCR records must share snapshot source")
            release_urls = tuple(record.release_url for record in self.records)
            if len(set(release_urls)) != len(release_urls):
                raise ValueError("NCR release URLs must be unique")
            expected_order = tuple(
                sorted(
                    self.records,
                    key=lambda item: (item.published_on, item.release_url),
                    reverse=True,
                )
            )
            if self.records != expected_order:
                raise ValueError("NCR records must be sorted newest first")
        elif self.source is not None or self.records or self.error_code is None:
            raise ValueError("unavailable NCR snapshot is inconsistent")
        return self
