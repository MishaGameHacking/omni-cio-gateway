from __future__ import annotations

from datetime import UTC, datetime

from omnicio.broker import AnalysisSource, BrokerEvidenceSnapshot, BrokerObservationBundle
from omnicio.intelligence import build_tbank_evidence
from omnicio.portfolio import PortfolioAnalysis
from omnicio.tbank import (
    TBankAssetFundamental,
    TBankBondEvent,
    TBankInstrumentMetadata,
    TBankMoney,
    TBankPortfolio,
    TBankPortfolioPosition,
    TBankPositions,
)


def _bundle() -> BrokerObservationBundle:
    now = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    position = TBankPortfolioPosition(
        ticker="BOND",
        figi="FIGI-BOND",
        instrument_uid="bond-uid",
        instrument_type="bond",
        quantity="2",
        current_price=TBankMoney("RUB", "1000"),
        average_price=None,
        expected_yield_percent="0",
        daily_yield=None,
        current_nkd=None,
        blocked=False,
        blocked_lots="0",
    )
    metadata = TBankInstrumentMetadata(
        uid="bond-uid",
        figi="FIGI-BOND",
        asset_uid="issuer-asset",
        position_uid="",
        name="Test bond",
        ticker="BOND",
        isin="RU000TEST",
        instrument_type="bond",
        currency="RUB",
        class_code="TQCB",
        lot=1,
        sector="energy",
        country_of_risk="RU",
        for_qual_investor=False,
        for_iis=True,
        api_trade_available=True,
        buy_available=True,
        sell_available=True,
        required_tests=(),
    )
    return BrokerObservationBundle(
        account_id="account-1",
        account_name="Main",
        environment="prod",
        refreshed_at=now,
        portfolio=TBankPortfolio(
            total=TBankMoney("RUB", "2000"),
            expected_yield_percent="0",
            daily_yield=None,
            daily_yield_percent="0",
            asset_totals=(),
            positions=(position,),
        ),
        positions=TBankPositions(
            money=(TBankMoney("RUB", "100"),),
            blocked_money=(),
            limits_loading_in_progress=False,
        ),
        metadata=(metadata,),
        analysis=PortfolioAnalysis(
            status="observed",
            nav_rub="2100",
            rub_cash_total="100",
            rub_cash_blocked="0",
            rub_cash_unblocked="100",
            security_count=1,
            valued_security_count=1,
            sector_coverage_percent="100",
            classes=(),
            sectors=(),
            securities=(),
            observations=(),
        ),
        sources=(),
    )


def _sources(now: datetime) -> tuple[AnalysisSource, ...]:
    return (
        AnalysisSource(
            id="payout_calendar",
            name="calendar",
            url="https://developer.tbank.ru/invest/services/instruments/methods",
            methods=(),
            retrieved_at=now,
            status="received",
        ),
        AnalysisSource(
            id="issuer_events",
            name="events",
            url="https://developer.tbank.ru/invest/services/instruments/methods",
            methods=(),
            retrieved_at=now,
            status="received",
        ),
        AnalysisSource(
            id="fundamentals",
            name="fundamentals",
            url="https://developer.tbank.ru/invest/services/instruments/methods",
            methods=(),
            retrieved_at=now,
            status="received",
        ),
        AnalysisSource(
            id="credit_ratings",
            name="ratings",
            url="https://www.cbr.ru/finm_infrastructure/ra/",
            methods=(),
            retrieved_at=now,
            status="not_requested",
        ),
    )


def test_unknown_rating_stays_data_missing_even_with_fresh_fundamentals() -> None:
    now = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=now,
        dividends=(),
        coupons=(),
        bond_events=(),
        reports=(),
        fundamentals=(
            TBankAssetFundamental(
                asset_uid="issuer-asset",
                currency="RUB",
                revenue_ttm="100",
                ebitda_ttm="20",
                net_income_ttm="10",
                free_cash_flow_ttm="5",
                total_debt_mrq="30",
                total_debt_to_equity_mrq="0.3",
                total_debt_to_ebitda_mrq="1.5",
                net_debt_to_ebitda="1.2",
                current_ratio_mrq="1.5",
                fixed_charge_coverage_ratio_fy="4",
                net_interest_margin_mrq=None,
                roe="0.15",
                roa="0.08",
                fiscal_period_start_date=datetime(2025, 1, 1, tzinfo=UTC),
                fiscal_period_end_date=datetime(2025, 12, 31, tzinfo=UTC),
            ),
        ),
        sources=_sources(now),
    )

    documents, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    assert len(documents) == 1
    facts = {fact.fact_key: fact for fact in documents[0].facts}
    assert facts["revenue_ttm"].currency == "RUB"
    assert facts["revenue_ttm"].unit is None
    assert facts["total_debt_mrq"].currency == "RUB"
    assert facts["total_debt_to_ebitda_mrq"].currency is None
    assert facts["total_debt_to_ebitda_mrq"].unit == "ratio"
    assert facts["roe"].currency is None
    assert facts["roe"].unit == "ratio"
    assert assessments[0].state == "data_missing"
    assert assessments[0].rating_status == "data_missing"
    assert assessments[0].fundamental_status == "received"
    assert "credit_rating_feed_not_verified" in assessments[0].reasons


def test_documented_bond_default_date_is_confirmed_default() -> None:
    now = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=now,
        dividends=(),
        coupons=(),
        bond_events=(
            TBankBondEvent(
                instrument_uid="bond-uid",
                event_number=7,
                event_date=datetime(2026, 9, 20, tzinfo=UTC),
                event_type="EVENT_TYPE_COUPON",
                default_date=datetime(2026, 9, 30, tzinfo=UTC),
                real_pay_date=None,
                pay_date=datetime(2026, 9, 25, tzinfo=UTC),
                pay_one_bond=TBankMoney("RUB", "50"),
                execution="",
                operation_type="",
                note="",
            ),
        ),
        reports=(),
        fundamentals=(),
        sources=_sources(now),
    )

    documents, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    assert documents[0].payout is not None
    assert documents[0].payout.status == "defaulted"
    assert assessments[0].state == "confirmed_default"
    assert assessments[0].evidence["default_date"] == "2026-09-30T00:00:00+00:00"


def test_partial_provider_evidence_never_becomes_normal() -> None:
    now = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    sources = list(_sources(now))
    sources[1] = AnalysisSource(
        id="issuer_events",
        name="events",
        url=sources[1].url,
        methods=(),
        retrieved_at=now,
        status="partial",
    )
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=now,
        dividends=(),
        coupons=(),
        bond_events=(),
        reports=(),
        fundamentals=(),
        sources=tuple(sources),
    )

    _, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    assert assessments[0].source_status == "partial"
    assert assessments[0].state == "data_missing"
    assert "provider_evidence_partial" in assessments[0].reasons
