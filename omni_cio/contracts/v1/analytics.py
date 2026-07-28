from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
)
from omni_cio.contracts.v1.portfolio import InstrumentType


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NegativeShock = Annotated[
    Decimal,
    Field(gt=Decimal("-1"), lt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
_WEIGHT_TOLERANCE = Decimal("1e-24")


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= _WEIGHT_TOLERANCE


class MissingDataCode(StrEnum):
    ISSUER = "issuer"
    SECTOR = "sector"
    LIQUIDITY = "liquidity"
    HISTORICAL_PRICES = "historical_prices"
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    BOND_DURATION = "bond_duration"
    BOND_MATURITY = "bond_maturity"
    CREDIT_RATING = "credit_rating"
    TAX_BASIS = "tax_basis"


class MissingDataV1(ContractModel):
    code: MissingDataCode
    message: Annotated[str, Field(min_length=1, max_length=512)]
    affected_calculations: tuple[
        Annotated[str, Field(min_length=1, max_length=128)], ...
    ]


class PositionWeightV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    name: Annotated[str, Field(min_length=1, max_length=256)]
    instrument_type: InstrumentType
    currency: CurrencyCode
    full_market_value: NonNegativeDecimal
    portfolio_weight: UnitInterval
    invested_weight: UnitInterval
    ticker: Annotated[str | None, Field(max_length=32)] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class AssetClassAllocationV1(ContractModel):
    instrument_type: InstrumentType
    full_market_value: NonNegativeDecimal
    position_count: NonNegativeInt
    portfolio_weight: UnitInterval
    invested_weight: UnitInterval


class ConcentrationMetricsV1(ContractModel):
    top_1_portfolio_weight: UnitInterval
    top_5_portfolio_weight: UnitInterval
    top_1_invested_weight: UnitInterval
    top_5_invested_weight: UnitInterval
    hhi_invested: UnitInterval
    effective_position_count: NonNegativeDecimal

    @model_validator(mode="after")
    def validate_concentration(self) -> ConcentrationMetricsV1:
        if self.top_1_portfolio_weight > self.top_5_portfolio_weight:
            raise ValueError("top-1 portfolio weight cannot exceed top-5")
        if self.top_1_invested_weight > self.top_5_invested_weight:
            raise ValueError("top-1 invested weight cannot exceed top-5")
        if self.hhi_invested == 0 and self.effective_position_count != 0:
            raise ValueError("zero HHI requires zero effective position count")
        if self.hhi_invested > 0:
            expected = Decimal("1") / self.hhi_invested
            if not _close(self.effective_position_count, expected):
                raise ValueError("effective position count must equal one divided by HHI")
        return self


class StressScenarioV1(ContractModel):
    shock: NegativeShock
    starting_invested_value: NonNegativeDecimal
    starting_total: NonNegativeDecimal
    invested_change: FiniteDecimal
    portfolio_change: FiniteDecimal
    stressed_invested_value: NonNegativeDecimal
    stressed_total: NonNegativeDecimal
    portfolio_change_ratio: Annotated[
        Decimal,
        Field(ge=Decimal("-1"), le=Decimal("0"), allow_inf_nan=False),
    ]

    @model_validator(mode="after")
    def validate_scenario(self) -> StressScenarioV1:
        expected_change = self.starting_invested_value * self.shock
        if self.invested_change != expected_change:
            raise ValueError("invested_change does not match shock")
        if self.portfolio_change != expected_change:
            raise ValueError("portfolio_change must equal invested change")
        if self.stressed_invested_value != self.starting_invested_value + expected_change:
            raise ValueError("stressed invested value does not reconcile")
        if self.stressed_total != self.starting_total + expected_change:
            raise ValueError("stressed total does not reconcile")
        expected_ratio = (
            expected_change / self.starting_total
            if self.starting_total > 0
            else Decimal("0")
        )
        if not _close(self.portfolio_change_ratio, expected_ratio):
            raise ValueError("portfolio change ratio does not reconcile")
        return self


class CurrencyPortfolioAnalyticsV1(ContractModel):
    currency: CurrencyCode
    cash: NonNegativeDecimal
    clean_securities: NonNegativeDecimal
    accrued_interest: NonNegativeDecimal
    invested_value: NonNegativeDecimal
    total: NonNegativeDecimal
    cash_weight: UnitInterval
    invested_weight: UnitInterval
    position_count: NonNegativeInt
    valued_position_count: NonNegativeInt
    positions: tuple[PositionWeightV1, ...]
    asset_classes: tuple[AssetClassAllocationV1, ...]
    concentration: ConcentrationMetricsV1
    stress_scenarios: tuple[StressScenarioV1, ...]

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_currency_analytics(self) -> CurrencyPortfolioAnalyticsV1:
        if self.invested_value != self.clean_securities + self.accrued_interest:
            raise ValueError("invested value must include clean value and accrued interest")
        if self.total != self.cash + self.invested_value:
            raise ValueError("portfolio total must equal cash plus invested value")
        if self.valued_position_count != len(self.positions):
            raise ValueError("valued position count does not match positions")
        if self.position_count != self.valued_position_count:
            raise ValueError("advanced analytics requires every position to be valued")

        position_value = sum(
            (position.full_market_value for position in self.positions),
            Decimal("0"),
        )
        if position_value != self.invested_value:
            raise ValueError("position values do not reconcile with invested value")

        if self.total > 0:
            if not _close(self.cash_weight + self.invested_weight, Decimal("1")):
                raise ValueError("cash and invested weights must sum to one")
        elif self.cash_weight != 0 or self.invested_weight != 0:
            raise ValueError("empty currency portfolio must have zero weights")

        if self.invested_value > 0:
            invested_weights = sum(
                (position.invested_weight for position in self.positions),
                Decimal("0"),
            )
            if not _close(invested_weights, Decimal("1")):
                raise ValueError("invested position weights must sum to one")
        elif any(position.invested_weight != 0 for position in self.positions):
            raise ValueError("zero invested value requires zero position weights")

        allocation_value = sum(
            (row.full_market_value for row in self.asset_classes),
            Decimal("0"),
        )
        if allocation_value != self.invested_value:
            raise ValueError("asset class values do not reconcile")
        if sum(row.position_count for row in self.asset_classes) != self.position_count:
            raise ValueError("asset class position counts do not reconcile")

        ordered_values = [position.full_market_value for position in self.positions]
        if ordered_values != sorted(ordered_values, reverse=True):
            raise ValueError("positions must be sorted by descending market value")
        return self


class AdvancedPortfolioAnalyticsV1(ContractModel):
    metadata: ContractMetadata
    source_snapshot_retrieved_at: datetime
    by_currency: tuple[CurrencyPortfolioAnalyticsV1, ...]
    missing_data: tuple[MissingDataV1, ...]
    no_cross_currency_aggregation: bool
    decision_ready: bool

    @field_validator("source_snapshot_retrieved_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source snapshot timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_analytics(self) -> AdvancedPortfolioAnalyticsV1:
        if self.metadata.schema_name != "advanced_portfolio_analytics":
            raise ValueError("schema_name must be advanced_portfolio_analytics")
        currencies = [row.currency for row in self.by_currency]
        if len(currencies) != len(set(currencies)):
            raise ValueError("currency analytics rows must be unique")
        if not self.no_cross_currency_aggregation:
            raise ValueError("cross-currency aggregation is forbidden")
        if not self.decision_ready:
            raise ValueError("advanced analytics contract requires verified source data")
        missing_codes = [row.code for row in self.missing_data]
        if len(missing_codes) != len(set(missing_codes)):
            raise ValueError("missing-data codes must be unique")
        return self
