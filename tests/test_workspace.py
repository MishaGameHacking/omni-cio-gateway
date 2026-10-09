from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from omnicio.workspace import (
    default_preferences,
    event_digest,
    event_id,
    goal_progress,
    normalize_goal,
    normalize_preferences,
    portfolio_value_change,
    quiet_now,
    snapshot_valuation_complete,
)
from omnicio.workspace_store import WorkspaceStore, _History

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


@pytest.mark.parametrize(
    ("target", "current", "reached"),
    (
        ("100000.00", "50.000000000", False),
        ("3.00", "1.000000000", False),
        ("100.00", "100.000000000", True),
    ),
)
def test_goal_events_accept_calculated_percent_precision_from_stored_money(
    target: str,
    current: str,
    reached: bool,
) -> None:
    owner = uuid4()
    goal = goal_document(
        id=str(uuid4()),
        version=1,
        target_amount_rub=Decimal(target),
        manual_amount_rub=Decimal(current),
        target_date=None,
        updated_at=END,
    )
    goal["progress"] = goal_progress(goal, connection=None, snapshot=None, now=END)
    assert goal["progress"]["status"] == "available"
    store = WorkspaceStore(Mock())
    with patch.object(store, "_insert_event") as insert:
        store._goal_events(Mock(), owner, [goal], END)
    assert insert.call_count == int(reached)
    if reached:
        assert insert.call_args.kwargs["kind"] == "goal_reached"


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


def test_manual_and_bound_goal_progress_have_distinct_authority() -> None:
    goal = {**goal_document(), "updated_at": END, "account_id": None, "environment": None}
    params: dict[str, Any] = {
        "connection": None,
        "snapshot": None,
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


def test_value_change_uses_only_our_snapshots_and_never_claims_profit() -> None:
    rows = [
        {"captured_at": START, "analysis_status": "observed", "nav_rub": "1000"},
        {"captured_at": END, "analysis_status": "observed", "nav_rub": "1500"},
    ]
    change = portfolio_value_change(rows)
    assert change["status"] == "available"
    assert change["nav_change_rub"] == "500"
    assert change["method"] == "snapshot_value_change"
    assert "не доходность" in change["limitation"]
    assert not {"return_percent", "investment_result_rub", "net_contributions_rub"} & change.keys()


@pytest.mark.parametrize("nav", [None, "NaN", "Infinity", "unknown"])
def test_missing_nav_is_not_zero_or_a_complete_value_observation(nav) -> None:
    row = {
        "captured_at": START,
        "analysis_status": "observed",
        "valuation_status": "complete",
        "nav_rub": nav,
    }
    assert not snapshot_valuation_complete(row)
    assert portfolio_value_change([row, {**row, "captured_at": END}])["nav_change_rub"] is None


def test_real_zero_nav_is_known_but_a_single_observation_has_no_change() -> None:
    first = {"captured_at": START, "analysis_status": "observed", "nav_rub": "0"}
    assert snapshot_valuation_complete(first)
    assert portfolio_value_change([first])["nav_change_rub"] is None
    assert portfolio_value_change([first, {**first, "captured_at": END}])["nav_change_rub"] == "0"


def test_workspace_snapshot_selection_never_reads_private_history_or_profile() -> None:
    owner = uuid4()
    cursor = Mock()
    cursor.fetchone.side_effect = [
        {"account_id": "A", "environment": "prod", "account_name": "Брокерский счёт"},
        {
            "id": uuid4(),
            "captured_at": END,
            "analysis_status": "partial",
            "nav_rub": None,
            "rub_cash_total": "100",
            "rub_cash_blocked": None,
            "rub_cash_unblocked": None,
            "evidence": {"analysis": {"valuation_status": "unavailable"}},
        },
    ]

    def enforce_scope(query, args):
        assert "operation_observations" not in query
        assert "broker_sync_state" not in query
        assert "broker_user" not in query
        assert "broker_statistics" not in query
        assert owner in args

    cursor.execute.side_effect = enforce_scope
    basis = WorkspaceStore(Mock())._basis(cursor, owner)
    overview = WorkspaceStore._overview(basis, _History([], [], {}), END)
    assert overview["status"] == "partial"
    assert overview["nav_rub"] is None
    assert overview["cash_rub"] == "100"
    assert overview["blocked_cash_rub"] is None
    assert overview["free_cash_rub"] is None
    assert "broker_statistics" not in overview


def test_goals_reject_new_automatic_income_source_but_keep_manual_income_targets() -> None:
    with pytest.raises(ValueError):
        normalize_goal(
            goal_document(
                kind="income",
                progress_source="income",
                allocation_percent="100",
                manual_amount_rub=None,
            )
        )
    assert normalize_goal(goal_document(kind="income"))["progress_source"] == "manual"
