from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from omnicio.balancing import (
    AllocationCap,
    BalancingPolicy,
    Candidate,
    Holding,
    build_balancing_preview,
    screen_candidates,
)


def _policy(**overrides) -> BalancingPolicy:
    values = {
        "reserve_rub": Decimal("10000"),
        "planned_withdrawal_rub": Decimal("0"),
        "max_instrument_percent": Decimal("20"),
        "max_sector_percent": Decimal("30"),
        "max_issuer_percent": Decimal("20"),
        "max_group_percent": Decimal("25"),
        "max_below_grade_percent": Decimal("5"),
        "max_unknown_percent": Decimal("0"),
        "max_liquidity_days": 5,
        "max_term_months": 120,
        "turnover_budget_rub": Decimal("100000"),
        "no_trade_band_percent": Decimal("1"),
        "min_replace_benefit_rub": Decimal("500"),
        "allowed_asset_classes": ("share", "bond", "etf"),
        "allowed_currencies": ("RUB",),
        "allowed_risk_states": ("normal",),
        "asset_class_caps": (
            AllocationCap("share", Decimal("70")),
            AllocationCap("bond", Decimal("80")),
            AllocationCap("etf", Decimal("70")),
        ),
        "currency_caps": (AllocationCap("RUB", Decimal("100")),),
        "replacement_same_asset_class": True,
    }
    values.update(overrides)
    return BalancingPolicy(**values)


def _candidate(
    uid: str,
    *,
    asset_class: str = "share",
    sector: str = "technology",
    issuer: str | None = None,
    group: str | None = None,
    rating: str = "not_applicable",
    lot_cost: str = "5000",
    expected_gain: str = "700",
    fee: str = "10",
    spread: str = "10",
    uncertainty: str = "50",
    credit_loss: str = "20",
    liquidity_penalty: str = "10",
    liquidity_days: int = 2,
    term_months: int = 0,
    ytw: Decimal | None = None,
    duration: Decimal | None = None,
    evidence_complete: bool = True,
) -> Candidate:
    if asset_class == "bond":
        ytw = ytw if ytw is not None else Decimal("12")
        duration = duration if duration is not None else Decimal("2.5")
        if term_months == 0:
            term_months = 60
    return Candidate(
        instrument_uid=uid,
        ticker=uid.upper(),
        asset_class=asset_class,
        sector=sector,
        issuer_id=issuer or f"issuer-{uid}",
        group_id=group or f"group-{uid}",
        rating_bucket=rating,  # type: ignore[arg-type]
        currency="RUB",
        risk_state="normal",
        lot_size=1,
        market_lot_cost_rub=Decimal(lot_cost),
        accrued_coupon_rub_per_lot=(
            Decimal("50") if asset_class == "bond" else Decimal("0")
        ),
        buy_fee_rub_per_lot=Decimal(fee),
        spread_cost_rub_per_lot=Decimal(spread),
        expected_horizon_gain_rub_per_lot=Decimal(expected_gain),
        uncertainty_haircut_rub_per_lot=Decimal(uncertainty),
        credit_loss_rub_per_lot=Decimal(credit_loss),
        liquidity_penalty_rub_per_lot=Decimal(liquidity_penalty),
        liquidity_days=liquidity_days,
        term_months=term_months,
        ytw_percent=ytw,
        duration_years=duration,
        api_trade_available=True,
        buy_available=True,
        required_tests_passed=True,
        evidence_complete=evidence_complete,
    )


def _holding(
    uid: str,
    *,
    risk_state: str = "normal",
    asset_class: str = "share",
    sector: str = "energy",
    value: str = "20000",
    expected_gain: str = "500",
    sell_fee: str = "0",
    spread: str = "0",
    tax: str = "0",
    blocked: bool = False,
) -> Holding:
    return Holding(
        instrument_uid=uid,
        ticker=uid.upper(),
        asset_class=asset_class,
        sector=sector,
        issuer_id=f"issuer-{uid}",
        group_id=f"group-{uid}",
        rating_bucket="not_applicable",
        currency="RUB",
        risk_state=risk_state,  # type: ignore[arg-type]
        lots=2,
        value_rub=Decimal(value),
        expected_horizon_gain_rub=Decimal(expected_gain),
        sell_fee_rub=Decimal(sell_fee),
        exit_spread_cost_rub=Decimal(spread),
        tax_if_sold_rub=Decimal(tax),
        blocked=blocked,
    )


def test_candidate_screening_fails_closed_on_missing_evidence_and_bond_metrics() -> None:
    bond = replace(
        _candidate("bond", asset_class="bond"),
        evidence_complete=False,
        ytw_percent=None,
        duration_years=None,
    )

    screened = screen_candidates((bond,), _policy())

    assert screened[0].eligible is False
    assert set(screened[0].reasons) >= {
        "critical_evidence_missing",
        "bond_ytw_missing",
        "bond_duration_missing",
    }


def test_small_capital_keeps_cash_when_no_integer_lot_fits_after_reserve() -> None:
    preview = build_balancing_preview(
        nav_rub=Decimal("50000"),
        cash_rub=Decimal("15000"),
        holdings=(),
        candidates=(_candidate("expensive", lot_cost="6000"),),
        policy=_policy(),
    )

    assert preview.hold.status == "feasible"
    assert preview.deploy_cash.status == "infeasible"
    assert preview.deploy_cash.reason == "integer_lot_or_policy_limits_block_all_buys"
    assert preview.deploy_cash.residual_cash_rub == Decimal("15000")
    assert preview.deploy_cash.trades == ()


def test_large_capital_respects_instrument_and_sector_caps_with_integer_lots() -> None:
    first = _candidate("first", sector="technology", lot_cost="5000", expected_gain="900")
    second = _candidate("second", sector="technology", lot_cost="5000", expected_gain="700")

    preview = build_balancing_preview(
        nav_rub=Decimal("100000"),
        cash_rub=Decimal("50000"),
        holdings=(),
        candidates=(first, second),
        policy=_policy(reserve_rub=Decimal("0")),
    )

    assert preview.deploy_cash.status == "feasible"
    assert [(trade.instrument_uid, trade.lots) for trade in preview.deploy_cash.trades] == [
        ("first", 4),
        ("second", 2),
    ]
    assert sum(trade.notional_rub for trade in preview.deploy_cash.trades) == Decimal(
        "30000"
    )
    assert preview.deploy_cash.turnover_rub == Decimal("30000")


def test_unknown_rating_is_not_treated_as_investment_grade() -> None:
    candidate = _candidate("unknown", rating="unknown")

    preview = build_balancing_preview(
        nav_rub=Decimal("100000"),
        cash_rub=Decimal("50000"),
        holdings=(),
        candidates=(candidate,),
        policy=_policy(reserve_rub=Decimal("0"), max_unknown_percent=Decimal("0")),
    )

    assert preview.deploy_cash.status == "infeasible"
    assert preview.deploy_cash.trades == ()


def test_below_grade_budget_is_respected_when_explicitly_allowed() -> None:
    candidate = _candidate("risky", rating="below_grade", lot_cost="1000")

    preview = build_balancing_preview(
        nav_rub=Decimal("100000"),
        cash_rub=Decimal("20000"),
        holdings=(),
        candidates=(candidate,),
        policy=_policy(
            reserve_rub=Decimal("0"),
            max_below_grade_percent=Decimal("3"),
        ),
    )

    assert preview.deploy_cash.status == "feasible"
    assert preview.deploy_cash.trades[0].lots == 3
    assert preview.deploy_cash.trades[0].notional_rub == Decimal("3000")


def test_no_churn_when_gross_improvement_does_not_cover_tax_costs_and_band() -> None:
    holding = _holding(
        "old",
        risk_state="elevated",
        expected_gain="1000",
        sell_fee="100",
        spread="100",
        tax="1500",
    )
    candidate = _candidate(
        "new",
        lot_cost="9000",
        expected_gain="1700",
        fee="100",
        spread="100",
        uncertainty="100",
        credit_loss="0",
        liquidity_penalty="0",
    )

    preview = build_balancing_preview(
        nav_rub=Decimal("100000"),
        cash_rub=Decimal("10000"),
        holdings=(holding,),
        candidates=(candidate,),
        policy=_policy(),
    )

    replacement = preview.replacements[0]
    assert replacement.status == "infeasible"
    assert replacement.reason == "no_replacement_clears_costs_and_no_trade_band"
    assert replacement.trades == ()


def test_replace_scenario_uses_integer_lots_and_reports_tax_and_costs() -> None:
    holding = _holding(
        "old",
        risk_state="critical",
        value="20000",
        expected_gain="-1000",
        sell_fee="100",
        spread="100",
        tax="300",
    )
    candidate = _candidate(
        "new",
        lot_cost="6000",
        expected_gain="1600",
        fee="20",
        spread="30",
        uncertainty="100",
        credit_loss="30",
        liquidity_penalty="20",
    )

    preview = build_balancing_preview(
        nav_rub=Decimal("100000"),
        cash_rub=Decimal("10000"),
        holdings=(holding,),
        candidates=(candidate,),
        policy=_policy(no_trade_band_percent=Decimal("0")),
    )

    replacement = preview.replacements[0]
    assert replacement.status == "feasible"
    assert replacement.kind == "replace"
    assert replacement.target_instrument_uid == "new"
    assert [trade.action for trade in replacement.trades] == ["sell", "buy"]
    assert replacement.trades[0].tax_rub == Decimal("300")
    assert replacement.trades[1].lots == 3
    assert replacement.residual_cash_rub == Decimal("1350")
    assert replacement.expected_incremental_gain_rub > Decimal("0")


def test_turnover_budget_blocks_replace_even_when_candidate_is_better() -> None:
    holding = _holding(
        "old",
        risk_state="critical",
        value="20000",
        expected_gain="-5000",
    )
    candidate = _candidate("new", lot_cost="5000", expected_gain="2000")

    preview = build_balancing_preview(
        nav_rub=Decimal("100000"),
        cash_rub=Decimal("10000"),
        holdings=(holding,),
        candidates=(candidate,),
        policy=_policy(turnover_budget_rub=Decimal("24999")),
    )

    replacement = preview.replacements[0]
    assert replacement.status == "infeasible"
    assert replacement.reason == "no_replacement_clears_costs_and_no_trade_band"


def test_blocked_holding_never_generates_sell_trade() -> None:
    holding = _holding("locked", risk_state="confirmed_default", blocked=True)

    preview = build_balancing_preview(
        nav_rub=Decimal("100000"),
        cash_rub=Decimal("10000"),
        holdings=(holding,),
        candidates=(_candidate("new"),),
        policy=_policy(),
    )

    replacement = preview.replacements[0]
    assert replacement.status == "infeasible"
    assert replacement.reason == "holding_blocked"
    assert replacement.trades == ()


def test_policy_requires_explicit_caps_instead_of_hidden_defaults() -> None:
    candidate = _candidate("share")

    screened = screen_candidates(
        (candidate,),
        _policy(asset_class_caps=(AllocationCap("bond", Decimal("80")),)),
    )

    assert screened[0].eligible is False
    assert "asset_class_cap_missing" in screened[0].reasons


def test_invalid_policy_is_rejected_before_optimization() -> None:
    with pytest.raises(ValueError, match="max_instrument_percent"):
        build_balancing_preview(
            nav_rub=Decimal("100000"),
            cash_rub=Decimal("10000"),
            holdings=(),
            candidates=(),
            policy=_policy(max_instrument_percent=Decimal("101")),
        )
