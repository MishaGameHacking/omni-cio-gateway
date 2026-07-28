from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from omni_cio.analytics import (
    AdvancedPortfolioAnalyticsError,
    build_advanced_portfolio_analytics,
)
from omni_cio.contracts.v1 import (
    AccountReference,
    Completeness,
    ContractMetadata,
    CurrencyTotalsV1,
    DataQuality,
    InstrumentIdentity,
    InstrumentType,
    Money,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    QualityMetadata,
    SourceReference,
    ValuationBasis,
)


NOW = datetime(2026, 7, 28, 18, 50, tzinfo=timezone.utc)


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="portfolio_snapshot",
        retrieved_at=NOW,
        account=AccountReference(masked_id="***3118"),
        provenance=(
            SourceReference(
                provider="t-invest",
                operation="get_portfolio_market_snapshot",
                retrieved_at=NOW,
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _position(*, instrument_currency: str, value_currency: str, value: str) -> PortfolioPositionV1:
    return PortfolioPositionV1(
        instrument=InstrumentIdentity(
            name="Synthetic share",
            uid="uid-synthetic-share",
            instrument_type=InstrumentType.SHARE,
            currency=instrument_currency,
            lot=1,
        ),
        quantity_units=Decimal("1"),
        quantity_lots=Decimal("1"),
        valuation=PositionValuation(
            basis=ValuationBasis.LAST_PRICE,
            currency=value_currency,
            as_of=NOW,
            unit_price=Decimal(value),
            market_value=Money(
                amount=Decimal(value),
                currency=value_currency,
            ),
        ),
    )


def test_instrument_and_valuation_currency_mismatch_is_rejected() -> None:
    snapshot = PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=(
            _position(
                instrument_currency="RUB",
                value_currency="USD",
                value="100",
            ),
        ),
        totals_by_currency=(
            CurrencyTotalsV1(
                currency="USD",
                cash=Decimal("0"),
                securities=Decimal("100"),
                accrued_interest=Decimal("0"),
                total=Decimal("100"),
            ),
        ),
    )

    with pytest.raises(
        AdvancedPortfolioAnalyticsError,
        match="PORTFOLIO_POSITION_CURRENCY_MISMATCH",
    ):
        build_advanced_portfolio_analytics(snapshot, retrieved_at=NOW)


def test_negative_long_position_value_is_rejected() -> None:
    snapshot = PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=(
            _position(
                instrument_currency="RUB",
                value_currency="RUB",
                value="-100",
            ),
        ),
        totals_by_currency=(
            CurrencyTotalsV1(
                currency="RUB",
                cash=Decimal("200"),
                securities=Decimal("-100"),
                accrued_interest=Decimal("0"),
                total=Decimal("100"),
            ),
        ),
    )

    with pytest.raises(
        AdvancedPortfolioAnalyticsError,
        match="PORTFOLIO_POSITION_VALUE_NEGATIVE",
    ):
        build_advanced_portfolio_analytics(snapshot, retrieved_at=NOW)
