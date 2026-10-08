"""Synthetic prices exist only here; test the chronology and money invariants."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from omnicio.backtest import (
    FactorObservation,
    HistoricalCashflow,
    HistoricalSplit,
    ResearchAsset,
    ResearchCosts,
    history_candidate,
    research_history_candidate,
    run_strategy_backtest,
)
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


def test_history_boundary_trim_uses_only_observed_common_sessions_and_preserves_old_replay():
    from omnicio.backtest import _common_research_times

    first, second = prices("a"), prices("b")
    panel = {
        "a": {bar.time: bar for bar in first.candles},
        "b": {bar.time: bar for bar in second.candles[3:-2]},
    }
    split = START + (END - START) * 0.7
    observations, training, testing, missing = _common_research_times(panel, split)
    assert not missing
    assert observations == len(second.candles) - 5
    assert all(when in panel["a"] and when in panel["b"] for when in (*training, *testing))
    assert "unaligned_history" in _common_research_times(
        panel, split, trim_boundaries=False,
    )[3]
    panel["b"].pop(second.candles[100].time)
    assert "unaligned_history" in _common_research_times(panel, split)[3]


def test_historical_income_screen_uses_only_paid_income_and_never_future_principal():
    asset = prices()
    cutoff = START + timedelta(days=140)
    observed = (
        HistoricalCashflow(
            START + timedelta(days=100), START + timedelta(days=110), Decimal(6), SOURCE
        ),
        HistoricalCashflow(
            START + timedelta(days=120),
            START + timedelta(days=130),
            Decimal(20),
            SOURCE,
            "principal",
        ),
        HistoricalCashflow(
            START + timedelta(days=145), START + timedelta(days=150), Decimal(90), SOURCE
        ),
    )
    document = research_document("income")
    document["policy"]["securities_tax_rate_percent"] = "13"
    candidate = history_candidate(
        asset.candidate,
        asset.candles,
        as_of=cutoff,
        cashflows=observed,
        document=document,
        costs=ZERO_COSTS,
    )
    assert candidate.facts["cashflow_yield_percent"].value == 6
    assert candidate.facts["dividend_yield_percent"].value == 6
    assert candidate.facts["net_yield_percent"].value == Decimal("5.22")
    assert candidate.facts["dividend_declared"].available_at == cutoff
    assert not history_candidate(
        asset.candidate, asset.candles, as_of=START + timedelta(days=100), cashflows=observed
    ).facts.get("cashflow_yield_percent")


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


def test_out_of_range_exponent_is_rejected_without_decimal_context_overflow():
    with pytest.raises(ValueError, match="research_decimal_invalid"):
        run(costs=ResearchCosts(Decimal("1e1000000"), Decimal(0)))


def test_rebalance_band_and_minimum_effect_control_actual_simulated_orders():
    ordinary = research_document()
    baseline = run(document=ordinary)
    ordinary["policy"]["no_trade_band_percent"] = "100"
    band = run(document=ordinary)
    assert baseline["metrics"]["trades"] > 0
    assert band["metrics"]["trades"] == 0
    ordinary["policy"]["no_trade_band_percent"] = "0"
    ordinary["policy"]["min_replace_benefit_rub"] = "1000000000"
    minimum = run(document=ordinary)
    assert minimum["metrics"]["trades"] == 0


def test_tax_and_stress_are_explicit_consumers_not_probability_claims():
    asset = prices()
    cashflow = HistoricalCashflow(
        START + timedelta(days=160), START + timedelta(days=170), Decimal(10), SOURCE
    )
    asset = replace(
        asset,
        basis="verified_total_return",
        cashflows=(cashflow,),
        lot_history_verified=True,
        cashflow_history_verified=True,
        verification_source=SOURCE,
    )
    document = research_document()
    document["policy"]["securities_tax_rate_percent"] = "13"
    document["policy"]["uncertainty_haircut_percent"] = "25"
    result = run([asset], document=document)
    assert result["status"] == "computed"
    assert Decimal(result["metrics"]["taxes_rub"]) == Decimal("130")
    stress = result["stress_scenario"]
    assert Decimal(stress["loss_rub"]) > 0
    assert stress["probability"] is None
    assert result["assumptions"]["tax_method"] == (
        "positive_realized_gain_and_distributions_no_offsets"
    )


def test_robustness_has_three_declared_windows_without_best_period_selection():
    from omnicio.backtest import research_robustness

    result = research_robustness(
        research_document(),
        [prices(increasing=True)],
        from_at=START,
        to_at=END,
        initial_capital_rub=Decimal(10000),
        costs=ZERO_COSTS,
        now=END,
    )
    assert result["computed_windows"] == 3
    assert [row["period"]["to"] for row in result["windows"]] == [
        (START + timedelta(days=days)).isoformat() for days in (120, 160, 200)
    ]
    assert all(
        row["period"]["train_end"] <= row["period"]["test_from"] for row in result["windows"]
    )


def test_split_changes_units_without_fabricating_loss_and_unknown_actions_block():
    asset = prices()
    when = START + timedelta(days=165)
    bars = tuple(
        replace(bar, open="50", high="51", low="49", close="50") if bar.time >= when else bar
        for bar in asset.candles
    )
    asset = replace(asset, candles=bars, corporate_action_dates=(when,))
    assert run([asset])["status"] == "insufficient_data"
    asset = replace(asset, splits=(HistoricalSplit(when, Decimal(2), SOURCE),))
    result = run([asset])
    assert result["status"] == "computed", result["missing_requirements"]
    assert Decimal(result["metrics"]["ending_nav_rub"]) == 10000
    assert Decimal(result["metrics"]["max_drawdown_percent"]) == 0
    assert result["selection"] == run([prices()])["selection"]


def test_reverse_split_requiring_fractional_settlement_is_explicitly_incomplete():
    asset = prices()
    when = START + timedelta(days=165)
    bars = tuple(
        replace(bar, open="200", high="201", low="199", close="200") if bar.time >= when else bar
        for bar in asset.candles
    )
    result = run(
        [replace(asset, candles=bars, splits=(HistoricalSplit(when, Decimal("0.5"), SOURCE),))],
        capital="10100",
    )
    assert result["status"] == "insufficient_data"
    assert "fractional_split_cash_settlement_required" in result["missing_requirements"]
    assert result["metrics"] is None


def test_dalio_factors_are_jointly_estimated_only_from_published_observations():
    asset, prior, bars, factors = prices(), Decimal(100), [], []
    for index, bar in enumerate(asset.candles):
        growth = Decimal(index % 5 - 2) / 1000
        inflation = Decimal(index % 7 - 3) / 1000
        close = prior * (1 + 2 * growth - 3 * inflation)
        bars.append(
            replace(
                bar,
                open=str(prior),
                close=str(close),
                high=str(max(prior, close) + 1),
                low=str(min(prior, close) - 1),
            )
        )
        factors.append(
            FactorObservation(bar.time, bar.time + timedelta(days=1), growth, inflation, SOURCE)
        )
        prior = close
    cutoff = START + timedelta(days=140)
    result = history_candidate(asset.candidate, bars, factors=factors, as_of=cutoff)
    assert abs(result.facts["growth_beta"].value - 2) < Decimal("1e-20")
    assert abs(result.facts["inflation_beta"].value + 3) < Decimal("1e-20")
    assert result.facts["factor_observations"].value == 139
    unpublished = [replace(row, available_at=END) for row in factors]
    missing = history_candidate(asset.candidate, bars, factors=unpublished, as_of=cutoff)
    assert "growth_beta" not in missing.facts
    singular = [replace(row, inflation_change=row.growth_change) for row in factors]
    missing = history_candidate(asset.candidate, bars, factors=singular, as_of=cutoff)
    assert "growth_beta" not in missing.facts


@pytest.mark.parametrize("ratio", [Decimal(0), Decimal("NaN")])
def test_corrupt_split_is_unavailable_before_math_and_cannot_replace_a_chosen_asset(ratio):
    asset = replace(
        prices(), splits=(HistoricalSplit(START + timedelta(days=60), ratio, SOURCE),)
    )
    result = run([asset, prices("b")])
    assert result["status"] == "insufficient_data"
    assert "split_evidence_invalid" in result["missing_requirements"]
    assert result["metrics"] is None
    assert all(row["instrument_uid"] != "a" for row in result["selection"]["selected"])
    with pytest.raises(ValueError, match="split_evidence_invalid"):
        research_history_candidate(asset, as_of=END)


def test_invalid_observed_income_is_not_allowed_to_poison_an_otherwise_valid_price_screen():
    asset = replace(
        prices(),
        observed_cashflows=(HistoricalCashflow(
            START + timedelta(days=60), START + timedelta(days=65), Decimal("NaN"), SOURCE
        ),),
    )
    result = run([asset])
    assert result["status"] == "insufficient_data"
    assert "invalid_distribution_event" in result["missing_requirements"]
    with pytest.raises(ValueError, match="invalid_distribution_event"):
        research_history_candidate(asset, as_of=END)


def test_naive_factor_time_is_rejected_before_comparison_with_aware_cutoff():
    asset = replace(prices(), factors=(FactorObservation(
        START, START.replace(tzinfo=None), Decimal(1), Decimal(1), SOURCE,
    ),))
    result = run([asset])
    assert result["status"] == "insufficient_data"
    assert "factor_history_invalid" in result["missing_requirements"]


def test_current_candidate_requires_actual_bars_even_if_imported_facts_claim_history():
    asset = prices()
    candidate = history_candidate(asset.candidate, asset.candles, as_of=END)
    asset = replace(asset, candidate=candidate, candles=())
    with pytest.raises(ValueError, match="insufficient_training_history"):
        research_history_candidate(asset, as_of=END)


def test_actual_provider_future_timestamp_cannot_overflow_or_enter_history_math():
    from omnicio.tbank import _historic_exchange_candle

    future = _historic_exchange_candle({
        "time": "9999-12-31T00:00:00Z", "isComplete": True,
        "candleSourceType": "CANDLE_SOURCE_EXCHANGE", "volume": "100",
        **{key: {"units": "999", "nano": 0} for key in ("open", "high", "low", "close")},
    }, "a")
    asset = prices()
    asset = replace(asset, candles=(*asset.candles, future))
    result = run([asset])
    assert result["status"] == "computed"
    assert result["period"]["observations"] == 200
    candidate = research_history_candidate(asset, as_of=END)
    assert candidate.facts["history_observations"].value == 200
    assert candidate.facts["price_rub"].value == 100


def test_complete_flag_does_not_make_an_unfinished_daily_interval_available():
    asset = prices()
    premature = replace(asset.candles[-1], time=END, open="999", high="999",
                        low="999", close="999", is_complete=True)
    asset = replace(asset, candles=(*asset.candles, premature))
    candidate = research_history_candidate(asset, as_of=END + timedelta(hours=12))
    assert candidate.facts["history_observations"].value == 200
    assert candidate.facts["price_rub"].value == 100


def test_current_engine_preserves_withdrawals_in_addition_to_target_cash_and_replays_old_math():
    data = research_document()
    data["allocation"].update(shares=50, cash=50)
    data["profile"].update(reserve_rub="1000", planned_withdrawal_rub="2000")
    current = run(document=data)
    old = run(document=data, engine_version="1.3.0")
    assert Decimal(current["metrics"]["ending_cash_rub"]) == 7000
    assert Decimal(old["metrics"]["ending_cash_rub"]) == 5000
    assert "historical_outcomes" not in old
    assert "holding_constraints" not in old


def test_observed_zero_volume_prevents_phantom_fills_even_when_previous_volume_was_high():
    asset = prices()
    asset = replace(asset, candles=tuple(
        replace(bar, volume_lots=0) if index >= 140 else bar
        for index, bar in enumerate(asset.candles)
    ))
    current = run([asset])
    old = run([asset], engine_version="1.3.0")
    assert current["metrics"]["trades"] == 0
    assert Decimal(current["metrics"]["ending_cash_rub"]) == 10000
    assert old["metrics"]["trades"] == 1


def test_minimum_rebalance_effect_applies_to_actual_fill_after_liquidity_clipping():
    data = research_document()
    data["policy"]["min_replace_benefit_rub"] = "500"
    asset = prices()
    asset = replace(asset, candles=tuple(
        replace(bar, volume_lots=1) if index >= 140 else bar
        for index, bar in enumerate(asset.candles)
    ))
    result = run([asset], document=data)
    assert result["status"] == "computed"
    assert result["metrics"]["trades"] == 0
    assert Decimal(result["metrics"]["ending_cash_rub"]) == 10000


def test_current_turnover_budget_includes_commission_and_preserves_archived_gross_only_math():
    data = research_document()
    data["policy"]["turnover_budget_percent"] = "10"
    costs = ResearchCosts(Decimal(100), Decimal(0))
    current = run(document=data, costs=costs)
    old = run(document=data, costs=costs, engine_version="1.3.0")
    # A 1000 RUB budget permits nine 100 RUB lots plus their 9 RUB commission.
    # Ten lots would spend 1010 RUB and exceed the same execution-plan budget.
    assert Decimal(current["equity_curve"][1]["cash_rub"]) == 9091
    assert Decimal(old["equity_curve"][1]["cash_rub"]) == 8990


def test_cash_only_model_is_computed_without_invented_candles_sessions_or_probabilities():
    from omnicio.backtest import research_robustness

    data = research_document()
    data["allocation"].update(shares=0, cash=100)
    data["policy"]["securities_tax_rate_percent"] = "0"
    result = run_strategy_backtest(
        data, [], from_at=START, to_at=END, now=END,
        initial_capital_rub=Decimal(10000), costs=ZERO_COSTS,
    )
    assert result["status"] == "computed"
    assert result["basis"] == "cash_balance_model"
    assert result["equity_curve"] == []
    assert result["sources"] == []
    assert result["benchmark"] is None
    assert result["period"]["observations"] == 0
    assert result["period"]["train_end"] is None
    assert result["period"]["test_from"] is None
    metrics = result["metrics"]
    assert metrics["return_observations"] == metrics["trades"] == 0
    assert Decimal(metrics["ending_cash_rub"]) == Decimal(metrics["ending_nav_rub"]) == 10000
    assert Decimal(metrics["net_return_percent"]) == 0
    assert metrics["var_95_percent"] is metrics["expected_shortfall_95_percent"] is None
    assert metrics["annualized_volatility_percent"] is None
    assert result["probability_of_profit"] is None
    projection = result["cash_projection"]
    assert projection["assumed_annual_cash_rate_percent"] == "0"
    assert projection["personal_constraints_ready"] is True
    assert all(row["reason"] == "cash_only_no_market_observations"
               and row["windows"] == 0 and row["profit_frequency_percent"] is None
               for row in result["historical_outcomes"]["horizons"])
    robustness = research_robustness(
        data, [], from_at=START, to_at=END, now=END,
        initial_capital_rub=Decimal(10000), costs=ZERO_COSTS,
    )
    assert robustness["method"] == "not_applicable_cash_balance_model"
    assert robustness["windows"] == []
    assert robustness["computed_windows"] == 0


@pytest.mark.parametrize("problem", ["unknown", "withdrawal_conflict"])
def test_cash_only_model_preserves_unknown_or_conflicting_personal_requirements(problem):
    data = research_document()
    data["allocation"].update(shares=0, cash=100)
    data["policy"]["securities_tax_rate_percent"] = "0"
    if problem == "unknown":
        data["profile"]["reserve_rub"] = None
        reason = "profile.reserve_rub"
    else:
        data["profile"]["planned_withdrawal_rub"] = "100"
        reason = "cash_reserve_conflict"
    result = run_strategy_backtest(
        data, [], from_at=START, to_at=END, now=END,
        initial_capital_rub=Decimal(10000), costs=ZERO_COSTS,
    )
    assert result["status"] == "insufficient_data"
    assert result["complete_strategy_coverage"] is False
    assert result["selection"]["candidate_selection_ready"] is False
    assert reason in result["missing_requirements"]
    assert result["cash_projection"]["personal_constraints_ready"] is False
    assert result["metrics"] is None


def test_open_price_gap_cannot_spend_another_assets_allocation_or_breach_concentration():
    first = prices()
    first = replace(first, candles=tuple(
        replace(bar, open="140", high="141", low="139", close="140") if index >= 140 else bar
        for index, bar in enumerate(first.candles)
    ))
    data = research_document()
    data["policy"]["max_instrument_percent"] = "50"
    result = run([first, prices("b")], document=data)
    # Opening prices permit 35 lots of A and 50 lots of B. The old previous-close
    # sizing bought 50 A (=70% NAV) and left only enough cash for 30 B.
    assert result["metrics"]["trades"] == 2
    assert Decimal(result["metrics"]["ending_cash_rub"]) == 100
    assert result["holding_constraints"]["breach_sessions"] == 0
    assert result["holding_constraints"]["breaches"] == []


def test_later_purchase_fees_do_not_push_earlier_purchase_above_weight_ceiling():
    data = research_document()
    data["policy"]["max_instrument_percent"] = "50"
    result = run([prices(), prices("b")], document=data,
                 costs=ResearchCosts(Decimal(10), Decimal(0)))
    assert result["metrics"]["trades"] == 2
    assert Decimal(result["metrics"]["ending_nav_rub"]) == Decimal("9990.2")
    assert Decimal(result["metrics"]["ending_cash_rub"]) == Decimal("190.2")
    assert result["holding_constraints"]["breach_sessions"] == 0


def test_expected_distribution_tax_is_in_nav_at_entitlement_not_a_fake_payment_day_loss():
    asset = prices()
    event = HistoricalCashflow(
        START + timedelta(days=155), START + timedelta(days=160), Decimal(10), SOURCE
    )
    asset = replace(
        asset,
        candles=tuple(replace(bar, open="90", high="91", low="89", close="90")
                      if index >= 155 else bar for index, bar in enumerate(asset.candles)),
        basis="verified_total_return", cashflows=(event,), lot_history_verified=True,
        cashflow_history_verified=True, verification_source=SOURCE,
    )
    data = research_document()
    data["policy"]["securities_tax_rate_percent"] = "13"
    result = run([asset], document=data)
    unpaid = result["equity_curve"][20]
    paid = result["equity_curve"][21]
    assert Decimal(unpaid["receivables_rub"]) == 870
    assert Decimal(unpaid["nav_rub"]) == Decimal(paid["nav_rub"]) == 9870
    assert Decimal(paid["receivables_rub"]) == 0
    assert Decimal(result["metrics"]["taxes_rub"]) == 130


def test_non_overlapping_outcomes_are_computed_from_executed_nav_without_future_probability():
    asset = prices()
    asset = replace(asset, candles=tuple(
        replace(bar, open="100", high="103", low="99",
                close="102" if index % 2 == 0 else "100") if index >= 140 else bar
        for index, bar in enumerate(asset.candles)
    ))
    result = run([asset])
    outcomes = result["historical_outcomes"]
    daily, weekly, monthly = outcomes["horizons"]
    assert result["probability_of_profit"] is None
    assert outcomes["future_probability_calibrated"] is False
    assert daily["windows"] == 60
    assert daily["profit_windows"] == daily["loss_windows"] == 30
    assert daily["flat_windows"] == 0
    assert Decimal(daily["profit_frequency_percent"]) == 50
    assert Decimal(daily["loss_frequency_percent"]) == 50
    assert daily["from"] == result["equity_curve"][0]["time"]
    assert daily["to"] == result["equity_curve"][-1]["time"]
    assert weekly["windows"] == 12 and monthly["windows"] == 2
    assert monthly["discarded_trailing_sessions"] == 18
    assert weekly["profit_frequency_percent"] is None
    assert monthly["profit_frequency_percent"] is None
    interval = daily["sampling_interval"]
    assert interval["method"] == "stationary_block_bootstrap_of_profit_indicators"
    assert interval["confidence"] == "0.95"
    assert Decimal(interval["lower_percent"]) < 50 < Decimal(interval["upper_percent"])
    assert outcomes == run([asset])["historical_outcomes"]


def test_constant_outcomes_do_not_get_a_falsely_certain_bootstrap_interval():
    row = run([prices(increasing=True)])["historical_outcomes"]["horizons"][0]
    assert Decimal(row["profit_frequency_percent"]) == 100
    assert row["sampling_interval"]["lower_percent"] is None
    assert row["sampling_interval"]["upper_percent"] is None
    assert row["sampling_interval"]["reason"] == "no_profit_indicator_variation"


def test_partial_basket_is_not_advertised_as_the_whole_strategy_profit_frequency():
    data = research_document()
    data["allocation"].update(shares=30, bonds=50, funds=10, cash=10)
    outcomes = run(document=data)["historical_outcomes"]
    assert outcomes["status"] == "insufficient_data"
    assert outcomes["complete_strategy_coverage"] is False
    assert all(row["profit_frequency_percent"] is None for row in outcomes["horizons"])
    assert all(row["reason"] == "incomplete_strategy_coverage" for row in outcomes["horizons"])


def test_requested_horizon_uses_calendar_months_and_never_silently_21_sessions():
    data = research_document()
    data["profile"]["horizon_months"] = "2"
    horizon = run(document=data)["historical_outcomes"]["requested_horizon"]
    assert horizon["calendar_months"] == "2"
    assert horizon["first_window_end"] == "2025-07-21T00:00:00+00:00"
    assert horizon["one_window_covered"] is False
    assert horizon["future_probability_of_profit"] is None
    assert horizon["reason"] == "insufficient_calendar_horizon_history"


def test_risk_stop_does_not_make_stationary_interval_from_a_known_cash_regime_change():
    data = research_document()
    data["profile"]["max_drawdown_percent"] = "1"
    asset = prices()
    asset = replace(asset, candles=tuple(
        replace(bar, open="90", high="91", low="89", close="90") if index >= 150 else bar
        for index, bar in enumerate(asset.candles)
    ))
    result = run([asset], document=data)
    assert result["metrics"]["risk_limit_triggered"] is True
    interval = result["historical_outcomes"]["horizons"][0]["sampling_interval"]
    assert interval["lower_percent"] is None
    assert interval["reason"] == "strategy_risk_stop_regime_change"


def test_post_close_price_drift_breaches_are_reported_without_claiming_hard_protection():
    data = research_document()
    data["policy"]["max_instrument_percent"] = "50"
    first = prices()
    first = replace(first, candles=tuple(
        replace(bar, open="100", high="111", low="99", close="110") if index >= 141 else bar
        for index, bar in enumerate(first.candles)
    ))
    result = run([first, prices("b")], document=data)
    assert result["holding_constraints"]["breach_sessions"] > 0
    assert "instrument_cap:a" in result["holding_constraints"]["breaches"]
