"""Synthetic completion-boundary regressions; no live provider is called."""
from contextlib import closing
import json

import httpx
import pytest
from fastapi import HTTPException

from backend import volume_chat as chat
from backend import volume_jobs as jobs
from backend.ai_budget import MoneyLedger, transaction
from backend.ai_guarded_client import GuardedAIClient, GuardError
from backend.investment_chat_policy import is_introduction, plan_chat, response_budget
from backend.tests.test_ai_controls import environment, model_response
from backend.tests.test_volume_workspace import fixture


GREETING = {"answer": "Здравствуйте! Могу объяснить данные портфеля или инвестиционный термин.",
            "claims": [], "highlights": [], "uncertainties": [], "actions": []}


def _thread(fixture, name="bounded-chat"):
    return chat.create_thread(chat.ThreadCreate(request_id=name), user=fixture["user"])["thread_id"]


def _provider(fixture, *, finish="stop", usage=None, answer=None):
    calls = []
    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        response = model_response()
        response["choices"][0] = {"finish_reason": finish, "message": {
            "content": json.dumps(GREETING if answer is None else answer, ensure_ascii=False),
            "reasoning_content": "PRIVATE_PROVIDER_REASONING_NOT_FOR_LOGS"}}
        if usage is not None:
            response["usage"] = usage
        return httpx.Response(200, json=response)
    fixture["patch"].setattr(chat, "GuardedAIClient", lambda user, connect, **kwargs:
        GuardedAIClient(user, connect, transport=httpx.MockTransport(respond), env=environment(), **kwargs))
    return calls


def _quoted_request(fixture, thread, *, text="Привет!", suffix="one"):
    endpoint = "/workspace/chat/threads/" + thread + "/messages"
    question = {"text": text, "context": {"mode": "general"}, "tier": "auto"}
    estimate = fixture["client"].post("/workspace/chat/estimate", json={"thread_id": thread, **question})
    assert estimate.status_code == 200, estimate.text
    quote = estimate.json()
    assert quote["available"] is True
    body = {"request_id": "bounded-request-" + suffix, **question,
            "max_cost_micro_rub": quote["cost_ceiling_micro_rub"], "expected_route_id": quote["route_id"]}
    return endpoint, body, quote


@pytest.mark.parametrize("text", ["привет", "  ЗДРАВСТВУЙТЕ!  ", "Что ты умеешь?", "Hi!", "При\u200bвет"])
def test_standalone_introduction_excludes_financial_packet_and_old_messages(fixture, text):
    thread = _thread(fixture)
    with transaction(chat.backend.connect) as db:
        db.execute("INSERT INTO workspace_chat_messages VALUES (?,?,?,?,?,?,?,?,?)", (
            "prior-question", thread, int(fixture["user"]["id"]), "user",
            "Проанализируй портфель PRIVATE_OLD_CONVERSATION", "2026-01-01T00:00:00Z", "prior", "prior-job", "{}"))
    messages, packet = chat.model_messages(fixture["user"], text, {"mode": "general"}, thread, max_output_tokens=600)
    contents = json.loads(messages[1]["content"])
    assert contents == {"question": text}
    assert "PRIVATE_OLD_CONVERSATION" not in json.dumps(messages)
    assert "capital:total" not in json.dumps(messages)
    assert packet["facts"] == []
    assert packet["sources"] == []
    assert packet["allowed_highlights"] == []
    assert packet["snapshot_id"] is None
    assert packet["as_of"] is None
    assert packet["coverage"]["financial_context_included"] is False
    assert "claims: []" in messages[0]["content"]


@pytest.mark.parametrize("text", ["Привет! Проанализируй портфель", "Привет, расскажи об облигациях",
                                  "Что ты умеешь и сколько у меня денег?", "Hello, explain my portfolio"])
def test_greeting_with_a_task_keeps_financial_context(fixture, text):
    assert is_introduction(text) is False
    messages, packet = chat.model_messages(fixture["user"], text, {"mode": "general"}, max_output_tokens=1200)
    assert packet["facts"]
    assert json.loads(messages[1]["content"])["context"]["facts"]
    assert "1200 токенов" in messages[0]["content"]
    assert "Не называй старый снимок текущим" in messages[0]["content"]


def test_greeting_still_rejects_wrong_account_and_wrong_thread(fixture):
    with pytest.raises(HTTPException) as wrong_account:
        chat.model_messages(fixture["user"], "Привет", {"mode": "portfolio", "account_id": "not-owned"})
    assert wrong_account.value.detail == "chat_account_not_in_workspace"
    other_thread = chat.create_thread(chat.ThreadCreate(request_id="other-bounded-thread"), user=fixture["other"])["thread_id"]
    with pytest.raises(HTTPException) as wrong_thread:
        chat.model_messages(fixture["user"], "Привет", {"mode": "general"}, other_thread)
    assert wrong_thread.value.detail == "chat_thread_not_found"


def test_introduction_cannot_cite_omitted_financial_facts(fixture):
    _, packet = chat.model_messages(fixture["user"], "Привет", {"mode": "general"})
    forged = {**GREETING, "claims": [{"text": "Invented balance", "fact_ids": ["capital:total"]}]}
    with pytest.raises(GuardError, match="ai_chat_evidence_not_in_context"):
        chat.validate_response(forged, packet)


def test_greeting_uses_guarded_provider_answer_with_one_bounded_paid_call(fixture):
    calls = _provider(fixture)
    endpoint, body, quote = _quoted_request(fixture, _thread(fixture))
    assert quote["max_output_tokens"] == 600
    assert fixture["client"].post(endpoint, json=body).status_code == 202
    job = fixture["client"].get("/workspace/jobs/by-request/" + body["request_id"]).json()
    assert job["state"] == "completed", job
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == job["job_id"]
    assert len(calls) == 1
    assert calls[0]["max_tokens"] == quote["max_output_tokens"]
    assert json.loads(calls[0]["messages"][1]["content"]) == {"question": body["text"]}
    answer = fixture["client"].get(endpoint).json()["items"][-1]
    assert answer["text"] == GREETING["answer"]
    assert answer["answer_origin"] == "model_interpretation"
    assert answer["evidence"] == []
    assert answer["context_as_of"] is None
    assert MoneyLedger(chat.backend.connect).user_summary(int(fixture["user"]["id"]))["unresolved_attempts"] == 0


@pytest.mark.parametrize("finish,expected", [("length", "length"), ("content_filter", "content_filter"),
                                           ("tool_calls", "tool_calls"), (None, "unknown"),
                                           ("PRIVATE_PROVIDER_SECRET", "unknown")])
def test_incomplete_response_keeps_usage_reason_and_never_replays(fixture, finish, expected):
    usage = {"prompt_tokens": 10, "completion_tokens": 600, "total_tokens": 610}
    calls = _provider(fixture, finish=finish, usage=usage)
    endpoint, body, _ = _quoted_request(fixture, _thread(fixture))
    assert fixture["client"].post(endpoint, json=body).status_code == 202
    path = "/workspace/jobs/by-request/" + body["request_id"]
    job = fixture["client"].get(path).json()
    assert job["state"] == "failed", job
    assert job["stage"] == "failed"
    assert job["error_code"] == "ai_incomplete_response"
    assert job["can_retry"] is False
    assert job["result"]["completion"] == {"finish_reason": expected, "max_output_tokens": 600,
        **usage, "usage_accounted": True, "answer_published": False, "automatic_retry": False}
    assert "PRIVATE_PROVIDER" not in json.dumps(job)
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == job["job_id"]
    assert fixture["client"].post("/workspace/jobs/" + job["job_id"] + "/retry", json={"request_id": "forbidden-replay"}).status_code == 409
    assert len(calls) == 1
    assert [m["role"] for m in fixture["client"].get(endpoint).json()["items"]] == ["user"]
    summary = MoneyLedger(chat.backend.connect).user_summary(int(fixture["user"]["id"]))
    assert summary["unresolved_attempts"] == 0
    with closing(chat.backend.connect()) as db:
        row = db.execute("SELECT state,input_tokens,output_tokens FROM ai_money_reservations WHERE user_id=?", (int(fixture["user"]["id"]),)).fetchone()
    assert tuple(row) == ("settled", 10, 600)


def test_invalid_usage_does_not_claim_accounted_completion(fixture):
    calls = _provider(fixture, finish="length", usage={"prompt_tokens": 10, "completion_tokens": 600, "total_tokens": 999})
    endpoint, body, _ = _quoted_request(fixture, _thread(fixture))
    assert fixture["client"].post(endpoint, json=body).status_code == 202
    job = fixture["client"].get("/workspace/jobs/by-request/" + body["request_id"]).json()
    assert job["state"] == "uncertain"
    assert job["result"] is None
    assert job["can_retry"] is False
    assert len(calls) == 1
    assert MoneyLedger(chat.backend.connect).user_summary(int(fixture["user"]["id"]))["unresolved_attempts"] == 1


@pytest.mark.parametrize("question,expected", [("Что такое облигация?", 600), ("Аудит портфеля", 1200), ("Дефолт эмитента", 1600)])
def test_output_contract_preserves_existing_hard_budgets(question, expected):
    plan = plan_chat(question)
    assert plan.max_output_tokens == expected
    budget = response_budget(plan.max_output_tokens)
    assert budget["max_output_tokens"] == expected
    assert budget["answer_characters_target"] < expected
    assert budget["claims_max"] <= 4


@pytest.mark.parametrize("value", [None, True, 0, -1, 4001, "600"])
def test_output_contract_rejects_invalid_caps(value):
    with pytest.raises(ValueError, match="chat_output_budget_invalid"):
        response_budget(value)


def test_event_output_contract_reserves_space_for_required_hypothesis():
    instruction = chat._response_instruction(600, impact_request=True)
    assert "600 токенов" in instruction
    assert "impact_hypothesis: ровно 1 канал" in instruction
    assert "Сохрани все обязательные fact_ids канала" in instruction


@pytest.mark.parametrize("code", ["ai_chat_policy_changed", "ai_chat_route_or_cost_changed",
                                 "chat_premium_confirmation_required", "chat_tier_insufficient"])
def test_changed_quote_is_not_retried_with_the_same_stale_routing(fixture, code):
    user_id = int(fixture["user"]["id"])
    job = jobs.enqueue(user_id, "old-quote-request", "chat", {})
    with transaction(chat.backend.connect) as db:
        db.execute("UPDATE workspace_jobs SET state='failed',stage='model_running',error_code=? WHERE id=?",
                   (code, job["job_id"]))
    outcome = jobs.get_job(user_id, job["job_id"])
    assert outcome["can_retry"] is False
    assert outcome["stage"] == "failed"
    response = fixture["client"].post("/workspace/jobs/" + job["job_id"] + "/retry", json={"request_id": "retry-stale-quote"})
    assert response.status_code == 409


def test_unsent_transient_chat_failure_remains_retryable(fixture):
    user_id = int(fixture["user"]["id"])
    job = jobs.enqueue(user_id, "transient-request", "chat", {})
    with transaction(chat.backend.connect) as db:
        db.execute("UPDATE workspace_jobs SET state='failed',stage='context_ready',error_code='workspace_refresh_required' WHERE id=?",
                   (job["job_id"],))
    outcome = jobs.get_job(user_id, job["job_id"])
    assert outcome["can_retry"] is True
    assert outcome["stage"] == "failed"
