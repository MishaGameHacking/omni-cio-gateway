"""Volume integration scenarios using isolated SQLite and synthetic broker fixtures.

No test credentials or fixtures are shipped as application data. Transport tests
exercise the real guarded model router with an in-process HTTP mock only.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import os
import time

import httpx
import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("TELEGRAM_CLIENT_ID", "123456")
os.environ.setdefault("TELEGRAM_CLIENT_SECRET", "test-only")
os.environ.setdefault("BACKEND_PUBLIC_URL", "https://example.invalid")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ["ANALYSIS_SCHEDULER_ENABLED"] = "false"

from backend import app as backend, autonomous_ai as ai
from backend import volume_state as state, volume_workspace as workspace
from backend import volume_chat as chat, volume_jobs as jobs, volume_market as market
from backend import volume_notifications as notifications, volume_devices as devices
from backend import volume_plans as plans, volume_analysis as analysis, volume_monitor as monitor, volume_credit as credit, volume_news as news
from backend import portfolio_details as details, research_store, portfolio_research
from backend.ai_budget import MoneyLedger, transaction
from backend.ai_guarded_client import GuardedAIClient, GuardError
from backend.ai_jobs import AnalysisQueue, CURRENT_JOB, LeaseLost
from backend.volume_contract import decimal, money, now_iso, source, digest
from backend.tests.test_ai_controls import environment, model_response


def position(uid, value, *, kind="share", quantity="10", sector="finance", country="RU"):
    return {"id": uid, "title": "Synthetic fixture " + uid, "ticker": uid.upper(),
            "instrumentType": kind, "quantity": quantity, "currentValue": {"value": value, "currency": "RUB"},
            "blocked": False, "blockedQuantity": "0", "sector": sector, "countryOfRisk": country, "lot": 1}


def config(**limits):
    return {"goal": "preservation", "horizon_months": 24, "reserve": {"amount": "20", "currency": "RUB"},
            "limits": {name + "_percent": str(limits.get(name, 80)) for name in ("position", "issuer", "group", "sector", "currency")},
            "risk_level": "moderate", "allowed_markets": ["MOEX"]}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "DATABASE_PATH", tmp_path / "workspace.db")
    monkeypatch.setenv("AI_EXTERNAL_PROCESSING_APPROVED", "false")
    backend.init_db()
    ai.init_autonomous_db()
    with closing(backend.connect()) as db:
        users = []
        for index in (1, 2):
            cursor = db.execute("INSERT INTO users(telegram_sub,telegram_id,tinvest_token_encrypted,created_at,updated_at) VALUES (?,?,?,?,?)",
                                ("volume-fixture-" + str(index), str(index), b"synthetic-encrypted-placeholder", 1, 1))
            users.append(db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone())
        db.commit()
    observed = now_iso()
    dashboard = {"currency": "RUB", "asOf": observed, "totalValue": {"value": "200", "currency": "RUB"}, "accounts": [
        {"id": "owned-account-a", "name": "A", "totalValue": {"value": "100", "currency": "RUB"},
         "positions": [position("aaa", "80"), position("cash:RUB", "20", kind="cash", quantity="20")]},
        {"id": "owned-account-b", "name": "B", "totalValue": {"value": "100", "currency": "RUB"},
         "positions": [position("bbb", "100", sector="energy", country="KZ")]},
    ]}
    snapshot = workspace.normalize_snapshot(users[0], dashboard)
    snapshot.update(snapshot_id="fixture-snapshot-1", events={"items": []},
                    operations={"items": [], "complete": True, "start": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(), "end": observed})
    workspace.persist(users[0], snapshot)
    backend.app.dependency_overrides[backend.current_user] = lambda: users[0]
    client = TestClient(backend.app)
    try:
        yield {"user": users[0], "other": users[1], "snapshot": snapshot, "dashboard": dashboard, "client": client, "patch": monkeypatch}
    finally:
        client.close()
        backend.app.dependency_overrides.pop(backend.current_user, None)


def save(fixture, value=None):
    workspace.persist(fixture["user"], value or fixture["snapshot"])


def reviewed(identifier, provider="example.invalid"):
    now = datetime.now(timezone.utc)
    return {"id": identifier, "url": "https://" + provider + "/fixture", "review_id": "fixture-review",
            "published_at": (now - timedelta(hours=1)).isoformat(), "checked_at": now.isoformat(),
            "expires_at": (now + timedelta(days=1)).isoformat()}


def operation(identifier="op-1", *, account="owned-account-a", uid="aaa", quantity="2", payment="-16", at=None):
    return {"id": identifier, "account_id": account, "instrumentUid": uid, "title": "Synthetic operation",
            "date": at or now_iso(), "type": "OPERATION_TYPE_BUY", "category": "trades",
            "quantity": quantity, "payment": {"currency": "RUB", "value": payment}, "state": "OPERATION_STATE_EXECUTED", "source_ids": []}


def test_workspace_read_never_fans_out_or_runs_ai(fixture):
    def unexpected(*args, **kwargs):
        pytest.fail("A materialized GET must not make an external request")
    fixture["patch"].setattr(details.BrokerReader, "__enter__", unexpected)
    fixture["patch"].setattr(GuardedAIClient, "complete_json", unexpected)
    response = fixture["client"].get("/workspace")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == 1
    assert body["sections"]["capital"]["data"]["total"] == money("200", "RUB")
    assert body["capabilities"]["frame_network_requests"] is False
    assert body["capabilities"]["read_only_broker"] is True


def test_other_user_and_reconnected_broker_do_not_read_previous_snapshot(fixture):
    assert state.saved_snapshot(fixture["other"]) is None
    changed = {**dict(fixture["user"]), "tinvest_token_encrypted": b"new-connection"}
    assert state.saved_snapshot(changed) is None
    assert state.saved_snapshot(fixture["user"], "USD") is None


@pytest.mark.parametrize("bad", [True, 1.5, "NaN", "Infinity", "1e-999999999", "1e999999999", {"units": True}])
def test_money_rejects_ambiguous_or_unbounded_values(bad):
    assert decimal(bad) is None


def test_quotation_and_scenario_arithmetic_ignore_ambient_decimal_precision(fixture):
    with localcontext() as context:
        context.prec = 3
        assert decimal({"units": "123456789123", "nano": 123456789}) == Decimal("123456789123.123456789")
        result = state.scenario(state.Scenario(shocks=[{"axis": "instrument", "id": "aaa", "percent": "-12.3456789"}]), user=fixture["user"])
    assert decimal(result["estimated_change"]) == Decimal("-9.876543120")
    assert result["complete"] is True
    assert result["is_forecast"] is False


@pytest.mark.parametrize("shocks,error", [
    ([{"axis": "instrument", "id": "not-held", "percent": "-10"}], "scenario_selector_not_in_verified_positions"),
    ([{"axis": "all", "id": "all", "percent": "-10"}, {"axis": "sector", "id": "finance", "percent": "-20"}], "scenario_overlapping_shocks"),
])
def test_scenarios_reject_unknown_selectors_and_implicit_overlap(fixture, shocks, error):
    with pytest.raises(HTTPException) as failure:
        state.scenario(state.Scenario(shocks=shocks), user=fixture["user"])
    assert failure.value.detail == error


def test_unknown_sector_cannot_be_assumed_unaffected(fixture):
    fixture["snapshot"]["positions"][-1]["metadata"]["sector"] = None
    save(fixture)
    result = state.scenario(state.Scenario(shocks=[{"axis": "sector", "id": "finance", "percent": "-10"}]), user=fixture["user"])
    assert result["estimated_after"] is None
    assert result["uncovered_instrument_uids"] == ["bbb"]
    assert result["complete"] is False


def test_compared_scenarios_share_one_real_baseline_without_forecast(fixture):
    response = fixture["client"].post("/workspace/risks/scenarios/compare", json={"scenarios": [
        {"id": "A", "title": "User assumption A", "shocks": [{"axis": "all", "id": "all", "percent": "-10"}]},
        {"id": "B", "title": "User assumption B", "shocks": [{"axis": "all", "id": "all", "percent": "-20"}]},
    ]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["comparison_basis"] == "same_observed_snapshot_same_currency"
    assert {row["result"]["snapshot_id"] for row in result["scenarios"]} == {result["snapshot_id"]}
    assert [decimal(row["result"]["estimated_after"]) for row in result["scenarios"]] == [Decimal("180"), Decimal("160")]
    assert all(row["result"]["is_forecast"] is False for row in result["scenarios"])


def test_goal_uses_actual_same_currency_capital_and_reserved_amount(fixture):
    body = {"request_id": "goal-fixture-1", "title": "Reserve goal", "target": money("500", "RUB"), "reserve": money("50", "RUB")}
    first = fixture["client"].post("/workspace/goals", json=body)
    assert first.status_code == 200, first.text
    assert fixture["client"].post("/workspace/goals", json=body).json() == first.json()
    goal = fixture["client"].get("/workspace/goals").json()["items"][0]
    assert goal["current"] == money("150", "RUB")
    body.update(request_id="goal-fixture-2", reserve=money("50", "USD"))
    assert fixture["client"].post("/workspace/goals", json=body).status_code == 422


def activate(fixture, value=None, *, expected=0, request="strategy-confirm-1"):
    preview = state.preview_strategy(state.StrategyPreview(expected_version=expected, config=value or config()), user=fixture["user"])
    payload = state.StrategyConfirm(preview_id=preview["preview_id"], expected_version=expected, request_id=request)
    return preview, payload, state.confirm_strategy(payload, user=fixture["user"])


def test_strategy_confirmation_is_cas_idempotent_and_applied_to_monitor(fixture):
    first = state.preview_strategy(state.StrategyPreview(expected_version=0, config=config(position=30)), user=fixture["user"])
    second = state.preview_strategy(state.StrategyPreview(expected_version=0, config=config(position=40)), user=fixture["user"])
    one = state.StrategyConfirm(preview_id=first["preview_id"], expected_version=0, request_id="strategy-cas-one")
    result = state.confirm_strategy(one, user=fixture["user"])
    assert result["active"]["version"] == 1
    assert state.confirm_strategy(one, user=fixture["user"]) == result
    with pytest.raises(HTTPException) as failure:
        state.confirm_strategy(state.StrategyConfirm(preview_id=second["preview_id"], expected_version=0, request_id="strategy-cas-two"), user=fixture["user"])
    assert failure.value.detail == "strategy_version_changed"
    assert ai.get_profile(int(fixture["user"]["id"]))["max_position_percent"] == 30
    assert any(row["breached"] for row in state.risk_data(fixture["user"])["concentrations"])
    assert first["impact"]["execution_state"] == "not_executed"


def test_strategy_preview_detects_snapshot_change_and_rollback_creates_new_version(fixture):
    _, _, first = activate(fixture)
    preview = state.preview_strategy(state.StrategyPreview(expected_version=1, config=config(position=50)), user=fixture["user"])
    fixture["snapshot"]["snapshot_id"] = "changed-after-preview"
    save(fixture)
    with pytest.raises(HTTPException) as failure:
        state.confirm_strategy(state.StrategyConfirm(preview_id=preview["preview_id"], expected_version=1, request_id="strategy-stale-preview"), user=fixture["user"])
    assert failure.value.detail == "strategy_snapshot_changed"
    _, _, second = activate(fixture, config(position=50), expected=1, request="strategy-second-confirm")
    rollback = state.preview_strategy(state.StrategyPreview(expected_version=2, rollback_to_version=1), user=fixture["user"])
    third = state.confirm_strategy(state.StrategyConfirm(preview_id=rollback["preview_id"], expected_version=2, request_id="strategy-rollback-confirm"), user=fixture["user"])
    assert third["active"]["config"] == first["active"]["config"]
    assert third["active"]["version"] == 3
    assert len(state.strategy_data(int(fixture["user"]["id"]))["history"]) == 3


def test_missing_risk_basis_is_not_recorded_as_resolved(fixture):
    activate(fixture, config(position=30))
    save(fixture)
    fixture["snapshot"]["positions"][0]["value"] = None
    fixture["snapshot"]["snapshot_id"] = "missing-risk-value"
    save(fixture)
    history = state.risk_events(user=fixture["user"])["items"]
    assert any(item["kind"] == "risk_data_stale" for item in history)
    assert not any(item["kind"] == "risk_limit_resolved" and "aaa" in item.get("instrument_uids", []) for item in history)


def test_verified_issuer_group_identity_is_used_without_ticker_guessing(fixture):
    payload = {"instrument_uid": "aaa", "issuer_id": "issuer-fixture", "issuer_name": "Fixture issuer",
               "group_id": "group-fixture", "group_name": "Fixture group", "source": reviewed("identity-fixture")}
    research_store.import_record(backend.connect, kind="issuer_identity", subject="aaa", payload=payload)
    fixture["snapshot"]["positions"][0]["verified_identity"] = payload
    data = state.exposure_data(fixture["snapshot"])
    groups = next(axis for axis in data["axes"] if axis["id"] == "group")
    assert groups["items"][0]["id"] == "group-fixture"
    assert groups["unknown_count"] == 1
    assert groups["complete"] is False


def test_notification_quiet_hours_and_read_ack_without_claim(fixture):
    prefs = {**notifications.DEFAULTS, "timezone": "Europe/Moscow"}
    at = int(datetime(2026, 10, 12, 20, 30, tzinfo=timezone.utc).timestamp())
    status, due, why = notifications.eligibility(prefs, "risk", at)
    assert status == "pending" and why == "quiet_hours"
    assert datetime.fromtimestamp(due, timezone.utc).isoformat() == "2026-10-13T05:00:00+00:00"
    with transaction(backend.connect) as db:
        notifications.enqueue_in(db, int(fixture["user"]["id"]), kind="risk", title="Fixture event", body="Source observed", event_id="fixture-event")
    item = notifications.events(user=fixture["user"])["items"][0]
    with pytest.raises(HTTPException):
        notifications.acknowledge(item["id"], notifications.Ack(state="presented"), user=fixture["user"])
    ack = notifications.acknowledge(item["id"], notifications.Ack(state="read"), user=fixture["user"])
    assert ack["state"] == "read"


def test_notification_preferences_are_applied_to_monitor_and_preview_sends_nothing(fixture):
    payload = notifications.PreferencesWrite(expected_version=0, enabled=False)
    saved = notifications.update_preferences(payload, user=fixture["user"])
    assert saved["applied"] and saved["delivery_channel"] == "app_poll"
    assert ai.get_profile(int(fixture["user"]["id"]))["notify_critical"] is False
    with transaction(backend.connect) as db:
        notifications.enqueue_in(db, int(fixture["user"]["id"]), kind="risk", title="Fixture", body="Actual test event", event_id="preview-event")
    before = notifications.events(user=fixture["user"])
    notifications.preview(notifications.Preview(preferences=notifications.Preferences(enabled=True)), user=fixture["user"])
    assert notifications.events(user=fixture["user"]) == before
    activate(fixture)
    assert ai.get_profile(int(fixture["user"]["id"]))["notify_briefs"] is False


def test_request_id_conflict_recovery_and_user_isolation(fixture):
    user_id = int(fixture["user"]["id"])
    first = jobs.enqueue(user_id, "durable-request-1", "refresh", {"currency": "RUB"})
    assert jobs.enqueue(user_id, "durable-request-1", "refresh", {"currency": "RUB"}) == first
    assert jobs.job_by_request("durable-request-1", user=fixture["user"])["job_id"] == first["job_id"]
    with pytest.raises(HTTPException):
        jobs.enqueue(user_id, "durable-request-1", "refresh", {"currency": "USD"})
    with pytest.raises(HTTPException):
        jobs.get_job(int(fixture["other"]["id"]), first["job_id"])


def test_checkpoint_retry_and_queue_selection_do_not_starve_other_users(fixture):
    job = jobs.enqueue(int(fixture["user"]["id"]), "checkpoint-request", "refresh", {})
    def fail_once(user, payload, checkpoint, progress):
        checkpoint["source_stage"] = "retained"
        progress("capital_collected", checkpoint)
        raise HTTPException(503, "fixture_retryable_source")
    fixture["patch"].setattr(workspace, "collect", fail_once)
    jobs.run_job(job["job_id"])
    retry = jobs.retry(job["job_id"], state.RequestId(request_id="checkpoint-retry"), BackgroundTasks(), user=fixture["user"])
    def resume(user, payload, checkpoint, progress):
        assert checkpoint["source_stage"] == "retained"
        return {"snapshot_id": "resumed-with-source-checkpoint"}
    fixture["patch"].setattr(workspace, "collect", resume)
    jobs.run_job(retry["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), retry["job_id"])["state"] == "completed"
    first = jobs.enqueue(int(fixture["user"]["id"]), "running-user-job", "refresh", {})
    jobs._claim(first["job_id"])
    jobs.enqueue(int(fixture["user"]["id"]), "blocked-user-job", "refresh", {})
    other = jobs.enqueue(int(fixture["other"]["id"]), "other-user-job", "refresh", {})
    assert jobs._claim()["id"] == other["job_id"]


def test_cancelled_worker_cannot_commit_and_paid_expiry_cannot_retry(fixture):
    identifier = jobs.enqueue(int(fixture["user"]["id"]), "cancel-workspace", "refresh", {})["job_id"]
    claimed = jobs._claim(identifier)
    token = jobs.CURRENT_WORKSPACE_JOB.set((identifier, claimed["owner"], int(fixture["user"]["id"])))
    try:
        assert jobs.cancel(identifier, user=fixture["user"])["state"] == "cancel_requested"
        with transaction(backend.connect) as db, pytest.raises(jobs.JobStopped):
            jobs.assert_current_in(db)
    finally:
        jobs.CURRENT_WORKSPACE_JOB.reset(token)
    with transaction(backend.connect) as db:
        db.execute("UPDATE workspace_jobs SET paid_started=1,expires_at=0 WHERE id=?", (identifier,))
        jobs._expire(db, int(time.time()))
    result = jobs.get_job(int(fixture["user"]["id"]), identifier)
    assert result["state"] == "uncertain" and not result["can_retry"]
    with pytest.raises(HTTPException):
        jobs.retry(identifier, state.RequestId(request_id="cannot-repeat-paid"), BackgroundTasks(), user=fixture["user"])


def seed_context(fixture):
    snapshot = fixture["snapshot"]
    old = datetime.fromisoformat(snapshot["as_of"]) - timedelta(hours=1)
    ref = source("GetOperationsByCursor", "owned-account-a", snapshot["as_of"])
    item = operation(at=old.isoformat())
    item["source_ids"] = [ref["id"]]
    snapshot["operations"]["items"] = [item, operation("other-op", account="owned-account-b", uid="bbb", at=old.isoformat())]
    snapshot["sources"].append(ref)
    snapshot["events"]["items"] = [{"id": "event-a", "title": "A fixture event", "instrument_uids": ["aaa"], "occurred_at": old.isoformat(), "source_ids": [ref["id"]]},
                                        {"id": "event-b", "title": "B fixture event", "instrument_uids": ["bbb"], "occurred_at": old.isoformat(), "source_ids": [ref["id"]]}]
    save(fixture)
    with transaction(backend.connect) as db:
        db.execute("INSERT INTO portfolio_value_history VALUES (?,?,?,?,?,?,?)", (int(fixture["user"]["id"]), "owned-account-a", "RUB", "hour", int(old.timestamp()) // 3600 * 3600, old.isoformat(), "95.000000001"))


def test_chat_scope_sources_real_history_and_allowlisted_navigation(fixture):
    seed_context(fixture)
    packet = chat.fact_packet(fixture["user"], {"mode": "instrument", "instrument_uid": "aaa", "account_id": "owned-account-a"})
    assert packet["coverage"]["selection_is_complete"] is True
    assert packet["coverage"]["scoped_positions"] == 1
    assert packet["coverage"]["total_positions"] == 3
    assert packet["coverage"]["operations"]["scoped_count"] == 1
    assert packet["coverage"]["events"]["scoped_count"] == 1
    real_bar = next(fact for fact in packet["facts"] if fact["id"].startswith("history:"))
    assert real_bar["value"]["value"] == money("95.000000001", "RUB")
    target = next(item for item in packet["allowed_highlights"] if item["section"] == "history")
    result = chat.validate_response({"answer": "Fixture explanation", "claims": [{"text": "Observed", "fact_ids": [real_bar["id"]]}],
                                     "highlights": [{**target, "account_id": "malicious-other-account"}]}, packet)
    assert result["highlights"][0]["account_id"] == "owned-account-a"
    assert result["sources"] and result["coverage"]["history"]["included_observations"] == 1
    messages, _ = chat.model_messages(fixture["user"], "Explain", {"mode": "portfolio", "account_id": "owned-account-a"})
    assert "owned-account-a" not in json.dumps(messages)
    with pytest.raises(GuardError):
        chat.validate_response({"answer": "Unsupported claim", "claims": [{"text": "False", "fact_ids": ["invented"]}]}, packet)


def test_scoped_chat_rejects_other_accounts(fixture):
    with pytest.raises(HTTPException) as failure:
        chat.fact_packet(fixture["user"], {"mode": "portfolio", "account_id": "not-owned"})
    assert failure.value.detail == "chat_account_not_in_workspace"


def test_chat_cursor_paginates_identical_timestamps_and_is_bound_to_user_thread(fixture):
    user_id, at = int(fixture["user"]["id"]), now_iso()
    thread = chat.create_thread(chat.ThreadCreate(request_id="pagination-thread"), user=fixture["user"])["thread_id"]
    with transaction(backend.connect) as db:
        for index in range(205):
            identifier = f"fixture-message-{index:04d}"
            db.execute("INSERT INTO workspace_chat_messages VALUES (?,?,?,?,?,?,?,?,?)", (identifier, thread, user_id, "user",
                "Synthetic pagination fixture", at, identifier, identifier, "{}"))
    first = chat.messages(thread, user=fixture["user"])
    second = chat.messages(thread, first["next_before"], user=fixture["user"])
    third = chat.messages(thread, second["next_before"], user=fixture["user"])
    all_ids = [row["id"] for page in (first, second, third) for row in page["items"]]
    assert len(all_ids) == 205 and len(set(all_ids)) == 205
    assert third["has_more"] is False
    other_thread = chat.create_thread(chat.ThreadCreate(request_id="other-pagination-thread"), user=fixture["other"])["thread_id"]
    with pytest.raises(HTTPException) as failure:
        chat.messages(other_thread, first["next_before"], user=fixture["other"])
    assert failure.value.status_code == 422


def model_fixture(fixture, *, timeout=False):
    requests = []
    def handle(request):
        requests.append(request)
        if timeout:
            raise httpx.ReadTimeout("synthetic ambiguity", request=request)
        reply = model_response()
        reply["choices"][0]["message"]["content"] = json.dumps({"answer": "Observed balance", "claims": [{"text": "Observed balance", "fact_ids": ["capital:total"]}], "highlights": [], "uncertainties": [], "actions": [{"type": "open_sources", "id": ""}]})
        return httpx.Response(200, json=reply)
    transport = httpx.MockTransport(handle)
    fixture["patch"].setattr(chat, "GuardedAIClient", lambda user, connect, **kwargs: GuardedAIClient(user, connect, transport=transport, env=environment(), **kwargs))
    return requests


def test_real_guarded_chat_is_charged_once_and_recovered_by_request(fixture):
    calls = model_fixture(fixture)
    thread = fixture["client"].post("/workspace/chat/threads", json={"request_id": "thread-for-fixture", "title": "Fixture"}).json()["thread_id"]
    endpoint = "/workspace/chat/threads/" + thread + "/messages"
    body = {"request_id": "chat-stable-request", "text": "Explain the balance", "context": {"mode": "portfolio"}, "tier": "fast"}
    first = fixture["client"].post(endpoint, json=body)
    assert first.status_code == 202, first.text
    identifier = first.json()["job_id"]
    recovered = fixture["client"].get("/workspace/jobs/by-request/chat-stable-request").json()
    assert recovered["job_id"] == identifier and recovered["state"] == "completed", recovered
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == identifier
    assert len(calls) == 1
    response = fixture["client"].get(endpoint).json()["items"][-1]
    assert response["role"] == "assistant" and response["sources"]
    assert response["claims"][0]["fact_ids"] == ["capital:total"]
    assert MoneyLedger(backend.connect).user_summary(int(fixture["user"]["id"]))["unresolved_attempts"] == 0
    assert fixture["client"].post(endpoint, json={**body, "text": "Changed request payload"}).status_code == 409


def test_ambiguous_chat_timeout_cannot_repeat_or_fake_an_answer(fixture):
    calls = model_fixture(fixture, timeout=True)
    thread = chat.create_thread(chat.ThreadCreate(request_id="timeout-thread-id"), user=fixture["user"])["thread_id"]
    endpoint = "/workspace/chat/threads/" + thread + "/messages"
    body = {"request_id": "timeout-chat-request", "text": "Explain", "tier": "fast"}
    job = fixture["client"].post(endpoint, json=body).json()
    outcome = jobs.get_job(int(fixture["user"]["id"]), job["job_id"])
    assert outcome["state"] == "uncertain" and outcome["can_retry"] is False
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == job["job_id"]
    assert len(calls) == 1
    assert [r["role"] for r in fixture["client"].get(endpoint).json()["items"]] == ["user"]
    assert MoneyLedger(backend.connect).user_summary(int(fixture["user"]["id"]))["unresolved_attempts"] == 1


def test_guarded_cancellation_before_send_refunds_known_unsent_only(fixture):
    calls = []
    def stop():
        raise jobs.JobStopped()
    def transport(request):
        calls.append(request)
        return httpx.Response(200, json=model_response())
    client = GuardedAIClient(int(fixture["user"]["id"]), backend.connect, env=environment(), transport=httpx.MockTransport(transport),
                             attempt_id="fixture-before-send", before_send=stop)
    with pytest.raises(jobs.JobStopped):
        client.complete_json(tier=ai.AnalysisTier.FAST, messages=[{"role": "user", "content": "Fixture"}], max_output_tokens=10)
    assert not calls
    summary = MoneyLedger(backend.connect).user_summary(int(fixture["user"]["id"]))
    assert summary["unresolved_attempts"] == 0 and summary["estimated_and_reserved_rub"] == "0"


def test_actual_ohlc_units_missing_intervals_and_conflict_validation():
    observed = now_iso()
    at = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    row = {"time": at, "open": "100.123456789", "high": "102", "low": "99", "close": "101", "volume": "7", "isComplete": False}
    values = market.normalize_candles([row, row], observed_at=observed, source_id="fixture-source")
    assert len(values) == 1 and values[0]["open"] == "100.123456789"
    assert values[0]["is_complete"] is False and values[0]["volume_lots"] == "7"
    assert market.quote_unit({"instrumentType": "bond", "currency": "rub"})[0] == "percent_of_nominal"
    assert market.quote_unit({"instrumentType": "futures", "currency": "rub"})[2] is None
    with pytest.raises(HTTPException):
        market.normalize_candles([row, {**row, "close": "100"}], observed_at=observed, source_id="fixture-source")
    with pytest.raises(HTTPException):
        market.normalize_candles([{**row, "low": "104"}], observed_at=observed, source_id="fixture-source")


def test_one_time_login_exchange_is_atomic_and_legacy_sessions_survive(fixture):
    user_id, now = int(fixture["user"]["id"]), int(time.time())
    with transaction(backend.connect) as db:
        db.execute("INSERT INTO sessions VALUES (?,?,?)", (backend.hash_token("old-session"), user_id, now + 10000))
        db.execute("INSERT INTO login_codes VALUES (?,?,?,0)", (backend.hash_token("fixture-login-code"), user_id, now + 300))
    def exchange(_):
        try:
            return backend.exchange_session(backend.SessionExchange(code="fixture-login-code", device_name="Fixture Android"))
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(exchange, range(4)))
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert outcomes.count(401) == 3
    listing = devices.devices(user=fixture["user"], authorization="Bearer old-session")
    assert len(listing["items"]) == 2
    assert listing["current_device_id"] is not None
    devices.revoke(listing["current_device_id"], user=fixture["other"])
    assert len(devices.devices(user=fixture["user"], authorization="Bearer old-session")["items"]) == 2
    devices.revoke(listing["current_device_id"], user=fixture["user"])
    with closing(backend.connect()) as db:
        assert db.execute("SELECT 1 FROM sessions WHERE token_hash=?", (backend.hash_token("old-session"),)).fetchone() is None


def test_structured_fact_versions_compare_actual_values_and_keep_unchanged(fixture):
    user_id = int(fixture["user"]["id"])
    with transaction(backend.connect) as db:
        # Capture retains only existing real card identities. These cards are
        # fixture records in the isolated database, never a production fallback.
        for identifier in ("before-card", "after-card"):
            db.execute("INSERT INTO insight_cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (identifier, user_id, "portfolio", "info", "Fixture", "Fixture", "[]", "[]", "[]", None, 0, int(time.time())))
        analysis.capture_in(db, user_id, "before-card")
    fixture["snapshot"]["positions"][0]["value"] = money("81", "RUB")
    fixture["snapshot"]["snapshot_id"] = "changed-fact-value"
    save(fixture)
    with transaction(backend.connect) as db:
        analysis.capture_in(db, user_id, "after-card")
    result = analysis.comparison(user_id, "after-card", "before-card", limit=100)
    assert result["counts"]["changed"] == 1
    assert result["counts"]["unchanged"] == 3
    changed = next(row for row in result["items"] if row["state"] == "changed")
    assert changed["before"]["value"]["value"] == money("80", "RUB")
    assert changed["after"]["value"]["value"] == money("81", "RUB")
    assert analysis.comparison(user_id, "legacy-card", "before-card")["available"] is False


def test_skipped_monitor_check_is_exposed_without_a_paid_analysis_record(fixture):
    monitor.record_check(int(fixture["user"]["id"]), datetime.now(timezone.utc), status="skipped", reason="unchanged", tier="none")
    result = workspace.ai_data(fixture["user"])
    assert result["last_check"]["state"] == "skipped"
    assert result["last_run"] is None


def test_risk_check_freezes_owned_evidence_and_survives_a_closed_position(fixture):
    activate(fixture, config(position=30))
    save(fixture)
    risk = next(item for item in state.risk_events(user=fixture["user"])["items"] if "aaa" in item["instrument_uids"])
    payload = state.CheckCreate(request_id="risk-check-frozen-evidence", title="Verify the recorded risk",
                                instrument_uids=["aaa"], event_id=risk["id"])
    first = state.create_check(payload, user=fixture["user"])
    assert first["basis"]["positions"][0]["value"] == money("80", "RUB")
    assert first["basis"]["confirmed_strategy"]["version"] == 1
    assert first["sources"] and first["steps"][0]["source_ids"]
    fixture["snapshot"]["positions"] = [p for p in fixture["snapshot"]["positions"] if p["instrument_uid"] != "aaa"]
    save(fixture)
    assert state.create_check(payload, user=fixture["user"]) == first
    other = state.create_check(payload.model_copy(update={"request_id": "closed-risk-new-check"}), user=fixture["user"])
    assert other["basis"]["closed_instrument_uids"] == ["aaa"]
    assert other["basis"]["event"]["id"] == risk["id"]
    with pytest.raises(HTTPException) as failure:
        state.create_check(payload, user=fixture["other"])
    assert failure.value.status_code == 404


def test_monitor_trigger_uses_previous_real_observation_and_preserves_slot_decision(fixture):
    from backend.ai_policy import AnalysisSignals
    previous = deepcopy(fixture["dashboard"])
    previous_row = {"digest": "previous-real-fixture-digest", "created_at": int(time.time()) - 600}
    current = deepcopy(previous)
    current["accounts"][0]["positions"][0]["quantity"] = "11"
    now = datetime.now(timezone.utc).replace(hour=6, minute=10, second=0, microsecond=0)
    fixture["snapshot"]["calendar"] = {"data": {"exchanges": [{"days": [{"date": now.date().isoformat(), "isTradingDay": True}]}]}}
    # Reusing the already materialized calendar is intentional in this fixture;
    # a real monitor calls the actual read-only calendar adapter.
    save(fixture)
    fixture["patch"].setattr(market, "calendar", lambda user: {"as_of": now.isoformat(), "source": source("TradingSchedules", "MOEX", now.isoformat()),
        "exchanges": [{"days": [{"date": now.date().isoformat(), "isTradingDay": True}]}]})
    observation = monitor.ingest(fixture["user"], current, now)
    trigger = monitor.trigger_evidence(fixture["user"], current, previous, previous_row, observation,
        AnalysisSignals(portfolio_changed=True, digest_changed=True, morning_due=True), now)
    change = next(row for row in trigger["observations"] if row["kind"] == "position_quantity")
    assert change["before"]["quantity"] == "10" and change["after"]["quantity"] == "11"
    assert trigger["previous_snapshot_id"] == previous_row["digest"]
    assert set(change["source_ids"]).issubset({ref["id"] for ref in trigger["sources"]})
    user_id = int(fixture["user"]["id"])
    monitor.record_check(user_id, now, status="completed", reason="portfolio_changed", tier="standard", card_id="fixture-completed-card", trigger=trigger)
    monitor.record_check(user_id, now + timedelta(minutes=10), status="skipped", reason="cooldown", tier="none", trigger=trigger)
    result = workspace.ai_data(fixture["user"])
    assert result["last_check"]["reason"] == "cooldown"
    assert result["slot_checks"][0]["card_id"] == "fixture-completed-card"
    assert len(result["check_history"]) == 2
    detail = monitor.check_detail(now.isoformat(), user=fixture["user"])
    assert detail["trigger"]["observations"] == trigger["observations"]
    with pytest.raises(HTTPException) as failure:
        monitor.check_detail(now.isoformat(), user=fixture["other"])
    assert failure.value.status_code == 404


def test_broker_fundamental_zero_is_absent_while_negative_value_is_real(fixture):
    class Reader:
        def __init__(self, user):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    fixture["patch"].setattr(details, "BrokerReader", Reader)
    raw = {"assetUid": "asset-aaa", "currency": "rub", "netIncomeTtm": -12.5, "revenueTtm": 0, "freeCashFlowTtm": -0.0,
           "fiscalPeriodEndDate": "2026-06-30T00:00:00Z"}
    fixture["patch"].setattr(market, "broker_read", lambda *args: {"fundamentals": [raw]})
    result = market.metric_section(fixture["user"], "aaa", {"assetUid": "asset-aaa"})
    values = {row["id"]: row for row in result["data"]["items"]}
    assert values["revenueTtm"]["value"] is None
    assert values["freeCashFlowTtm"]["missing_reason"] == "broker_zero_means_unavailable"
    assert values["netIncomeTtm"]["value"] == "-12.5"
    assert portfolio_research._broker_metric(raw, "revenueTtm") is None
    assert portfolio_research._broker_metric(raw, "netIncomeTtm") == -12.5


def test_report_calendar_uses_one_instrument_and_never_infers_publication(fixture):
    class Reader:
        def __init__(self, user):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, method, body):
            assert method == "dividends"
            return {"dividends": []}
    when = datetime.now(timezone.utc) - timedelta(days=2)
    def read(reader, method, body):
        assert method == "reports" and body["instrumentId"] == "aaa" and "instrumentIds" not in body
        return {"events": [{"instrumentId": "aaa", "reportDate": when.isoformat(), "periodYear": 2026,
                             "periodNum": 2, "periodType": "PERIOD_TYPE_QUARTER", "createdAt": when.isoformat()},
                            {"instrumentId": "not-requested", "reportDate": when.isoformat()}]}
    fixture["patch"].setattr(details, "BrokerReader", Reader)
    fixture["patch"].setattr(market, "broker_read", read)
    result = market.instrument_events(fixture["user"], "aaa", {"instrumentType": "share"}, when - timedelta(days=1), when + timedelta(days=3))
    assert len(result["data"]["items"]) == 1
    event = result["data"]["items"][0]
    assert event["status"] == "scheduled" and event["publication_confirmed"] is False
    assert event["period_num"] == 2 and event["period_year"] == 2026
    assert result["state"] == "partial"


def test_news_does_not_infer_original_or_same_event_from_equal_headlines(fixture):
    when = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    first = {"id": "101", "source": "Agency A", "title": "Same headline", "content": "Different first fact", "ts": when}
    second = {"id": "102", "source": "Agency B", "title": "Same headline", "content": "Different second fact", "ts": when}
    ref = source("News", "market-news", now_iso())
    result, errors = news.group_news([first, first, second], uid=None, ref=ref)
    assert not errors and len(result) == 2
    assert all(row["event_identity_verified"] is False and row["primary_sources"] == [] for row in result)
    assert all(row["sources"][0]["publication_role"] == "unknown" for row in result)
    result, errors = news.group_news([first, {**second, "id": "101"}], uid=None, ref=ref)
    assert result == [] and "news_id_conflicting_observations" in errors


def test_reviewed_news_links_bind_exact_observations_and_expose_original_repost(fixture):
    when = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    first = {"id": "201", "source": "Issuer", "title": "Published report", "content": "Actual fixture source", "ts": when}
    second = {"id": "202", "source": "Agency", "title": "Report coverage", "content": "Actual fixture repost", "ts": when}
    primary = reviewed("primary-news-source", "issuer.example")
    for raw, role, proof in ((first, "primary", primary), (second, "repost", reviewed("secondary-news-source", "agency.example"))):
        payload = {"broker_news_id": raw["id"], "news_sha256": news.observation_fingerprint(raw), "event_id": "fixture-report-event",
                   "publication_role": role, "primary_source": primary, "source": proof}
        research_store.import_record(backend.connect, kind="news_event", subject=raw["id"], payload=payload)
    result, errors = news.group_news([first, second], uid=None, ref=source("News", "market-news", now_iso()))
    assert not errors and len(result) == 1 and result[0]["event_identity_verified"]
    assert {row["publication_role"] for row in result[0]["sources"]} == {"primary", "repost"}
    assert result[0]["primary_sources"][0]["url"] == primary["url"]
    changed, errors = news.group_news([first, {**second, "content": "A corrected unrelated statement"}], uid=None,
                                     ref=source("News", "market-news", now_iso()))
    assert len(changed) == 2
    assert next(row for row in changed if row["id"] != "event:fixture-report-event")["sources"][0]["publication_role"] == "unknown"


def test_manual_broker_handoff_does_not_claim_execution_and_requires_operation_association(fixture):
    plan = plans.create(plans.PlanCreate(request_id="manual-plan-create", title="Fixture manual plan", instrument_uid="aaa",
        account_id="owned-account-a", side="buy", quantity="2", strategy_version=0), user=fixture["user"])
    assert plan["state"] == "calculated" and plan["executed_quantity"] == "0"
    opened = plans.opened(plan["id"], state.RequestId(request_id="manual-plan-open"), user=fixture["user"])
    assert opened["execution_state"] == "not_confirmed"
    raw = operation(at=now_iso())
    class Reader:
        def __init__(self, user):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def account(self, account_id):
            assert account_id == "owned-account-a"
        def read(self, method, payload):
            assert method in {"portfolio", "operations"}
            return {"positions": [{"instrumentUid": "aaa", "quantity": "12"}]} if method == "portfolio" else {"items": [raw], "hasNext": False}
    fixture["patch"].setattr(details, "BrokerReader", Reader)
    pending = plans.reconcile_plan(fixture["user"], {"plan_id": plan["id"], "operation_ids": []}, lambda *args, **kwargs: None)
    assert pending["state"] == "pending" and pending["executed_quantity"] == "0"
    assert len(pending["candidate_operations"]) == 1
    done = plans.reconcile_plan(fixture["user"], {"plan_id": plan["id"], "operation_ids": [raw["id"]]}, lambda *args, **kwargs: None)
    assert done["state"] == "done" and done["executed_quantity"] == "2"
    assert done["automatic_order_execution"] is False
    raw["quantity"] = "1"
    corrected = plans.reconcile_plan(fixture["user"], {"plan_id": plan["id"], "operation_ids": []}, lambda *args, **kwargs: None)
    assert corrected["state"] == "partial" and corrected["executed_quantity"] == "1"


def test_reviewed_rating_change_updates_risk_history_sources_and_coverage(fixture):
    identity = {"instrument_uid": "aaa", "issuer_id": "fixture-rated-issuer", "source": reviewed("rated-identity")}
    research_store.import_record(backend.connect, kind="issuer_identity", subject="aaa", payload=identity)
    fixture["snapshot"]["positions"][0]["verified_identity"] = identity
    payload = {"agency": "ACRA", "scale": "RU_NATIONAL_LONG_TERM", "grade": "A(RU)", "subject_kind": "issuer",
               "subject_id": "fixture-rated-issuer", "status": "active", "outlook": "stable", "source": reviewed("rating-first", "acra-ratings.ru")}
    research_store.import_record(backend.connect, kind="rating", subject="fixture-rated-issuer", payload=payload)
    save(fixture)
    first = deepcopy(fixture["snapshot"]["rating_observations"]["aaa"])
    payload = {**payload, "grade": "BBB-(RU)", "source": reviewed("rating-second", "acra-ratings.ru")}
    research_store.import_record(backend.connect, kind="rating", subject="fixture-rated-issuer", payload=payload)
    save(fixture)
    assert credit.critical(fixture["snapshot"]["rating_observations"]["aaa"], first)
    events = state.risk_events(user=fixture["user"])["items"]
    changed = next(item for item in events if item["kind"] == "risk_rating_changed")
    assert changed["details"]["before"]["items"][0]["grade"] == "A(RU)"
    assert changed["details"]["after"]["items"][0]["grade"] == "BBB-(RU)"
    assert "rating-second" in changed["source_ids"] and changed["sources"]
    coverage = next(row for row in state.risk_data(fixture["user"])["coverage"] if row["direction"] == "ratings")
    assert coverage["known_positions"] == 1 and coverage["state"] == "partial"


@pytest.mark.parametrize("agency,grade,domain", [("NKR", "BBB-.ru", "ratings.ru"), ("NRA", "BBB-|ru|", "ra-national.ru")])
def test_supported_national_rating_notations_are_kept_per_agency(agency, grade, domain):
    from backend.credit_evidence import Rating, Source
    rating = Rating(agency=agency, scale="RU_NATIONAL_LONG_TERM", grade=grade, subject_kind="issue", subject_id="fixture-bond",
                    status="active", outlook="stable", source=Source(**reviewed("fixture-" + agency, domain)))
    assert rating.level() == 9
    assert rating.bucket().startswith(agency + ":")
