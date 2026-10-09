"""Provider contract, credential isolation, and orchestration fail-closed behavior."""

from __future__ import annotations

import json
from io import BytesIO
from threading import Event
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
    _Cancellation,
    investment_context,
    portfolio_context,
    source_read,
    source_references,
    source_search,
    validate_source_response,
)
from omnicio.assistant_store import AssistantStore
from omnicio.db import Database
from omnicio.workspace_store import WorkspaceNotFound


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
    result.store.update_stream.return_value = 1
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
        assert "temperature" not in payload
        assert "max_tokens" not in payload
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


def test_research_context_keeps_partial_coverage_and_metric_limitations() -> None:
    research = {
        "status": "computed", "basis": "unadjusted_price",
        "complete_strategy_coverage": False, "research_asset_weight_percent": "40",
        "return_label": "Изменение цены после заданных издержек",
        "metrics": {"net_return_percent": "3"},
        "limitations": ["Исследована частичная корзина; выплаты не включены."],
        "missing_requirements": ["verified_cashflows", "eligible_bonds"],
        "probability_reason": "Один тест не определяет вероятность будущей прибыли.",
        "raw_account_id": "private-account",
    }
    selected = investment_context({}, research=research)["research"]
    for field in ("complete_strategy_coverage", "research_asset_weight_percent", "return_label",
                  "limitations", "missing_requirements", "probability_reason"):
        assert selected[field] == research[field]
    assert selected["limitations_truncated"] is False
    assert selected["probability_of_profit"] is None
    assert "private-account" not in json.dumps(selected)
    research["limitations"] = ["x" * 501] * 21
    bounded = investment_context({}, research=research)["research"]
    assert bounded["limitations_truncated"] is True
    assert len(bounded["limitations"]) == 20
    assert len(bounded["limitations"][0]) == 500


def test_portfolio_context_excludes_legacy_transaction_based_returns() -> None:
    performance = {
        "status": "available", "return_percent": "5", "return_method": "modified_dietz",
        "return_denominator_rub": "10000", "return_is_estimate": True,
        "return_is_annualized": False, "return_time_basis": "broker_operation_instruction_time",
        "return_limitations": ["An estimate can differ from time-weighted return."],
    }
    value_change = {
        "status": "available", "method": "snapshot_value_change",
        "nav_change_rub": "500", "label": "Изменение стоимости",
        "limitation": "Пополнения и выплаты не учитываются; это не доходность.",
    }
    context = portfolio_context({"performance": performance, "value_change": value_change})
    assert "performance" not in context
    assert "broker_operation_instruction_time" not in json.dumps(context)
    assert context["value_change"] == value_change


@pytest.mark.parametrize("provider", ["ollama", "openai_compatible"])
def test_real_stream_protocol_accumulates_content_and_never_exposes_thinking(provider: str) -> None:
    client = AssistantClient(base_url="https://model.example.invalid", model="test",
                             provider=provider)
    if provider == "ollama":
        frames = [
            {"message": {"role": "assistant", "content": "Первая ",
                         "thinking": "private-reasoning"},
             "done": False},
            {"message": {"role": "assistant", "content": "часть"}, "done": True,
             "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 2},
        ]
        raw = b"\n".join(json.dumps(frame).encode() for frame in frames) + b"\n"
    else:
        frames = [
            {"choices": [{"delta": {"role": "assistant", "content": "Первая "},
                          "finish_reason": None}]},
            {"choices": [{"delta": {"content": "часть"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
        ]
        raw = b"".join(b"data: " + json.dumps(frame).encode() + b"\n\n" for frame in frames)
        raw += b"data: [DONE]\n\n"
    connection = Mock()
    connection.getresponse.return_value = Mock(status=200, readline=BytesIO(raw).readline)
    with patch("omnicio.assistant.http.client.HTTPSConnection", return_value=connection):
        events = list(client.stream(message="Вопрос", history=[]))
    assert [event["delta"] for event in events if "delta" in event] == ["Первая ", "часть"]
    assert events[-1]["result"]["reply"] == "Первая часть"
    assert events[-1]["result"]["usage"] == {"input_tokens": 5, "output_tokens": 2}
    assert "private-reasoning" not in json.dumps(events)
    assert json.loads(connection.request.call_args.kwargs["body"])["stream"] is True
    connection.close.assert_called_once()


@pytest.mark.parametrize("raw", [
    b'{"message":{"role":"assistant","content":"partial"},"done":false}\n',
    b'{"message":{"role":"assistant","content":"partial"},"done":true,"done_reason":"length"}\n',
    b'{"message":{"role":"assistant","content":"partial","tool_calls":[{}]},"done":true}\n',
    b"{invalid-json}\n",
    b"x" * 131073,
], ids=("truncated", "token_limit", "tool_call", "malformed", "oversized"))
def test_stream_truncation_tools_malformed_or_oversized_data_is_not_a_complete_answer(
    raw: bytes,
) -> None:
    client = AssistantClient(base_url="https://model.example.invalid", model="test")
    connection = Mock()
    connection.getresponse.return_value = Mock(status=200, readline=BytesIO(raw).readline)
    with patch("omnicio.assistant.http.client.HTTPSConnection", return_value=connection), \
            pytest.raises(AssistantUnavailable):
        list(client.stream(message="Вопрос", history=[]))


def test_cancellation_before_network_prevents_provider_request() -> None:
    client = AssistantClient(base_url="https://model.example.invalid", model="test")
    stop = _Cancellation()
    stop.cancel()
    connection = Mock()
    with patch("omnicio.assistant.http.client.HTTPSConnection", return_value=connection), \
            pytest.raises(AssistantRequestConflict, match="cancelled"):
        list(client.stream(message="Вопрос", history=[], cancellation=stop))
    connection.request.assert_not_called()


def test_source_catalog_search_and_read_use_only_selected_real_facts() -> None:
    context = {"overview": {"nav_rub": "123456", "observed_at": "2026-10-07T10:00:00Z"},
               "research": {"metrics": {"net_return_percent": "3.2"}},
               "news": [{"title": "Ставка Банка России", "url": "https://www.cbr.ru/press/1",
                         "published_at": "2026-10-06T12:00:00Z"},
                        {"title": "Injected", "url": "https://private.example.invalid"}]}
    found = source_search(context, "Ставка")
    assert found["scope"] == "selected_sources"
    assert found["web_search"] is False
    assert found["total"] == 1
    record = source_read(context, found["items"][0]["id"])
    assert record["content"]["title"] == "Ставка Банка России"
    assert record["published_at"] == "2026-10-06T12:00:00Z"
    assert all("private.example" not in json.dumps(ref) for ref in source_references(context))
    with pytest.raises(WorkspaceNotFound):
        source_read(None, record["id"])
    assert source_search(None, "Ставка")["total"] == 0


def test_evidence_guard_rejects_invented_sums_links_and_source_ids() -> None:
    context = {"overview": {"nav_rub": "123456"}, "performance": {"return_percent": "3.2"}}
    validate_source_response("Стоимость: 123 456 руб. Доходность: 3,2%.", context)
    for reply in ("Стоимость: 123 999 руб.", "Доходность: 90%.", "Доходность: 123456%.",
                  "Стоимость: 123456 USD.",
                  "Источник https://unknown.example/path", "[source:invented]"):
        with pytest.raises(AssistantUnavailable):
            validate_source_response(reply, context)


def test_news_source_reference_keeps_receipt_time_and_staleness() -> None:
    context = investment_context({}, news=[{
        "title": "Ставка Банка России", "url": "https://www.cbr.ru/press/1",
        "published_at": "2026-10-07T08:00:00Z", "fetched_at": "2026-10-08T09:00:00Z",
        "freshness": "stale", "raw": "private-field",
    }])
    reference = next(row for row in source_references(context) if row["kind"] == "official_news")
    assert reference["observed_at"] == "2026-10-08T09:00:00Z"
    assert reference["published_at"] == "2026-10-07T08:00:00Z"
    stored = source_read(context, reference["id"])
    assert stored["content"]["freshness"] == "stale"
    assert stored["content"]["fetched_at"] == reference["observed_at"]
    assert "raw" not in stored["content"]


def test_service_stream_persists_real_prefix_and_finishes_once() -> None:
    system, owner, conversation, request = service(), uuid4(), uuid4(), uuid4()
    system.store.update_stream.side_effect = [1, 2, 3]
    with patch.object(system.default_client, "stream", return_value=iter([
        {"delta": "Реальная "}, {"delta": "часть"}, {"result": {"reply": "Реальная часть"}},
    ])) as provider:
        events = list(system.stream(owner, conversation, message="Вопрос", context=None,
                                    request_id=request, expected_version=0))
    assert events[0]["event"] == "accepted"
    prefixes = [event["data"]["reply_prefix"] for event in events if event["event"] == "delta"]
    assert prefixes[0] == "Реальная "
    assert events[-1]["event"] == "complete"
    assert events[-1]["data"]["result"]["reply"] == "Реальная часть"
    assert system.store.finish.call_count == 1
    assert provider.call_count == 1
    assert system.store.update_stream.call_args.args[2] in prefixes


def test_personal_stream_never_exposes_unverified_financial_prefix() -> None:
    system, owner, conversation, request = service(), uuid4(), uuid4(), uuid4()
    system.store.read_request.return_value = {"status": "running"}
    with patch.object(system.default_client, "stream", return_value=iter([
        {"delta": "На счёте 999999 руб."}, {"result": {"reply": "На счёте 999999 руб."}},
    ])):
        events = list(system.stream(owner, conversation, message="Вопрос",
                                    context={"overview": {"nav_rub": "1000"}},
                                    request_id=request, expected_version=0))
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "assistant_evidence_unverified"
    assert all(call.args[2] == "" for call in system.store.update_stream.call_args_list)
    assert "999999" not in json.dumps(events)
    system.store.finish.assert_not_called()
    system.store.uncertain.assert_called_once_with(owner, request)


def test_user_cancel_discards_late_stream_completion_and_returns_durable_state() -> None:
    system, owner, conversation, request = service(), uuid4(), uuid4(), uuid4()
    started, released = Event(), Event()
    system.store.cancel_request.return_value = {"status": "cancelled", "reply_prefix": ""}
    system.store.read_request.return_value = {"status": "cancelled"}

    def delayed(**kwargs):
        started.set()
        assert released.wait(3)
        yield {"result": {"reply": "Late private result"}}

    with patch.object(system.default_client, "stream", side_effect=delayed):
        events = system.stream(owner, conversation, message="Вопрос", context=None,
                               request_id=request, expected_version=0)
        assert started.wait(3)
        assert system.cancel_request(owner, request)["status"] == "cancelled"
        released.set()
        visible = list(events)
    assert visible[-1]["event"] == "cancelled"
    assert "Late private" not in json.dumps(visible)
    system.store.finish.assert_not_called()


def test_completed_stream_replay_never_starts_provider_and_disabled_stream_is_local() -> None:
    system, owner = service(), uuid4()
    system.store.claim.return_value = {"completed": {"reply": "Saved"}}
    with patch.object(system.default_client, "stream") as provider:
        result = list(system.stream(owner, uuid4(), message="Вопрос", context=None,
                                    request_id=uuid4(), expected_version=0))
        assert result[0]["data"]["replayed"] is True
        provider.assert_not_called()
        system.enabled = False
        with pytest.raises(AssistantNotConfigured, match="activation_disabled"):
            system.stream(owner, uuid4(), message="Вопрос", context=None,
                          request_id=uuid4(), expected_version=0)


def test_closing_browser_stream_does_not_restart_or_discard_background_request() -> None:
    system, owner = service(), uuid4()
    started, released, saved = Event(), Event(), Event()

    def delayed(**kwargs):
        started.set()
        assert released.wait(3)
        yield {"result": {"reply": "Сохранённый ответ"}}

    def finish(*args):
        saved.set()
        return args[-1]

    system.store.finish.side_effect = finish
    with patch.object(system.default_client, "stream", side_effect=delayed) as provider:
        stream = system.stream(owner, uuid4(), message="Вопрос", context=None,
                               request_id=uuid4(), expected_version=0)
        assert next(stream)["event"] == "accepted"
        assert started.wait(3)
        stream.close()
        released.set()
        assert saved.wait(3)
    assert provider.call_count == 1
    assert system.store.finish.call_count == 1


def test_shutdown_cancels_only_own_active_requests_and_closes_future_admission() -> None:
    system, owner, request = service(), uuid4(), uuid4()
    entered = Event()
    system.store.read_request.return_value = {"status": "cancelled"}

    def delayed(**kwargs):
        entered.set()
        assert kwargs["cancellation"].event.wait(3)
        yield {"result": {"reply": "Must be discarded"}}

    with patch.object(system.default_client, "stream", side_effect=delayed):
        stream = system.stream(owner, uuid4(), message="Вопрос", context=None,
                               request_id=request, expected_version=0)
        assert entered.wait(3)
        system.close()
        events = list(stream)
    system.store.cancel_request.assert_called_once_with(owner, request)
    assert events[-1]["event"] == "cancelled"
    system.store.finish.assert_not_called()
    with pytest.raises(AssistantNotConfigured, match="shutting_down"):
        system.stream(owner, uuid4(), message="Вопрос", context=None,
                      request_id=uuid4(), expected_version=0)


def test_memory_replay_and_new_request_after_settings_change_do_not_cancel_valid_work() -> None:
    system, owner, memory, request = service(), uuid4(), uuid4(), uuid4()
    control = _Cancellation()
    system._active[(owner, request)] = control
    system.store.save_memory.return_value = {"id": str(memory), "version": 1, "_changed": False}
    replay = system.save_memory(owner, memory, "Кратко", "preference",
                                 expected_version=0, confirmed=True)
    assert "_changed" not in replay
    assert not control.event.is_set()
    system.store.save_memory.return_value = {"id": str(memory), "version": 2, "_changed": True}
    system.store.read_request.return_value = {"status": "running"}
    system.save_memory(owner, memory, "Подробно", "preference", expected_version=1, confirmed=True)
    assert not control.event.is_set()
    system.store.save_memory.return_value = {"id": str(memory), "version": 3, "_changed": True}
    system.store.read_request.return_value = {"status": "cancelled"}
    system.save_memory(owner, memory, "Кратко", "preference", expected_version=2, confirmed=True)
    assert control.event.is_set()


def test_current_valuation_coverage_survives_context_filter_but_legacy_payments_do_not() -> None:
    context = portfolio_context({
        "overview": {"status": "stale", "nav_rub": "1000", "valuation_status": "complete",
                     "sector_status": "partial", "valid_until": "2026-10-07T10:05:00Z"},
        "income": {"status": "unavailable", "metric_coverage": {
            "dividends_rub": {"status": "partial", "value_rub": None,
                              "observed_rub": None, "reason": "fx_unavailable", "secret": "hidden"},
        }, "native_payment_sums": {"USD": {"dividends": "12.5", "secret": "hidden"}}},
    })
    assert context["overview"]["status"] == "stale"
    assert context["overview"]["sector_status"] == "partial"
    assert context["overview"]["valuation_status"] == "complete"
    assert context["overview"]["valid_until"] == "2026-10-07T10:05:00Z"
    assert "income" not in context
    assert "hidden" not in json.dumps(context)
    with pytest.raises(AssistantUnavailable, match="evidence_unverified"):
        validate_source_response("Получено 12,5 USD.", context)
    with pytest.raises(AssistantUnavailable, match="evidence_unverified"):
        validate_source_response("Получено 12,5 руб.", context)
    validate_source_response("Ставка 15%.", {
        "news": [{"title": "Ставка 15%", "url": "https://www.cbr.ru/press/1"}],
    })


def test_saved_sources_preserve_admitted_facts_after_current_context_changes() -> None:
    system, owner, request = service(), uuid4(), uuid4()
    current = {"overview": {"nav_rub": "1000", "observed_at": "2026-10-07T10:00:00Z"}}

    def changed(**kwargs):
        current["overview"]["nav_rub"] = "9999"
        assert kwargs["context"]["overview"]["nav_rub"] == "1000"
        return {"reply": "Стоимость: 1000 руб."}

    with patch.object(system.default_client, "chat", side_effect=changed):
        reply = system.chat(owner, uuid4(), message="Вопрос", context=current,
                            request_id=request, expected_version=0)
    source = reply["sources"][0]
    assert source["content"]["nav_rub"] == "1000"
    assert current["overview"]["nav_rub"] == "9999"
    system.store.read_request.return_value = {"status": "completed", "sources": reply["sources"]}
    saved = system.read_request_source(owner, request, source["id"])
    assert saved["content"] == source["content"]
    assert saved["immutable"] is True
    assert saved["request_id"] == str(request)
    with pytest.raises(WorkspaceNotFound):
        system.read_request_source(owner, request, "missing")


def test_oversized_source_catalog_is_rejected_before_quota_claim_or_provider_use() -> None:
    system, owner = service(), uuid4()
    context = {"overview": {"nav_rub": "1000"}, "_selection": {"scope": "x" * 10000},
               "news": [{"title": f"News {number}", "url": f"https://www.cbr.ru/press/{number}"}
                        for number in range(10)]}
    with patch.object(system.default_client, "chat") as provider, pytest.raises(ValueError):
        system.chat(owner, uuid4(), message="Вопрос", context=context,
                     request_id=uuid4(), expected_version=0)
    system.store.claim.assert_not_called()
    provider.assert_not_called()


@pytest.mark.parametrize("context", [
    {"research": {"observations": [1e308] * 212}},
    {"research": {"measurement": float("nan")}},
    {"research": {"measurement": float("inf")}},
    {"research": {"description": "invalid\x00text"}},
], ids=("expanded_numeric_limit", "nonfinite_nan", "nonfinite_infinity", "null_character"))
def test_unpersistable_sources_never_claim_quota_or_start_provider(context: dict) -> None:
    system, owner = service(), uuid4()
    assert len(json.dumps(context).encode()) < 48000
    with patch.object(system.default_client, "stream") as provider, pytest.raises(ValueError):
        system.stream(owner, uuid4(), message="Вопрос", context=context,
                      request_id=uuid4(), expected_version=0)
    system.store.claim.assert_not_called()
    provider.assert_not_called()
