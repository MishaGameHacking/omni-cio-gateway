from __future__ import annotations

from datetime import UTC, datetime, timedelta

from omnicio.risk import (
    FundamentalEvidence,
    InstrumentRiskEvidence,
    ReportEvidence,
    SourceEvidenceStatus,
    assess_instrument,
)


NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
REPORT = ReportEvidence(
    instrument_uid="uid-1",
    report_date=NOW - timedelta(days=30),
    period_year=2026,
    period_num=2,
    period_type="PERIOD_TYPE_QUARTER",
    created_at=NOW - timedelta(days=35),
)


def _fundamental(**metrics: str | None) -> FundamentalEvidence:
    return FundamentalEvidence(
        instrument_uid="uid-1",
        asset_uid="asset-1",
        currency="RUB",
        retrieved_at=NOW,
        fiscal_period_start=NOW - timedelta(days=180),
        fiscal_period_end=NOW - timedelta(days=30),
        metrics=metrics,
    )


def _sources() -> tuple[SourceEvidenceStatus, ...]:
    return (
        SourceEvidenceStatus(
            source_id="tbank_fundamentals",
            scope_key="uid-1",
            status="received",
            retrieved_at=NOW,
            source_url="https://developer.tbank.ru/fundamentals",
        ),
        SourceEvidenceStatus(
            source_id="tbank_reports",
            scope_key="uid-1",
            status="received",
            retrieved_at=NOW,
            source_url="https://developer.tbank.ru/reports",
        ),
        SourceEvidenceStatus(
            source_id="cbr_cra_registry",
            scope_key="uid-1",
            status="not_configured",
            retrieved_at=NOW,
            source_url="https://ratings.cbr.ru/",
        ),
    )


def _evidence(
    *,
    sector: str = "industry",
    fundamental: FundamentalEvidence | None = None,
    confirmed_default_at: datetime | None = None,
) -> InstrumentRiskEvidence:
    return InstrumentRiskEvidence(
        instrument_uid="uid-1",
        ticker="TEST",
        instrument_type="bond",
        sector=sector,
        fundamental=fundamental,
        reports=(REPORT,),
        payouts=(),
        confirmed_default_at=confirmed_default_at,
        sources=_sources(),
    )


def test_ordinary_company_high_leverage_is_explainable_elevated_watch() -> None:
    result = assess_instrument(
        _evidence(
            fundamental=_fundamental(
                net_debt_to_ebitda="6.5",
                fixed_charge_coverage_ratio_fy="3",
            )
        ),
        now=NOW,
    )

    assert result.state == "elevated"
    assert result.coverage == "partial"
    assert result.sector_model == "ordinary_company"
    assert any(reason.code == "high_leverage" for reason in result.reasons)
    assert any(reason.code == "rating_feed_missing" for reason in result.reasons)


def test_bank_never_inherits_ordinary_company_debt_to_ebitda_thresholds() -> None:
    result = assess_instrument(
        _evidence(
            sector="Banks",
            fundamental=_fundamental(
                net_debt_to_ebitda="20",
                roa="1.2",
                net_interest_margin_mrq="4.1",
            ),
        ),
        now=NOW,
    )

    assert result.sector_model == "bank"
    assert result.state == "data_missing"
    assert not any(reason.code == "high_leverage" for reason in result.reasons)
    assert any(reason.code == "bank_model_limited" for reason in result.reasons)


def test_insurer_stays_fail_closed_without_specialized_sector_metrics() -> None:
    result = assess_instrument(
        _evidence(
            sector="Insurance",
            fundamental=_fundamental(net_debt_to_ebitda="20"),
        ),
        now=NOW,
    )

    assert result.sector_model == "insurer"
    assert result.state == "data_missing"
    assert not any(reason.code == "high_leverage" for reason in result.reasons)
    assert any(reason.code == "insurer_model_limited" for reason in result.reasons)


def test_explicit_provider_default_date_is_confirmed_default_not_probability() -> None:
    default_at = NOW - timedelta(days=1)
    result = assess_instrument(
        _evidence(
            fundamental=_fundamental(net_debt_to_ebitda="2"),
            confirmed_default_at=default_at,
        ),
        now=NOW,
    )

    assert result.state == "confirmed_default"
    assert result.reasons[0].code == "confirmed_default"
    assert default_at.date().isoformat() in result.reasons[0].detail


def test_missing_fundamentals_never_become_normal() -> None:
    result = assess_instrument(_evidence(fundamental=None), now=NOW)

    assert result.state == "data_missing"
    assert result.coverage == "missing"
    assert any(reason.code == "fundamentals_missing" for reason in result.reasons)
