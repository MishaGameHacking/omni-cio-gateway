from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TypeVar

from omni_cio.contracts.v1.equity_fundamentals import (
    EquityAccountingStandard,
    EquityFundamentalAssessmentV1,
    EquityFundamentalBlocker,
    EquityFundamentalEvidenceV1,
    EquityFundamentalMetricsV1,
    EquityFundamentalPolicyV1,
    EquityFundamentalStatus,
    EquityFundamentalWarning,
)
from omni_cio.contracts.v1.market import (
    MarketAssessmentStatus,
    MarketFreshnessPolicyV1,
    MarketResearchBundleV1,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.market.assessment_v1 import assess_market_research_bundle


_SECONDS_PER_DAY = 86_400
_T = TypeVar("_T")


class EquityFundamentalAssessmentError(ValueError):
    """The supplied equity evidence cannot be assessed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise EquityFundamentalAssessmentError(
            "EQUITY_FUNDAMENTAL_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique(target: list[_T], value: _T) -> None:
    if value not in target:
        target.append(value)


def _age_seconds(value: datetime, assessed_at: datetime) -> int:
    return max(0, int((assessed_at - value).total_seconds()))


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _build_metrics(
    evidence: EquityFundamentalEvidenceV1,
    *,
    warnings: list[EquityFundamentalWarning],
) -> EquityFundamentalMetricsV1:
    unavailable: list[str] = []
    net_debt = evidence.total_debt - evidence.cash_and_equivalents
    if net_debt < 0:
        _append_unique(warnings, EquityFundamentalWarning.NET_CASH_POSITION)

    net_margin = _ratio(evidence.net_income, evidence.revenue)
    free_cash_flow_margin = _ratio(evidence.free_cash_flow, evidence.revenue)
    if net_margin is None:
        unavailable.append("net_margin")
    if free_cash_flow_margin is None:
        unavailable.append("free_cash_flow_margin")

    operating_margin = None
    if evidence.operating_profit is None:
        unavailable.append("operating_margin")
        _append_unique(
            warnings,
            EquityFundamentalWarning.OPERATING_PROFIT_NOT_PROVIDED,
        )
    else:
        operating_margin = _ratio(evidence.operating_profit, evidence.revenue)
        if operating_margin is None:
            unavailable.append("operating_margin")
        if evidence.operating_profit <= 0:
            _append_unique(
                warnings,
                EquityFundamentalWarning.NON_POSITIVE_OPERATING_PROFIT,
            )

    ebitda_margin = None
    net_debt_to_ebitda = None
    if evidence.ebitda is None:
        unavailable.extend(("ebitda_margin", "net_debt_to_ebitda"))
        _append_unique(warnings, EquityFundamentalWarning.EBITDA_NOT_PROVIDED)
    else:
        ebitda_margin = _ratio(evidence.ebitda, evidence.revenue)
        if ebitda_margin is None:
            unavailable.append("ebitda_margin")
        if evidence.ebitda > 0:
            net_debt_to_ebitda = net_debt / evidence.ebitda
        else:
            unavailable.append("net_debt_to_ebitda")
            _append_unique(warnings, EquityFundamentalWarning.NON_POSITIVE_EBITDA)

    price_to_earnings = None
    dividend_payout_ratio = None
    if evidence.net_income > 0:
        price_to_earnings = evidence.market_cap / evidence.net_income
        if evidence.dividends_paid is not None:
            dividend_payout_ratio = evidence.dividends_paid / evidence.net_income
            if evidence.dividends_paid > evidence.net_income:
                _append_unique(
                    warnings,
                    EquityFundamentalWarning.DIVIDENDS_EXCEED_POSITIVE_NET_INCOME,
                )
        else:
            unavailable.append("dividend_payout_ratio")
            _append_unique(warnings, EquityFundamentalWarning.DIVIDENDS_NOT_PROVIDED)
    else:
        unavailable.extend(("price_to_earnings", "dividend_payout_ratio"))
        _append_unique(warnings, EquityFundamentalWarning.NEGATIVE_NET_INCOME)
        if evidence.dividends_paid is None:
            _append_unique(warnings, EquityFundamentalWarning.DIVIDENDS_NOT_PROVIDED)

    price_to_book = None
    if evidence.total_equity > 0:
        price_to_book = evidence.market_cap / evidence.total_equity
    else:
        unavailable.append("price_to_book")
        _append_unique(warnings, EquityFundamentalWarning.NEGATIVE_EQUITY)

    if evidence.operating_cash_flow < 0:
        _append_unique(
            warnings,
            EquityFundamentalWarning.NEGATIVE_OPERATING_CASH_FLOW,
        )
    if evidence.free_cash_flow < 0:
        _append_unique(warnings, EquityFundamentalWarning.NEGATIVE_FREE_CASH_FLOW)
    if evidence.shares_outstanding is None:
        _append_unique(
            warnings,
            EquityFundamentalWarning.SHARES_OUTSTANDING_NOT_PROVIDED,
        )
    if evidence.accounting_standard == EquityAccountingStandard.OTHER:
        _append_unique(warnings, EquityFundamentalWarning.ACCOUNTING_STANDARD_OTHER)

    return EquityFundamentalMetricsV1(
        currency=evidence.currency,
        revenue=evidence.revenue,
        operating_profit=evidence.operating_profit,
        ebitda=evidence.ebitda,
        net_income=evidence.net_income,
        operating_cash_flow=evidence.operating_cash_flow,
        capital_expenditure=evidence.capital_expenditure,
        free_cash_flow=evidence.free_cash_flow,
        total_debt=evidence.total_debt,
        cash_and_equivalents=evidence.cash_and_equivalents,
        net_debt=net_debt,
        total_equity=evidence.total_equity,
        dividends_paid=evidence.dividends_paid,
        market_cap=evidence.market_cap,
        net_margin=net_margin,
        operating_margin=operating_margin,
        ebitda_margin=ebitda_margin,
        free_cash_flow_margin=free_cash_flow_margin,
        net_debt_to_ebitda=net_debt_to_ebitda,
        earnings_yield=evidence.net_income / evidence.market_cap,
        free_cash_flow_yield=evidence.free_cash_flow / evidence.market_cap,
        price_to_earnings=price_to_earnings,
        price_to_book=price_to_book,
        dividend_payout_ratio=dividend_payout_ratio,
        unavailable_metrics=tuple(sorted(set(unavailable))),
    )


def assess_equity_fundamentals(
    bundle: MarketResearchBundleV1,
    evidence: EquityFundamentalEvidenceV1,
    *,
    policy: EquityFundamentalPolicyV1 | None = None,
    market_policy: MarketFreshnessPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> EquityFundamentalAssessmentV1:
    """Assess reproducible equity fundamentals without forecasting or advice."""

    active_policy = policy or EquityFundamentalPolicyV1()
    evaluation_time = _aware_utc(assessed_at)
    market_readiness = assess_market_research_bundle(
        bundle,
        policy=market_policy,
        assessed_at=evaluation_time,
    )
    blockers: list[EquityFundamentalBlocker] = []
    warnings: list[EquityFundamentalWarning] = [
        EquityFundamentalWarning.MULTIPLES_NOT_FORECASTS,
        EquityFundamentalWarning.NO_CROSS_CURRENCY_AGGREGATION,
    ]

    if market_readiness.status != MarketAssessmentStatus.READY:
        _append_unique(
            blockers,
            EquityFundamentalBlocker.MARKET_RESEARCH_NOT_READY,
        )

    reference = bundle.reference
    if reference is None:
        _append_unique(blockers, EquityFundamentalBlocker.REFERENCE_MISSING)
    else:
        if reference.instrument_type != InstrumentType.SHARE:
            _append_unique(blockers, EquityFundamentalBlocker.NOT_A_SHARE)
        if reference.stable_key != evidence.instrument_key:
            _append_unique(
                blockers,
                EquityFundamentalBlocker.INSTRUMENT_IDENTITY_MISMATCH,
            )
        if reference.currency != evidence.currency:
            _append_unique(blockers, EquityFundamentalBlocker.CURRENCY_MISMATCH)

    trusted = set(active_policy.trusted_authorities)
    if evidence.report_source.authority not in trusted:
        _append_unique(
            blockers,
            EquityFundamentalBlocker.UNTRUSTED_REPORT_SOURCE,
        )
    if evidence.market_cap_source.authority not in trusted:
        _append_unique(
            blockers,
            EquityFundamentalBlocker.UNTRUSTED_MARKET_CAP_SOURCE,
        )

    report_delta_seconds = (evaluation_time - evidence.published_at).total_seconds()
    report_age_days = max(0, int(report_delta_seconds // _SECONDS_PER_DAY))
    if report_delta_seconds < -active_policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            EquityFundamentalBlocker.REPORT_FUTURE_TIMESTAMP,
        )
    elif report_age_days > active_policy.max_report_age_days:
        _append_unique(blockers, EquityFundamentalBlocker.REPORT_STALE)
    if evidence.period_end > evaluation_time.date():
        _append_unique(blockers, EquityFundamentalBlocker.REPORT_PERIOD_FUTURE)

    market_cap_delta_seconds = (
        evaluation_time - evidence.market_cap_as_of
    ).total_seconds()
    market_cap_age_seconds = max(0, int(market_cap_delta_seconds))
    if market_cap_delta_seconds < -active_policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            EquityFundamentalBlocker.MARKET_CAP_FUTURE_TIMESTAMP,
        )
    elif market_cap_age_seconds > active_policy.max_market_cap_age_seconds:
        _append_unique(blockers, EquityFundamentalBlocker.MARKET_CAP_STALE)

    metrics = _build_metrics(evidence, warnings=warnings)
    ready = not blockers
    return EquityFundamentalAssessmentV1(
        assessed_at=evaluation_time,
        status=(
            EquityFundamentalStatus.READY
            if ready
            else EquityFundamentalStatus.REJECTED
        ),
        analysis_ready=ready,
        instrument_key=evidence.instrument_key,
        currency=evidence.currency,
        report_age_days=report_age_days,
        market_cap_age_seconds=market_cap_age_seconds,
        policy=active_policy,
        market_readiness=market_readiness,
        metrics=metrics,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
