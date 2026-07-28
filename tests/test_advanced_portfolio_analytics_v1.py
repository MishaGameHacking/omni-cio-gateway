from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.analytics import (
    AdvancedPortfolioAnalyticsError,
    build_advanced_portfolio_analytics,
)
from omni_cio.contracts.v1 import (
    AccountReference,
    CashBalanceV1,
    Completeness,
    ContractMetadata,
    CurrencyTotalsV1,
    DataQuality,
    InstrumentIdentity,
    InstrumentType,
    MissingDataCode,
    Money,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    QualityMetadata,
    SourceReference,
    ValuationBasis,
)


NOW = datetime(2026, 7, 28, 18, 30, tzinfo=timezone.utc)


def _metadata(
    *,
    quality: DataQuality = DataQuality.VERIFIED,
    completeness: Completeness = Completeness.COMPLETE,
) -> ContractMetadata:
    return ContractMetadata(
        schema_name="portfolio_snapshot",
        retrieved_at=NOW,
        account=AccountReference(masked_id="***3118", account_type="ИИС"),
        provenance=(
            SourceReference(
                provider="t-invest",
                operation="get_portfolio_market_snapshot",
                retrieved_at=NOW,
                source_id="3.9.1",
            ),
        ),
        quality=QualityMetadata(
            quality=quality,
            completeness=completeness,
        ),
    )


def _position(
    *,
    name: str,
    uid: str,
    instrument_type: InstrumentType,
    currency: str,
    clean_value: str,
    accrued_interest: str = "0",
) -> PortfolioPositionV1:
    accrued = Decimal(accrued_interest)
    return PortfolioPositionV1(
        instrument=InstrumentIdentity(
            name=name,
            ticker=name[:4].upper(),
            uid=uid,
            instrument_type=instrument_type,
            currency=currency,
            lot=1,
        ),
        quantity_units=Decimal("1"),
        quantity_lots=Decimal("1"),
        valuation=PositionValuation(
            basis=ValuationBasis.LAST_PRICE,
            currency=currency,
            as_of=NOW,
            unit_price=Decimal(clean_value),
            market_value=Money(
                amount=Decimal(clean_value),
                currency=currency,
            ),
            accrued_interest=(
                Money(amount=accrued, currency=currency) if accrued else None
            ),
        ),
    )


def _rub_snapshot() -> PortfolioSnapshotV1:
    return PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=(
            _position(
                name="Share",
                uid="uid-share",
                instrument_type=InstrumentType.SHARE,
                currency="RUB",
                clean_value="600",
            ),
            _position(
                name="Bond",
                uid="uid-bond",
                instrument_type=InstrumentType.BOND,
                currency="RUB",
                clean_value="300",
                accrued_interest="100",
            ),
        ),
        cash_balances=(
            CashBalanceV1(
                reported=Money(amount=Decimal("1000"), currency="RUB"),
                as_of=NOW,
            ),
        ),
        totals_by_currency=(
            CurrencyTotalsV1(
                currency="RUB",
                cash=Decimal("1000"),
                securities=Decimal("900"),
                accrued_interest=Decimal("100"),
                total=Decimal("2000"),
            ),
        ),
    )


def test_mixed_portfolio_concentration_allocations_and_stress() -> None:
    result = build_advanced_portfolio_analytics(
        _rub_snapshot(),
        retrieved_at=NOW,
    )

    row = result.by_currency[0]
    assert row.currency == "RUB"
    assert row.cash_weight == Decimal("0.5")
    assert row.invested_weight == Decimal("0.5")
    assert row.invested_value == Decimal("1000")
    assert row.positions[0].name == "Share"
    assert row.positions[0].portfolio_weight == Decimal("0.3")
    assert row.positions[0].invested_weight == Decimal("0.6")
    assert row.positions[1].full_market_value == Decimal("400")
    assert row.concentration.top_1_portfolio_weight == Decimal("0.3")
    assert row.concentration.top_5_portfolio_weight == Decimal("0.5")
    assert row.concentration.hhi_invested == Decimal("0.52")
    assert row.concentration.effective_position_count == Decimal("1") / Decimal(
        "0.52"
    )
    assert {
        allocation.instrument_type: allocation.full_market_value
        for allocation in row.asset_classes
    } == {
        InstrumentType.SHARE: Decimal("600"),
        InstrumentType.BOND: Decimal("400"),
    }

    scenario = row.stress_scenarios[0]
    assert scenario.shock == Decimal("-0.10")
    assert scenario.portfolio_change == Decimal("-100.00")
    assert scenario.stressed_total == Decimal("1900.00")
    assert scenario.portfolio_change_ratio == Decimal("-0.05")
    assert result.decision_ready is True
    assert result.no_cross_currency_aggregation is True


def test_bond_missing_data_is_explicit() -> None:
    result = build_advanced_portfolio_analytics(_rub_snapshot(), retrieved_at=NOW)
    codes = {row.code for row in result.missing_data}

    assert MissingDataCode.ISSUER in codes
    assert MissingDataCode.SECTOR in codes
    assert MissingDataCode.LIQUIDITY in codes
    assert MissingDataCode.BOND_DURATION in codes
    assert MissingDataCode.BOND_MATURITY in codes
    assert MissingDataCode.CREDIT_RATING in codes
    assert MissingDataCode.TAX_BASIS in codes


def test_multi_currency_rows_are_kept_separate() -> None:
    rub = _rub_snapshot()
    usd_position = _position(
        name="ETF",
        uid="uid-usd-etf",
        instrument_type=InstrumentType.ETF,
        currency="USD",
        clean_value="100",
    )
    snapshot = PortfolioSnapshotV1(
        metadata=rub.metadata,
        positions=(*rub.positions, usd_position),
        cash_balances=(*rub.cash_balances,),
        totals_by_currency=(
            *rub.totals_by_currency,
            CurrencyTotalsV1(
                currency="USD",
                cash=Decimal("100"),
                securities=Decimal("100"),
                accrued_interest=Decimal("0"),
                total=Decimal("200"),
            ),
        ),
    )

    result = build_advanced_portfolio_analytics(snapshot, retrieved_at=NOW)

    assert [row.currency for row in result.by_currency] == ["RUB", "USD"]
    usd = result.by_currency[1]
    assert usd.total == Decimal("200")
    assert usd.cash_weight == Decimal("0.5")
    assert usd.positions[0].instrument_type == InstrumentType.ETF


def test_cash_only_portfolio_has_zero_concentration_and_stress_loss() -> None:
    snapshot = PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=(),
        cash_balances=(
            CashBalanceV1(
                reported=Money(amount=Decimal("500"), currency="RUB"),
                as_of=NOW,
            ),
        ),
        totals_by_currency=(
            CurrencyTotalsV1(
                currency="RUB",
                cash=Decimal("500"),
                securities=Decimal("0"),
                accrued_interest=Decimal("0"),
                total=Decimal("500"),
            ),
        ),
    )

    result = build_advanced_portfolio_analytics(snapshot, retrieved_at=NOW)
    row = result.by_currency[0]

    assert row.cash_weight == Decimal("1")
    assert row.invested_weight == Decimal("0")
    assert row.positions == ()
    assert row.asset_classes == ()
    assert row.concentration.hhi_invested == Decimal("0")
    assert row.stress_scenarios[0].portfolio_change == Decimal("0.00")


def test_three_equal_positions_tolerate_decimal_repetition() -> None:
    positions = tuple(
        _position(
            name=f"Share {index}",
            uid=f"uid-share-{index}",
            instrument_type=InstrumentType.SHARE,
            currency="RUB",
            clean_value="1",
        )
        for index in range(3)
    )
    snapshot = PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=positions,
        totals_by_currency=(
            CurrencyTotalsV1(
                currency="RUB",
                cash=Decimal("0"),
                securities=Decimal("3"),
                accrued_interest=Decimal("0"),
                total=Decimal("3"),
            ),
        ),
    )

    result = build_advanced_portfolio_analytics(snapshot, retrieved_at=NOW)

    row = result.by_currency[0]
    assert row.concentration.hhi_invested == Decimal("3") * (
        Decimal("1") / Decimal("3")
    ) ** 2
    assert row.concentration.top_5_invested_weight == sum(
        (position.invested_weight for position in row.positions),
        Decimal("0"),
    )


def test_partial_or_unvalued_snapshot_is_rejected() -> None:
    partial = PortfolioSnapshotV1(
        metadata=_metadata(
            quality=DataQuality.PARTIAL,
            completeness=Completeness.PARTIAL,
        ),
    )
    with pytest.raises(
        AdvancedPortfolioAnalyticsError,
        match="PORTFOLIO_SNAPSHOT_NOT_DECISION_READY",
    ):
        build_advanced_portfolio_analytics(partial, retrieved_at=NOW)

    unvalued = PortfolioSnapshotV1(
        metadata=_metadata(),
        positions=(
            PortfolioPositionV1(
                instrument=InstrumentIdentity(
                    name="Unknown",
                    uid="uid-unvalued",
                    instrument_type=InstrumentType.SHARE,
                    currency="RUB",
                    lot=1,
                ),
                quantity_units=Decimal("1"),
                quantity_lots=Decimal("1"),
            ),
        ),
        totals_by_currency=(
            CurrencyTotalsV1(
                currency="RUB",
                cash=Decimal("0"),
                securities=Decimal("0"),
                accrued_interest=Decimal("0"),
                total=Decimal("0"),
            ),
        ),
    )
    with pytest.raises(
        AdvancedPortfolioAnalyticsError,
        match="PORTFOLIO_POSITION_VALUATION_INCOMPLETE",
    ):
        build_advanced_portfolio_analytics(unvalued, retrieved_at=NOW)


def test_totals_and_currency_coverage_fail_closed() -> None:
    mismatched = _rub_snapshot().model_copy(
        update={
            "totals_by_currency": (
                CurrencyTotalsV1(
                    currency="RUB",
                    cash=Decimal("1000"),
                    securities=Decimal("899"),
                    accrued_interest=Decimal("100"),
                    total=Decimal("1999"),
                ),
            )
        }
    )
    with pytest.raises(
        AdvancedPortfolioAnalyticsError,
        match="PORTFOLIO_POSITION_TOTAL_RECONCILIATION_FAILED",
    ):
        build_advanced_portfolio_analytics(mismatched, retrieved_at=NOW)


def test_stress_inputs_and_contract_immutability() -> None:
    snapshot = _rub_snapshot()
    with pytest.raises(
        AdvancedPortfolioAnalyticsError,
        match="STRESS_SHOCKS_MUST_BE_UNIQUE",
    ):
        build_advanced_portfolio_analytics(
            snapshot,
            stress_shocks=(Decimal("-0.1"), Decimal("-0.1")),
            retrieved_at=NOW,
        )
    with pytest.raises(
        AdvancedPortfolioAnalyticsError,
        match="STRESS_SHOCK_OUT_OF_RANGE",
    ):
        build_advanced_portfolio_analytics(
            snapshot,
            stress_shocks=(Decimal("-1"),),
            retrieved_at=NOW,
        )

    result = build_advanced_portfolio_analytics(snapshot, retrieved_at=NOW)
    with pytest.raises(ValidationError):
        result.decision_ready = False  # type: ignore[misc]
