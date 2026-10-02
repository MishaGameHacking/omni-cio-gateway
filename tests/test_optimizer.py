from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from omnicio.optimizer import (
    OptimizationPolicy,
    OptimizerCandidate,
    PortfolioExposureState,
    ReplacementCase,
    compare_replacement,
    optimize_integer_lots,
    screen_candidate,
)


NOW = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)


def _policy(**overrides: object) -> OptimizationPolicy:
    values: dict[str, object] = {
        "reserve_rub": Decimal("5000"),
        "planned_withdrawal_rub": Decimal("0"),
        "horizon_months": 24,
        "max_duration_years": Decimal("5"),
        "max_instrument_percent": Decimal("20"),
        "max_issuer_percent": Decimal("25"),
        "max_group_percent": Decimal("30"),
        "max_sector_percent": Decimal("40"),
        "max_asset_class_percent": Decimal("60"),
        "rating_max_percent": {
            "AAA": Decimal("60"),
            "AA": Decimal("50"),
            "A": Decimal("40"),
            "BBB": Decimal("30"),
            "below_investment_grade": Decimal("10"),
            "unknown": Decimal("0"),
        },
        "max_turnover_percent": Decimal("20"),
        "min_trade_rub": Decimal("1000"),
        "no_trade_band_percent": Decimal("1"),
        "inflation_percent": Decimal("5"),
        "rating_haircut_percent": {
            "AAA": Decimal("0.5"),
            "AA": Decimal("1"),
            "A": Decimal("1.5"),
            "BBB": Decimal("2.5"),
            "below_investment_grade": Decimal("5"),
            "unknown": Decimal("0"),
        },
        "max_quote_age_seconds": 900,
        "max_evidence_age_seconds": 36 * 60 * 60,
        "allow_below_investment_grade": False,
        "is_qualified_investor": False,
    }
    values.update(overrides)
    return OptimizationPolicy(**values)  # type: ignore[arg-type]


def _candidate(**overrides: object) -> OptimizerCandidate:
    candidate = OptimizerCandidate(
        instrument_uid="bond-1",
        ticker="BOND1",
        name="Test bond",
        instrument_type="bond",
        asset_class="bonds",
        issuer_id="issuer-1",
        issuer_country_code="RU",
        group_id="group-1",
        sector="finance",
        rating_tier="AA",
        funding_per_lot_rub=Decimal("5000"),
        exposure_per_lot_rub=Decimal("4990"),
        commission_per_lot_rub=Decimal("10"),
        spread_cost_per_lot_rub=Decimal("5"),
        estimated_tax_per_lot_rub=Decimal("0"),
        ytw_percent=Decimal("14"),
        duration_years=Decimal("2.4"),
        quote_at=NOW - timedelta(seconds=30),
        evidence_at=NOW - timedelta(hours=1),
        api_trade_available=True,
        buy_available=True,
        liquidity=True,
        for_qual_investor=False,
        required_tests=(),
        real_exchange="REAL_EXCHANGE_MOEX",
        floating_coupon=False,
        perpetual=False,
        amortization=False,
        subordinated=False,
    )
    return replace(candidate, **overrides)


def _state(**overrides: object) -> PortfolioExposureState:
    state = PortfolioExposureState(
        nav_rub=Decimal("100000"),
        available_cash_rub=Decimal("30000"),
        instrument_rub={},
        issuer_rub={},
        group_rub={},
        sector_rub={},
        asset_class_rub={},
        rating_rub={},
    )
    return replace(state, **overrides)


def test_integer_lot_optimizer_respects_cash_turnover_and_exposure_limits() -> None:
    plan = optimize_integer_lots(
        _state(),
        (_candidate(),),
        _policy(),
        now=NOW,
    )

    assert plan.status == "feasible"
    assert len(plan.allocations) == 1
    allocation = plan.allocations[0]
    assert allocation.lots == 4
    assert allocation.funding_rub == Decimal("20000")
    assert allocation.exposure_rub == Decimal("19960")
    assert plan.allocated_cash_rub == Decimal("20000")
    assert plan.residual_cash_rub == Decimal("5000")
    assert plan.execution_enabled is False


def test_existing_issuer_limit_can_make_integer_plan_infeasible() -> None:
    plan = optimize_integer_lots(
        _state(issuer_rub={"issuer-1": Decimal("24000")}),
        (_candidate(),),
        _policy(),
        now=NOW,
    )

    assert plan.status == "infeasible"
    assert plan.allocations == ()
    assert "integer_lot_constraints_infeasible" in plan.reasons


def test_small_capital_keeps_cash_when_minimum_economic_trade_is_unreachable() -> None:
    plan = optimize_integer_lots(
        _state(
            nav_rub=Decimal("50000"),
            available_cash_rub=Decimal("5200"),
        ),
        (_candidate(funding_per_lot_rub=Decimal("2000")),),
        _policy(
            reserve_rub=Decimal("4500"),
            min_trade_rub=Decimal("1000"),
        ),
        now=NOW,
    )

    assert plan.status == "hold"
    assert plan.allocated_cash_rub == 0
    assert plan.residual_cash_rub == Decimal("700")
    assert plan.reasons == ("insufficient_economic_trade_budget",)


def test_large_capital_still_stops_at_explicit_instrument_cap() -> None:
    plan = optimize_integer_lots(
        _state(
            nav_rub=Decimal("1000000"),
            available_cash_rub=Decimal("300000"),
        ),
        (_candidate(),),
        _policy(
            reserve_rub=Decimal("0"),
            max_turnover_percent=Decimal("50"),
        ),
        now=NOW,
    )

    assert plan.status == "feasible"
    allocation = plan.allocations[0]
    assert allocation.lots == 40
    assert allocation.exposure_rub == Decimal("199600")
    assert allocation.exposure_rub <= Decimal("200000")


def test_stale_quote_and_unknown_rating_fail_closed() -> None:
    screen = screen_candidate(
        _candidate(
            rating_tier="unknown",
            quote_at=NOW - timedelta(hours=2),
        ),
        _policy(),
        now=NOW,
    )

    assert screen.eligible is False
    assert "credit_rating_missing" in screen.reasons
    assert "quote_stale_or_missing" in screen.reasons
    assert screen.net_real_ytw_percent is None


def test_special_bond_cashflows_are_excluded_until_supported() -> None:
    screen = screen_candidate(
        _candidate(
            floating_coupon=True,
            amortization=True,
        ),
        _policy(),
        now=NOW,
    )

    assert screen.eligible is False
    assert "floating_coupon_cashflow_not_supported" in screen.reasons
    assert "amortizing_cashflow_not_supported" in screen.reasons


def test_replacement_requires_tax_evidence() -> None:
    scenario = compare_replacement(
        ReplacementCase(
            source_instrument_uid="old-bond",
            source_market_value_rub=Decimal("50000"),
            source_hold_ytw_percent=Decimal("4"),
            sell_commission_rub=Decimal("100"),
            estimated_tax_rub=None,
            candidate=_candidate(),
        ),
        _policy(),
        now=NOW,
    )

    assert scenario.action == "hold"
    assert scenario.reasons == ("tax_estimate_missing",)
    assert scenario.execution_enabled is False


def test_replacement_only_passes_when_net_improvement_clears_no_trade_band() -> None:
    profitable = compare_replacement(
        ReplacementCase(
            source_instrument_uid="old-bond",
            source_market_value_rub=Decimal("50000"),
            source_hold_ytw_percent=Decimal("4"),
            sell_commission_rub=Decimal("200"),
            estimated_tax_rub=Decimal("800"),
            candidate=_candidate(),
        ),
        _policy(),
        now=NOW,
    )
    churn = compare_replacement(
        ReplacementCase(
            source_instrument_uid="old-bond",
            source_market_value_rub=Decimal("50000"),
            source_hold_ytw_percent=Decimal("8"),
            sell_commission_rub=Decimal("200"),
            estimated_tax_rub=Decimal("800"),
            candidate=_candidate(),
        ),
        _policy(),
        now=NOW,
    )

    assert profitable.action == "replace"
    assert profitable.lots == 9
    assert profitable.projected_improvement_rub is not None
    assert profitable.projected_improvement_rub > 0
    assert churn.action == "hold"
    assert churn.reasons == ("replacement_does_not_clear_no_trade_band",)
