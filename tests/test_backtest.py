"""Synthetic prices exist only here; test the chronology and money invariants."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from omnicio.backtest import HistoricalCashflow, ResearchAsset, ResearchCosts, run_strategy_backtest
from omnicio.strategy import preset_document
from omnicio.strategy_assessment import StrategyCandidateFacts, StrategyFact
from omnicio.tbank import TBankHistoricCandle

START = datetime(2025, 1, 1, tzinfo=UTC)
END = START + timedelta(days=200)
SOURCE = "https://synthetic.example/test-fixture"
ZERO_COSTS = ResearchCosts(Decimal(0), Decimal(0))


def research_document(preset="balanced"):
    document = preset_document(preset)
    document["allocation"] = {"shares": 100, "bonds": 0, "funds": 0, "cash": 0}
    document["profile"].update(
        reserve_rub="0", planned_withdrawal_rub="0", max_drawdown_percent="100"
    )
    for name in (
        "max_instrument_percent",
        "max_issuer_percent",
        "max_sector_percent",
        "max_group_percent",
        "max_share_percent",
        "turnover_budget_percent",
        "max_daily_turnover_participation_percent",
    ):
        document["policy"][name] = "100"
    return document


def prices(uid="a", *, increasing=False, lot=1):
    bars = []
    prior = Decimal(100)
    for index in range(200):
        price = Decimal(100) + (Decimal(index) / 10 if increasing else 0)
        bars.append(
            TBankHistoricCandle(
                uid,
                str(price),
                100000,
                START + timedelta(days=index),
                True,
                "CANDLE_SOURCE_EXCHANGE",
                str(prior),
                str(max(prior, price) + 1),
                str(min(prior, price) - 1),
            )
        )
        prior = price
    facts = {
        key: StrategyFact(value, START, SOURCE)
        for key, value in (
            ("issuer_id", "issuer-" + uid),
            ("group_id", "group-" + uid),
            ("sector", uid),
        )
    }
    return ResearchAsset(
        StrategyCandidateFacts(uid, uid.upper(), "shares", lot, "RUB", facts), tuple(bars)
    )


def run(assets=None, *, document=None, costs=ZERO_COSTS, capital="10000", **kwargs):
    return run_strategy_backtest(
        document or research_document(),
        assets or [prices()],
        from_at=START,
        to_at=END,
        now=END,
        initial_capital_rub=Decimal(capital),
        costs=costs,
        **kwargs,
    )


def test_flat_prices_charge_real_cost_model_once_and_do_not_spend_negative_cash():
    result = run(costs=ResearchCosts(Decimal(100), Decimal(100)))
    assert result["status"] == "computed", result["missing_requirements"]
    assert result["basis"] == "unadjusted_price"
    assert "Изменение цены" in result["return_label"]
    assert Decimal(result["metrics"]["ending_nav_rub"]) == Decimal("9803.02")
    assert Decimal(result["metrics"]["transaction_costs_rub"]) == Decimal("196.98")
    assert result["metrics"]["trades"] == 1
    assert all(Decimal(row["cash_rub"]) >= 0 for row in result["equity_curve"])
    assert result["probability_of_profit"] is None
    assert result["probability_reason"]
    assert result["benchmark"]["basis"] == result["basis"]


def test_test_prices_cannot_change_training_selection_or_first_execution():
    assets = [prices("a", increasing=True), prices("b")]
    original = run(assets)
    bars = list(assets[0].candles)
    for index in range(160, 200):
        bar = bars[index]
        bars[index] = replace(bar, open="115", high="126", low="105", close="106")
    modified = run([replace(assets[0], candles=tuple(bars)), assets[1]])
    assert original["status"] == modified["status"] == "computed"
    assert original["selection"] == modified["selection"]
    assert original["equity_curve"][:15] == modified["equity_curve"][:15]
    assert original["metrics"]["net_return_percent"] != modified["metrics"]["net_return_percent"]
    assert original["data_hash"] != modified["data_hash"]


def test_repeated_research_is_reproducible_and_observation_counts_are_honest():
    first, second = run([prices(increasing=True)]), run([prices(increasing=True)])
    assert first == second
    assert first["period"]["train_observations"] == 140
    assert first["period"]["test_observations"] == 60
    assert first["metrics"]["return_observations"] == 60
    assert len(first["equity_curve"]) == 61
    assert Decimal(first["metrics"]["net_return_percent"]) > 0
    assert first["assumptions"]["configurations_tested"] == 1


def test_buy_is_filled_at_next_open_with_integer_lots_and_cash_capacity():
    asset = prices(lot=3)
    bars = list(asset.candles)
    bars[140] = replace(bars[140], open="140", high="141", low="139", close="140")
    bars[141] = replace(bars[141], open="140", high="141", low="99", close="100")
    result = run([replace(asset, candles=tuple(bars))], capital="1000")
    assert result["status"] == "computed"
    # Six shares in two lots are affordable at the actual 140 open. Sizing from
    # the signal's 100 close must not invent execution at 100 or fractional lots.
    assert Decimal(result["equity_curve"][1]["cash_rub"]) == Decimal(160)
    assert Decimal(result["equity_curve"][2]["nav_rub"]) == Decimal(760)


def test_current_fundamentals_are_not_backdated_to_fiscal_period_end():
    asset = prices()
    facts = dict(asset.candidate.facts)
    facts.update(
        {
            key: StrategyFact(Decimal(value), END, SOURCE)
            for key, value in (
                ("roe_percent", "25"),
                ("debt_to_ebitda", "1"),
                ("free_cashflow_yield_percent", "10"),
            )
        }
    )
    result = run(
        [replace(asset, candidate=replace(asset.candidate, facts=facts))],
        document=research_document("buffett"),
    )
    assert result["status"] == "insufficient_data"
    assert "missing:roe_percent" in result["missing_requirements"]
    assert result["metrics"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "same_day",
        "reversed",
        "incomplete",
        "wrong_source",
        "corporate_action",
        "price_break",
        "gap",
    ],
)
def test_invalid_or_discontinuous_history_is_not_silently_repaired(fault):
    asset = prices()
    bars = list(asset.candles)
    if fault == "duplicate":
        bars.insert(150, bars[150])
    elif fault == "same_day":
        bars.insert(151, replace(bars[150], time=bars[150].time + timedelta(hours=1)))
    elif fault == "reversed":
        bars.reverse()
    elif fault == "incomplete":
        bars = [replace(bar, is_complete=False) for bar in bars]
    elif fault == "wrong_source":
        bars[150] = replace(bars[150], source="dealer")
    elif fault == "corporate_action":
        asset = replace(asset, corporate_action_dates=(START + timedelta(days=155),))
    elif fault == "price_break":
        bars[150] = replace(bars[150], open="10", high="11", low="9", close="10")
    else:
        bars = bars[:150] + bars[170:]
    result = run([replace(asset, candles=tuple(bars))])
    assert result["status"] == "insufficient_data"
    assert result["metrics"] is None
    assert result["missing_requirements"]
    assert result["equity_curve"] == []


def test_dividend_entitlement_and_payment_are_separate_without_double_counting():
    asset = prices()
    bars = list(asset.candles)
    for index in range(155, 200):
        bars[index] = replace(bars[index], open="90", high="91", low="89", close="90")
    event = HistoricalCashflow(
        START + timedelta(days=155), START + timedelta(days=160), Decimal(10), SOURCE
    )
    asset = replace(
        asset,
        candles=tuple(bars),
        basis="verified_total_return",
        cashflows=(event,),
        lot_history_verified=True,
        cashflow_history_verified=True,
        verification_source=SOURCE,
    )
    result = run([asset])
    assert result["status"] == "computed", result["missing_requirements"]
    assert result["basis"] == "verified_total_return"
    # A 10% ex-distribution price drop is offset by a receivable, then by cash.
    assert all(Decimal(row["nav_rub"]) == Decimal(10000) for row in result["equity_curve"])
    before_payment = next(
        row
        for row in result["equity_curve"]
        if row["time"] == (START + timedelta(days=158)).isoformat()
    )
    assert Decimal(before_payment["cash_rub"]) == 0
    assert Decimal(before_payment["receivables_rub"]) == 1000
    assert Decimal(result["metrics"]["net_return_percent"]) == 0
    assert Decimal(result["metrics"]["max_drawdown_percent"]) == 0


def test_unverified_total_return_claim_is_rejected():
    result = run([replace(prices(), basis="verified_total_return")])
    assert result["status"] == "insufficient_data"
    assert "total_return_basis_not_verified" in result["missing_requirements"]


def test_bond_total_return_requires_principal_and_accrual_history():
    asset = prices()
    facts = dict(asset.candidate.facts)
    facts.update(
        {
            key: StrategyFact(value, START, SOURCE)
            for key, value in (
                ("rating", "AAA"),
                ("maturity_date", END + timedelta(days=100)),
                ("perpetual", False),
            )
        }
    )
    data = research_document()
    data["allocation"].update(shares=0, bonds=100)
    data["policy"]["max_bond_percent"] = "100"
    result = run(
        [
            replace(
                asset,
                candidate=replace(asset.candidate, asset_class="bonds", facts=facts),
                basis="verified_total_return",
                lot_history_verified=True,
                cashflow_history_verified=True,
                verification_source=SOURCE,
            )
        ],
        document=data,
    )
    assert result["status"] == "insufficient_data"
    assert "bond_principal_and_accrual_history_required" in result["missing_requirements"]


def test_liquidity_horizon_caps_total_position_as_well_as_daily_order():
    data = research_document()
    data["profile"]["liquidity_horizon_days"] = "2"
    data["policy"]["max_daily_turnover_participation_percent"] = "10"
    asset = prices()
    asset = replace(asset, candles=tuple(replace(bar, volume_lots=100) for bar in asset.candles))
    result = run([asset], document=data)
    assert result["status"] == "computed"
    # Ten lots per order; at most two days of that liquidity may be held.
    assert result["metrics"]["trades"] == 2
    assert Decimal(result["metrics"]["ending_cash_rub"]) == 8000
    assert Decimal(result["metrics"]["ending_nav_rub"]) == 10000


def test_research_hash_includes_lot_and_verification_evidence():
    original = run()
    different_lot = run([prices(lot=2)])
    different_evidence = run([replace(prices(), verification_source=SOURCE)])
    assert original["metrics"] == different_lot["metrics"] == different_evidence["metrics"]
    assert len({row["data_hash"] for row in (original, different_lot, different_evidence)}) == 3


def test_partial_research_exposes_unfilled_target_without_inventing_assets():
    data = research_document()
    data["allocation"].update(shares=30, bonds=50, funds=10, cash=10)
    result = run(document=data)
    assert result["status"] == "computed"
    assert result["complete_strategy_coverage"] is False
    assert Decimal(result["research_asset_weight_percent"]) == 30
    assert Decimal(result["selection"]["cash_weight_percent"]) == 70
    assert "eligible_bonds" in result["missing_requirements"]
    assert result["limitations"]


def test_empirical_tail_loss_and_volatility_include_transaction_costs():
    result = run(costs=ResearchCosts(Decimal(100), Decimal(100)))
    metrics = result["metrics"]
    assert Decimal(metrics["annualized_volatility_percent"]) > 0
    assert Decimal(metrics["expected_shortfall_95_percent"]) > Decimal(metrics["var_95_percent"])
    assert Decimal(metrics["max_drawdown_percent"]) > 0


def test_future_window_and_nonfinite_costs_are_rejected_before_research():
    document = research_document()
    capital = Decimal(1000)
    nonfinite_costs = ResearchCosts(Decimal("NaN"), Decimal(0))
    with pytest.raises(ValueError, match="window"):
        run_strategy_backtest(
            document,
            [],
            from_at=START,
            to_at=END,
            now=START,
            initial_capital_rub=capital,
            costs=ZERO_COSTS,
        )
    with pytest.raises(ValueError, match="decimal"):
        run(costs=nonfinite_costs)
