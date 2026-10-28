"""Synthetic contract regressions for the preview50 release-blocker refactor.

No broker, external model, owner database, process launcher or publication.
Assertions exercise public results, not the names of extracted helpers.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend import market_schedule as calendar
from backend import portfolio_accounting as cash
from backend import source_observability as provenance

NOW = datetime(2026, 10, 28, 10, tzinfo=timezone.utc)
START = NOW - timedelta(days=1)
SCOPE = cash.Scope("synthetic-owner", "synthetic-connection", "synthetic-account")


def balances():
    opening = cash.CashBalance(SCOPE, START, "RUB", "100", "opening",
                               independent_of_operation_ledger=True)
    closing = cash.CashBalance(SCOPE, NOW, "RUB", "150", "closing",
                               independent_of_operation_ledger=True)
    return opening, closing


def movement(identifier="payment", amount="50", at=NOW, state="settled"):
    return cash.CashMovement(SCOPE, identifier, at, "RUB", amount, identifier + "-evidence", state)


def complete_window():
    return cash.ObservedWindow(SCOPE, START, NOW, "settlement-window", True)


def test_cash_exact_public_result_preserves_deduplication_and_open_left_boundary():
    opening, closing = balances()
    movements = [movement(), movement(), movement("opening-boundary", "999", START)]
    result = cash.reconcile_cash(opening, closing, movements, [complete_window()])
    assert result == {
        "state": "matched", "reconciled": True, "reasons": [], "currency": "RUB",
        "opening": "100", "observed_closing": "150", "expected_closing": "150",
        "difference": "0", "settled_movements": 1,
        "evidence_ids": ["closing", "opening", "opening-boundary-evidence",
                         "payment-evidence", "settlement-window"],
        "tax_liability_estimated": False,
    }


def test_conflicting_versions_outside_window_still_block_reconciliation():
    opening, closing = balances()
    records = [movement(), movement("previous", "1", START), movement("previous", "2", START)]
    result = cash.reconcile_cash(opening, closing, records, [complete_window()])
    assert result["state"] == "incomplete"
    assert result["expected_closing"] is None
    assert result["reasons"] == ["conflicting_movement_versions"]


@pytest.mark.parametrize("state", ["pending", "unknown"])
def test_unresolved_movement_at_closing_boundary_is_not_silently_ignored(state):
    opening, closing = balances()
    result = cash.reconcile_cash(opening, closing, [movement(state=state)], [complete_window()])
    assert result["reconciled"] is False
    assert result["difference"] is None
    assert result["reasons"] == ["unresolved_cash_movements"]


def test_pending_opening_boundary_and_cancelled_records_do_not_count_as_cash():
    opening, closing = balances()
    records = [movement(), movement("pending-before", "99", START, "pending"),
               movement("cancelled", "88", NOW, "cancelled")]
    result = cash.reconcile_cash(opening, closing, records, [complete_window()])
    assert result["state"] == "matched"
    assert result["settled_movements"] == 1


@pytest.mark.parametrize("complete", [False, None, 1, "true"])
def test_only_actual_complete_boolean_makes_a_settlement_window_usable(complete):
    opening, closing = balances()
    window = replace(complete_window(), complete=complete)
    result = cash.reconcile_cash(opening, closing, [movement()], [window])
    assert result["state"] == "incomplete"
    assert result["reasons"] == ["settlement_coverage_incomplete"]


def test_scope_validation_is_not_skipped_for_outside_window_records():
    opening, closing = balances()
    record = replace(movement(at=START), currency="USD")
    windows = [complete_window()]
    with pytest.raises(cash.AccountingError, match="accounting_movement_currency_mismatch"):
        cash.reconcile_cash(opening, closing, [record], windows)


def test_xirr_zero_is_a_computed_return_not_a_missing_root():
    flows = [cash.InvestorCashFlow(date(2025, 1, 1), "-1000", "deposit"),
             cash.InvestorCashFlow(date(2026, 1, 1), "1000", "terminal")]
    result = cash.money_weighted_return(flows, currency="RUB", all_external_flows_observed=True,
                                        terminal_value_reconciled=True)
    assert result["state"] == "computed_from_supplied_evidence"
    assert abs(Decimal(result["return"])) < Decimal("1e-25")
    assert result["evidence_ids"] == ["deposit", "terminal"]


def test_xirr_outside_supported_rate_bounds_remains_unavailable():
    flows = [cash.InvestorCashFlow(date(2026, 1, 1), "-1", "deposit"),
             cash.InvestorCashFlow(date(2026, 1, 2), "1e24", "terminal")]
    result = cash.money_weighted_return(flows, currency="RUB", all_external_flows_observed=True,
                                        terminal_value_reconciled=True)
    assert result == {"state": "unavailable", "reason": "xirr_root_outside_supported_bounds", "return": None}


def test_required_venues_remain_sorted_distinct_and_exact():
    positions = [{"instrument_type": "bond", "metadata": {"exchange": venue}}
                 for venue in ("MOEX-bond", "MOEX", "MOEX-bond")]
    assert calendar.required_exchanges({"positions": positions}) == ("MOEX", "MOEX-bond")
    positions.append({"instrument_type": "share", "metadata": {}})
    assert calendar.required_exchanges({"positions": positions}) == ()
    assert calendar.required_exchanges({"positions": []}) == ("MOEX",)


def broker_calendar():
    row = {"date": NOW.replace(hour=0).isoformat(), "isTradingDay": True,
           "startTime": NOW.replace(hour=7).isoformat(), "endTime": NOW.replace(hour=16).isoformat()}
    return {"state": "available", "data": {"timezone": "UTC", "as_of": NOW.isoformat(),
            "exchanges": [{"exchange": "MOEX", "days": [row]}]}}


def test_calendar_does_not_mutate_and_preserves_the_full_read_only_contract():
    value = broker_calendar()
    original = deepcopy(value)
    result = calendar.polling_state(value, ("MOEX",), now=NOW)
    assert result == {
        "state": "scheduled_window", "reason": "broker_schedule_scheduled_window",
        "as_of": NOW.isoformat(), "checked_at": NOW.isoformat(), "timezone": "UTC",
        "display_timezone": "Europe/Moscow", "required_exchanges": ["MOEX"],
        "next_transition_at": NOW.replace(hour=16).isoformat(),
        "regular_price_polling_allowed": True, "main_session_verified": False,
        "trade_permission": False, "interval_classification": "legacy_broker_window",
        "sections": [{"exchange": "MOEX", "state": "scheduled_window"}],
    }
    assert value == original


def test_partial_section_evidence_does_not_authorize_missing_second_venue():
    result = calendar.polling_state(broker_calendar(), ("MOEX", "missing"), now=NOW)
    assert result["sections"] == [{"exchange": "MOEX", "state": "scheduled_window"}]
    assert result["state"] == "unknown"
    assert result["reason"] == "calendar_incomplete_or_conflicting"
    assert result["regular_price_polling_allowed"] is False
    assert result["trade_permission"] is False


def source(**changes):
    return {"id": "source", "observed_at": (NOW - timedelta(seconds=5)).isoformat(),
            "expires_at": (NOW + timedelta(seconds=20)).isoformat(),
            "published_at": (NOW - timedelta(seconds=10)).isoformat(), **changes}


@pytest.mark.parametrize("changes,category", [
    ({"observed_at": None}, "invalid"),
    ({"expires_at": None}, "invalid"),
    ({"expires_at": NOW.isoformat()}, "stale"),
    ({"published_at": NOW.isoformat()}, "future"),
    ({"published_at": "not-a-time"}, "invalid"),
    ({"published_at": None}, "current"),
])
def test_source_clock_classification_keeps_its_existing_precedence(changes, category):
    snapshot = {"sources": [source(**changes)], "positions": [{"source_ids": ["source"]}]}
    before = deepcopy(snapshot)
    result = provenance.provenance_inventory(snapshot, now=NOW)
    assert result["counts"][category] == 1
    assert result["financial_facts_verified"] is False
    assert snapshot == before


def test_duplicate_conflict_remains_unresolved_after_a_later_equal_observation():
    first = source()
    second = source(published_at=(NOW - timedelta(seconds=11)).isoformat())
    snapshot = {"sources": [first, second, first], "positions": [{"source_ids": ["source"]}]}
    result = provenance.provenance_inventory(snapshot, now=NOW)
    assert result["source_count"] == 0
    assert result["counts"]["conflicting_ids"] == 1
    assert result["unresolved_reference_count"] == 1
    assert result["reference_resolution_complete"] is False
    assert result["reasons"] == ["source_id_conflicting_versions", "source_references_unresolved"]


def test_reference_walk_does_not_treat_source_ids_contents_as_nested_documents():
    snapshot = {"sources": [source()], "positions": [{"source_ids": [
        "source", {"source_ids": ["not-an-actual-reference"]}, ""]}]}
    result = provenance.provenance_inventory(snapshot, now=NOW)
    assert result["referenced_count"] == 1
    assert result["unresolved_reference_count"] == 0
    assert result["reasons"] == ["source_reference_id_invalid"]
    assert result["reference_resolution_complete"] is False


def test_reference_walk_retains_explicit_resource_limit(monkeypatch):
    monkeypatch.setattr(provenance, "MAX_REFERENCE_NODES", 2)
    result = provenance.provenance_inventory({"sources": [], "operations": [1, 2, 3]}, now=NOW)
    assert "source_reference_resource_limit" in result["reasons"]
    assert result["reference_resolution_complete"] is False
