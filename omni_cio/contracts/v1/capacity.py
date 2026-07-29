from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority


PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class CapacityStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class CapacityBlocker(StrEnum):
    MARKET_NOT_READY = "market_not_ready"
    EVIDENCE_STALE = "evidence_stale"
    EVIDENCE_FROM_FUTURE = "evidence_from_future"
    UNTRUSTED_SOURCE = "untrusted_source"
    INSUFFICIENT_TURNOVER_HISTORY = "insufficient_turnover_history"
    DAILY_PARTICIPATION_EXCEEDED = "daily_participation_exceeded"
    TOP_OF_BOOK_PARTICIPATION_EXCEEDED = "top_of_book_participation_exceeded"
    EXECUTION_WINDOW_TOO_SHORT = "execution_window_too_short"
    ESTIMATED_IMPACT_EXCEEDED = "estimated_impact_exceeded"
    ZERO_SAFE_CAPACITY = "zero_safe_capacity"


class CapacityWarning(StrEnum):
    SQUARE_ROOT_IMPACT_PROXY = "square_root_impact_proxy"
    IMPACT_IS_NOT_EXECUTION_PRICE = "impact_is_not_execution_price"
    TOP_OF_BOOK_ONLY = "top_of_book_only"
    SINGLE_VENUE_EVIDENCE = "single_venue_evidence"
    CAPACITY_IS_POINT_IN_TIME = "capacity_is_point_in_time"
    ORDER_SPLITTING_REQUIRED = "order_splitting_required"
    HIGH_SPREAD = "high_spread"
    TURNOVER_VARIABILITY_HIGH = "turnover_variability_high"


class CapacityPolicyV1(ContractModel):
    evidence_max_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 300
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60
    minimum_turnover_history_days: Annotated[int, Field(ge=5, le=252)] = 20
    maximum_daily_turnover_participation: Annotated[
        Decimal,
        Field(gt=Decimal("0"), le=Decimal("0.50"), allow_inf_nan=False),
    ] = Decimal("0.05")
    maximum_top_of_book_participation: Annotated[
        Decimal,
        Field(gt=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
    ] = Decimal("0.25")
    maximum_estimated_impact_bps: Annotated[
        Decimal,
        Field(gt=Decimal("0"), le=Decimal("5000"), allow_inf_nan=False),
    ] = Decimal("100")
    impact_coefficient: Annotated[
        Decimal,
        Field(gt=Decimal("0"), le=Decimal("10"), allow_inf_nan=False),
    ] = Decimal("0.50")
    high_spread_warning_bps: NonNegativeDecimal = Decimal("50")
    high_turnover_variability_ratio: Annotated[
        Decimal,
        Field(ge=Decimal("1"), le=Decimal("100"), allow_inf_nan=False),
    ] = Decimal("2")
    trusted_authorities: tuple[SourceAuthority, ...] = (
        SourceAuthority.PRIMARY,
        SourceAuthority.OFFICIAL,
        SourceAuthority.REGULATED,
    )

    @model_validator(mode="after")
    def validate_policy(self) -> CapacityPolicyV1:
        if not self.trusted_authorities:
            raise ValueError("capacity policy requires trusted authorities")
        if len(set(self.trusted_authorities)) != len(self.trusted_authorities):
            raise ValueError("capacity trusted authorities must be unique")
        return self


class CapacityOrderRequestV1(ContractModel):
    request_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    side: OrderSide
    currency: CurrencyCode
    quantity_lots: PositiveInt
    lot_size: PositiveInt
    reference_price: PositiveDecimal
    intended_execution_days: Annotated[int, Field(ge=1, le=20)] = 1
    units: PositiveInt
    order_notional: PositiveDecimal
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_request(self) -> CapacityOrderRequestV1:
        expected_units = self.quantity_lots * self.lot_size
        if self.units != expected_units:
            raise ValueError("capacity request units do not reconcile")
        expected_notional = Decimal(self.units) * self.reference_price
        if self.order_notional != expected_notional:
            raise ValueError("capacity request notional does not reconcile")
        return self


class CapacityEvidenceV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    lot_size: PositiveInt
    as_of: datetime
    source: MarketSourceV1
    venue: Annotated[str, Field(min_length=1, max_length=64)]
    reference_price: PositiveDecimal
    spread_bps: NonNegativeDecimal
    top_of_book_depth_notional: PositiveDecimal
    average_daily_turnover_notional: PositiveDecimal
    median_daily_turnover_notional: PositiveDecimal
    turnover_history_days: PositiveInt
    daily_return_volatility: NonNegativeDecimal
    depth_is_notional: Literal[True] = True
    turnover_is_notional: Literal[True] = True
    single_venue: Literal[True] = True
    complete: Literal[True] = True
    truncated: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity evidence timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evidence(self) -> CapacityEvidenceV1:
        if self.source.retrieved_at < self.as_of:
            raise ValueError("capacity source was retrieved before evidence time")
        return self


class CapacityMetricsV1(ContractModel):
    order_notional: PositiveDecimal
    daily_slice_notional: PositiveDecimal
    daily_turnover_participation: NonNegativeDecimal
    top_of_book_participation: NonNegativeDecimal
    minimum_execution_days: PositiveInt
    estimated_impact_bps: NonNegativeDecimal
    half_spread_bps: NonNegativeDecimal
    impact_ex_spread_bps: NonNegativeDecimal
    maximum_notional_by_daily_turnover: NonNegativeDecimal
    maximum_notional_by_top_of_book: NonNegativeDecimal
    maximum_notional_by_impact: NonNegativeDecimal
    safe_notional_for_requested_window: NonNegativeDecimal
    safe_lots_for_requested_window: NonNegativeInt
    requested_notional_within_safe_capacity: bool

    @model_validator(mode="after")
    def validate_metrics(self) -> CapacityMetricsV1:
        if self.estimated_impact_bps != (
            self.half_spread_bps + self.impact_ex_spread_bps
        ):
            raise ValueError("capacity impact components do not reconcile")
        expected_safe = min(
            self.maximum_notional_by_daily_turnover,
            self.maximum_notional_by_top_of_book,
            self.maximum_notional_by_impact,
        )
        if self.safe_notional_for_requested_window != expected_safe:
            raise ValueError("capacity safe notional does not reconcile")
        expected_within = self.order_notional <= self.safe_notional_for_requested_window
        if self.requested_notional_within_safe_capacity is not expected_within:
            raise ValueError("capacity safe-notional status is inconsistent")
        return self


class CapacityAssessmentV1(ContractModel):
    schema_name: Literal["market_capacity_assessment"] = "market_capacity_assessment"
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: CapacityStatus
    capacity_ready: bool
    request: CapacityOrderRequestV1
    evidence: CapacityEvidenceV1
    policy: CapacityPolicyV1
    market_decision_ready: bool
    metrics: CapacityMetricsV1
    blockers: tuple[CapacityBlocker, ...] = ()
    warnings: tuple[CapacityWarning, ...] = ()
    capacity_model: Literal["adv_depth_square_root_proxy"] = (
        "adv_depth_square_root_proxy"
    )
    impact_is_estimate: Literal[True] = True
    execution_price_predicted: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_assessment(self) -> CapacityAssessmentV1:
        if self.request.instrument_key != self.evidence.instrument_key:
            raise ValueError("capacity assessment instrument mismatch")
        if self.request.currency != self.evidence.currency:
            raise ValueError("capacity assessment currency mismatch")
        if self.request.lot_size != self.evidence.lot_size:
            raise ValueError("capacity assessment lot size mismatch")
        if self.request.reference_price != self.evidence.reference_price:
            raise ValueError("capacity assessment reference price mismatch")
        if self.metrics.order_notional != self.request.order_notional:
            raise ValueError("capacity assessment order notional mismatch")

        expected_slice = self.request.order_notional / Decimal(
            self.request.intended_execution_days
        )
        if self.metrics.daily_slice_notional != expected_slice:
            raise ValueError("capacity daily slice does not reconcile")
        if self.metrics.daily_turnover_participation != (
            expected_slice / self.evidence.average_daily_turnover_notional
        ):
            raise ValueError("capacity daily participation does not reconcile")
        if self.metrics.top_of_book_participation != (
            expected_slice / self.evidence.top_of_book_depth_notional
        ):
            raise ValueError("capacity top-of-book participation does not reconcile")

        expected_days = int(
            (
                self.request.order_notional
                / (
                    self.evidence.average_daily_turnover_notional
                    * self.policy.maximum_daily_turnover_participation
                )
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        if self.metrics.minimum_execution_days != max(1, expected_days):
            raise ValueError("capacity minimum execution days do not reconcile")

        lot_notional = self.request.reference_price * Decimal(self.request.lot_size)
        expected_safe_lots = int(
            (
                self.metrics.safe_notional_for_requested_window / lot_notional
            ).to_integral_value(rounding=ROUND_FLOOR)
        )
        if self.metrics.safe_lots_for_requested_window != expected_safe_lots:
            raise ValueError("capacity safe lots do not reconcile")

        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("capacity blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("capacity warnings must be unique")
        expected_ready = not self.blockers
        if self.capacity_ready is not expected_ready:
            raise ValueError("capacity readiness is inconsistent")
        expected_status = CapacityStatus.READY if expected_ready else CapacityStatus.REJECTED
        if self.status is not expected_status:
            raise ValueError("capacity status is inconsistent")
        market_blocked = CapacityBlocker.MARKET_NOT_READY in self.blockers
        if self.market_decision_ready is market_blocked:
            raise ValueError("market readiness blocker is inconsistent")
        return self
