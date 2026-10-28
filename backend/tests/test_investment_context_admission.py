"""Owner-selected context regression; no live model or broker request."""
import pytest
from backend.investment_chat_policy import ChatPolicyError, plan_chat
from backend.tests.test_volume_workspace import fixture, model_fixture
from backend import volume_chat as chat


@pytest.mark.parametrize("text", ["Почему?", "Explain the balance", "Разобрать возможное влияние"])
def test_selected_context_permits_only_bounded_clarifications(text):
    assert plan_chat(text, verified_context=True).tier.value == "fast"
    with pytest.raises(ChatPolicyError, match="scope_unclear"):
        plan_chat(text)


@pytest.mark.parametrize("text", ["Напиши рецепт супа", "Расскажи про котов", "Почему коты мурлыкают?"])
def test_selected_context_does_not_whitelist_arbitrary_topics(text):
    with pytest.raises(ChatPolicyError):
        plan_chat(text, verified_context=True)


def test_followup_does_not_downgrade_default_risk():
    plan = plan_chat("Почему?", history=["Проверь риск банкротства эмитента"])
    assert plan.tier.value == "premium"


def test_owned_selection_uses_current_broker_binding(fixture):
    user_id = int(fixture["user"]["id"])
    assert chat._selected_financial_context(user_id, {"mode": "portfolio"})
    assert chat._selected_financial_context(user_id, {"mode": "instrument", "instrument_uid": "aaa"})
    assert not chat._selected_financial_context(user_id, {"mode": "portfolio", "account_id": "not-owned"})
    assert not chat._selected_financial_context(user_id, {"mode": "instrument", "instrument_uid": "absent"})
    assert not chat._selected_financial_context(int(fixture["other"]["id"]), {"mode": "portfolio"})
    assert not chat._selected_financial_context(user_id, {"mode": "general"})


def test_unknown_question_never_reaches_paid_transport(fixture):
    calls = model_fixture(fixture)
    thread = chat.create_thread(chat.ThreadCreate(request_id="scope-regression-thread"), user=fixture["user"])["thread_id"]
    endpoint = "/workspace/chat/threads/" + thread + "/messages"
    response = fixture["client"].post(endpoint, json={"request_id": "scope-regression-question", "text": "Расскажи про котов",
        "context": {"mode": "portfolio"}, "tier": "fast"})
    assert response.status_code == 422
    assert not calls
    assert chat.messages(thread, user=fixture["user"])["items"] == []
