from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from omnicio.workspace import (
    cashflow_summary,
    default_preferences,
    event_digest,
    event_id,
    goal_progress,
    normalize_goal,
    normalize_preferences,
    portfolio_performance,
    quiet_now,
)
from omnicio.workspace_store import WorkspaceStore, _Basis

START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=30)


def goal_document(**changes: Any) -> dict[str, Any]:
    return {
        "title": "Первоначальный взнос",
        "kind": "capital",
        "target_amount_rub": "100000",
        "target_date": "2027-01-01",
        "start_date": "2026-01-01",
        "progress_source": "manual",
        "allocation_percent": None,
        "manual_amount_rub": "25000",
        "status": "active",
        **changes,
    }


def operation(
    kind: str,
    payment: str,
    *,
    day: int = 10,
    currency: str = "RUB",
    **changes: Any,
) -> dict[str, Any]:
    return {
        "operation_date": START + timedelta(days=day),
        "operation_type": "OPERATION_TYPE_" + kind,
        "operation_state": "OPERATION_STATE_EXECUTED",
        "payment_value": Decimal(payment),
        "payment_currency": currency,
        **changes,
    }


def test_income_uses_selected_period_and_keeps_principal_separate() -> None:
    basis = _Basis(
        connection=None,
        latest={"evidence": {"account": {"opened_at": START.isoformat()}}},
        operations=[
            operation("DIVIDEND", "100", day=5),
            operation("COUPON", "50", day=20),
            operation("BOND_REPAYMENT", "1000", day=25),
        ],
        watermark=END, complete=True,
    )
    all_time = WorkspaceStore._income(basis, END)
    selected = WorkspaceStore._income(basis, END, from_at=START + timedelta(days=10))
    assert all_time["total_rub"] == "150"
    assert selected["total_rub"] == "50"
    assert selected["dividends_rub"] == "0"
    assert selected["redemptions_rub"] == "1000"
    assert selected["from"] == (START + timedelta(days=10)).isoformat()
    assert selected["by_month"][0]["total_rub"] == "50"
    after_watermark = WorkspaceStore._income(basis, END, from_at=END + timedelta(days=1))
    assert after_watermark["status"] == "unavailable"
    assert after_watermark["total_rub"] is None


def test_preferences_defaults_have_no_invented_user_facts_and_do_not_alias() -> None:
    first = default_preferences()
    first["watchlist"].append({"instrument_uid": "id", "ticker": "", "name": ""})
    fresh = default_preferences()
    assert fresh["watchlist"] == []
    assert fresh["display_name"] == ""
    assert normalize_preferences(fresh) == fresh
    assert not fresh["quiet_hours"]["enabled"]


def test_old_digest_preferences_keep_midnight_schedule_and_new_defaults_are_explicit() -> None:
    preferences = default_preferences()
    assert preferences["digest_time"] == "20:30"
    preferences.pop("digest_time")
    preferences.pop("digest_timezone")
    preferences["quiet_hours"]["timezone"] = "Europe/Berlin"
    old = normalize_preferences(preferences)
    assert old["digest_time"] == "00:00"
    assert old["digest_timezone"] == "Europe/Berlin"
    with pytest.raises(ValueError, match="digest_time_invalid"):
        normalize_preferences({**old, "digest_time": "24:00"})


def test_independent_nav_coverage_unlocks_fund_return_but_unknown_legacy_partial_does_not() -> None:
    snapshots = [
        {"captured_at": START, "analysis_status": "partial", "nav_rub": "1000",
         "valuation_status": "complete"},
        {"captured_at": END, "analysis_status": "partial", "nav_rub": "1100",
         "valuation_status": "complete"},
    ]
    result = portfolio_performance(snapshots, [], watermark=END, history_complete=True)
    assert result["return_percent"] == "10.0"
    assert result["investment_result_rub"] == "100"
    snapshots[0].pop("valuation_status")
    assert portfolio_performance(snapshots, [], watermark=END, history_complete=True)[
        "return_status"
    ] == "unavailable"


def test_foreign_internal_payments_do_not_require_fabricated_fx_for_rub_nav_return() -> None:
    snapshots = [
        {"captured_at": START, "analysis_status": "observed", "nav_rub": "1000"},
        {"captured_at": END, "analysis_status": "observed", "nav_rub": "1100"},
    ]
    operations = [operation("DIVIDEND", "2", currency="USD"), operation("BROKER_FEE", "-1")]
    result = portfolio_performance(snapshots, operations, watermark=END, history_complete=True)
    assert result["return_percent"] == "10.0"
    assert result["income_received_rub"] is None
    assert result["fees_rub"] == "1"
    assert result["metric_coverage"]["dividends_rub"]["status"] == "unavailable"
    assert result["native_payment_sums"]["currencies"]["USD"]["dividends"] == "2"
    operations.append(operation("INPUT", "2", currency="USD"))
    result = portfolio_performance(snapshots, operations, watermark=END, history_complete=True)
    assert result["return_percent"] is None
    assert result["nav_change_rub"] == "100"
    assert result["metric_coverage"]["fees_rub"]["status"] == "complete"


@pytest.mark.parametrize(
    "change",
    [
        {"mask_balances": "true"},
        {"locale": "invented"},
        {"theme": "not-a-theme"},
        {"display_name": "bad\x00name"},
        {"display_name": "bad\ud800name"},
        {"display_name": "x" * 81},
        {"watchlist": [{"instrument_uid": "../secret", "ticker": "", "name": ""}]},
        {"watchlist": [{"instrument_uid": "one", "ticker": "", "name": ""}] * 2},
        {"notifications": {"system": True}},
    ],
)
def test_preferences_reject_ambiguous_or_unbounded_values(change: dict[str, Any]) -> None:
    document = {**default_preferences(), **change}
    with pytest.raises(ValueError):
        normalize_preferences(document)


def test_preferences_unicode_watchlist_cannot_exceed_database_document_budget() -> None:
    preferences = default_preferences()
    preferences["watchlist"] = [
        {"instrument_uid": str(index), "ticker": "TEST", "name": "Ф" * 256} for index in range(50)
    ]
    assert len(normalize_preferences(preferences)["watchlist"]) == 50
    for item in preferences["watchlist"]:
        item["name"] = "🟦" * 256
    with pytest.raises(ValueError, match="preferences_too_large"):
        normalize_preferences(preferences)


def test_quiet_hours_respect_timezone_midnight_and_dst() -> None:
    preferences = default_preferences()
    preferences["quiet_hours"] = {
        "enabled": True,
        "start": "22:00",
        "end": "08:00",
        "timezone": "Europe/Moscow",
    }
    preferences = normalize_preferences(preferences)
    assert quiet_now(preferences, datetime(2026, 10, 6, 19, 0, tzinfo=UTC))
    assert quiet_now(preferences, datetime(2026, 10, 7, 4, 59, tzinfo=UTC))
    assert not quiet_now(preferences, datetime(2026, 10, 7, 5, 0, tzinfo=UTC))
    preferences["quiet_hours"]["timezone"] = "Europe/Berlin"
    assert quiet_now(preferences, datetime(2026, 7, 1, 20, 0, tzinfo=UTC))
    assert not quiet_now(preferences, datetime(2026, 1, 1, 20, 0, tzinfo=UTC))


@pytest.mark.parametrize(
    "quiet",
    [
        {"enabled": True, "start": "22:00", "end": "22:00", "timezone": "UTC"},
        {"enabled": True, "start": "25:00", "end": "08:00", "timezone": "UTC"},
        {"enabled": True, "start": "22:00", "end": "08:00", "timezone": "../private"},
    ],
)
def test_invalid_quiet_hours_are_not_silently_accepted(quiet: dict[str, Any]) -> None:
    document = {**default_preferences(), "quiet_hours": quiet}
    with pytest.raises(ValueError):
        normalize_preferences(document)


@pytest.mark.parametrize(
    "changes",
    [
        {"target_amount_rub": "NaN"},
        {"target_amount_rub": True},
        {"target_amount_rub": "0"},
        {"manual_amount_rub": None},
        {"manual_amount_rub": "-1"},
        {"target_amount_rub": "1.123456789"},
        {"target_date": "2025-12-31"},
        {"target_date": "2026-02-30"},
        {"progress_source": "portfolio", "allocation_percent": "40", "manual_amount_rub": "0"},
        {"progress_source": "income", "allocation_percent": "40", "manual_amount_rub": None},
    ],
)
def test_goals_require_explicit_coherent_source_and_exact_amounts(changes: dict[str, Any]) -> None:
    document = goal_document(**changes)
    with pytest.raises(ValueError):
        normalize_goal(document)


def test_goal_document_cannot_assign_identity_or_trade_authority() -> None:
    data = goal_document()
    assert normalize_goal(data) == data
    with pytest.raises(ValueError, match="fields"):
        normalize_goal({**data, "user_id": "someone-else"})
    with pytest.raises(ValueError, match="fields"):
        normalize_goal({**data, "execute": True})


def test_accounting_does_not_count_deposits_principal_or_fees_twice() -> None:
    rows = [
        operation("INPUT", "20000"),
        operation("OUTPUT", "-5000"),
        operation("BUY", "-10000", commission_value=Decimal("10")),
        operation("BROKER_FEE", "-10"),
        operation("BOND_TAX", "-130"),
        operation("COUPON", "1000"),
        operation("DIVIDEND", "2000"),
        operation("BOND_REPAYMENT_FULL", "10000"),
    ]
    flow = cashflow_summary(rows, from_at=START, to_at=END, complete=True)
    assert flow["status"] == "available"
    assert flow["net_contributions_rub"] == "15000"
    assert flow["fees_rub"] == "10"
    assert flow["taxes_rub"] == "130"
    assert flow["income"]["total_rub"] == "3000"
    assert flow["income"]["redemptions_rub"] == "10000"
    snapshots = [
        {"captured_at": START, "nav_rub": "100000", "analysis_status": "observed"},
        {"captured_at": END, "nav_rub": "117860", "analysis_status": "observed"},
    ]
    result = portfolio_performance(snapshots, rows, watermark=END, history_complete=True)
    assert result["nav_change_rub"] == "17860"
    assert result["investment_result_rub"] == "2860"
    assert result["income_received_rub"] == "3000"
    assert Decimal(result["return_percent"]) == Decimal("2.6")
    assert result["return_method"] == "modified_dietz"
    assert result["return_status"] == "available"
    assert Decimal(result["return_denominator_rub"]) == Decimal("110000")
    assert result["return_is_estimate"] is True
    assert result["return_is_annualized"] is False


@pytest.mark.parametrize(
    "rows, closing, expected", [
        ([], "110000", "10"),
        ([operation("INPUT", "100000", day=15)], "215000", "10"),
        ([operation("INPUT", "100000", day=30)], "210000", "10"),
        ([operation("OUTPUT", "-50000", day=15)], "57500", "10"),
        ([operation("INPUT", "100000", day=0)], "110000", "10"),
        ([operation("INPUT", "100000", day=31)], "110000", "10"),
        ([], "90000", "-10"),
    ],
)
def test_dietz_return_weights_external_flows_and_respects_valuation_boundaries(
    rows: list[dict[str, Any]], closing: str, expected: str,
) -> None:
    snapshots = [
        {"captured_at": START, "nav_rub": "100000", "analysis_status": "observed"},
        {"captured_at": END, "nav_rub": closing, "analysis_status": "observed"},
    ]
    result = portfolio_performance(snapshots, rows, watermark=END, history_complete=True)
    assert Decimal(result["return_percent"]) == Decimal(expected)
    incomplete = portfolio_performance(snapshots, rows, watermark=END, history_complete=False)
    assert incomplete["return_percent"] is None
    assert incomplete["return_status"] == "unavailable"


def test_dietz_does_not_report_percentage_when_weighted_capital_is_nonpositive() -> None:
    snapshots = [
        {"captured_at": START, "nav_rub": "100", "analysis_status": "observed"},
        {"captured_at": END, "nav_rub": "100", "analysis_status": "observed"},
    ]
    result = portfolio_performance(
        snapshots, [operation("OUTPUT", "-300", day=10)], watermark=END, history_complete=True,
    )
    assert result["investment_result_rub"] == "300"
    assert result["return_percent"] is None
    assert result["return_reason"] == "non_positive_or_negligible_invested_capital"


@pytest.mark.parametrize(
    "row, reason",
    [
        (operation("INPUT_SECURITIES", "0"), "unclassified_or_non_cash_transfer"),
        (operation("BUY_CARD", "-10000"), "unclassified_or_non_cash_transfer"),
        (operation("UNKNOWN_NEW_ENUM", "10"), "unclassified_or_non_cash_transfer"),
        (operation("INPUT", "100", currency="USD"), "payment_currency_or_amount_unavailable"),
        (operation("INPUT", "-100"), "external_flow_sign_invalid"),
        (operation("COUPON", "1", operation_state="unknown"), "operation_state_unknown"),
    ],
)
def test_unknown_external_flows_block_performance(row: dict[str, Any], reason: str) -> None:
    flow = cashflow_summary([row], from_at=START, to_at=END, complete=True)
    assert flow["status"] == "unavailable"
    assert reason in flow["reason"]
    assert flow["net_contributions_rub"] is None


def test_canceled_pending_and_outside_period_operations_are_excluded() -> None:
    rows = [
        operation("INPUT", "10", operation_state="OPERATION_STATE_CANCELED"),
        operation("COUPON", "50", operation_state="OPERATION_STATE_PROGRESS"),
        operation("INPUT", "999", day=0),
        operation("COUPON", "1000", day=31),
        operation("COUPON", "30", day=30),
    ]
    flow = cashflow_summary(rows, from_at=START, to_at=END, complete=True)
    assert flow["income"]["total_rub"] == "30"
    assert flow["net_contributions_rub"] == "0"


def test_incomplete_history_never_displays_zero_as_known_income() -> None:
    flow = cashflow_summary([], from_at=START, to_at=END, complete=False)
    assert flow["income"]["status"] == "unavailable"
    assert flow["income"]["total_rub"] is None
    assert flow["income"]["by_month"] == []
    no_payments = cashflow_summary([], from_at=START, to_at=END, complete=True)
    assert no_payments["income"]["total_rub"] == "0"


def test_performance_never_extrapolates_after_sync_watermark() -> None:
    snapshots = [
        {"captured_at": START, "nav_rub": "100000", "analysis_status": "observed"},
        {"captured_at": END, "nav_rub": "105000", "analysis_status": "observed"},
        {
            "captured_at": END + timedelta(seconds=1),
            "nav_rub": "200000",
            "analysis_status": "observed",
        },
    ]
    result = portfolio_performance(snapshots, [], watermark=END, history_complete=True)
    assert result["end_nav_rub"] == "105000"
    assert result["investment_result_rub"] == "5000"
    assert (
        portfolio_performance(snapshots, [], watermark=None, history_complete=False)[
            "investment_result_rub"
        ]
        is None
    )


def test_manual_and_bound_goal_progress_have_distinct_authority() -> None:
    goal = {**goal_document(), "updated_at": END, "account_id": None, "environment": None}
    params: dict[str, Any] = {
        "connection": None,
        "snapshot": None,
        "operations": [],
        "watermark": None,
        "history_complete": False,
        "now": END,
    }
    manual = goal_progress(goal, **params)
    assert manual["amount_rub"] == "25000"
    assert manual["percent"] == "25.00"
    goal.update(
        progress_source="portfolio",
        allocation_percent="40",
        manual_amount_rub=None,
        account_id="A",
        environment="prod",
    )
    params.update(
        connection={"account_id": "A", "environment": "prod"},
        snapshot={"captured_at": END, "analysis_status": "observed", "nav_rub": "150000"},
    )
    progress = goal_progress(goal, **params)
    assert progress["amount_rub"] == "60000"
    params["connection"]["account_id"] = "B"
    changed = goal_progress(goal, **params)
    assert changed["amount_rub"] is None
    assert changed["reason"] == "linked_account_unavailable"


def test_income_goal_uses_only_allocated_received_income() -> None:
    goal = {
        **goal_document(
            kind="income", progress_source="income", allocation_percent="25", manual_amount_rub=None
        ),
        "updated_at": END,
        "account_id": "A",
        "environment": "prod",
    }
    result = goal_progress(
        goal,
        connection={"account_id": "A", "environment": "prod"},
        snapshot=None,
        operations=[operation("COUPON", "1000"), operation("BOND_REPAYMENT_FULL", "10000")],
        watermark=END,
        history_complete=True,
        now=END,
    )
    assert result["amount_rub"] == "250"


def test_income_goal_calendar_start_includes_midnight_without_earlier_payments() -> None:
    midnight_moscow = datetime(2025, 12, 31, 21, tzinfo=UTC)
    goal = {
        **goal_document(kind="income", progress_source="income", allocation_percent="100",
                        manual_amount_rub=None),
        "updated_at": END, "account_id": "A", "environment": "prod",
    }
    result = goal_progress(
        goal, connection={"account_id": "A", "environment": "prod"}, snapshot=None,
        operations=[
            operation("COUPON", "100", operation_date=midnight_moscow),
            operation("COUPON", "900", operation_date=midnight_moscow - timedelta(microseconds=1)),
        ],
        watermark=END, history_complete=True, now=END,
    )
    assert result["amount_rub"] == "100"


def test_zero_nav_is_a_real_observation_but_one_point_is_not_a_performance_period() -> None:
    first = {"captured_at": START, "nav_rub": "0", "analysis_status": "observed"}
    single = portfolio_performance([first], [], watermark=END, history_complete=True)
    assert single["investment_result_rub"] is None
    assert single["reason"] == "insufficient_covered_snapshots"
    second = {"captured_at": END, "nav_rub": "0", "analysis_status": "observed"}
    pair = portfolio_performance([first, second], [], watermark=END, history_complete=True)
    assert pair["investment_result_rub"] == "0"
    assert pair["return_percent"] is None


def test_event_identity_is_stable_and_digest_is_not_a_probability() -> None:
    identity = {"instrument": "bond", "state": "watch"}
    assert event_id("risk", identity) == event_id("risk", copy.deepcopy(identity))
    assert event_id("risk", identity) != event_id("payment", identity)
    preferences = default_preferences()
    preferences["digest_frequency"] = "weekly"
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    rows = [
        {"category": "system", "occurred_at": now - timedelta(days=10),
         "updated_at": now, "read_at": None},
        {"category": "goals", "occurred_at": now, "updated_at": now, "read_at": now},
        {"category": "system", "occurred_at": now, "read_at": None},
    ]
    digest = event_digest(rows, preferences, now)
    assert digest["count"] == 1
    assert digest["by_category"]["system"] == 1
    assert digest["period_basis"] == "available_at"
    assert datetime.fromisoformat(digest["from"]).weekday() == 0
