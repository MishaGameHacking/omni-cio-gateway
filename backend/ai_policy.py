"""Deterministic gate deciding when an expensive AI analysis is justified.

The module deliberately contains no model call. Market data collection, risk
calculations and deduplication happen first; a caller may invoke Timeweb AI
Gateway only when ``decide_analysis`` returns a non-NONE tier.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AnalysisTier(str, Enum):
    NONE = "none"
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


class AnalysisReason(str, Enum):
    NO_MATERIAL_CHANGE = "no_material_change"
    MORNING_BRIEF = "morning_brief"
    EVENING_BRIEF = "evening_brief"
    PORTFOLIO_CHANGED = "portfolio_changed"
    CASH_CHANGED = "cash_changed"
    RISK_EVENT = "risk_event"
    MARKET_REGIME_CHANGED = "market_regime_changed"
    DATA_RECOVERY = "data_recovery"
    BUDGET_EXHAUSTED = "budget_exhausted"
    COOLDOWN = "cooldown"


@dataclass(frozen=True)
class AnalysisSignals:
    morning_due: bool = False
    evening_due: bool = False
    portfolio_changed: bool = False
    cash_changed: bool = False
    critical_risk: bool = False
    market_regime_changed: bool = False
    data_recovered: bool = False
    digest_changed: bool = False
    minutes_since_last_analysis: int | None = None


@dataclass(frozen=True)
class AnalysisBudget:
    fast_calls_left: int
    standard_calls_left: int
    premium_calls_left: int


@dataclass(frozen=True)
class AnalysisDecision:
    tier: AnalysisTier
    reason: AnalysisReason
    notify_user: bool
    max_output_tokens: int


NONE_DECISION = AnalysisDecision(
    tier=AnalysisTier.NONE,
    reason=AnalysisReason.NO_MATERIAL_CHANGE,
    notify_user=False,
    max_output_tokens=0,
)


def decide_analysis(
    signals: AnalysisSignals,
    budget: AnalysisBudget,
    *,
    cooldown_minutes: int = 90,
) -> AnalysisDecision:
    """Return the least expensive tier that can responsibly handle the event.

    Critical portfolio risk bypasses the normal cooldown, while scheduled and
    routine triggers are deduplicated by ``digest_changed`` and bounded by the
    supplied per-tier budget. The function never silently upgrades cost.
    """
    if signals.critical_risk:
        if budget.premium_calls_left > 0:
            return AnalysisDecision(
                AnalysisTier.PREMIUM,
                AnalysisReason.RISK_EVENT,
                True,
                1_200,
            )
        if budget.standard_calls_left > 0:
            return AnalysisDecision(
                AnalysisTier.STANDARD,
                AnalysisReason.RISK_EVENT,
                True,
                800,
            )
        if budget.fast_calls_left > 0:
            return AnalysisDecision(
                AnalysisTier.FAST,
                AnalysisReason.RISK_EVENT,
                True,
                450,
            )
        return AnalysisDecision(
            AnalysisTier.NONE,
            AnalysisReason.BUDGET_EXHAUSTED,
            False,
            0,
        )

    if (
        signals.minutes_since_last_analysis is not None
        and signals.minutes_since_last_analysis < cooldown_minutes
        and not signals.portfolio_changed
        and not signals.cash_changed
    ):
        return AnalysisDecision(
            AnalysisTier.NONE,
            AnalysisReason.COOLDOWN,
            False,
            0,
        )

    standard_reason = None
    if signals.portfolio_changed:
        standard_reason = AnalysisReason.PORTFOLIO_CHANGED
    elif signals.cash_changed:
        standard_reason = AnalysisReason.CASH_CHANGED
    elif signals.market_regime_changed:
        standard_reason = AnalysisReason.MARKET_REGIME_CHANGED
    elif signals.morning_due:
        standard_reason = AnalysisReason.MORNING_BRIEF
    elif signals.evening_due:
        standard_reason = AnalysisReason.EVENING_BRIEF

    if standard_reason is not None:
        if not signals.digest_changed and standard_reason not in {
            AnalysisReason.PORTFOLIO_CHANGED,
            AnalysisReason.CASH_CHANGED,
        }:
            return NONE_DECISION
        if budget.standard_calls_left > 0:
            return AnalysisDecision(
                AnalysisTier.STANDARD,
                standard_reason,
                True,
                750,
            )
        if budget.fast_calls_left > 0:
            return AnalysisDecision(
                AnalysisTier.FAST,
                standard_reason,
                True,
                400,
            )
        return AnalysisDecision(
            AnalysisTier.NONE,
            AnalysisReason.BUDGET_EXHAUSTED,
            False,
            0,
        )

    if signals.data_recovered and signals.digest_changed:
        if budget.fast_calls_left > 0:
            return AnalysisDecision(
                AnalysisTier.FAST,
                AnalysisReason.DATA_RECOVERY,
                False,
                300,
            )
        return AnalysisDecision(
            AnalysisTier.NONE,
            AnalysisReason.BUDGET_EXHAUSTED,
            False,
            0,
        )

    return NONE_DECISION
