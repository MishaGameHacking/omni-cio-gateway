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
    with pytest.raises(ValueError):
        annual_yield(Decimal(100), [(0, Decimal(110))])


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
    activate(fixture, config(), expected=1, request="legacy-construction-edit")
    assert state.active_strategy(fixture["user"]["id"])["config"]["construction"] == value["construction"]
    response = fixture["client"].get("/workspace/strategy")
    assert response.status_code == 200
    assert response.json()["allocation"]["paid_model_required"] is False
