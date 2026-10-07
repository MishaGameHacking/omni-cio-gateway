"""Provider contract, credential isolation, and orchestration fail-closed behavior."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from omnicio.assistant import (
    AssistantClient,
    AssistantNotConfigured,
    AssistantRequestConflict,
    AssistantService,
    AssistantUnavailable,
    investment_context,
)
from omnicio.assistant_store import AssistantStore
from omnicio.db import Database


def service(*, enabled: bool = True) -> AssistantService:
    result = AssistantService(
        Mock(spec=Database),
        credential_key=Fernet.generate_key().decode(),
        enabled=enabled,
        allowed_endpoints=("https://approved.example.invalid/v1",),
        default_client=AssistantClient(base_url="https://operator.example.invalid", model="test"),
    )
    result.store = Mock(spec=AssistantStore)
    result.store.connection.return_value = None
    result.store.quota.return_value = {"used": 0, "remaining": 30, "limit": 30}
    result.store.claim.return_value = {"history": [], "version": 1}
    result.store.finish.side_effect = lambda user, request, reply: reply
    return result


@pytest.mark.parametrize("model", ["test", "gpt-5-test"])
def test_openai_transport_has_bounded_compatible_request_and_usage(model: str) -> None:
    client = AssistantClient(
        provider="openai_compatible",
        base_url="https://approved.example.invalid/v1",
        model=model,
        api_key="private-key",
    )
    transport = Mock()
    transport.getresponse.return_value = Mock(
        status=200,
        read=Mock(
            return_value=json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": "Ответ",
                                "tool_calls": [{"ignored": True}],
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                }
            ).encode()
        ),
    )
    with patch("omnicio.assistant.http.client.HTTPSConnection", return_value=transport):
        reply = client.chat(message="Вопрос", history=[])
    assert transport.request.call_args.args == ("POST", "/v1/chat/completions")
    payload = json.loads(transport.request.call_args.kwargs["body"])
    assert "tools" not in payload
    assert "tool_calls" not in reply
    if model.startswith("gpt-5"):
        assert payload["max_completion_tokens"] == 1024
        assert "temperature" not in payload and "max_tokens" not in payload
    else:
        assert payload["max_tokens"] == 1024
    assert reply["usage"] == {"input_tokens": 10, "output_tokens": 4}
    assert "private-key" not in json.dumps(reply)


@pytest.mark.parametrize("finish", ["length", "tool_calls", None])
def test_openai_incomplete_response_is_not_a_success(finish: str | None) -> None:
    client = AssistantClient(
        provider="openai_compatible",
        base_url="https://approved.example.invalid/v1",
        model="test",
    )
    with (
        patch.object(
            client,
            "_request",
            return_value={
                "choices": [
                    {
                        "finish_reason": finish,
                        "message": {"role": "assistant", "content": "Partial"},
                    }
                ]
            },
        ),
        pytest.raises(AssistantUnavailable),
    ):
        client.chat(message="Вопрос", history=[])


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"data": [{"id": "test"}]}, "healthy"),
        ({"data": [{"id": "different"}]}, "model_missing"),
        ({"data": "invalid"}, "unavailable"),
    ],
)
def test_real_health_distinguishes_configuration_and_model_availability(payload, expected) -> None:
    client = AssistantClient(
        provider="openai_compatible",
        base_url="https://approved.example.invalid/v1",
        model="test",
    )
    assert client.status()["health"]["status"] == "unchecked"
    with patch.object(client, "_request", return_value=payload) as request:
        assert client.health()["status"] == expected
    request.assert_called_once_with("GET", "/v1/models")


def test_credential_ciphertext_is_bound_to_owner_provider_endpoint_model_and_never_echoed() -> None:
    system, user = service(), uuid4()
    system.save_connection(
        user,
        {
            "provider": "openai_compatible",
            "base_url": "https://approved.example.invalid/v1",
            "model": "test",
            "api_key": "private-key",
        },
        expected_version=0,
    )
    record = system.store.save_connection.call_args.args[1]
    assert b"private-key" not in record["key_ciphertext"]
    assert system._secret(user, record) == "private-key"
    for owner, changes in (
        (uuid4(), {}),
        (user, {"model": "other"}),
        (user, {"base_url": "https://other.example.invalid/v1"}),
    ):
        with pytest.raises(AssistantNotConfigured, match="credential_invalid"):
            system._secret(owner, {**record, **changes})
    system.store.connection.return_value = {
        **record,
        "version": 1,
        "health_status": "unchecked",
        "checked_at": None,
    }
    assert system.status(user)["has_key"] is True
    assert "private-key" not in json.dumps(system.status(user))
    assert "key_ciphertext" not in json.dumps(system.status(user))


def test_activation_disabled_and_endpoint_allowlist_block_network() -> None:
    system, user = service(enabled=False), uuid4()
    with patch("omnicio.assistant.http.client.HTTPSConnection") as network:
        with pytest.raises(AssistantNotConfigured, match="activation_disabled"):
            system.chat(
                user,
                uuid4(),
                message="Вопрос",
                context=None,
                request_id=uuid4(),
                expected_version=0,
            )
        with pytest.raises(AssistantNotConfigured, match="activation_disabled"):
            system.check_connection(user)
        with pytest.raises(ValueError, match="endpoint_not_allowed"):
            system.save_connection(
                user,
                {
                    "provider": "openai_compatible",
                    "base_url": "https://169.254.169.254/v1",
                    "model": "test",
                    "api_key": "private-key",
                },
                expected_version=0,
            )
    network.assert_not_called()
    assert system.status(user)["status"] == "activation_disabled"


def test_conflicting_request_does_not_mark_another_running_invocation_uncertain() -> None:
    system, user = service(), uuid4()
    system.store.claim.side_effect = AssistantRequestConflict("assistant_request_running")
    with (
        patch.object(system.default_client, "chat") as provider,
        pytest.raises(AssistantRequestConflict),
    ):
        system.chat(
            user,
            uuid4(),
            message="Вопрос",
            context=None,
            request_id=uuid4(),
            expected_version=0,
        )
    provider.assert_not_called()
    system.store.uncertain.assert_not_called()


@pytest.mark.parametrize("before_provider", [True, False])
def test_revoked_context_never_commits_answer_and_records_uncertainty(
    before_provider: bool,
) -> None:
    system, user, request_id = service(), uuid4(), uuid4()
    guard = Mock(
        side_effect=[PermissionError("session_revoked")]
        if before_provider
        else [None, PermissionError("session_revoked")]
    )
    with (
        patch.object(system.default_client, "chat", return_value={"reply": "Private"}) as provider,
        pytest.raises(PermissionError),
    ):
        system.chat(
            user,
            uuid4(),
            message="Вопрос",
            context=None,
            request_id=request_id,
            expected_version=0,
            validate_context=guard,
        )
    assert provider.call_count == (0 if before_provider else 1)
    system.store.finish.assert_not_called()
    system.store.uncertain.assert_called_once_with(user, request_id)


def test_request_selection_hash_is_stable_for_fresh_snapshot_but_changes_with_scope() -> None:
    system, user, conversation, request_id = service(), uuid4(), uuid4(), uuid4()
    hashes = []
    with patch.object(system.default_client, "chat", return_value={"reply": "Ответ"}):
        for stamp, scope in (
            ("first", "portfolio"),
            ("second", "portfolio"),
            ("second", "investment"),
        ):
            reply = system.chat(
                user,
                conversation,
                message="Вопрос",
                request_id=request_id,
                expected_version=0,
                context={"generated_at": stamp, "_selection": {"scope": scope}},
            )
            hashes.append(system.store.claim.call_args.kwargs["input_hash"])
            assert len(reply["sources"][0]["sha256"]) == 64
            assert reply["sources"][0]["selection"] == {"scope": scope}
    assert hashes[0] == hashes[1] != hashes[2]


def test_expanded_context_preserves_evidence_limits_and_excludes_private_raw_fields() -> None:
    context = investment_context(
        {},
        positions=[{"ticker": "TEST", "quantity": 2, "account_id": "private-account"}],
        goals=[{"title": "Цель", "progress_percent": 2, "secret": "private-goal"}],
        research={
            "status": "ready",
            "metrics": {"net_return_percent": 3, "secret": "private"},
            "period": {"observations": 90},
            "source_url": "private-evidence",
            "probability_of_profit": 99,
        },
        news=[{"title": "Наблюдение", "summary": "x" * 1000, "raw": "private-news"}] * 100,
    )
    assert context["research"]["metrics"]["net_return_percent"] == 3
    assert context["research"]["probability_of_profit"] is None
    assert context["coverage"]["news"] == {"available": 100, "included": 10}
    assert "private" not in json.dumps(context)
