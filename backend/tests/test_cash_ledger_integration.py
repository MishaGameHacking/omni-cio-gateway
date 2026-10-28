"""Cash history and materialized workspace state commit or roll back together."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend import app as backend, volume_credit, volume_state as state
from backend import volume_workspace as workspace
from backend.tests.test_volume_workspace import fixture, operation
from backend.volume_contract import source


def observed_operations(fixture, identifier="cash-coupon", amount="3"):
    snapshot = deepcopy(state.saved_snapshot(fixture["user"]))
    observed = datetime.now(timezone.utc)
    when = observed - timedelta(minutes=1)
    refs = [source("GetOperationsByCursor", account["id"], observed.isoformat(), ttl=900)
            for account in snapshot["accounts"]]
    snapshot["sources"].extend(refs)
    item = operation(identifier, payment=amount, at=when.isoformat())
    item.update(type="OPERATION_TYPE_COUPON", category="coupons", source_ids=[refs[0]["id"]])
    snapshot["operations"] = {"items": [item], "complete": True,
        "start": (observed - timedelta(days=60)).isoformat(), "end": observed.isoformat()}
    snapshot.setdefault("section_as_of", {})["operations"] = observed.isoformat()
    return snapshot


def history_count():
    with closing(backend.connect()) as db:
        return db.execute("SELECT COUNT(*) FROM broker_operation_history_v1").fetchone()[0]


def test_workspace_persists_history_and_authenticated_materialized_receipt(fixture):
    snapshot = observed_operations(fixture)
    workspace.persist(fixture["user"], snapshot)
    stored = state.saved_snapshot(fixture["user"])
    assert stored["cash_ledger"]["state"] == "observed"
    assert stored["cash_ledger"]["cash_movements"] == [
        {"currency": "RUB", "category": "coupon_income", "amount": "3"}]
    count = history_count()
    first = fixture["client"].get("/workspace/cash-ledger")
    second = fixture["client"].get("/workspace/cash-ledger")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["cash_movements"] == stored["cash_ledger"]["cash_movements"]
    assert first.json()["performance_calculated"] is False
    assert history_count() == count


def test_later_snapshot_failure_rolls_back_both_ledger_and_workspace(fixture):
    prior = state.saved_snapshot(fixture["user"])
    count = history_count()
    snapshot = observed_operations(fixture, "must-roll-back")

    def fail_after_write(*args):
        raise RuntimeError("synthetic_later_snapshot_failure")

    fixture["patch"].setattr(volume_credit, "record_changes_in", fail_after_write)
    with pytest.raises(RuntimeError, match="synthetic_later_snapshot_failure"):
        workspace.persist(fixture["user"], snapshot)
    assert history_count() == count
    assert state.saved_snapshot(fixture["user"]) == prior


def test_rejected_compare_and_swap_cannot_append_cash_history(fixture):
    prior = state.saved_snapshot(fixture["user"])
    count = history_count()
    stale = deepcopy(prior)
    stale["as_of"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with pytest.raises(HTTPException) as error:
        workspace.persist(fixture["user"], observed_operations(fixture), expected_snapshot=stale)
    assert error.value.status_code == 409
    assert history_count() == count
    assert state.saved_snapshot(fixture["user"]) == prior


def test_cash_history_remains_when_next_window_no_longer_contains_operation(fixture):
    first = observed_operations(fixture)
    workspace.persist(fixture["user"], first)
    count = history_count()
    later = deepcopy(state.saved_snapshot(fixture["user"]))
    later["operations"]["items"] = []
    workspace.persist(fixture["user"], later)
    assert history_count() == count
    assert state.saved_snapshot(fixture["user"])["cash_ledger"]["cash_movements"] == [
        {"currency": "RUB", "category": "coupon_income", "amount": "3"}]


def test_cash_ledger_requires_authentication_and_matching_broker_connection(fixture):
    workspace.persist(fixture["user"], observed_operations(fixture))
    user = dict(fixture["user"])
    user["tinvest_token_encrypted"] = b"synthetic-new-broker-connection"
    backend.app.dependency_overrides[backend.current_user] = lambda: user
    response = fixture["client"].get("/workspace/cash-ledger")
    assert response.status_code == 200
    assert response.json()["state"] == "unavailable"
    assert "cash_movements" not in response.json()
    backend.app.dependency_overrides.pop(backend.current_user, None)
    assert fixture["client"].get("/workspace/cash-ledger").status_code == 401
