from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
    QualityMetadata,
)
from omni_cio.contracts.v1.portfolio import InstrumentType


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]


class SourceAuthority(StrEnum):
    PRIMARY = "primary"
    OFFICIAL = "official"
    REGULATED = "regulated"
    SECONDARY = "secondary"
    UNTRUSTED = "untrusted"


class ComponentStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class RatingScope(StrEnum):
    ISSUER = "issuer"
    ISSUE = "issue"


class RatingAction(StrEnum):
    ASSIGNED = "assigned"
    AFFIRMED = "affirmed"
    UPGRADED = "upgraded"
    DOWNGRADED = "downgraded"
    WITHDRAWN = "withdrawn"


class CorporateEventType(StrEnum):
    DIVIDEND = "dividend"
    COUPON = "coupon"
    MATURITY = "maturity"
    OFFER = "offer"
    AMORTIZATION = "amortization"
    REPORTING = "reporting"
    SHAREHOLDER_MEETING = "shareholder_meeting"
    LISTING = "listing"
    DELISTING = "delisting"
    OTHER = "other"


class MarketAssessmentStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    REJECTED = "rejected"


class MarketSourceV1(ContractModel):
    provider: Annotated[str, Field(min_length=1, max_length=128)]
    authority: SourceAuthority
    retrieved_at: datetime
    source_id: Annotated[str | None, Field(max_length=256)] = None

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class ComponentStateV1(ContractModel):
    status: ComponentStatus
    source: MarketSourceV1 | None = None
    checked_at: datetime | None = None
    record_count: NonNegativeInt = 0
    message: Annotated[str | None, Field(max_length=512)] = None

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("component checked_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_state(self) -> ComponentStateV1:
        if self.status in (ComponentStatus.OK, ComponentStatus.DEGRADED):
            if self.source is None or self.checked_at is None:
                raise ValueError(
                    "available component state requires source and checked_at"
                )
        if self.status in (
            ComponentStatus.UNAVAILABLE,
            ComponentStatus.NOT_APPLICABLE,
        ) and self.record_count != 0:
            raise ValueError(
                "unavailable/not-applicable component cannot contain records"
            )
        return self


class MarketResearchMetadataV1(ContractModel):
    schema_name: Literal["market_research_bundle"] = "market_research_bundle"
    schema_version: Literal["1.0"] = "1.0"
    retrieved_at: datetime
    quality: QualityMetadata

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bundle retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class InstrumentReferenceV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    name: Annotated[str, Field(min_length=1, max_length=256)]
    instrument_type: InstrumentType
    currency: CurrencyCode
    lot: PositiveInt
    source: MarketSourceV1
    ticker: Annotated[str | None, Field(max_length=32)] = None
    isin: Annotated[
        str | None,
        Field(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$"),
    ] = None
    uid: Annotated[str | None, Field(max_length=128)] = None
    figi: Annotated[str | None, Field(max_length=32)] = None
    issuer_id: Annotated[str | None, Field(max_length=128)] = None
    sector: Annotated[str | None, Field(max_length=128)] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_identity(self) -> InstrumentReferenceV1:
        if not any((self.uid, self.isin, self.figi, self.ticker)):
            raise ValueError("instrument reference requires a stable identifier")
        return self


class MarketQuoteV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    as_of: datetime
    source: MarketSourceV1
    last_price: PositiveDecimal | None = None
    best_bid: PositiveDecimal | None = None
    best_ask: PositiveDecimal | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("quote as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_quote(self) -> MarketQuoteV1:
        if (
            self.last_price is None
            and self.best_bid is None
            and self.best_ask is None
        ):
            raise ValueError("quote requires at least one price")
        if (
            self.best_bid is not None
            and self.best_ask is not None
            and self.best_bid > self.best_ask
        ):
            raise ValueError("best bid cannot exceed best ask")
        return self


class MarketLiquidityV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    as_of: datetime
    source: MarketSourceV1
    best_bid: PositiveDecimal
    best_ask: PositiveDecimal
    spread_absolute: NonNegativeDecimal
    spread_bps: NonNegativeDecimal
    bid_depth: NonNegativeDecimal | None = None
    ask_depth: NonNegativeDecimal | None = None
    turnover_24h: NonNegativeDecimal | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("liquidity as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_spread(self) -> MarketLiquidityV1:
        if self.best_bid > self.best_ask:
            raise ValueError("best bid cannot exceed best ask")
        spread = self.best_ask - self.best_bid
        if self.spread_absolute != spread:
            raise ValueError("spread_absolute does not reconcile")
        midpoint = (self.best_ask + self.best_bid) / Decimal("2")
        expected_bps = spread / midpoint * Decimal("10000")
        if self.spread_bps != expected_bps:
            raise ValueError("spread_bps does not reconcile")
        return self


class CreditRatingV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    scope: RatingScope
    agency: Annotated[str, Field(min_length=1, max_length=128)]
    rating: Annotated[str, Field(min_length=1, max_length=32)]
    action: RatingAction
    effective_at: datetime
    source: MarketSourceV1
    outlook: Annotated[str | None, Field(max_length=64)] = None
    previous_rating: Annotated[str | None, Field(max_length=32)] = None

    @field_validator("effective_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("rating effective_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @property
    def is_current(self) -> bool:
        return self.action != RatingAction.WITHDRAWN


class BondMetricsV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    as_of: datetime
    source: MarketSourceV1
    maturity_date: date
    duration_years: NonNegativeDecimal
    accrued_interest: NonNegativeDecimal
    yield_to_maturity: FiniteDecimal | None = None
    yield_to_offer: FiniteDecimal | None = None
    offer_date: date | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bond metrics as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_dates(self) -> BondMetricsV1:
        if self.offer_date is not None and self.offer_date > self.maturity_date:
            raise ValueError("offer date cannot follow maturity date")
        return self


class CorporateEventV1(ContractModel):
    event_id: Annotated[str, Field(min_length=1, max_length=256)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    event_type: CorporateEventType
    announced_at: datetime
    event_at: datetime
    source: MarketSourceV1
    amount: FiniteDecimal | None = None
    currency: CurrencyCode | None = None
    title: Annotated[str, Field(min_length=1, max_length=256)]

    @field_validator("announced_at", "event_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_amount(self) -> CorporateEventV1:
        if (self.amount is None) != (self.currency is None):
            raise ValueError(
                "event amount and currency must be supplied together"
            )
        return self


class MarketResearchBundleV1(ContractModel):
    metadata: MarketResearchMetadataV1
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    reference_state: ComponentStateV1
    quote_state: ComponentStateV1
    liquidity_state: ComponentStateV1
    ratings_state: ComponentStateV1
    bond_metrics_state: ComponentStateV1
    events_state: ComponentStateV1
    reference: InstrumentReferenceV1 | None = None
    quote: MarketQuoteV1 | None = None
    liquidity: MarketLiquidityV1 | None = None
    ratings: tuple[CreditRatingV1, ...] = ()
    bond_metrics: BondMetricsV1 | None = None
    events: tuple[CorporateEventV1, ...] = ()
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_bundle(self) -> MarketResearchBundleV1:
        records = {
            "reference": int(self.reference is not None),
            "quote": int(self.quote is not None),
            "liquidity": int(self.liquidity is not None),
            "ratings": len(self.ratings),
            "bond_metrics": int(self.bond_metrics is not None),
            "events": len(self.events),
        }
        states = {
            "reference": self.reference_state,
            "quote": self.quote_state,
            "liquidity": self.liquidity_state,
            "ratings": self.ratings_state,
            "bond_metrics": self.bond_metrics_state,
            "events": self.events_state,
        }
        for component_name, count in records.items():
            if states[component_name].record_count != count:
                raise ValueError(
                    f"{component_name} record_count does not reconcile"
                )

        items = [
            self.reference,
            self.quote,
            self.liquidity,
            self.bond_metrics,
        ]
        items.extend(self.ratings)
        items.extend(self.events)
        for item in items:
            if item is None:
                continue
            item_key = (
                item.stable_key
                if isinstance(item, InstrumentReferenceV1)
                else item.instrument_key
            )
            if item_key != self.instrument_key:
                raise ValueError(
                    "market component instrument identity mismatch"
                )

        if self.reference is not None:
            reference_currency = self.reference.currency
            for priced_component in (
                self.quote,
                self.liquidity,
                self.bond_metrics,
            ):
                if (
                    priced_component is not None
                    and priced_component.currency != reference_currency
                ):
                    raise ValueError("market component currency mismatch")
        return self


class MarketFreshnessPolicyV1(ContractModel):
    reference_max_age_seconds: PositiveInt = 2_592_000
    quote_max_age_seconds: PositiveInt = 300
    liquidity_max_age_seconds: PositiveInt = 300
    ratings_check_max_age_seconds: PositiveInt = 86_400
    bond_metrics_max_age_seconds: PositiveInt = 86_400
    events_check_max_age_seconds: PositiveInt = 86_400
    future_tolerance_seconds: NonNegativeInt = 60


class MarketReadinessAssessmentV1(ContractModel):
    assessed_at: datetime
    status: MarketAssessmentStatus
    decision_ready: bool
    stale_components: tuple[
        Annotated[str, Field(min_length=1, max_length=64)], ...
    ]
    missing_components: tuple[
        Annotated[str, Field(min_length=1, max_length=64)], ...
    ]
    untrusted_components: tuple[
        Annotated[str, Field(min_length=1, max_length=64)], ...
    ]
    warnings: tuple[
        Annotated[str, Field(min_length=1, max_length=512)], ...
    ] = ()

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "assessment timestamp must be timezone-aware"
            )
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_assessment(self) -> MarketReadinessAssessmentV1:
        blocked = bool(
            self.stale_components
            or self.missing_components
            or self.untrusted_components
        )
        if self.decision_ready == blocked:
            raise ValueError(
                "decision_ready does not match blocking components"
            )
        expected = (
            MarketAssessmentStatus.READY
            if self.decision_ready
            else MarketAssessmentStatus.REJECTED
            if self.untrusted_components
            else MarketAssessmentStatus.PARTIAL
        )
        if self.status != expected:
            raise ValueError(
                "market assessment status is inconsistent"
            )
        return self
