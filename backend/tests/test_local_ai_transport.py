"""Local inference must preserve access guards and never fall back to a provider."""
import json
from unittest import mock

import pytest

from backend import local_ai_transport as local, volume_chat as chat
from backend.ai_guarded_client import GuardError, GuardedAIClient, configured_route
from backend.tests.test_ai_controls import DatabaseCase, FAST, environment, model_response
from backend.tests.ai_broker_fixtures import bind_synthetic_broker
from backend.tests.test_volume_workspace import fixture
from backend.tests.test_chat_answer_contract import GENERAL_ANSWER, quoted_question
from backend.tests.test_local_research_worker import worker


def local_environment():
    return {**environment(), "AI_TRANSPORT": "local", "LOCAL_AI_ENABLED": "true",
            "AI_EXTERNAL_PROCESSING_APPROVED": "false", "AI_USER_DAILY_RUB": "0",
            "AI_PROJECT_DAILY_RUB": "0"}


def local_response(answer=None):
    value = model_response(model=local.MODEL_ID)
    value["choices"][0]["message"]["content"] = json.dumps(answer or {"ok": True})
    return json.dumps(value).encode()


class LocalGuardTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        bind_synthetic_broker(self.connect)
        self.client = GuardedAIClient(1, self.connect, env=local_environment())
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(local, "ensure_ready").start()

    def complete(self):
        return self.client.complete_json(tier=FAST, messages=[{"role": "user", "content": "fixture"}],
                                         max_output_tokens=100)

    def test_local_inference_with_zero_cloud_budget_never_reserves_or_uses_http(self):
        with mock.patch.object(local, "ensure_ready"), mock.patch.object(local, "complete", return_value=local_response()), \
                mock.patch.object(self.client, "_send", side_effect=AssertionError("external dispatch")), \
                mock.patch.object(self.client.ledger, "reserve", side_effect=AssertionError("paid reservation")):
            assert self.complete().data == {"ok": True}
        assert self.client.ledger.user_summary(1)["unresolved_attempts"] == 0

    def test_local_failure_never_attempts_paid_fallback(self):
        with mock.patch.object(local, "ensure_ready", side_effect=local.LocalAIError("local_ai_unavailable")), \
                mock.patch.object(local, "complete") as complete, mock.patch.object(self.client, "_send") as cloud:
            with pytest.raises(GuardError, match="local_ai_unavailable"):
                self.complete()
        complete.assert_not_called()
        cloud.assert_not_called()

    def test_cancellation_guard_runs_before_local_inference(self):
        self.client.budget_guard = mock.Mock(side_effect=GuardError("cancelled"))
        with mock.patch.object(local, "complete") as complete:
            with pytest.raises(GuardError, match="cancelled"):
                self.complete()
        complete.assert_not_called()

    def test_disconnected_broker_remains_a_dispatch_boundary(self):
        with self.connect() as db:
            db.execute("UPDATE users SET tinvest_token_encrypted=NULL WHERE id=1")
        with mock.patch.object(local, "complete") as complete:
            with pytest.raises(GuardError, match="broker_connection_required"):
                self.complete()
        complete.assert_not_called()


def test_local_route_is_explicit_and_has_a_stable_free_quote():
    route = configured_route(FAST, local_environment())
    assert route.mode == "local" and route.url == local.SOCKET
    assert route.input_rate == route.output_rate == 0 and route.key == ""
    with pytest.raises(GuardError, match="local_ai_not_enabled"):
        configured_route(FAST, {**local_environment(), "LOCAL_AI_ENABLED": "false"})
    with pytest.raises(GuardError, match="output_limit"):
        configured_route(FAST, local_environment(), max_output_tokens=1601)


def test_zero_cost_chat_runs_once_and_recovers_the_saved_answer(fixture):
    fixture["patch"].setattr(chat, "GuardedAIClient", lambda user, connect, **kwargs:
                            GuardedAIClient(user, connect, env=local_environment(), **kwargs))
    fixture["patch"].setattr(local, "ensure_ready", lambda: None)
    calls = []
    def complete(messages, limit):
        calls.append((messages, limit))
        return local_response(GENERAL_ANSWER)
    fixture["patch"].setattr(local, "complete", complete)
    endpoint, body = quoted_question(fixture, "local")
    assert body["max_cost_micro_rub"] == 0
    response = fixture["client"].post(endpoint, json=body)
    assert response.status_code == 202, response.text
    job = fixture["client"].get("/workspace/jobs/by-request/" + body["request_id"]).json()
    assert job["state"] == "completed", job
    assert fixture["client"].post(endpoint, json=body).json()["job_id"] == job["job_id"]
    assert len(calls) == 1
    assert fixture["client"].get(endpoint).json()["items"][-1]["text"] == GENERAL_ANSWER["answer"]


@pytest.mark.parametrize("change", [{"tools": []}, {"max_output_tokens": True}, {"max_output_tokens": 1601},
                                      {"messages": [{"role": "user", "content": "x", "url": "https://example.invalid"}]}])
def test_worker_rejects_extra_capabilities_before_inference(worker, change):
    engine, runtime = mock.Mock(), mock.Mock()
    request = {"messages": [{"role": "user", "content": "fixture"}], "max_output_tokens": 100, **change}
    with pytest.raises(ValueError):
        worker.model_complete(engine, runtime, request)
    engine.create_conversation.assert_not_called()


def test_worker_keeps_context_bound_and_disables_tools(worker):
    engine, runtime = mock.Mock(), mock.Mock()
    engine.tokenize.return_value = [1] * 5
    conversation = mock.MagicMock()
    engine.create_conversation.return_value = conversation
    conversation.__enter__.return_value.send_message.return_value = {"content": [{"type": "text", "text": '{"ok":true}'}]}
    request = {"messages": [{"role": "user", "content": "fixture"}], "max_output_tokens": 100}
    assert worker.model_complete(engine, runtime, request)["model"] == local.MODEL_ID
    assert engine.create_conversation.call_args.kwargs["tools"] == []
    assert engine.create_conversation.call_args.kwargs["automatic_tool_calling"] is False
    engine.create_conversation.reset_mock()
    engine.tokenize.return_value = [1] * 8192
    with pytest.raises(ValueError, match="local_context_full"):
        worker.model_complete(engine, runtime, request)
    engine.create_conversation.assert_not_called()


@pytest.mark.parametrize("status,checksum", [(302, local.MODEL_SHA256), (200, "wrong-model")])
def test_private_transport_rejects_redirects_and_changed_weights(status, checksum):
    response = mock.Mock(status=status)
    response.getheader.return_value = checksum
    connection = mock.Mock()
    connection.getresponse.return_value = response
    with mock.patch.object(local, "UnixConnection", return_value=connection):
        with pytest.raises(local.LocalAIError):
            local.complete([{"role": "user", "content": "fixture"}], 100)
    connection.close.assert_called_once()
    response.read.assert_not_called()
