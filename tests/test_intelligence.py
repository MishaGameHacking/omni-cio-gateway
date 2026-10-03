from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from omnicio.broker import AnalysisSource, BrokerEvidenceSnapshot, BrokerObservationBundle
from omnicio.intelligence import assess_candidate_fundamental_risk, build_tbank_evidence
from omnicio.portfolio import PortfolioAnalysis
from omnicio.tbank import (
    TBankAssetFundamental,
    TBankAssetReport,
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
    assert assessments[0].evidence["ruleset_version"] == "r3-evidence-v1"
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


def test_report_date_is_preserved_as_publication_time() -> None:
    report_date = datetime(2026, 9, 30, 7, 0, tzinfo=UTC)
    created_at = datetime(2026, 9, 29, 18, 0, tzinfo=UTC)
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
        dividends=(),
        coupons=(),
        bond_events=(),
        reports=(
            TBankAssetReport(
                instrument_uid="bond-uid",
                report_date=report_date,
                period_year=2026,
                period_num=3,
                period_type="PERIOD_TYPE_QUARTER",
                created_at=created_at,
            ),
        ),
        fundamentals=(),
        sources=_sources(datetime(2026, 10, 2, 6, 0, tzinfo=UTC)),
    )

    documents, _ = build_tbank_evidence(
        _bundle(),
        evidence,
        assessed_at=datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
    )

    report = next(item for item in documents if item.document_type == "issuer_report_calendar")
    assert report.published_at == report_date
    assert report.facts[0].published_at == report_date


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


def test_figi_fallback_keeps_default_evidence_joined_to_snapshot_key() -> None:
    now = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    bundle = _bundle()
    position = replace(bundle.portfolio.positions[0], instrument_uid="")
    bundle = replace(
        bundle,
        portfolio=replace(bundle.portfolio, positions=(position,)),
    )
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=now,
        dividends=(),
        coupons=(),
        bond_events=(
            TBankBondEvent(
                instrument_uid="bond-uid",
                event_number=9,
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

    _, assessments = build_tbank_evidence(bundle, evidence, assessed_at=now)

    assert assessments[0].instrument_uid == "FIGI-BOND"
    assert assessments[0].state == "confirmed_default"
    assert assessments[0].evidence["asset_uid"] == "issuer-asset"


def test_empty_fundamental_record_remains_data_missing() -> None:
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
                revenue_ttm=None,
                ebitda_ttm=None,
                net_income_ttm=None,
                free_cash_flow_ttm=None,
                total_debt_mrq=None,
                total_debt_to_equity_mrq=None,
                total_debt_to_ebitda_mrq=None,
                net_debt_to_ebitda=None,
                current_ratio_mrq=None,
                fixed_charge_coverage_ratio_fy=None,
                net_interest_margin_mrq=None,
                roe=None,
                roa=None,
                fiscal_period_start_date=datetime(2025, 1, 1, tzinfo=UTC),
                fiscal_period_end_date=datetime(2025, 12, 31, tzinfo=UTC),
            ),
        ),
        sources=_sources(now),
    )

    _, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    assert assessments[0].fundamental_status == "data_missing"
    assert assessments[0].state == "data_missing"
    assert "fundamental_data_missing" in assessments[0].reasons


def test_stale_evidence_retrieval_is_fail_closed() -> None:
    now = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)
    stale_at = datetime(2026, 9, 30, 5, 0, tzinfo=UTC)
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=stale_at,
        dividends=(),
        coupons=(),
        bond_events=(),
        reports=(),
        fundamentals=(),
        sources=_sources(stale_at),
    )

    _, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    assert assessments[0].source_status == "partial"
    assert assessments[0].state == "data_missing"
    assert "provider_evidence_stale" in assessments[0].reasons
    assert assessments[0].evidence["evidence_retrieval_max_age_hours"] == 36
    assert assessments[0].evidence["ruleset_version"] == "r3-evidence-v1"



def test_corporate_fccr_below_one_is_explainable_elevated_watch() -> None:
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
                ebitda_ttm="10",
                net_income_ttm="2",
                free_cash_flow_ttm="-3",
                total_debt_mrq="40",
                total_debt_to_equity_mrq="1.2",
                total_debt_to_ebitda_mrq="4",
                net_debt_to_ebitda="3.5",
                current_ratio_mrq="0.8",
                fixed_charge_coverage_ratio_fy="0.7",
                net_interest_margin_mrq=None,
                roe="0.04",
                roa="0.02",
                fiscal_period_start_date=datetime(2025, 1, 1, tzinfo=UTC),
                fiscal_period_end_date=datetime(2025, 12, 31, tzinfo=UTC),
            ),
        ),
        sources=_sources(now),
    )

    _, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    risk = assessments[0]
    assert risk.state == "elevated"
    assert risk.rating_status == "data_missing"
    assert risk.evidence["metric_profile"] == "corporate"
    assert "fixed_charge_coverage_ratio_below_one" in risk.reasons
    assert "credit_rating_feed_not_verified" in risk.reasons
    signals = risk.evidence["metric_signals"]
    assert any(
        item["metric"] == "fixed_charge_coverage_ratio_fy"
        and item["value"] == "0.7"
        for item in signals
    )


def test_bank_like_metrics_do_not_apply_corporate_leverage_rules() -> None:
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
                ebitda_ttm="-10",
                net_income_ttm="-2",
                free_cash_flow_ttm="-3",
                total_debt_mrq="400",
                total_debt_to_equity_mrq="8",
                total_debt_to_ebitda_mrq="20",
                net_debt_to_ebitda="15",
                current_ratio_mrq="0.5",
                fixed_charge_coverage_ratio_fy="0.2",
                net_interest_margin_mrq="0.03",
                roe="0.05",
                roa="0.01",
                fiscal_period_start_date=datetime(2025, 1, 1, tzinfo=UTC),
                fiscal_period_end_date=datetime(2025, 12, 31, tzinfo=UTC),
            ),
        ),
        sources=_sources(now),
    )

    _, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    risk = assessments[0]
    assert risk.state == "data_missing"
    assert risk.evidence["metric_profile"] == "bank_like"
    assert "fixed_charge_coverage_ratio_below_one" not in risk.reasons
    assert "ebitda_negative" not in risk.reasons
    assert "credit_rating_feed_not_verified" in risk.reasons


def test_negative_bank_profitability_is_watch_not_default_prediction() -> None:
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
                revenue_ttm=None,
                ebitda_ttm=None,
                net_income_ttm="-5",
                free_cash_flow_ttm=None,
                total_debt_mrq=None,
                total_debt_to_equity_mrq=None,
                total_debt_to_ebitda_mrq=None,
                net_debt_to_ebitda=None,
                current_ratio_mrq=None,
                fixed_charge_coverage_ratio_fy=None,
                net_interest_margin_mrq="-0.01",
                roe="-0.05",
                roa="-0.01",
                fiscal_period_start_date=datetime(2025, 1, 1, tzinfo=UTC),
                fiscal_period_end_date=datetime(2025, 12, 31, tzinfo=UTC),
            ),
        ),
        sources=_sources(now),
    )

    _, assessments = build_tbank_evidence(_bundle(), evidence, assessed_at=now)

    risk = assessments[0]
    assert risk.state == "watch"
    assert risk.evidence["metric_profile"] == "bank_like"
    assert "net_interest_margin_mrq_negative" in risk.reasons
    assert "roe_negative" in risk.reasons
    assert "roa_negative" in risk.reasons
    assert risk.state != "confirmed_default"



def test_future_default_date_is_not_reported_as_confirmed_default() -> None:
    now = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=now,
        dividends=(),
        coupons=(),
        bond_events=(
            TBankBondEvent(
                instrument_uid="bond-uid",
                event_number=11,
                event_date=now,
                event_type="EVENT_TYPE_COUPON",
                default_date=datetime(2026, 10, 10, tzinfo=UTC),
                real_pay_date=datetime(2026, 10, 9, tzinfo=UTC),
                pay_date=datetime(2026, 10, 5, tzinfo=UTC),
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

    documents, assessments = build_tbank_evidence(
        _bundle(),
        evidence,
        assessed_at=now,
    )

    event = next(item for item in documents if item.document_type == "bond_event")
    assert event.payout is not None
    assert event.payout.status == "observed"
    assert event.payout.actual_at is None
    assert assessments[0].state == "data_missing"
    assert assessments[0].evidence["default_date"] is None



def test_candidate_fundamental_risk_can_be_normal_without_inventing_rating() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    info = _bundle().metadata[0]
    fundamental = TBankAssetFundamental(
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
    )

    assessment = assess_candidate_fundamental_risk(
        info,
        fundamental,
        assessed_at=now,
    )

    assert assessment.state == "normal"
    assert assessment.fundamental_status == "received"
    assert assessment.rating_status == "data_missing"
    assert "credit_rating_feed_not_verified" in assessment.reasons
    assert assessment.evidence["rating_policy"] == "unknown_bucket_until_verified_feed"


def test_candidate_fundamental_risk_fails_closed_when_metrics_are_missing() -> None:
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    assessment = assess_candidate_fundamental_risk(
        _bundle().metadata[0],
        None,
        assessed_at=now,
    )

    assert assessment.state == "data_missing"
    assert assessment.fundamental_status == "data_missing"
    assert assessment.rating_status == "data_missing"
    assert "fundamental_data_missing" in assessment.reasons
