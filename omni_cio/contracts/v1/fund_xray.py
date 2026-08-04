from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode, FiniteDecimal
from omni_cio.contracts.v1.market import MarketLiquidityV1
from omni_cio.contracts.v1.portfolio import InstrumentIdentity
from omni_cio.contracts.v1.research_evidence import ResearchTargetV1


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
UnitWeight = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]


class FundManagementStyle(StrEnum):
    INDEX = "index"
    ACTIVE = "active"
    RULES_BASED = "rules_based"
    UNKNOWN = "unknown"


class FundCompositionMode(StrEnum):
    FULL_HOLDINGS = "full_holdings"
    PARTIAL_HOLDINGS = "partial_holdings"
    DOCUMENTED_BUCKETS = "documented_buckets"
    UNAVAILABLE = "unavailable"


class FundExposureDimension(StrEnum):
    ASSET_CLASS = "asset_class"
    SECTOR = "sector"
    CURRENCY = "currency"
    ISSUER = "issuer"
    GEOGRAPHY = "geography"


class FundOverlapKind(StrEnum):
    DIRECT_HOLDINGS = "direct_holdings"
    OTHER_FUND = "other_fund"


class FundBlockerCode(StrEnum):
    DOSSIER_NOT_READY = "dossier_not_ready"
    DOSSIER_BINDING_MISMATCH = "dossier_binding_mismatch"
    UNIVERSE_BINDING_MISMATCH = "universe_binding_mismatch"
    NOT_ETF = "not_etf"
    SOURCE_PROVENANCE_MISSING = "source_provenance_missing"
    SOURCE_NOT_DECISION_GRADE = "source_not_decision_grade"
    COMPOSITION_MISSING = "composition_missing"
    COMPOSITION_STALE = "composition_stale"
    FULL_HOLDINGS_NOT_RECONCILED = "full_holdings_not_reconciled"
    DOCUMENTED_BUCKETS_NOT_RECONCILED = "documented_buckets_not_reconciled"
    LIQUIDITY_IDENTITY_MISMATCH = "liquidity_identity_mismatch"
    LIQUIDITY_STALE = "liquidity_stale"


class FundProfileV1(ContractModel):
    instrument: InstrumentIdentity
    asset_uid: Annotated[str | None, Field(max_length=128)] = None
    manager: Annotated[str | None, Field(max_length=256)] = None
    benchmark: Annotated[str | None, Field(max_length=256)] = None
    strategy: Annotated[str | None, Field(max_length=512)] = None
    management_style: FundManagementStyle = FundManagementStyle.UNKNOWN
    constituent_count: Annotated[int | None, Field(ge=0)] = None
    aum: NonNegativeDecimal | None = None
    aum_currency: CurrencyCode | None = None
    average_turnover: NonNegativeDecimal | None = None
    tracking_error: NonNegativeDecimal | None = None
    expense_ratio_percent: NonNegativeDecimal | None = None
    buy_premium_percent: NonNegativeDecimal | None = None
    sell_discount_percent: NonNegativeDecimal | None = None
    as_of: datetime
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fund profile as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("aum_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        return _normalize_hashes(value, label="fund profile")

    @model_validator(mode="after")
    def validate_profile(self) -> FundProfileV1:
        if self.instrument.instrument_type.value != "etf":
            raise ValueError("fund profile requires ETF instrument identity")
        if (self.aum is None) != (self.aum_currency is None):
            raise ValueError("fund AUM and currency must be supplied together")
        return self


class FundHoldingV1(ContractModel):
    holding_key: Annotated[str, Field(min_length=3, max_length=256)]
    name: Annotated[str, Field(min_length=1, max_length=256)]
    weight: UnitWeight
    instrument_uid: Annotated[str | None, Field(max_length=128)] = None
    issuer_key: Annotated[str | None, Field(max_length=256)] = None
    asset_class: Annotated[str | None, Field(max_length=128)] = None
    sector: Annotated[str | None, Field(max_length=128)] = None
    currency: CurrencyCode | None = None
    geography: Annotated[str | None, Field(max_length=128)] = None
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        return _normalize_hashes(value, label="fund holding")


class FundExposureBucketV1(ContractModel):
    dimension: FundExposureDimension
    bucket_key: Annotated[str, Field(min_length=1, max_length=256)]
    weight: UnitWeight
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        return _normalize_hashes(value, label="fund exposure bucket")


class FundCompositionV1(ContractModel):
    mode: FundCompositionMode
    as_of: datetime | None = None
    holdings: tuple[FundHoldingV1, ...] = ()
    documented_buckets: tuple[FundExposureBucketV1, ...] = ()
    reported_coverage_weight: UnitWeight = Decimal("0")
    source_record_sha256s: tuple[Sha256, ...] = ()

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fund composition as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("holdings", mode="before")
    @classmethod
    def normalize_holdings(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("fund holdings must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "holding_key")))

    @field_validator("documented_buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("fund exposure buckets must be a collection")
        return tuple(
            sorted(
                value,
                key=lambda row: (
                    _item_key(row, "dimension"),
                    _item_key(row, "bucket_key"),
                ),
            )
        )

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if value is None:
            return ()
        return _normalize_hashes(value, label="fund composition")

    @model_validator(mode="after")
    def validate_composition(self) -> FundCompositionV1:
        holding_keys = [row.holding_key for row in self.holdings]
        if len(holding_keys) != len(set(holding_keys)):
            raise ValueError("fund holdings must have unique stable keys")
        bucket_keys = [
            (row.dimension, row.bucket_key) for row in self.documented_buckets
        ]
        if len(bucket_keys) != len(set(bucket_keys)):
            raise ValueError("fund exposure buckets must be unique per dimension")

        holding_sum = sum((row.weight for row in self.holdings), Decimal("0"))
        if holding_sum > Decimal("1.0001"):
            raise ValueError("fund holding weights cannot exceed 100%")

        if self.mode is FundCompositionMode.UNAVAILABLE:
            if self.as_of is not None or self.holdings or self.documented_buckets:
                raise ValueError("unavailable composition cannot carry composition data")
            if self.reported_coverage_weight != 0 or self.source_record_sha256s:
                raise ValueError("unavailable composition cannot claim coverage/provenance")
            return self

        if self.as_of is None or not self.source_record_sha256s:
            raise ValueError("available composition requires timestamp and provenance")

        if self.mode in {
            FundCompositionMode.FULL_HOLDINGS,
            FundCompositionMode.PARTIAL_HOLDINGS,
        }:
            if not self.holdings or self.documented_buckets:
                raise ValueError("holdings composition requires holdings only")
            if abs(holding_sum - self.reported_coverage_weight) > Decimal("0.0001"):
                raise ValueError("reported holdings coverage must reconcile to weights")
            if self.mode is FundCompositionMode.FULL_HOLDINGS:
                if abs(holding_sum - Decimal("1")) > Decimal("0.0001"):
                    raise ValueError("full holdings must reconcile to 100%")
            elif self.reported_coverage_weight >= Decimal("0.9999"):
                raise ValueError("partial holdings must preserve incomplete coverage")
        elif self.mode is FundCompositionMode.DOCUMENTED_BUCKETS:
            if self.holdings or not self.documented_buckets:
                raise ValueError("documented-bucket composition requires buckets only")
            by_dimension: dict[FundExposureDimension, Decimal] = {}
            for bucket in self.documented_buckets:
                by_dimension[bucket.dimension] = (
                    by_dimension.get(bucket.dimension, Decimal("0")) + bucket.weight
                )
            if any(value > Decimal("1.0001") for value in by_dimension.values()):
                raise ValueError("documented exposure dimension cannot exceed 100%")
            if abs(max(by_dimension.values()) - self.reported_coverage_weight) > Decimal(
                "0.0001"
            ):
                raise ValueError("documented bucket coverage must reconcile")
        return self


class FundLookThroughExposureV1(ContractModel):
    dimension: FundExposureDimension
    bucket_key: Annotated[str, Field(min_length=1, max_length=256)]
    weight: UnitWeight


class FundConcentrationV1(ContractModel):
    top_1_weight: UnitWeight
    top_5_weight: UnitWeight
    hhi: UnitWeight
    measured_coverage_weight: UnitWeight


class DirectUnderlyingExposureV1(ContractModel):
    holding_key: Annotated[str, Field(min_length=3, max_length=256)]
    portfolio_weight: UnitWeight


class OtherFundCompositionV1(ContractModel):
    fund_key: Annotated[str, Field(min_length=3, max_length=256)]
    holdings: tuple[FundHoldingV1, ...]

    @field_validator("holdings", mode="before")
    @classmethod
    def normalize_holdings(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("other fund holdings must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "holding_key")))

    @model_validator(mode="after")
    def validate_holdings(self) -> OtherFundCompositionV1:
        keys = [row.holding_key for row in self.holdings]
        if len(keys) != len(set(keys)):
            raise ValueError("other fund holdings must have unique keys")
        total = sum((row.weight for row in self.holdings), Decimal("0"))
        if total > Decimal("1.0001"):
            raise ValueError("other fund holdings cannot exceed 100%")
        return self


class FundOverlapV1(ContractModel):
    kind: FundOverlapKind
    counterpart_key: Annotated[str, Field(min_length=3, max_length=256)]
    overlap_weight: UnitWeight
    shared_holding_keys: tuple[Annotated[str, Field(min_length=3, max_length=256)], ...]

    @field_validator("shared_holding_keys", mode="before")
    @classmethod
    def normalize_keys(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("shared holding keys must be a collection")
        return tuple(sorted(set(value)))


class FundFreshnessPolicyV1(ContractModel):
    composition_max_age_seconds: Annotated[int, Field(ge=3600)] = 604_800
    liquidity_max_age_seconds: Annotated[int, Field(ge=30)] = 300
    future_tolerance_seconds: Annotated[int, Field(ge=0)] = 60


class FundXRayV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    dossier_sha256: Sha256
    universe_sha256: Sha256
    target: ResearchTargetV1
    profile: FundProfileV1
    composition: FundCompositionV1
    liquidity: MarketLiquidityV1 | None = None
    exposures: tuple[FundLookThroughExposureV1, ...] = ()
    concentration: FundConcentrationV1 | None = None
    overlaps: tuple[FundOverlapV1, ...] = ()
    unknown_weight: UnitWeight
    blockers: tuple[FundBlockerCode, ...] = ()
    xray_sha256: Sha256
    decision_ready: bool
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fund X-Ray assessed_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("exposures", mode="before")
    @classmethod
    def normalize_exposures(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("look-through exposures must be a collection")
        return tuple(
            sorted(
                value,
                key=lambda row: (
                    _item_key(row, "dimension"),
                    _item_key(row, "bucket_key"),
                ),
            )
        )

    @field_validator("overlaps", mode="before")
    @classmethod
    def normalize_overlaps(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("fund overlaps must be a collection")
        return tuple(
            sorted(
                value,
                key=lambda row: (
                    _item_key(row, "kind"),
                    _item_key(row, "counterpart_key"),
                ),
            )
        )

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("fund blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_xray(self) -> FundXRayV1:
        if self.decision_ready != (not self.blockers):
            raise ValueError("fund X-Ray readiness must reconcile to blockers")
        if self.target.instrument_uid != self.profile.instrument.uid:
            raise ValueError("fund profile identity must bind target instrument UID")
        if self.xray_sha256 != fund_xray_sha256(self):
            raise ValueError("xray_sha256 does not match canonical fund X-Ray payload")
        return self


def _normalize_hashes(value: object, *, label: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ValueError(f"{label} source hashes must be a collection")
    return tuple(sorted(set(value)))


def _item_key(row: object, attribute: str) -> str:
    if isinstance(row, dict):
        value = row.get(attribute)
    else:
        value = getattr(row, attribute, None)
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fund_xray_sha256(xray: FundXRayV1) -> str:
    payload = xray.model_dump(mode="json", exclude={"xray_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
