"""Financial invariants for strategy construction; synthetic broker data only."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import pytest

from backend.strategy_construction import allocation_policy, profile_construction, target_value, permitted_classes
from backend.strategy_actions import affordable_target_lots, next_action_plan
from backend.strategy_sales import reduction_lots
from backend.strategy_yield import annual_yield, parse_key_rate, yield_filter
from backend.fund_policy import fund_reasons
from backend.tests.test_portfolio_mandate import configured
from backend.tests.test_volume_workspace import fixture, activate, config
from backend import volume_state as state


def policy():
    value = configured()
    value["tuning"] = {"profile_id": "balanced", "enabled": True}
    value["construction"] = profile_construction("balanced", {})
    value["construction"].update(loss_capacity_confirmed=True, income_stability="stable")
    value["mandate"]["loss_capacity_percent"] = "10"
    value["horizon_months"] = 120
    return value


def test_age_cannot_invent_loss_capacity():
    value = policy()
    value["construction"]["loss_capacity_confirmed"] = False
    for age in (18, 30, 65, 100):
        value["construction"]["age"] = age
        result = allocation_policy(value)
        assert result["weights_percent"]["cash"] == "100.00"
        assert result["age_used_as_loss_capacity"] is False


def test_weights_and_stress_keep_budget_under_all_combinations():
    for profile in ("capital", "coupon", "balanced", "growth", "equity"):
        for horizon in (12, 36, 120):
            for capacity in (0, 1, 5, 30):
                value = policy()
                value["tuning"]["profile_id"] = profile
                value["construction"] = profile_construction(profile, {})
                value["construction"].update(loss_capacity_confirmed=True, income_stability="stable")
                value["horizon_months"] = horizon
                value["mandate"]["loss_capacity_percent"] = str(capacity)
                before = deepcopy(value)
                result = allocation_policy(value)
                weights = {key: Decimal(number) for key, number in result["weights_percent"].items()}
                assert sum(weights.values()) == 100
                assert all(weight >= 0 for weight in weights.values())
                assert Decimal(result["stress_loss_percent"]) <= capacity
                if horizon < 36:
                    assert weights["share"] == weights["etf"] == 0
                assert value == before


@pytest.mark.parametrize("profile", ["capital", "balanced", "growth"])
def test_new_presets_do_not_allocate_to_funds(profile):
    value = policy()
    value["tuning"]["profile_id"] = profile
    value["construction"] = profile_construction(profile, {})
    value["construction"].update(loss_capacity_confirmed=True, income_stability="stable")
    value["mandate"]["loss_capacity_percent"] = "100"
    assert value["construction"]["version"] == 2
    assert "etf" not in permitted_classes(value)
    result = allocation_policy(value)
    assert Decimal(result["weights_percent"]["etf"]) == 0
    assert Decimal(result["weights_percent"]["bond"]) > 0
    if profile != "capital":
        assert Decimal(result["weights_percent"]["share"]) > 0


def test_saved_version_one_allocations_are_not_silently_replaced():
    value = policy()
    value["construction"].update(version=1, enabled_classes=["bond", "share", "etf"])
    value["mandate"]["loss_capacity_percent"] = "100"
    before = deepcopy(value)
    result = allocation_policy(value)
    assert result["weights_percent"] == {"bond": "34.00", "share": "17.00", "etf": "34.00", "cash": "15.00"}
    assert value == before


@pytest.mark.parametrize("profile, allowed, excluded", [("coupon", "bond", "share"), ("equity", "share", "bond")])
def test_legacy_profile_edit_with_version_two_keeps_its_actual_asset_weights(profile, allowed, excluded):
    value = policy()
    value["tuning"]["profile_id"] = profile
    value["mandate"]["loss_capacity_percent"] = "100"
    before = deepcopy(value)
    result = allocation_policy(value)
    assert Decimal(result["weights_percent"][allowed]) > 0
    assert Decimal(result["weights_percent"][excluded]) == 0
    assert Decimal(result["weights_percent"]["etf"]) == 0
    assert value == before


@pytest.mark.parametrize("enabled", [["bond"], ["share"], ["etf"], []])
def test_switching_profile_keeps_disabled_classes_disabled(enabled):
    previous = policy()
    previous["construction"]["enabled_classes"] = enabled
    original = deepcopy(previous)
    for profile in ("capital", "balanced", "growth"):
        next_config = profile_construction(profile, previous)
        assert set(next_config["enabled_classes"]) <= set(enabled)
        assert "etf" not in next_config["enabled_classes"]
        assert next_config["loss_capacity_confirmed"] is True
        assert next_config["income_stability"] == "stable"
    assert previous == original


def test_variable_income_and_disabled_assets_never_raise_risk():
    value = policy()
    original = allocation_policy(value)
    value["construction"].update(income_stability="variable", enabled_classes=["bond", "etf"])
    result = allocation_policy(value)
    assert Decimal(result["stress_loss_percent"]) <= Decimal(original["stress_loss_percent"])
    assert Decimal(result["weights_percent"]["share"]) == 0
    assert permitted_classes(value) == {"bond", "etf"}


def test_small_budget_and_large_lot_cannot_spend_reserve():
    value = policy()
    kwargs = dict(total=Decimal(5000), current=Decimal(0), held_class=Decimal(0),
        cash=Decimal(5000), unit_cost=Decimal(1000), lot=10, visible=100, config=value, kind="bond")
    assert affordable_target_lots(**kwargs) == 0
    kwargs.update(unit_cost=Decimal(10), lot=1)
    lots = affordable_target_lots(**kwargs)
    target = target_value(value, kwargs["total"], "bond", Decimal(0), Decimal(0))
    assert 0 < lots * Decimal("10.1") <= target
    with localcontext() as context:
        context.prec = 3
        assert affordable_target_lots(**kwargs) == lots


def test_sales_never_exceed_unblocked_held_units_or_broker_limit():
    args = (Decimal(10000), Decimal(2000), Decimal(100), Decimal(25), Decimal(100), 10, 100, 100)
    assert reduction_lots(*args) == 7
    assert reduction_lots(*args[:-1], 2) == 2
    assert reduction_lots(*args[:3], Decimal(101), *args[4:]) == 0


def test_only_one_current_funded_action_is_exposed():
    rows = [{"instrument_uid": str(i), "evidence_current": True, "suggested_lots": 2, "missing_evidence": []} for i in range(3)]
    result = next_action_plan({"candidates": rows})
    assert result["actions"] == rows[:1]
    assert result["automatic_order"] is False
    for row in rows:
        row["evidence_current"] = False
    assert next_action_plan({"candidates": rows})["actions"] == []


def test_yield_solver_known_zero_coupon_and_cost_sensitivity():
    assert annual_yield(Decimal(100), [(365, Decimal(110))]) == Decimal("10.0000")
    assert annual_yield(Decimal(101), [(365, Decimal(110))]) < Decimal(10)
    cost, flows = Decimal(100), [(0, Decimal(110))]
    with pytest.raises(ValueError):
        annual_yield(cost, flows)


def test_key_rate_parser_rejects_stale_future_and_conflicting_rows():
    now = datetime(2026, 10, 29, tzinfo=timezone.utc)
    doc = "<table><tr><td>28.10.2026</td><td>15,00</td></tr></table>"
    assert parse_key_rate(doc, now)["percent"] == "15.00"
    for bad in (doc.replace("28.10", "01.10"), doc.replace("28.10", "30.10"), doc + doc.replace("15,00", "16,00")):
        with pytest.raises(ValueError):
            parse_key_rate(bad, now)


def test_key_rate_filter_does_not_compare_stocks_or_funds_to_bond_yield():
    value = policy()
    value["construction"]["key_rate_mode"] = "at_least_key_rate"
    for kind in ("share", "etf"):
        assert yield_filter(value, {"instrumentType": kind}, [], Decimal(100), {}, datetime.now(timezone.utc)) == {"passed": True, "applicable": False}


def test_funds_require_real_typed_terms_and_do_not_allow_leverage():
    assert fund_reasons({"assetUid": "asset"})
    meta = {"assetUid": "asset", "fund_policy": {"asset_uid": "asset", "details": {
        "totalExpense": {"units": "1", "nano": 0}, "primaryIndex": "index", "focusType": "equity"}}}
    assert fund_reasons(meta) == []
    meta["fund_policy"]["details"]["leveragedFlag"] = True
    assert "leveraged_fund_not_allowed" in fund_reasons(meta)


def test_legacy_editor_preserves_construction_and_current_read_has_allocation(fixture):
    value = policy()
    activate(fixture, value)
    saved = state.active_strategy(fixture["user"]["id"])["config"]["construction"]
    activate(fixture, config(), expected=1, request="legacy-construction-edit")
    assert state.active_strategy(fixture["user"]["id"])["config"]["construction"] == saved
    response = fixture["client"].get("/workspace/strategy")
    assert response.status_code == 200
    assert response.json()["allocation"]["paid_model_required"] is False


def test_broker_commission_is_separate_from_bond_accrued_interest():
    from backend.strategy_actions import _exact_budget_reasons
    value = policy()
    result = {"total_cost": {"amount": "106", "currency": "RUB"},
              "clean_principal": {"amount": "100", "currency": "RUB"},
              "estimated_commission": {"units": "0", "nano": 100000000, "currency": "rub"}}
    assert _exact_budget_reasons(result, value, Decimal(5000), Decimal(5000), Decimal(250), Decimal(0)) == []
    result["estimated_commission"]["units"] = "5"
    assert _exact_budget_reasons(result, value, Decimal(5000), Decimal(5000), Decimal(250), Decimal(0)) == ["commission_above_strategy_limit"]


def test_recent_real_trades_consume_budget_and_prevent_repeated_rebalance():
    from datetime import timedelta
    from backend.strategy_activity import activity_budget
    value = policy()
    value["mandate"].update(turnover_window_days=30, rebalance_cooldown_days=10, max_discretionary_turnover_percent="20")
    now = datetime(2026, 10, 29, tzinfo=timezone.utc)
    row = {"id": "executed-1", "account_id": "a", "instrumentUid": "held", "category": "trades",
           "state": "OPERATION_STATE_EXECUTED", "date": (now - timedelta(days=5)).isoformat(),
           "payment": {"amount": "-100", "currency": "RUB"}}
    snapshot = {"operations": {"complete": True, "start": (now - timedelta(days=31)).isoformat(),
        "end": now.isoformat(), "items": [row, dict(row)]}}
    assert activity_budget(value, snapshot, "a", "other", Decimal(1000), now) == 100
    capital = Decimal(1000)
    with pytest.raises(ValueError, match="strategy_rebalance_cooldown"):
        activity_budget(value, snapshot, "a", "held", capital, now)
    snapshot["operations"]["complete"] = False
    with pytest.raises(ValueError, match="strategy_operation_window_incomplete"):
        activity_budget(value, snapshot, "a", "other", capital, now)


def test_income_switch_disables_additions_before_quote_calls(monkeypatch):
    from backend import strategy_actions as actions
    value = policy()
    value["construction"]["reinvest"] = False
    snapshot = {"snapshot_id": "s", "accounts": [{"id": "a", "value": {"amount": "5000", "currency": "RUB"}}], "positions": []}
    def forbidden(*args):
        pytest.fail("Paused additions must not request broker quotes")
    monkeypatch.setattr(actions, "_book_offer", forbidden)
    result = actions.assess_candidate({"id": 1}, {"uid": "asset", "instrument_type": "bond", "lot": "1"},
        "a", {"version": 1, "config": value}, snapshot)
    assert result["suggested_lots"] == 0
    assert result["missing_evidence"] == ["reinvestment_disabled_new_buys_paused"]


def test_reduction_has_priority_without_spending_unsettled_sale_proceeds():
    rows = [{"action": action, "evidence_current": True, "suggested_lots": 1, "missing_evidence": []} for action in ("buy", "sell")]
    assert next_action_plan({"candidates": rows})["actions"] == [rows[1]]


def test_bond_horizon_handles_month_end_and_lot_changes():
    from backend.strategy_construction import instrument_policy_reasons
    value = policy()
    value["horizon_months"] = 12
    now = datetime(2024, 2, 29, tzinfo=timezone.utc)
    meta = {"lot": 10, "instrumentType": "bond", "maturityDate": "2025-02-28T00:00:00Z"}
    assert instrument_policy_reasons(meta, 10, value, now) == []
    assert instrument_policy_reasons(meta, 1, value, now) == ["instrument_lot_changed_refresh_required"]
    meta["maturityDate"] = "2025-03-01T00:00:00Z"
    assert instrument_policy_reasons(meta, 10, value, now) == ["bond_maturity_outside_horizon"]
    meta.pop("maturityDate")
    assert instrument_policy_reasons(meta, 10, value, now) == ["bond_maturity_unknown"]

