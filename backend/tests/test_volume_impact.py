"""Owned event interpretation over the real chat/ledger, using HTTP fixtures."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest
from fastapi import HTTPException

from backend.tests.test_volume_workspace import fixture, reviewed
from backend import volume_chat as chat, volume_impact as impact, volume_jobs as jobs
from backend import volume_workspace as workspace, volume_market as market, research_store
from backend import app as backend, volume_state as state, portfolio_details as details
from backend.ai_budget import MoneyLedger
from backend.ai_guarded_client import GuardError, GuardedAIClient
from backend.volume_contract import source, now_iso
from backend.tests.test_ai_controls import environment, model_response


def event_fixture(fixture, *, identity=True, stored=True):
    observed = now_iso()
    ref = source("News", "market-news", observed, ttl=300)
    event = {"id": "news:impact-fixture", "title": "Synthetic fixture: issuer reports production interruption",
             "summary": "A synthetic event used only to validate the evidence path.",
             "published_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
             "instrument_uids": ["aaa"], "source_ids": [ref["id"]], "primary_sources": [],
             "event_identity_verified": False, "relationship": "broker_link"}
    if identity:
        research_store.import_record(backend.connect, kind="issuer_identity", subject="aaa",
            payload={"instrument_uid": "aaa", "issuer_id": "fixture-issuer", "issuer_name": "Reviewed fixture issuer",
                     "source": reviewed("fixture-identity")})
    if stored:
        snapshot = deepcopy(fixture["snapshot"])
        snapshot["events"]["items"] = [event]
        snapshot["sources"].append(ref)
        workspace.persist(fixture["user"], snapshot)
    return event, ref


def context(event):
    return {"mode": "instrument", "instrument_uid": "aaa", "event_id": event["id"]}


def channel(request):
    refs = [request["event_fact_id"], request["position_fact_ids"][0]]
    if request["company_fact_id"]:
        refs.append(request["company_fact_id"])
    return {"mechanism": "Если остановка продолжится, она может ограничить выпуск продукции эмитента и повысить неопределённость для держателя бумаги.",
            "direction": "negative", "horizon": "unclear", "assumptions": ["Остановка затрагивает существенную часть производства."],
            "uncertainty": "Продолжительность и финансовая значимость в доступных фактах не установлены.", "fact_ids": refs}


def packet(fixture, event):
    return chat.fact_packet(fixture["user"], context(event))


def test_event_hypothesis_binds_owned_event_company_positions_and_actual_sources(fixture):
    event, ref = event_fixture(fixture)
    value = packet(fixture, event)
    result = impact.validate({"channels": [channel(value["impact_context"]["model_request"])]}, value)
    assert result["kind"] == "hypothesis"
    assert result["computed_financial_impact"] is None
    assert result["event"]["id"] == event["id"]
    assert result["companies"][0]["issuer_id"] == "fixture-issuer"
    assert result["companies"][0]["identity_state"] == "verified"
    assert {row["account_id"] for row in result["positions"]} == {"owned-account-a"}
    assert {row["instrument_uid"] for row in result["positions"]} == {"aaa"}
    assert ref["id"] in {row["id"] for row in result["sources"]}
    assert {ref for row in result["channels"] for ref in row["source_ids"]}.issubset({row["id"] for row in result["sources"]})
    messages, _ = chat.model_messages(fixture["user"], "Объясни возможный канал влияния", context(event))
    serialized = json.dumps(messages, ensure_ascii=False)
    assert "owned-account-a" not in serialized
    assert "impact_request" in serialized
    assert impact.MODEL_INSTRUCTION in messages[0]["content"]


def test_event_hypothesis_reuses_dossier_cache_and_rejects_foreign_scope_before_loading(fixture):
    event, ref = event_fixture(fixture, stored=False)
    loaded, keys, cache = [], [], {}
    def read_news(user):
        loaded.append(user["id"])
        return {"data": {"items": [event]}, "sources": [ref]}
    def cached(key, ttl, loader):
        keys.append(key)
        if key not in cache:
            cache[key] = loader()
        return deepcopy(cache[key])
    fixture["patch"].setattr(market, "load_news", read_news)
    fixture["patch"].setattr(details, "cached", cached)
    assert packet(fixture, event)["impact_context"]["event"]["id"] == event["id"]
    assert packet(fixture, event)["impact_context"]["event"]["id"] == event["id"]
    assert loaded == [fixture["user"]["id"]]
    assert all(key == ("workspace-news", *details.identity(fixture["user"])) for key in keys)
    prepared_argument_1 = {**context(event), "account_id": "not-owned"}
    with pytest.raises(HTTPException) as failure:
        chat.fact_packet(fixture["user"], prepared_argument_1)
    assert failure.value.status_code == 404
    assert len(loaded) == 1
    prepared_argument_1 = {**context(event), "instrument_uid": "bbb"}
    with pytest.raises(HTTPException) as failure:
        chat.fact_packet(fixture["user"], prepared_argument_1)
    assert failure.value.detail == "chat_event_not_linked_to_owned_instrument"


@pytest.mark.parametrize("failure", ["missing_event", "missing_company", "missing_position", "unknown_fact", "numeric_effect", "invalid_direction", "missing_assumption"])
def test_hypothesis_requires_complete_chain_and_rejects_unverified_output(fixture, failure):
    event, _ = event_fixture(fixture)
    value = packet(fixture, event)
    request = value["impact_context"]["model_request"]
    row = channel(request)
    if failure.startswith("missing_") and failure != "missing_assumption":
        key = {"missing_event": request["event_fact_id"], "missing_company": request["company_fact_id"],
               "missing_position": request["position_fact_ids"][0]}[failure]
        row["fact_ids"].remove(key)
    elif failure == "unknown_fact":
        row["fact_ids"].append("other-user-or-invented-fact")
    elif failure == "numeric_effect":
        row["expected_return"] = "10%"
    elif failure == "invalid_direction":
        row["direction"] = []
    else:
        row["assumptions"] = []
    with pytest.raises(GuardError):
        impact.validate({"channels": [row]}, value)


def test_unknown_company_and_primary_source_are_not_fabricated(fixture):
    event, _ = event_fixture(fixture, identity=False)
    value = packet(fixture, event)
    result = impact.validate({"channels": [channel(value["impact_context"]["model_request"])]}, value)
    company = result["companies"][0]
    assert company["identity_state"] == "unavailable"
    assert company["issuer_id"] is None
    assert company["issuer_name"] is None
    assert result["event"]["primary_source_verified"] is False
    assert len(result["limitations"]) == 5
    prepared_argument_1 = {"channels": [channel(value["impact_context"]["model_request"])]}
    with pytest.raises(GuardError):
        impact.validate(prepared_argument_1, {"facts": []})


def test_real_guarded_event_hypothesis_is_charged_once_and_recovered(fixture):
    event, _ = event_fixture(fixture)
    calls = []
    def handle(request):
        calls.append(request)
        sent = json.loads(request.content)
        model_context = json.loads(sent["messages"][-1]["content"])["context"]
        row = channel(model_context["impact_request"])
        reply = model_response()
        reply["choices"][0]["message"]["content"] = json.dumps({"answer": "Возможный механизм требует проверки масштаба события.",
            "claims": [{"text": "Публикация отнесена к удерживаемому инструменту.", "fact_ids": row["fact_ids"]}],
            "highlights": [], "uncertainties": [row["uncertainty"]], "actions": [], "impact_hypothesis": {"channels": [row]}})
        return httpx.Response(200, json=reply)
    transport = httpx.MockTransport(handle)
    fixture["patch"].setattr(chat, "GuardedAIClient", lambda user, connect, **kwargs: GuardedAIClient(user, connect,
        transport=transport, env=environment(), **kwargs))
    thread = chat.create_thread(chat.ThreadCreate(request_id="impact-thread"), user=fixture["user"])["thread_id"]
    endpoint = "/workspace/chat/threads/" + thread + "/messages"
    body = {"request_id": "impact-stable-request", "text": "Разобрать возможное влияние", "context": context(event), "tier": "fast"}
    response = fixture["client"].post(endpoint, json=body)
    assert response.status_code == 202, response.text
    job = fixture["client"].get("/workspace/jobs/by-request/impact-stable-request").json()
    assert job["state"] == "completed", job
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == job["job_id"]
    assert len(calls) == 1
    answer = fixture["client"].get(endpoint).json()["items"][-1]
    assert answer["impact_hypothesis"]["event"]["id"] == event["id"]
    assert answer["impact_hypothesis"]["positions"][0]["account_id"] == "owned-account-a"
    assert answer["impact_hypothesis"]["computed_financial_impact"] is None
    assert MoneyLedger(backend.connect).user_summary(int(fixture["user"]["id"]))["unresolved_attempts"] == 0


def test_scheduler_recovers_expired_collection_without_a_client_request_but_never_repeats_paid_work(fixture):
    calls = []
    def resume(user, payload, checkpoint, progress):
        calls.append(checkpoint["verified_stage"])
        return {"snapshot_id": "synthetic-resumed-checkpoint"}
    fixture["patch"].setattr(workspace, "collect", resume)
    first = jobs.enqueue(int(fixture["user"]["id"]), "restart-collection", "refresh", {}, checkpoint={"verified_stage": "source_received"})
    with closing(backend.connect()) as db:
        db.execute("UPDATE workspace_jobs SET state='running',owner='dead-process',expires_at=0 WHERE id=?", (first["job_id"],))
        db.commit()
    jobs.drain(limit=1)
    assert calls == ["source_received"]
    assert jobs.get_job(int(fixture["user"]["id"]), first["job_id"])["state"] == "completed"
    paid = jobs.enqueue(int(fixture["user"]["id"]), "restart-paid", "chat", {})
    with closing(backend.connect()) as db:
        db.execute("UPDATE workspace_jobs SET state='running',paid_started=1,owner='dead-process',expires_at=0 WHERE id=?", (paid["job_id"],))
        db.commit()
    jobs.drain(limit=1)
    with closing(backend.connect()) as db:
        observed = db.execute("SELECT state FROM workspace_jobs WHERE id=?", (paid["job_id"],)).fetchone()[0]
    assert observed == "uncertain"
    assert calls == ["source_received"]
