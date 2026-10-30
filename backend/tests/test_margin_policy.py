"""Cash-floor arithmetic with synthetic fixtures; no broker reads or writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest

from backend.margin_policy import CASH_FLOOR_RUB, evaluate_buy, evaluate_current, observe_portfolio


NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
ACCOUNT = "account-synthetic"


def observation(cash="5000", pending=None):
    return {"account_id": ACCOUNT, "currency": "RUB", "cash_rub": cash,
        "cash_basis": "signed_cash_with_explicit_pending_inclusion",
        "observed_at": NOW.isoformat(), "pending_complete": True,
        "pending_debits": [] if pending is None else pending}


def debit(amount="100", *, included=False, identity="pending-synthetic"):
    return {"id": identity, "currency": "RUB", "amount_rub": amount,
        "included_in_cash": included}


def quote(total="9999", principal="9970"):
    return {"account_id": ACCOUNT, "proposal_id": "proposal-synthetic",
        "currency": "RUB", "costs_complete": True, "observed_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
        "principal_rub": principal, "commission_rub": "9",
        "accrued_interest_rub": "20", "other_charges_rub": "0", "total_rub": total}


def tariff():
    return {"account_id": ACCOUNT, "source_id": "tariff-synthetic", "verified": True,
        "all_charges_known": True, "observed_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(hours=1)).isoformat()}


def assert_never_ready(result):
    assert result["ready_for_order"] is False
    assert result["real_orders_enabled"] is False
    assert result["broker_margin_check_required"] is True
    assert result["margin_call_risk_assessed"] is False
    assert result["safety_guaranteed"] is False
    assert result["policy_floor_is_not_broker_margin_call_threshold"] is True


def test_own_5000_all_in_9999_is_exact_floor_but_never_credit_approval():
    result = evaluate_buy(observation(), quote(), tariff(), now=NOW)
    actual_floor = CASH_FLOOR_RUB
    projected_cash = Decimal(result["projected_cash_rub"])
    projected_breach = Decimal(result["projected_breach_amount_rub"])
    assert actual_floor == -4999
    assert projected_cash == -4999
    assert projected_breach == 0
    assert result["arithmetic_policy_passed"] is True
    assert result["reasons"] == ["broker_margin_check_required"]
    assert_never_ready(result)


def test_one_kopeck_over_floor_is_rejected_including_fee_and_accrued_interest():
    cost = quote(total="9999.01")
    cost["other_charges_rub"] = "0.01"
    result = evaluate_buy(observation(), cost, tariff(), now=NOW)
    projected_cash = Decimal(result["projected_cash_rub"])
    expected_cash = Decimal("-4999.01")
    assert result["arithmetic_policy_passed"] is False
    assert projected_cash == expected_cash
    assert result["required_repayment_if_executed_rub"] == "0.01"
    assert "margin_proposed_buy_breaches_floor" in result["reasons"]
    assert_never_ready(result)


def test_existing_borrowing_is_already_in_signed_cash_not_added_again():
    current = evaluate_current(observation(cash="-1000"), now=NOW)
    available_all_in = Decimal(current["maximum_all_in_buy_rub"])
    assert available_all_in == 3999
    result = evaluate_buy(observation(cash="-1000"), quote("3999", "3970"), tariff(), now=NOW)
    projected_cash = Decimal(result["projected_cash_rub"])
    assert projected_cash == -4999
    assert result["arithmetic_policy_passed"] is True
    assert_never_ready(result)


@pytest.mark.parametrize("included, expected_capacity", [(False, "9899"), (True, "9999")])
def test_pending_amount_is_counted_once_and_reflected_cash_is_not_debited_twice(included, expected_capacity):
    pending = debit(included=included)
    result = evaluate_current(observation(pending=[pending, deepcopy(pending)]), now=NOW)
    available_all_in = Decimal(result["maximum_all_in_buy_rub"])
    unreflected_pending = Decimal(result["unreflected_pending_debits_rub"])
    expected_available = Decimal(expected_capacity)
    assert available_all_in == expected_available
    assert unreflected_pending == (0 if included else 100)
    assert_never_ready(result)


def test_unreflected_pending_charge_reduces_new_purchase_capacity():
    result = evaluate_buy(observation(pending=[debit()]), quote(), tariff(), now=NOW)
    cash_after_commitments = Decimal(result["cash_after_commitments_rub"])
    projected_cash = Decimal(result["projected_cash_rub"])
    assert cash_after_commitments == 4900
    assert projected_cash == -5099
    assert result["required_repayment_if_executed_rub"] == "100.00"
    assert result["arithmetic_policy_passed"] is False


def test_previously_committed_proposal_is_not_calculated_twice():
    snapshot = observation(pending=[debit(identity="proposal-synthetic")])
    result = evaluate_buy(snapshot, quote(), tariff(), now=NOW)
    assert result["projected_cash_rub"] is None
    assert "margin_proposal_already_committed" in result["reasons"]
    assert result["arithmetic_policy_passed"] is False


@pytest.mark.parametrize("field, value", [("amount_rub", "101"), ("included_in_cash", True)])
def test_conflicting_duplicate_obligations_are_unknown(field, value):
    first, second = debit(), debit()
    second[field] = value
    result = evaluate_current(observation(pending=[first, second]), now=NOW)
    assert result["state"] == "unknown"
    assert result["maximum_all_in_buy_rub"] is None
    assert result["required_repayment_rub"] is None
    assert "margin_pending_debit_conflict" in result["reasons"]


@pytest.mark.parametrize("field, value", [("pending_complete", False), ("pending_debits", None)])
def test_unknown_obligations_are_not_assumed_zero(field, value):
    snapshot = observation()
    snapshot[field] = value
    result = evaluate_buy(snapshot, quote(), tariff(), now=NOW)
    assert result["arithmetic_policy_passed"] is False
    assert result["cash_after_commitments_rub"] is None
    assert result["projected_cash_rub"] is None
    assert "margin_pending_debits_incomplete" in result["reasons"]


def test_missing_pending_inclusion_flag_does_not_guess_cash_semantics():
    pending = debit(included=None)
    result = evaluate_current(observation(pending=[pending]), now=NOW)
    assert result["state"] == "unknown"
    assert "margin_pending_debit_invalid" in result["reasons"]


@pytest.mark.parametrize("cash, pending, observed_breach, repayment", [
    ("-5000", [], True, "1.00"),
    ("-4999", [debit("0.01")], False, "0.01"),
    ("-4999.000000001", [], True, "0.01"),
])
def test_current_breach_only_reports_required_cash_repayment(cash, pending, observed_breach, repayment):
    result = evaluate_current(observation(cash, pending), now=NOW)
    assert result["state"] == "breached"
    assert result["observed_cash_breaches_floor"] is observed_breach
    assert result["commitments_breach_floor"] is True
    assert result["required_repayment_rub"] == repayment
    assert result["maximum_all_in_buy_rub"] == "0"
    assert result["arithmetic_policy_passed"] is False
    assert_never_ready(result)


def test_new_purchase_is_blocked_when_current_commitments_already_breach_floor():
    result = evaluate_buy(observation(cash="-5000"), quote("100", "71"), tariff(), now=NOW)
    assert result["projected_cash_rub"] is None
    assert "margin_existing_commitments_breach_floor" in result["reasons"]
    assert result["arithmetic_policy_passed"] is False


@pytest.mark.parametrize("replacement", [None, {}, {"verified": False}, {"all_charges_known": False},
    {"account_id": "other-account"}, {"expires_at": NOW.isoformat()}, {"source_id": None}])
def test_unknown_or_unverified_tariff_blocks_projection(replacement):
    evidence = tariff()
    if isinstance(replacement, dict) and replacement:
        evidence.update(replacement)
    else:
        evidence = replacement
    result = evaluate_buy(observation(), quote(), evidence, now=NOW)
    assert result["projected_cash_rub"] is None
    assert "margin_tariff_or_charges_unknown" in result["reasons"]
    assert_never_ready(result)


@pytest.mark.parametrize("field, value", [
    ("commission_rub", None), ("accrued_interest_rub", None), ("other_charges_rub", None),
    ("principal_rub", "NaN"), ("total_rub", 9999.0), ("commission_rub", True),
    ("commission_rub", "0.0000000001"), ("total_rub", {"amount": "9999", "currency": "USD"}),
    ("costs_complete", False), ("currency", "USD"),
])
def test_unknown_or_ambiguous_all_in_costs_are_blocked(field, value):
    cost = quote()
    cost[field] = value
    result = evaluate_buy(observation(), cost, tariff(), now=NOW)
    assert result["arithmetic_policy_passed"] is False
    assert result["projected_cash_rub"] is None
    assert "margin_all_in_cost_unknown" in result["reasons"]


def test_cost_breakdown_must_equal_confirmed_total():
    cost = quote()
    cost["commission_rub"] = "8"
    result = evaluate_buy(observation(), cost, tariff(), now=NOW)
    assert result["projected_cash_rub"] is None
    assert "margin_all_in_cost_conflict" in result["reasons"]


@pytest.mark.parametrize("observed", [(NOW - timedelta(seconds=60)).isoformat(),
    (NOW + timedelta(seconds=1)).isoformat(), "2026-10-30T12:00:00", None])
def test_stale_future_or_unzoned_cash_observation_is_unknown(observed):
    snapshot = observation()
    snapshot["observed_at"] = observed
    result = evaluate_current(snapshot, now=NOW)
    assert result["state"] == "unknown"
    assert result["cash_after_commitments_rub"] is None
    assert result["maximum_all_in_buy_rub"] is None
    assert "margin_cash_observation_stale_or_future" in result["reasons"]


@pytest.mark.parametrize("field, value", [("expires_at", NOW.isoformat()),
    ("observed_at", (NOW - timedelta(seconds=60)).isoformat()),
    ("observed_at", (NOW + timedelta(seconds=1)).isoformat())])
def test_quote_has_independent_freshness_and_expiry(field, value):
    cost = quote()
    cost[field] = value
    result = evaluate_buy(observation(), cost, tariff(), now=NOW)
    assert result["projected_cash_rub"] is None
    assert "margin_quote_stale_or_future" in result["reasons"]


@pytest.mark.parametrize("field, value", [("cash_basis", None), ("currency", "USD"),
    ("cash_rub", {"amount": "5000", "currency": "USD"}), ("account_id", "")])
def test_unverified_cash_basis_currency_or_account_never_becomes_buying_power(field, value):
    snapshot = observation()
    snapshot[field] = value
    result = evaluate_buy(snapshot, quote(), tariff(), now=NOW)
    assert result["arithmetic_policy_passed"] is False
    assert result["cash_after_commitments_rub"] is None
    assert result["projected_cash_rub"] is None
    assert_never_ready(result)


def test_decimal_precision_is_isolated_and_inputs_are_unchanged():
    snapshot, cost, evidence = observation(), quote(), tariff()
    original_snapshot, original_cost, original_evidence = deepcopy((snapshot, cost, evidence))
    with localcontext() as context:
        context.prec = 3
        result = evaluate_buy(snapshot, cost, evidence, now=NOW)
    projected_cash = Decimal(result["projected_cash_rub"])
    assert projected_cash == -4999
    assert result["arithmetic_policy_passed"] is True
    assert snapshot == original_snapshot
    assert cost == original_cost
    assert evidence == original_evidence


def test_naive_clock_is_rejected():
    snapshot = observation()
    naive_now = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError, match="margin_aware_clock_required"):
        evaluate_current(snapshot, now=naive_now)


def portfolio(cash="-5000"):
    return {"as_of": NOW.isoformat(), "accounts": [{"id": ACCOUNT}],
        "positions": [{"account_id": ACCOUNT, "instrument_type": "cash", "instrument_uid": "cash:RUB",
            "value": {"amount": cash, "currency": "RUB"}, "metadata": {"instrument_currency": "RUB"}}]}


def test_monitor_reports_fresh_observed_breach_without_claiming_complete_obligations():
    snapshot = portfolio()
    snapshot.update(pending_complete=False, pending_debits=None)
    result = observe_portfolio(snapshot, ACCOUNT, now=NOW)
    assert result["fresh"] is True
    assert result["observed_cash_rub"] == "-5000"
    assert result["observed_floor_breached"] is True
    assert result["minimum_observed_shortfall_rub"] == "1.00"
    assert result["commitments_verified"] is False
    assert result["full_repayment_unknown"] is True
    assert result["full_repayment_rub"] is None
    assert result["ready_for_order"] is False
    assert result["real_orders_enabled"] is False
    assert "maximum_all_in_buy_rub" not in result
    assert "arithmetic_policy_passed" not in result


@pytest.mark.parametrize("cash, breached, shortfall", [
    ("-4999", False, "0.00"), ("5000", False, "0.00"), ("-4999.000000001", True, "0.01")])
def test_monitor_boundary_and_repayment_rounding(cash, breached, shortfall):
    result = observe_portfolio(portfolio(cash), ACCOUNT, now=NOW)
    assert result["observed_floor_breached"] is breached
    assert result["minimum_observed_shortfall_rub"] == shortfall


@pytest.mark.parametrize("change", [
    {"instrument_uid": "cash:USD", "metadata": {"instrument_currency": "USD"}},
    {"instrument_uid": "cash:USD"},
    {"metadata": {"instrument_currency": "USD"}},
    {"instrument_uid": "cash-unknown", "metadata": {}},
    {"value": {"amount": "-5000", "currency": "USD"}},
    {"metadata": "invalid"},
])
def test_monitor_rejects_foreign_valuations_and_ambiguous_native_currency(change):
    snapshot = portfolio()
    snapshot["positions"][0].update(change)
    result = observe_portfolio(snapshot, ACCOUNT, now=NOW)
    assert result["fresh"] is False
    assert result["observed_cash_rub"] is None
    assert result["observed_floor_breached"] is None
    assert result["minimum_observed_shortfall_rub"] is None


def test_monitor_reads_only_selected_accounts_native_cash_in_mixed_currency_snapshot():
    snapshot = portfolio("100")
    snapshot["accounts"].append({"id": "other-account"})
    snapshot["positions"].extend([
        {"account_id": ACCOUNT, "instrument_type": "cash", "instrument_uid": "cash:USD",
         "value": {"amount": "-10000", "currency": "RUB"}, "metadata": {"instrument_currency": "USD"}},
        {"account_id": "other-account", "instrument_type": "cash", "instrument_uid": "cash:RUB",
         "value": {"amount": "-5000", "currency": "RUB"}}])
    result = observe_portfolio(snapshot, ACCOUNT, now=NOW)
    assert result["observed_cash_rub"] == "100"
    assert result["fresh"] is True
    assert result["observed_floor_breached"] is False


@pytest.mark.parametrize("key", ["accounts", "positions"])
def test_monitor_rejects_duplicate_account_or_ruble_cash_rows(key):
    snapshot = portfolio()
    snapshot[key].append(deepcopy(snapshot[key][0]))
    result = observe_portfolio(snapshot, ACCOUNT, now=NOW)
    assert result["fresh"] is False
    assert result["observed_cash_rub"] is None
    assert result["observed_floor_breached"] is None


@pytest.mark.parametrize("account", ["missing-account", "", None])
def test_monitor_never_falls_back_to_another_account(account):
    result = observe_portfolio(portfolio(), account, now=NOW)
    assert result["observed_cash_rub"] is None
    assert result["observed_floor_breached"] is None
    assert "margin_selected_account_unverified" in result["reasons"]


@pytest.mark.parametrize("stamp", [(NOW - timedelta(seconds=300)).isoformat(),
    (NOW + timedelta(seconds=1)).isoformat(), "2026-10-30T12:00:00", None])
def test_monitor_keeps_stale_cash_visible_but_never_emits_current_breach(stamp):
    snapshot = portfolio()
    snapshot["as_of"] = stamp
    result = observe_portfolio(snapshot, ACCOUNT, now=NOW)
    assert result["observed_cash_rub"] == "-5000"
    assert result["state"] == "stale"
    assert result["fresh"] is False
    assert result["observed_floor_breached"] is None
    assert result["minimum_observed_shortfall_rub"] is None
