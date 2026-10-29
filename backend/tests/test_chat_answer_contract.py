"""Strict chat answer contract, through the real queued flow and a mock provider.

The examples are synthetic test responses. They never replace a production
model answer or relax evidence validation.
"""
import json

import httpx
import pytest

from backend import volume_chat as chat
from backend.ai_budget import MoneyLedger
from backend.ai_guarded_client import GuardedAIClient
from backend.tests.test_ai_controls import environment, model_response
from backend.tests.test_volume_workspace import fixture


GENERAL_ANSWER = {
    "answer": "Облигация — долговая ценная бумага. Это общее определение, а не оценка вашего портфеля.",
    "claims": [], "highlights": [], "uncertainties": [], "actions": [],
}


def mock_answer(fixture, answer):
    calls = []

    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        response = model_response()
        response["choices"][0]["message"]["content"] = json.dumps(answer, ensure_ascii=False)
        return httpx.Response(200, json=response)

    transport = httpx.MockTransport(handle)
    fixture["patch"].setattr(
        chat, "GuardedAIClient",
        lambda user, connect, **kwargs: GuardedAIClient(
            user, connect, transport=transport, env=environment(), **kwargs),
    )
    return calls


def quoted_question(fixture, suffix):
    client = fixture["client"]
    thread = client.post("/workspace/chat/threads", json={
        "request_id": "general-thread-" + suffix, "title": "Synthetic general question",
    }).json()["thread_id"]
    question = {"text": "Что такое облигация?", "context": {"mode": "general"}, "tier": "auto"}
    estimate = client.post("/workspace/chat/estimate", json={"thread_id": thread, **question})
    assert estimate.status_code == 200, estimate.text
    quote = estimate.json()
    assert quote["available"] is True
    assert quote["selected_tier"] == "fast"
    assert quote["requires_cost_confirmation"] is False
    return "/workspace/chat/threads/" + thread + "/messages", {
        "request_id": "general-question-" + suffix, **question,
        "max_cost_micro_rub": quote["cost_ceiling_micro_rub"],
        "expected_route_id": quote["route_id"],
    }


def test_general_answer_completes_and_is_recovered_without_another_paid_call(fixture):
    calls = mock_answer(fixture, GENERAL_ANSWER)
    endpoint, body = quoted_question(fixture, "valid")
    response = fixture["client"].post(endpoint, json=body)
    assert response.status_code == 202, response.text
    job = fixture["client"].get("/workspace/jobs/by-request/" + body["request_id"]).json()
    assert job["state"] == "completed", job
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == job["job_id"]
    assert len(calls) == 1
    # The provider receives the explicit valid representation for general knowledge.
    assert "claims: []" in calls[0]["messages"][0]["content"]
    messages = fixture["client"].get(endpoint).json()["items"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    answer = messages[-1]
    assert answer["text"] == GENERAL_ANSWER["answer"]
    assert answer["claims"] == []
    assert answer["evidence"] == []
    assert any("общее объяснение" in text for text in answer["uncertainties"])
    assert answer["claim_meaning_verified"] is False
    summary = MoneyLedger(chat.backend.connect).user_summary(int(fixture["user"]["id"]))
    assert summary["unresolved_attempts"] == 0


@pytest.mark.parametrize("fact_ids,error_code", [
    ([], "ai_chat_claims_invalid"),
    (["invented-fact"], "ai_chat_evidence_not_in_context"),
    (["capital:total", "invented-fact"], "ai_chat_evidence_not_in_context"),
])
def test_paid_invalid_claim_is_not_published_or_automatically_replayed(fixture, fact_ids, error_code):
    unsupported = {
        **GENERAL_ANSWER,
        "claims": [{"text": "Synthetic unsupported portfolio statement", "fact_ids": fact_ids}],
    }
    calls = mock_answer(fixture, unsupported)
    endpoint, body = quoted_question(fixture, "invalid")
    response = fixture["client"].post(endpoint, json=body)
    assert response.status_code == 202, response.text
    job = fixture["client"].get("/workspace/jobs/by-request/" + body["request_id"]).json()
    assert job["state"] == "failed", job
    assert job["error_code"] == error_code
    assert job["can_retry"] is False
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == job["job_id"]
    assert len(calls) == 1
    assert [message["role"] for message in fixture["client"].get(endpoint).json()["items"]] == ["user"]
    # Usage was settled even though the answer was rejected; the audit is retained.
    summary = MoneyLedger(chat.backend.connect).user_summary(int(fixture["user"]["id"]))
    assert summary["unresolved_attempts"] == 0
