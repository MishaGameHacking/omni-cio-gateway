"""Controller regressions with isolated SQLite and explicitly synthetic sources."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("TELEGRAM_CLIENT_ID", "123456")
os.environ.setdefault("TELEGRAM_CLIENT_SECRET", "test-only")
os.environ.setdefault("BACKEND_PUBLIC_URL", "https://example.invalid")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

from backend import app as backend, autonomous_ai as ai
from backend import autonomous_controller as controller, volume_state as state
from backend import volume_workspace as workspace, volume_jobs as jobs
from backend.ai_guarded_client import GuardError
from backend.monitoring_access import monitoring_connection
from backend.volume_contract import now_iso
from backend.tests.test_autonomous_ai import sample_snapshot


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "DATABASE_PATH", tmp_path / "controller.sqlite")
    monkeypatch.setenv("AI_EXTERNAL_PROCESSING_APPROVED", "false")
    monkeypatch.setenv("AI_USER_DAILY_RUB", "0")
    monkeypatch.setenv("AI_PROJECT_DAILY_RUB", "0")
    backend.init_db()
    ai.init_autonomous_db()
    with closing(backend.connect()) as db:
        for index, token in ((1, b"synthetic-connection-a"), (2, None)):
            db.execute("""INSERT INTO users(telegram_sub,telegram_id,tinvest_token_encrypted,created_at,updated_at)
                VALUES (?,?,?,?,?)""", ("controller-" + str(index), str(index), token, 1, 1))
        db.commit()
        user = db.execute("SELECT * FROM users WHERE telegram_id='1'").fetchone()
        other = db.execute("SELECT * FROM users WHERE telegram_id='2'").fetchone()
    return {"user": user, "other": other, "patch": monkeypatch}


def saved(fixture, *, age=0, full=True):
    observed = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
    dashboard = {**sample_snapshot(), "asOf": observed}
    for account in dashboard["accounts"]:
        for item in account["positions"]:
            item["instrumentType"] = "cash" if item["id"].startswith("cash:") else "share"
    snapshot = workspace.normalize_snapshot(fixture["user"], dashboard)
    snapshot["snapshot_id"] = "synthetic-controller-" + str(age)
    if full:
        snapshot["collection"] = {"finished_at": observed}
    workspace.persist(fixture["user"], snapshot)
    return snapshot


def active_strategy(fixture):
    config = {"goal": "preservation", "horizon_months": 36, "reserve": {"amount": "1000", "currency": "RUB"},
              "risk_level": "moderate", "allowed_markets": ["MOEX"],
              "limits": {axis + "_percent": "25" for axis in ("position", "issuer", "group", "sector", "currency")}}
    active = {"version": 1, "config": config}
    fixture["patch"].setattr(state, "active_strategy", lambda *args, **kwargs: active)
    return active


def synthetic_candidate(uid="fixture-security"):
    return {"uid": uid, "ticker": "FIXTURE", "name": "Synthetic test security", "instrument_type": "share",
            "currency": "RUB", "lot": 1, "realExchange": "REAL_EXCHANGE_MOEX",
            "buyAvailableFlag": True, "apiTradeAvailableFlag": True, "blockedTcaFlag": False,
            "subordinatedFlag": False, "perpetualFlag": False}


def test_initial_full_collection_is_automatic_idempotent_and_connection_bound(fixture):
    first = controller.enqueue_collection(fixture["user"])
    second = controller.enqueue_collection(fixture["user"], now=int(time.time()) + 301)
    assert first["job_id"] == second["job_id"]
    assert second["state"] == "coalesced"
    with closing(backend.connect()) as db:
        row = db.execute("SELECT * FROM workspace_jobs").fetchone()
        assert row["kind"] == "refresh"
        assert json.loads(row["checkpoint_json"])["broker_key"] == state.broker_key(fixture["user"])
        assert db.execute("SELECT COUNT(*) FROM workspace_jobs").fetchone()[0] == 1


def test_concurrent_schedulers_do_not_duplicate_collection(fixture):
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: controller.enqueue_collection(fixture["user"]), range(4)))
    assert len({result["job_id"] for result in results}) == 1
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_jobs").fetchone()[0] == 1


def test_fresh_full_collection_is_reused_even_if_monitor_snapshot_changed(fixture):
    saved(fixture)
    assert controller.enqueue_collection(fixture["user"]) == {"state": "current"}
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_jobs").fetchone()[0] == 0


def test_missing_token_and_paused_owner_enqueue_nothing(fixture):
    assert controller.enqueue_collection(fixture["other"]) == {"state": "not_connected"}
    result = controller.update_preferences(controller.PreferenceUpdate(enabled=False, expected_version=0), fixture["user"])
    assert result["enabled"] is False and result["version"] == 1
    assert controller.enqueue_collection(fixture["user"]) == {"state": "paused"}
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_jobs").fetchone()[0] == 0


def test_pause_persists_and_rejects_stale_preference_edit(fixture):
    first = controller.enqueue_collection(fixture["user"])
    ai.AnalysisQueue(backend.connect).enqueue(int(fixture["user"]["id"]))
    controller.update_preferences(controller.PreferenceUpdate(enabled=False, expected_version=0), fixture["user"])
    with pytest.raises(HTTPException) as conflict:
        controller.update_preferences(controller.PreferenceUpdate(enabled=True, expected_version=0), fixture["user"])
    assert conflict.value.detail == "automation_preferences_changed"
    with closing(backend.connect()) as db:
        assert db.execute("SELECT state FROM workspace_jobs WHERE id=?", (first["job_id"],)).fetchone()[0] == "cancelled"
        assert db.execute("SELECT status FROM ai_work_jobs").fetchone()[0] == "failed"
    controller.initialize()
    assert controller.preferences(int(fixture["user"]["id"]))["enabled"] is False


def test_reconnect_does_not_run_old_connection_checkpoint(fixture):
    old = controller.enqueue_collection(fixture["user"])
    with closing(backend.connect()) as db:
        db.execute("UPDATE users SET tinvest_token_encrypted=? WHERE id=?", (b"synthetic-connection-b", fixture["user"]["id"]))
        db.commit()
        changed = db.execute("SELECT * FROM users WHERE id=?", (fixture["user"]["id"],)).fetchone()
    newer = controller.enqueue_collection(changed)
    assert old["job_id"] != newer["job_id"]
    called = []
    fixture["patch"].setattr(workspace.details, "load_dashboard", lambda *args, **kwargs: called.append(True))
    jobs.run_job(old["job_id"])
    assert called == []
    with closing(backend.connect()) as db:
        row = db.execute("SELECT state,error_code FROM workspace_jobs WHERE id=?", (old["job_id"],)).fetchone()
    assert row["state"] == "failed"
    assert row["error_code"] == "workspace_broker_connection_changed"


def test_first_observation_is_once_and_never_claims_trade_or_model(fixture):
    snapshot = saved(fixture)
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected broker or paid model call")
    fixture["patch"].setattr(controller.catalogue, "load_catalogue", forbidden)
    fixture["patch"].setattr(ai, "analyze_if_needed", forbidden)
    with monitoring_connection(int(fixture["user"]["id"]), fixture["user"]["tinvest_token_encrypted"]):
        controller.observe_and_discover(fixture["user"], snapshot, datetime.now(timezone.utc))
        controller.observe_and_discover(fixture["user"], snapshot, datetime.now(timezone.utc))
    result = controller.decisions(fixture["user"])
    assert [row["kind"] for row in result["events"]] == ["initial_observation"]
    assert result["discovery"]["state"] == "blocked"
    assert result["discovery"]["reasons"][0]["code"] == "strategy_required"
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM insight_cards").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM ai_money_reservations").fetchone()[0] == 0


def test_revoked_connection_cannot_commit_initial_observation(fixture):
    snapshot = saved(fixture)
    with closing(backend.connect()) as db:
        db.execute("UPDATE users SET tinvest_token_encrypted=NULL WHERE id=?", (fixture["user"]["id"],))
        db.commit()
    with pytest.raises(HTTPException):
        controller.record_initial_observation(fixture["user"], snapshot, int(time.time()))
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM automation_observations").fetchone()[0] == 0


def test_paused_analysis_never_reads_broker_or_model(fixture):
    controller.update_preferences(controller.PreferenceUpdate(enabled=False, expected_version=0), fixture["user"])
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network work")
    fixture["patch"].setattr(ai, "get_tinvest_portfolio", forbidden)
    fixture["patch"].setattr(ai, "analyze_if_needed", forbidden)
    assert ai.run_user_analysis(int(fixture["user"]["id"]))["state"] == "paused"


def test_status_and_decisions_are_read_only_and_have_no_network_side_effects(fixture):
    saved(fixture)
    def forbidden(*args, **kwargs):
        raise AssertionError("GET must not perform work")
    fixture["patch"].setattr(controller.catalogue, "load_catalogue", forbidden)
    fixture["patch"].setattr(ai, "analyze_if_needed", forbidden)
    fixture["patch"].setattr(jobs, "enqueue", forbidden)
    fixture["patch"].setattr(controller, "configured_route", lambda *args, **kwargs: (_ for _ in ()).throw(GuardError("ai_not_configured")))
    original = backend.connect
    def read_only():
        db = original()
        db.execute("PRAGMA query_only=ON")
        return db
    fixture["patch"].setattr(backend, "connect", read_only)
    result = controller.status(fixture["user"])
    assert result["broker_connected"] is True
    assert result["execution"] == {"mode": "read_only", "real_orders_enabled": False}
    assert result["ai"]["available"] is False
    assert controller.decisions(fixture["other"])["events"] == []


def test_status_reports_missing_connection_instead_of_false_running(fixture):
    fixture["patch"].setattr(ai, "SCHEDULER_ENABLED", True)
    result = controller.status(fixture["other"])
    assert result["state"] == "not_connected"
    assert result["last_observation_at"] is None
    assert result["discovery"]["candidates"] == []
    assert result["blockers"][0]["code"] == "tinvest_not_connected"


def test_failed_collection_preserves_last_good_snapshot_and_reports_failure(fixture):
    snapshot = saved(fixture, age=1900)
    job = controller.enqueue_collection(fixture["user"])
    fixture["patch"].setattr(workspace.details, "load_dashboard",
                            lambda *args, **kwargs: (_ for _ in ()).throw(HTTPException(503, "tinvest_timeout")))
    jobs.run_job(job["job_id"])
    fixture["patch"].setattr(ai, "SCHEDULER_ENABLED", True)
    result = controller.status(fixture["user"])
    assert result["state"] == "attention"
    assert "workspace_collection_failed" in {item["code"] for item in result["blockers"]}
    assert state.saved_snapshot(fixture["user"])["snapshot_id"] == snapshot["snapshot_id"]


def test_discovery_requires_real_strategy_and_observed_cash(fixture):
    saved(fixture)
    active = active_strategy(fixture)
    active["config"]["reserve"]["amount"] = "999999999"
    def forbidden(*args, **kwargs):
        raise AssertionError("No catalogue request without observed excess cash")
    fixture["patch"].setattr(controller.catalogue, "load_catalogue", forbidden)
    result, _ = controller._collect_discovery(fixture["user"], 0, int(time.time()))
    assert result["state"] == "blocked"
    assert result["reasons"][0]["code"] == "observed_cash_not_above_reserve"
    assert result["candidates"] == []


def test_discovery_bounds_and_rotates_actual_catalogue_candidates_without_ai(fixture):
    saved(fixture)
    active_strategy(fixture)
    items = [synthetic_candidate("fixture-" + str(i).zfill(2)) for i in range(12)]
    def catalog(user, kind):
        return {"items": items if kind == "share" else [], "source": {"id": "synthetic-source-" + kind}}
    fixture["patch"].setattr(controller.catalogue, "load_catalogue", catalog)
    checked = []
    def check(user, item, account, version):
        checked.append(item["uid"])
        return {"instrument_uid": item["uid"], "constraints_passed": False,
                "missing_evidence": ["investment_thesis_and_valuation"], "checks": [], "expires_at": None}
    fixture["patch"].setattr(controller, "_check_candidate", check)
    result, cursor = controller._collect_discovery(fixture["user"], 0, int(time.time()))
    assert result["coverage"]["scanned"] == 12
    assert result["coverage"]["reviewed"] == controller.MAX_REVIEWED_PER_CYCLE
    assert len(set(checked)) == controller.MAX_REVIEWED_PER_CYCLE
    assert result["recommendation_complete"] is False
    assert result["automatic_orders"] is False
    checked.clear()
    controller._collect_discovery(fixture["user"], cursor, int(time.time()))
    assert checked[0] == "fixture-08"


def test_discovery_excludes_foreign_blocked_and_unpriced_lots(fixture):
    config = active_strategy(fixture)["config"]
    base = synthetic_candidate()
    assert controller._catalogue_candidate(base, config)
    for change in ({"currency": "USD"}, {"blockedTcaFlag": True}, {"lot": None},
                   {"apiTradeAvailableFlag": False}, {"realExchange": "REAL_EXCHANGE_OTC"},
                   {"subordinatedFlag": True}):
        assert not controller._catalogue_candidate({**base, **change}, config)


def test_discovery_lease_prevents_duplicate_paid_or_broker_fanout(fixture):
    saved(fixture)
    first = controller._claim_discovery(fixture["user"], int(time.time()))
    assert first is not None
    assert controller._claim_discovery(fixture["user"], int(time.time())) is None


def test_old_connection_discovery_is_never_visible_after_reconnect(fixture):
    snapshot = saved(fixture)
    controller.observe_and_discover(fixture["user"], snapshot, datetime.now(timezone.utc))
    with closing(backend.connect()) as db:
        db.execute("UPDATE users SET tinvest_token_encrypted=? WHERE id=?", (b"replacement-fixture", fixture["user"]["id"]))
        db.commit()
        replacement = db.execute("SELECT * FROM users WHERE id=?", (fixture["user"]["id"],)).fetchone()
    result = controller.decisions(replacement)
    assert result["events"] == []
    assert result["discovery"]["state"] == "waiting"


def test_candidate_check_uses_only_read_methods_and_keeps_missing_investment_thesis(fixture):
    class Reader:
        def __init__(self, user):
            self.user = user
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    fixture["patch"].setattr(controller.details, "BrokerReader", Reader)
    methods = []
    def read(reader, method, payload):
        methods.append(method)
        assert payload == {"instrumentId": "fixture-security", "depth": 1}
        # Official unary shape: isConsistent is a field of streamed OrderBook.
        return {"instrumentUid": "fixture-security", "depth": 1, "orderbookTs": now_iso(),
                "asks": [{"price": {"units": "100", "nano": 0}, "quantity": "1"}]}
    fixture["patch"].setattr(controller.market, "broker_read", read)
    def checked(payload, user, *, archive=True):
        assert archive is False
        assert payload.instrument_uid == "fixture-security"
        assert payload.lots == 1
        assert payload.limit_price == "100"
        return {"constraints_passed": True, "reasons": [],
                "remaining_checks": ["investment_thesis_and_valuation"],
                "as_of": now_iso(), "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat(),
                "total_cost": {"amount": "100", "currency": "RUB"}, "check_id": "synthetic-check"}
    fixture["patch"].setattr(controller.purchases, "_check_purchase", checked)
    result = controller._check_candidate(fixture["user"], synthetic_candidate(), "synthetic-account", 1)
    assert methods == ["order_book"]
    assert result["constraints_passed"] is True
    assert result["recommendation_complete"] is False
    assert "investment_thesis_and_valuation" in result["missing_evidence"]


def test_expired_candidate_evidence_never_reads_as_current(fixture):
    key = state.broker_key(fixture["user"])
    result = controller._empty_discovery("partial")
    result["candidates"] = [{"expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}]
    now = int(time.time())
    with closing(backend.connect()) as db:
        db.execute("INSERT INTO automation_discovery VALUES (?,?,NULL,0,'partial',?,?,?,NULL,NULL,0)",
                   (fixture["user"]["id"], key, json.dumps(result), now, now))
        db.commit()
    assert controller.decisions(fixture["user"])["discovery"]["candidates"][0]["evidence_current"] is False


def test_http_routes_require_authenticated_owner_and_preference_cas(fixture):
    with TestClient(backend.app) as client:
        assert client.get("/automation/status").status_code == 401
        assert client.get("/automation/decisions").status_code == 401
        assert client.put("/automation/preferences", json={"enabled": False, "expected_version": 0}).status_code == 401
        backend.app.dependency_overrides[backend.current_user] = lambda: fixture["user"]
        try:
            assert client.get("/automation/status").status_code == 200
            response = client.put("/automation/preferences", json={"enabled": False, "expected_version": 0})
            assert response.status_code == 200
            assert response.json()["enabled"] is False
            assert client.put("/automation/preferences", json={"enabled": True, "expected_version": 0}).status_code == 409
        finally:
            backend.app.dependency_overrides.pop(backend.current_user, None)

def store_current_candidate(fixture):
    snapshot = saved(fixture)
    active = active_strategy(fixture)
    now = int(time.time())
    with closing(backend.connect()) as db:
        controller.purchases.research_store.initialize(db)
        revision = asdict(controller.purchases.research_store.read_revision(db))
        result = controller._empty_discovery("partial")
        result.update(snapshot_id=snapshot["snapshot_id"], strategy_version=active["version"], as_of=now_iso())
        result["candidates"] = [{
            "instrument_uid": "synthetic-current-candidate", "constraints_passed": True,
            "snapshot_id": snapshot["snapshot_id"], "strategy_version": active["version"],
            "evidence_revision": revision,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
        }]
        db.execute("INSERT INTO automation_discovery VALUES (?,?,?,?,'partial',?,?,?,NULL,NULL,0)",
                   (fixture["user"]["id"], state.broker_key(fixture["user"]), snapshot["snapshot_id"],
                    active["version"], json.dumps(result), now, now))
        db.commit()
    return active


def test_current_candidate_read_does_not_initialize_or_write_evidence(fixture):
    active = store_current_candidate(fixture)
    original = backend.connect
    def read_only():
        db = original()
        db.execute("PRAGMA query_only=ON")
        return db
    fixture["patch"].setattr(backend, "connect", read_only)
    result = controller._discovery(fixture["user"], active, int(time.time()))
    assert result["candidates"][0]["evidence_current"] is True


@pytest.mark.parametrize("mutation", ["snapshot", "research_revision"])
def test_candidate_expires_immediately_when_inputs_change_before_time_limit(fixture, mutation):
    active = store_current_candidate(fixture)
    assert controller._discovery(fixture["user"], active, int(time.time()))["candidates"][0]["evidence_current"] is True
    with closing(backend.connect()) as db:
        if mutation == "snapshot":
            db.execute("UPDATE workspace_snapshots SET id='new-synthetic-observation' WHERE user_id=?",
                       (fixture["user"]["id"],))
        else:
            db.execute("UPDATE research_revision_v1 SET sequence=sequence+1 WHERE singleton=1")
        db.commit()
    result = controller._discovery(fixture["user"], active, int(time.time()))
    assert result["candidates"][0]["evidence_current"] is False


def test_new_strategy_claim_cannot_relabel_previous_candidate_results(fixture):
    active = store_current_candidate(fixture)
    active["version"] = 2
    assert controller._claim_discovery(fixture["user"], int(time.time())) is not None
    with closing(backend.connect()) as db:
        row = db.execute("SELECT strategy_version,result_json FROM automation_discovery WHERE user_id=?",
                         (fixture["user"]["id"],)).fetchone()
    assert row["strategy_version"] == 2
    assert row["result_json"] is None
    result = controller._discovery(fixture["user"], active, int(time.time()))
    assert result["state"] == "running"
    assert result["candidates"] == []


def test_full_collection_compares_subsecond_clock_without_accepting_future_data(fixture):
    snapshot = saved(fixture)
    observed = datetime.fromisoformat(snapshot["collection"]["finished_at"]).timestamp()
    assert controller.enqueue_collection(fixture["user"], now=observed + 0.125) == {"state": "current"}
    assert controller.enqueue_collection(fixture["user"], now=observed - 0.125)["state"] == "queued"


@pytest.mark.parametrize("case, expected_reason", [
    ("wrong_identity", "purchase_market_identity_mismatch"),
    ("missing_identity", "purchase_market_identity_mismatch"),
    ("stale", "order_book_stale_or_undated"),
    ("future", "order_book_stale_or_undated"),
    ("undated", "order_book_stale_or_undated"),
    ("empty_undated", "order_book_stale_or_undated"),
    ("false_consistency", "order_book_not_consistent"),
    ("invalid_consistency", "order_book_not_consistent"),
    ("empty_asks", "order_book_invalid"),
    ("malformed_ask", "order_book_invalid"),
    ("zero_price", "order_book_invalid"),
    ("zero_quantity", "order_book_invalid"),
    ("fractional_quantity", "order_book_invalid"),
])
def test_unary_candidate_invalid_observation_never_reaches_purchase_check(fixture, case, expected_reason):
    # GetOrderBookResponse omits isConsistent; all other guards still apply.
    book = {"instrumentUid": "fixture-security", "depth": 1, "orderbookTs": now_iso(),
            "asks": [{"price": {"units": "100", "nano": 0}, "quantity": "1"}]}
    if case == "wrong_identity":
        book["instrumentUid"] = "another-synthetic-security"
    elif case == "missing_identity":
        book.pop("instrumentUid")
    elif case in {"stale", "future"}:
        offset = -61 if case == "stale" else 60
        book["orderbookTs"] = (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()
    elif case in {"undated", "empty_undated"}:
        book.pop("orderbookTs")
        if case == "empty_undated":
            book["asks"] = []
    elif case == "false_consistency":
        book["isConsistent"] = False
    elif case == "invalid_consistency":
        book["isConsistent"] = "true"
    elif case == "empty_asks":
        book["asks"] = []
    elif case == "malformed_ask":
        book["asks"] = [None]
    elif case == "zero_price":
        book["asks"][0]["price"]["units"] = "0"
    elif case == "zero_quantity":
        book["asks"][0]["quantity"] = "0"
    elif case == "fractional_quantity":
        book["asks"][0]["quantity"] = "0.5"
    class Reader:
        def __init__(self, user):
            self.user = user
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    calls = []
    def read(reader, method, payload):
        calls.append((method, payload))
        return book
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid market evidence must not reach the purchase check")
    fixture["patch"].setattr(controller.details, "BrokerReader", Reader)
    fixture["patch"].setattr(controller.market, "broker_read", read)
    fixture["patch"].setattr(controller.purchases, "_check_purchase", forbidden)
    result = controller._check_candidate(fixture["user"], synthetic_candidate(), "synthetic-account", 1)
    assert calls == [("order_book", {"instrumentId": "fixture-security", "depth": 1})]
    assert result["constraints_passed"] is False
    assert result["recommendation_complete"] is False
    assert result["missing_evidence"] == [expected_reason]
    assert result["expires_at"] is None
