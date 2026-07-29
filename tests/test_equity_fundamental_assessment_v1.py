from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.common import (
    Completeness,
    DataQuality,
    QualityMetadata,
)
from omni_cio.contracts.v1.equity_fundamentals import (
    EquityAccountingStandard,
    EquityFundamentalBlocker,
    EquityFundamentalEvidenceV1,
    EquityFundamentalMetricsV1,
    EquityFundamentalPolicyV1,
    EquityFundamentalStatus,
    EquityFundamentalWarning,
    EquityReportingPeriodKind,
)
from omni_cio.contracts.v1.market import (
    ComponentStateV1,
    ComponentStatus,
    InstrumentReferenceV1,
    MarketLiquidityV1,
    MarketQuoteV1,
    MarketResearchBundleV1,
    MarketResearchMetadataV1,
    MarketSourceV1,
    SourceAuthority,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.market.equity_fundamentals_v1 import assess_equity_fundamentals


NOW = datetime(2026, 7, 29, 14, 0, tzinfo=timezone.utc)
KEY = "uid:equity-a"


def _source(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    retrieved_at: datetime = NOW,
    provider: str = "synthetic-official-source",
) -> MarketSourceV1:
    return MarketSourceV1(
        provider=provider,
        authority=authority,
        retrieved_at=retrieved_at,
        source_id="source-record-1",
    )


def _state(
    *,
    count: int,
    status: ComponentStatus = ComponentStatus.OK,
    checked_at: datetime | None = NOW,
) -> ComponentStateV1:
    source = _source() if status in {ComponentStatus.OK, ComponentStatus.DEGRADED} else None
    return ComponentStateV1(
        status=status,
        source=source,
        checked_at=checked_at,
        record_count=count,
    )


def _bundle(
    *,
    instrument_type: InstrumentType = InstrumentType.SHARE,
    currency: str = "RUB",
    stable_key: str = KEY,
    quote_as_of: datetime = NOW,
    quote_authority: SourceAuthority = SourceAuthority.OFFICIAL,
) -> MarketResearchBundleV1:
    not_applicable = ComponentStateV1(
        status=ComponentStatus.NOT_APPLICABLE,
        record_count=0,
    )
    return MarketResearchBundleV1(
        metadata=MarketResearchMetadataV1(
            retrieved_at=NOW,
            quality=QualityMetadata(
                quality=DataQuality.VERIFIED,
                completeness=Completeness.COMPLETE,
            ),
        ),
        instrument_key=stable_key,
        reference_state=_state(count=1),
        quote_state=_state(count=1),
        liquidity_state=_state(count=1),
        ratings_state=not_applicable,
        bond_metrics_state=not_applicable,
        events_state=_state(count=0),
        reference=InstrumentReferenceV1(
            stable_key=stable_key,
            name="Synthetic Equity",
            ticker="SYNE",
            uid="equity-a",
            instrument_type=instrument_type,
            currency=currency,
            lot=10,
            issuer_id="issuer-a",
            sector="technology",
            source=_source(authority=SourceAuthority.PRIMARY),
        ),
        quote=MarketQuoteV1(
            instrument_key=stable_key,
            currency=currency,
            as_of=quote_as_of,
            source=_source(authority=quote_authority),
            last_price=Decimal("100"),
            best_bid=Decimal("99"),
            best_ask=Decimal("101"),
        ),
        liquidity=MarketLiquidityV1(
            instrument_key=stable_key,
            currency=currency,
            as_of=NOW,
            source=_source(),
            best_bid=Decimal("99"),
            best_ask=Decimal("101"),
            spread_absolute=Decimal("2"),
            spread_bps=Decimal("200"),
            bid_depth=Decimal("100000"),
            ask_depth=Decimal("120000"),
            turnover_24h=Decimal("5000000"),
        ),
        ratings=(),
        bond_metrics=None,
        events=(),
        trading_methods=False,
    )


def _evidence(
    *,
    instrument_key: str = KEY,
    currency: str = "RUB",
    report_authority: SourceAuthority = SourceAuthority.OFFICIAL,
    market_cap_authority: SourceAuthority = SourceAuthority.REGULATED,
    published_at: datetime = NOW - timedelta(days=90),
    market_cap_as_of: datetime = NOW,
    revenue: str = "1000",
    operating_profit: str | None = "180",
    ebitda: str | None = "220",
    net_income: str = "120",
    operating_cash_flow: str = "170",
    capex: str = "50",
    free_cash_flow: str = "120",
    debt: str = "300",
    cash: str = "100",
    equity: str = "600",
    dividends: str | None = "60",
    market_cap: str = "2400",
    shares_outstanding: str | None = "24",
) -> EquityFundamentalEvidenceV1:
    return EquityFundamentalEvidenceV1(
        instrument_key=instrument_key,
        currency=currency,
        accounting_standard=EquityAccountingStandard.IFRS,
        period_kind=EquityReportingPeriodKind.TTM,
        period_start=date(2025, 7, 1),
        period_end=date(2026, 6, 30),
        published_at=published_at,
        report_source=_source(
            authority=report_authority,
            retrieved_at=max(NOW, published_at),
            provider="synthetic-issuer-disclosure",
        ),
        revenue=Decimal(revenue),
        operating_profit=(Decimal(operating_profit) if operating_profit is not None else None),
        ebitda=Decimal(ebitda) if ebitda is not None else None,
        net_income=Decimal(net_income),
        operating_cash_flow=Decimal(operating_cash_flow),
        capital_expenditure=Decimal(capex),
        free_cash_flow=Decimal(free_cash_flow),
        total_debt=Decimal(debt),
        cash_and_equivalents=Decimal(cash),
        total_equity=Decimal(equity),
        dividends_paid=Decimal(dividends) if dividends is not None else None,
        market_cap=Decimal(market_cap),
        market_cap_as_of=market_cap_as_of,
        market_cap_source=_source(
            authority=market_cap_authority,
            retrieved_at=max(NOW, market_cap_as_of),
            provider="synthetic-exchange-capitalization",
        ),
        shares_outstanding=(
            Decimal(shares_outstanding) if shares_outstanding is not None else None
        ),
    )


def test_ready_equity_assessment_reconciles_exact_decimal_metrics() -> None:
    result = assess_equity_fundamentals(
        _bundle(),
        _evidence(),
        assessed_at=NOW,
    )

    assert result.status is EquityFundamentalStatus.READY
    assert result.analysis_ready is True
    assert result.blockers == ()
    assert result.metrics.net_debt == Decimal("200")
    assert result.metrics.net_margin == Decimal("0.12")
    assert result.metrics.operating_margin == Decimal("0.18")
    assert result.metrics.ebitda_margin == Decimal("0.22")
    assert result.metrics.free_cash_flow_margin == Decimal("0.12")
    assert result.metrics.net_debt_to_ebitda == Decimal("200") / Decimal("220")
    assert result.metrics.earnings_yield == Decimal("0.05")
    assert result.metrics.free_cash_flow_yield == Decimal("0.05")
    assert result.metrics.price_to_earnings == Decimal("20")
    assert result.metrics.price_to_book == Decimal("4")
    assert result.metrics.dividend_payout_ratio == Decimal("0.5")
    assert result.metrics.unavailable_metrics == ()
    assert result.no_price_forecast is True
    assert result.no_investment_recommendation is True
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_negative_results_remain_analyzable_without_fabricated_positive_multiples() -> None:
    evidence = _evidence(
        operating_profit="-20",
        ebitda="-10",
        net_income="-40",
        operating_cash_flow="-10",
        capex="20",
        free_cash_flow="-30",
        equity="-50",
        dividends=None,
        shares_outstanding=None,
    )

    result = assess_equity_fundamentals(_bundle(), evidence, assessed_at=NOW)

    assert result.status is EquityFundamentalStatus.READY
    assert result.metrics.price_to_earnings is None
    assert result.metrics.price_to_book is None
    assert result.metrics.net_debt_to_ebitda is None
    assert result.metrics.dividend_payout_ratio is None
    assert "price_to_earnings" in result.metrics.unavailable_metrics
    assert "price_to_book" in result.metrics.unavailable_metrics
    assert EquityFundamentalWarning.NEGATIVE_NET_INCOME in result.warnings
    assert EquityFundamentalWarning.NEGATIVE_FREE_CASH_FLOW in result.warnings
    assert EquityFundamentalWarning.NON_POSITIVE_EBITDA in result.warnings
    assert EquityFundamentalWarning.NEGATIVE_EQUITY in result.warnings


def test_missing_optional_metrics_are_explicit_not_guessed() -> None:
    result = assess_equity_fundamentals(
        _bundle(),
        _evidence(
            operating_profit=None,
            ebitda=None,
            dividends=None,
            shares_outstanding=None,
        ),
        assessed_at=NOW,
    )

    assert result.analysis_ready is True
    assert result.metrics.operating_margin is None
    assert result.metrics.ebitda_margin is None
    assert result.metrics.net_debt_to_ebitda is None
    assert result.metrics.dividend_payout_ratio is None
    assert EquityFundamentalWarning.OPERATING_PROFIT_NOT_PROVIDED in result.warnings
    assert EquityFundamentalWarning.EBITDA_NOT_PROVIDED in result.warnings
    assert EquityFundamentalWarning.DIVIDENDS_NOT_PROVIDED in result.warnings
    assert EquityFundamentalWarning.SHARES_OUTSTANDING_NOT_PROVIDED in result.warnings


def test_identity_currency_and_instrument_type_fail_closed() -> None:
    wrong_identity = assess_equity_fundamentals(
        _bundle(),
        _evidence(instrument_key="uid:other"),
        assessed_at=NOW,
    )
    assert EquityFundamentalBlocker.INSTRUMENT_IDENTITY_MISMATCH in wrong_identity.blockers

    wrong_currency = assess_equity_fundamentals(
        _bundle(currency="RUB"),
        _evidence(currency="USD"),
        assessed_at=NOW,
    )
    assert EquityFundamentalBlocker.CURRENCY_MISMATCH in wrong_currency.blockers

    fund_bundle = _bundle(instrument_type=InstrumentType.ETF)
    not_share = assess_equity_fundamentals(
        fund_bundle,
        _evidence(),
        assessed_at=NOW,
    )
    assert EquityFundamentalBlocker.NOT_A_SHARE in not_share.blockers
    assert not_share.status is EquityFundamentalStatus.REJECTED


def test_untrusted_and_stale_evidence_is_rejected() -> None:
    evidence = _evidence(
        report_authority=SourceAuthority.SECONDARY,
        market_cap_authority=SourceAuthority.UNTRUSTED,
        published_at=NOW - timedelta(days=600),
        market_cap_as_of=NOW - timedelta(days=2),
    )

    result = assess_equity_fundamentals(_bundle(), evidence, assessed_at=NOW)

    assert result.analysis_ready is False
    assert EquityFundamentalBlocker.UNTRUSTED_REPORT_SOURCE in result.blockers
    assert EquityFundamentalBlocker.UNTRUSTED_MARKET_CAP_SOURCE in result.blockers
    assert EquityFundamentalBlocker.REPORT_STALE in result.blockers
    assert EquityFundamentalBlocker.MARKET_CAP_STALE in result.blockers


def test_future_report_market_cap_and_period_are_rejected() -> None:
    evidence = _evidence(
        published_at=NOW + timedelta(minutes=2),
        market_cap_as_of=NOW + timedelta(minutes=2),
    ).model_copy(update={"period_end": date(2026, 8, 1)})

    result = assess_equity_fundamentals(_bundle(), evidence, assessed_at=NOW)

    assert EquityFundamentalBlocker.REPORT_FUTURE_TIMESTAMP in result.blockers
    assert EquityFundamentalBlocker.MARKET_CAP_FUTURE_TIMESTAMP in result.blockers
    assert EquityFundamentalBlocker.REPORT_PERIOD_FUTURE in result.blockers


def test_market_research_failure_propagates_without_hiding_fundamental_math() -> None:
    result = assess_equity_fundamentals(
        _bundle(quote_as_of=NOW - timedelta(minutes=10)),
        _evidence(),
        assessed_at=NOW,
    )

    assert EquityFundamentalBlocker.MARKET_RESEARCH_NOT_READY in result.blockers
    assert result.analysis_ready is False
    assert result.metrics.net_margin == Decimal("0.12")


def test_custom_policy_controls_report_and_market_cap_freshness() -> None:
    evidence = _evidence(
        published_at=NOW - timedelta(days=31),
        market_cap_as_of=NOW - timedelta(seconds=61),
    )
    policy = EquityFundamentalPolicyV1(
        max_report_age_days=30,
        max_market_cap_age_seconds=60,
    )

    result = assess_equity_fundamentals(
        _bundle(),
        evidence,
        policy=policy,
        assessed_at=NOW,
    )

    assert EquityFundamentalBlocker.REPORT_STALE in result.blockers
    assert EquityFundamentalBlocker.MARKET_CAP_STALE in result.blockers


def test_evidence_rejects_unreconciled_free_cash_flow_and_time_provenance() -> None:
    payload = _evidence().model_dump()
    payload["free_cash_flow"] = Decimal("121")
    with pytest.raises(ValidationError, match="free cash flow"):
        EquityFundamentalEvidenceV1.model_validate(payload)

    payload = _evidence().model_dump()
    payload["market_cap_source"]["retrieved_at"] = NOW - timedelta(minutes=1)
    payload["market_cap_as_of"] = NOW
    with pytest.raises(ValidationError, match="market cap was retrieved before"):
        EquityFundamentalEvidenceV1.model_validate(payload)


def test_metrics_contract_rejects_tampered_reconciliation() -> None:
    metrics = assess_equity_fundamentals(
        _bundle(),
        _evidence(),
        assessed_at=NOW,
    ).metrics
    payload = metrics.model_dump()
    payload["net_debt"] = Decimal("201")
    with pytest.raises(ValidationError, match="net debt"):
        EquityFundamentalMetricsV1.model_validate(payload)
