"""Automatic research keeps full input checks without an unbounded archive."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend import app as backend, volume_purchases as purchases
from backend.tests.test_volume_workspace import fixture
from backend.tests.test_purchase_policy import prepare_endpoint


def test_automatic_checks_do_not_archive_full_snapshots_and_manual_checks_still_do(fixture):
    payload, _, calls = prepare_endpoint(fixture)
    request = purchases.PurchaseCheck(**payload)
    for _ in range(3):
        result = purchases._check_purchase(request, fixture["user"], archive=False)
        assert result["constraints_passed"] is True
        assert result["check_id"] is None
        assert result["snapshot_id"]
        assert result["evidence_revision"]
        assert result["suitability_complete"] is False
    assert calls[0] == ("ownership", "owned-a")
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_records WHERE kind='purchase_check'").fetchone()[0] == 0
    manual = purchases._check_purchase(request, fixture["user"])
    assert manual["check_id"]
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_records WHERE kind='purchase_check'").fetchone()[0] == 1
    archived = purchases.historical_check(manual["check_id"], fixture["user"])
    assert archived["result"] == manual
    assert purchases.digest(archived["inputs"]) == manual["input_digest"]


@pytest.mark.parametrize("mutation", ["snapshot", "strategy", "broker_token", "research_revision", "expiry"])
def test_automatic_check_still_rejects_inputs_changed_at_final_validation(fixture, mutation):
    payload, _, _ = prepare_endpoint(fixture)
    original = purchases.archive_check
    def changed(user, result, observations, *, persist=True):
        assert persist is False
        if mutation == "expiry":
            result["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        else:
            with closing(backend.connect()) as db:
                if mutation == "snapshot":
                    db.execute("UPDATE workspace_snapshots SET id='new-synthetic-snapshot' WHERE user_id=?", (user["id"],))
                elif mutation == "strategy":
                    db.execute("UPDATE workspace_strategy_versions SET version=2 WHERE user_id=?", (user["id"],))
                elif mutation == "broker_token":
                    db.execute("UPDATE users SET tinvest_token_encrypted=NULL WHERE id=?", (user["id"],))
                else:
                    db.execute("UPDATE research_revision_v1 SET sequence=sequence+1 WHERE singleton=1")
                db.commit()
        return original(user, result, observations, persist=persist)
    fixture["patch"].setattr(purchases, "archive_check", changed)
    with pytest.raises(HTTPException) as rejected:
        purchases._check_purchase(purchases.PurchaseCheck(**payload), fixture["user"], archive=False)
    assert rejected.value.detail == ("purchase_observations_expired" if mutation == "expiry" else "purchase_inputs_changed")
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_records WHERE kind='purchase_check'").fetchone()[0] == 0
