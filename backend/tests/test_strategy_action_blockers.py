"""Blocked decisions remain inspectable; all broker observations are synthetic."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest
from fastapi import HTTPException

from backend import strategy_actions as actions
from backend.decision_views import project
from backend.strategy_construction import profile_construction


def config():
    value = {
        "horizon_months": 120, "reserve": {"amount": "0", "currency": "RUB"},
        "limits": {"position_percent": "5"},
        "tuning": {"profile_id": "capital", "enabled": True},
        "mandate": {"loss_capacity_percent": "50", "max_trade_cost_percent": "1"},
        "construction": profile_construction("capital", {}),
    }
    value["construction"].update(loss_capacity_confirmed=True, income_stability="stable")
    return value


def snapshot(cash="5000"):
    return {"snapshot_id": "snapshot-synthetic", "accounts": [
        {"id": "account-synthetic", "value": {"amount": "5000", "currency": "RUB"}}],
        "positions": [{"account_id": "account-synthetic", "instrument_uid": "cash:RUB",
            "instrument_type": "cash", "value": {"amount": cash, "currency": "RUB"},
            "blocked": False, "blocked_quantity": "0"}]}


def item():
    return {"uid": "bond-synthetic", "instrument_type": "bond", "lot": "1"}


def assess(value, observed):
    return actions.assess_candidate({"id": 1}, item(), "account-synthetic",
                                    {"version": 1, "config": value}, observed)


def forbid_purchase_check(*args, **kwargs):
    pytest.fail("A zero-lot or unpriced candidate must not request an order-price check")


def market(monkeypatch, price="100"):
    monkeypatch.setattr(actions, "_book_offer", lambda *args: (Decimal(price), 100))
    monkeypatch.setattr(actions.details, "BrokerReader", lambda *args: nullcontext(object()))
    metadata = {"uid": "bond-synthetic", "lot": 1, "currency": "RUB",
        "nominal": {"units": "1000", "nano": 0, "currency": "rub"},
        "maturityDate": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()}
    monkeypatch.setattr(actions.market, "broker_read", lambda *args: {"instrument": metadata})
    monkeypatch.setattr(actions, "activity_budget", lambda *args: Decimal("10000"))
    monkeypatch.setattr(actions.purchases, "_check_purchase", forbid_purchase_check)


def assert_pending(result):
    assert result["observed_at"] and result["as_of"]
    assert result["action"] == "wait"
    assert result["suggested_lots"] == 0
    assert result["constraints_passed"] is False
    assert result["expires_at"] is None
    assert result["quote_as_of"] is None
    assert result["account_id"] == "account-synthetic"
    now = datetime.now(timezone.utc).timestamp()
    view = project({"candidates": [result]}, [], now)
    assert view["pending"] == [result]
    assert view["current"] == []
    assert actions.next_action_plan({"candidates": [result]})["actions"] == []


def test_small_account_explains_position_limit_without_widening_it(monkeypatch):
    market(monkeypatch)
    value = config()
    original = deepcopy(value)
    result = assess(value, snapshot())
    assert_pending(result)
    budget = result["budget_diagnostics"]
    assert Decimal(budget["position_cap_value"]) == 250
    assert Decimal(budget["planning_budget"]) == 250
    assert Decimal(budget["minimum_lot_principal"]) == 1000
    assert Decimal(budget["quote_allowance_amount"]) == 10
    assert Decimal(budget["minimum_lot_planning_amount"]) == 1010
    assert Decimal(budget["planning_budget_shortfall"]) == 760
    assert Decimal(budget["planning_capital_for_position_limit"]) == 20200
    assert Decimal(budget["capital_shortfall_for_position_limit"]) == 15200
    assert budget["limited_by"] == ["position_limit"]
    assert budget["quote_allowance_is_actual_fee"] is False
    assert budget["broker_all_in_quote"] is None
    assert value == original


def test_low_cash_reports_protected_reserve_and_cash_shortfall(monkeypatch):
    market(monkeypatch)
    result = assess(config(), snapshot(cash="1300"))
    assert_pending(result)
    budget = result["budget_diagnostics"]
    assert Decimal(budget["protected_reserve"]) == 1250
    assert Decimal(budget["cash_after_reserve"]) == 50
    assert Decimal(budget["planning_budget"]) == 50
    assert Decimal(budget["cash_shortfall_at_current_reserve"]) == 960
    assert set(budget["limited_by"]) == {"cash_after_reserve", "position_limit"}


def test_unknown_quote_keeps_unknown_costs_and_visible_failure(monkeypatch):
    def unavailable(*args):
        raise HTTPException(503, "order_book_stale_or_undated")
    monkeypatch.setattr(actions, "_book_offer", unavailable)
    monkeypatch.setattr(actions.purchases, "_check_purchase", forbid_purchase_check)
    result = assess(config(), snapshot())
    assert_pending(result)
    assert result["missing_evidence"] == ["order_book_stale_or_undated"]
    budget = result["budget_diagnostics"]
    assert Decimal(budget["planning_budget"]) == 250
    for key in ("minimum_lot_principal", "minimum_lot_planning_amount", "planning_budget_shortfall",
                "planning_capital_for_position_limit", "capital_shortfall_for_position_limit", "broker_all_in_quote"):
        assert budget[key] is None


def test_disabled_reinvestment_is_visible_without_broker_calls(monkeypatch):
    monkeypatch.setattr(actions, "_book_offer", forbid_purchase_check)
    value = config()
    value["construction"]["reinvest"] = False
    result = assess(value, snapshot())
    assert_pending(result)
    assert result["missing_evidence"] == ["reinvestment_disabled_new_buys_paused"]
    assert result["budget_diagnostics"]["broker_all_in_quote"] is None


def test_unknown_loss_capacity_remains_zero_and_visible(monkeypatch):
    market(monkeypatch)
    value = config()
    value["construction"]["loss_capacity_confirmed"] = False
    result = assess(value, snapshot())
    assert_pending(result)
    assert "loss_capacity_not_confirmed" in result["missing_evidence"]
    assert "allocation_policy" in result["budget_diagnostics"]["limited_by"]
    assert Decimal(result["budget_diagnostics"]["planning_budget"]) == 0


def test_planning_allowance_is_separate_from_broker_all_in_quote(monkeypatch):
    market(monkeypatch, price="10")
    now = datetime.now(timezone.utc)
    quote = {"as_of": now.isoformat(), "expires_at": (now + timedelta(seconds=45)).isoformat(),
        "total_cost": {"amount": "212", "currency": "RUB"},
        "clean_principal": {"amount": "200", "currency": "RUB"},
        "estimated_commission": {"amount": "0.2", "currency": "RUB"},
        "constraints_passed": True, "reasons": [], "evidence_revision": {"revision": 1},
        "remaining_checks": ["investment_thesis_and_valuation"]}
    monkeypatch.setattr(actions.purchases, "_check_purchase", lambda *args, **kwargs: quote)
    result = assess(config(), snapshot())
    budget = result["budget_diagnostics"]
    assert Decimal(budget["minimum_lot_principal"]) == 100
    assert Decimal(budget["minimum_lot_planning_amount"]) == 101
    assert budget["broker_all_in_quote"] == {"amount": "212", "currency": "RUB"}
    assert budget["broker_quote_lots"] == 2
    assert result["quote_as_of"] == quote["as_of"]
    assert result["observed_at"]
    assert result["recommendation_complete"] is False
    assert budget["automatic_order"] is False


def test_recent_blocker_with_stale_quote_stays_pending_and_old_review_is_hidden():
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    stale = (now - timedelta(days=2)).isoformat()
    recent = (now - timedelta(minutes=1)).isoformat()
    rows = [{"instrument_uid": "recent", "observed_at": recent, "as_of": stale,
             "expires_at": stale, "evidence_current": False, "missing_evidence": ["fresh_observations_required"]},
            {"instrument_uid": "old", "observed_at": stale, "as_of": recent, "evidence_current": False}]
    view = project({"candidates": rows}, [], now.timestamp())
    assert view["pending"] == rows[:1]
    assert view["current"] == []
    assert view["hidden_obsolete_count"] == 1
    assert actions.next_action_plan({"candidates": rows})["actions"] == []


def test_budget_diagnostics_are_independent_of_caller_decimal_precision():
    arguments = dict(total=Decimal("5000"), current=Decimal("0"), held_class=Decimal("0"),
        cash=Decimal("5000"), config=config(), kind="bond", unit_cost=Decimal("1000.13"), lot=1, visible=5)
    expected = actions.budget_diagnostics(**arguments)
    with localcontext() as context:
        context.prec = 3
        assert actions.budget_diagnostics(**arguments) == expected


def test_foreign_cash_valued_in_rubles_does_not_fund_ruble_purchase(monkeypatch):
    market(monkeypatch)
    observed = snapshot(cash="1000")
    foreign = deepcopy(observed["positions"][0])
    foreign.update(instrument_uid="cash:USD", value={"amount": "4000", "currency": "RUB"})
    observed["positions"].append(foreign)
    result = assess(config(), observed)
    assert_pending(result)
    budget = result["budget_diagnostics"]
    assert Decimal(budget["observed_cash"]) == 1000
    assert Decimal(budget["cash_after_reserve"]) == 0
    assert "cash_after_reserve" in budget["limited_by"]


@pytest.mark.parametrize("missing", ["denomination", "value_currency", "blocked", "blocked_quantity"])
def test_ambiguous_cash_cannot_supply_budget_and_security_values_are_unchanged(missing):
    observed = snapshot(cash="1000")
    unknown = deepcopy(observed["positions"][0])
    unknown["value"]["amount"] = "4000"
    if missing == "denomination":
        unknown["instrument_uid"] = "cash-without-verified-currency"
    elif missing == "value_currency":
        unknown["value"].pop("currency")
    else:
        unknown.pop(missing)
    held = {"account_id": "account-synthetic", "instrument_uid": "bond-synthetic",
        "instrument_type": "bond", "value": {"amount": "300", "currency": "RUB"}}
    observed["positions"].extend([unknown, held])
    current, held_class, cash = actions.held_values(observed, "account-synthetic", "bond-synthetic", "bond")
    assert current == held_class == 300
    assert cash == 1000
