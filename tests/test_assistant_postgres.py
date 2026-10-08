"""Actual FORCE-RLS history, quota, and credential custody on disposable PostgreSQL."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from test_workspace_postgres import user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.assistant import (
    AssistantClient,
    AssistantQuotaExceeded,
    AssistantRequestConflict,
    AssistantService,
    AssistantUnavailable,
    _source_catalog,
)
from omnicio.db import Database
from omnicio.portfolio_store import SettingsVersionConflict
from omnicio.workspace_store import WorkspaceNotFound

pytestmark = pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"),
    reason="ephemeral PostgreSQL is required",
)


def setup(database: Database, *, limit: int = 30) -> tuple[AssistantService, UUID, UUID]:
    owner = user(database)
    service = AssistantService(
        database,
        credential_key=Fernet.generate_key().decode(),
        enabled=True,
        allowed_endpoints=("https://model.example.invalid/v1",),
        daily_request_limit=limit,
        default_client=AssistantClient(base_url="https://operator.example.invalid", model="test"),
    )
    conversation = UUID(service.create_conversation(owner)["id"])
    return service, owner, conversation


def test_durable_reply_replay_is_once_and_deleting_history_cannot_reset_quota(workspace_database):
    service, owner, conversation = setup(workspace_database[0], limit=1)
    request = uuid4()
    with patch.object(
        service.default_client,
        "chat",
        return_value={
            "reply": "Ответ",
            "sources": [],
            "usage": {"input_tokens": 7, "output_tokens": 2},
        },
    ) as provider:
        reply = service.chat(
            owner,
            conversation,
            message="Вопрос",
            context=None,
            request_id=request,
            expected_version=0,
        )
        assert reply["version"] == 2
        assert (
            service.chat(
                owner,
                conversation,
                message="Вопрос",
                context=None,
                request_id=request,
                expected_version=0,
            )
            == reply
        )
        assert provider.call_count == 1
    history = service.conversation(owner, conversation)
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
    assert all(m["request_status"] == "completed" for m in history["messages"])
    assert service.delete_conversation(owner, conversation)
    with service.store._transaction(owner) as cur:
        cur.execute("SELECT reply_prefix, source_refs, conversation_id FROM assistant_requests "
                    "WHERE user_id = %s AND id = %s", (owner, request))
        retained = cur.fetchone()
        assert retained["reply_prefix"] == ""
        assert retained["source_refs"] == []
        assert retained["conversation_id"] is None
    assert service.status(owner)["quota"]["remaining"] == 0
    next_conversation = UUID(service.create_conversation(owner)["id"])
    with pytest.raises(AssistantQuotaExceeded):
        service.chat(
            owner,
            next_conversation,
            message="Вопрос",
            context=None,
            request_id=uuid4(),
            expected_version=0,
        )
    with pytest.raises(WorkspaceNotFound):
        service.chat(
            owner,
            conversation,
            message="Вопрос",
            context=None,
            request_id=request,
            expected_version=0,
        )


def test_private_connection_cas_ciphertext_and_forced_rls(workspace_database):
    database = workspace_database[0]
    service, owner, conversation = setup(database)
    other = user(database)
    document = {
        "provider": "openai_compatible",
        "base_url": "https://model.example.invalid/v1",
        "model": "test",
        "api_key": "private-personal-key",
    }
    status = service.save_connection(owner, document, expected_version=0)
    assert status["connection_version"] == 1
    assert status["has_key"]
    assert "private-personal-key" not in str(status)
    ciphertext = service.store.connection(owner)["key_ciphertext"]
    assert b"private-personal-key" not in bytes(ciphertext)
    with pytest.raises(SettingsVersionConflict):
        service.save_connection(owner, {**document, "api_key": "wrong"}, expected_version=0)
    assert bytes(service.store.connection(owner)["key_ciphertext"]) == bytes(ciphertext)
    assert service.list_conversations(other)["items"] == []
    with pytest.raises(WorkspaceNotFound):
        service.conversation(other, conversation)
    assert not service.delete_conversation(other, conversation)
    with database.pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other),))
        for table in (
            "assistant_connections",
            "assistant_conversations",
            "assistant_requests",
            "assistant_messages",
        ):
            # Constant table names only, no caller-supplied SQL identifiers.
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM " + table + " WHERE user_id = %s", (owner,)
                ).fetchone()["n"]
                == 0
            )
    assert service.disconnect(owner, expected_version=1)["configured"] is False
    assert service.store.connection(owner)["key_ciphertext"] is None
    with pytest.raises(SettingsVersionConflict):
        service.save_connection(owner, document, expected_version=0)


def test_duplicate_inflight_request_does_not_cancel_the_original(workspace_database):
    service, owner, conversation = setup(workspace_database[0])
    request, started, finish = uuid4(), Event(), Event()

    def held(**kwargs):
        started.set()
        assert finish.wait(timeout=10)
        return {"reply": "Единственный ответ"}

    with (
        patch.object(service.default_client, "chat", side_effect=held) as provider,
        ThreadPoolExecutor(max_workers=1) as workers,
    ):
        original = workers.submit(
            service.chat,
            owner,
            conversation,
            message="Вопрос",
            context=None,
            request_id=request,
            expected_version=0,
        )
        try:
            assert started.wait(timeout=5)
            with pytest.raises(AssistantRequestConflict, match="running"):
                service.chat(
                    owner,
                    conversation,
                    message="Вопрос",
                    context=None,
                    request_id=request,
                    expected_version=0,
                )
        finally:
            finish.set()
        assert original.result(timeout=10)["reply"] == "Единственный ответ"
    assert provider.call_count == 1
    assert service.status(owner)["quota"]["used"] == 1


def test_failed_provider_is_durable_uncertain_and_never_blindly_retried(workspace_database):
    service, owner, conversation = setup(workspace_database[0])
    request = uuid4()
    with patch.object(service.default_client, "chat", side_effect=AssistantUnavailable) as provider:
        with pytest.raises(AssistantUnavailable):
            service.chat(
                owner,
                conversation,
                message="Вопрос",
                context=None,
                request_id=request,
                expected_version=0,
            )
        with pytest.raises(AssistantRequestConflict, match="uncertain"):
            service.chat(
                owner,
                conversation,
                message="Вопрос",
                context=None,
                request_id=request,
                expected_version=0,
            )
    assert provider.call_count == 1
    history = service.conversation(owner, conversation)
    assert len(history["messages"]) == 1
    assert history["messages"][0]["request_status"] == "uncertain"
    assert service.status(owner)["quota"]["used"] == 1


def test_connection_change_during_provider_discards_answer_and_preserves_quota(workspace_database):
    service, owner, conversation = setup(workspace_database[0])

    def disconnected(**kwargs):
        service.disconnect(owner, expected_version=0)
        return {"reply": "Must never persist"}

    with (
        patch.object(service.default_client, "chat", side_effect=disconnected),
        pytest.raises(AssistantRequestConflict, match="context_changed"),
    ):
        service.chat(
            owner,
            conversation,
            message="Вопрос",
            context=None,
            request_id=uuid4(),
            expected_version=0,
        )
    history = service.conversation(owner, conversation)
    assert [m["content"] for m in history["messages"]] == ["Вопрос"]
    assert history["messages"][0]["request_status"] == "cancelled"
    assert service.status(owner)["quota"]["used"] == 1


def test_stale_claim_and_changed_selection_cannot_trigger_duplicate_external_work(
    workspace_database,
):
    service, owner, conversation = setup(workspace_database[0])
    request = uuid4()
    with patch.object(service.default_client, "chat", return_value={"reply": "Ответ"}) as provider:
        service.chat(
            owner,
            conversation,
            message="Вопрос",
            context={"_selection": {"scope": "one"}},
            request_id=request,
            expected_version=0,
        )
        with pytest.raises(AssistantRequestConflict, match="input_changed"):
            service.chat(
                owner,
                conversation,
                message="Вопрос",
                context={"_selection": {"scope": "two"}},
                request_id=request,
                expected_version=0,
            )
    assert provider.call_count == 1
    expired = uuid4()
    service.store.claim(
        owner,
        conversation,
        expired,
        message="Ожидание",
        input_hash="a" * 64,
        expected_version=2,
        connection_version=0,
        model="test",
        context_used=False,
        daily_limit=30,
    )
    with workspace_database[0].pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "UPDATE assistant_requests SET created_at = now() - interval '3 minutes', "
            "updated_at = now() - interval '3 minutes' "
            "WHERE user_id = %s AND id = %s",
            (owner, expired),
        )
    history = service.conversation(owner, conversation)
    assert history["messages"][-1]["request_status"] == "uncertain"
    assert service.store.quota(owner, 30)["used"] == 2


def test_memory_is_explicit_versioned_owner_scoped_and_delete_cancels_pending_context(
    workspace_database,
):
    database = workspace_database[0]
    service, owner, conversation = setup(database)
    other, memory, request = user(database), uuid4(), uuid4()
    with pytest.raises(ValueError):
        service.save_memory(owner, memory, "Ответы кратко", "preference",
                            expected_version=0, confirmed=False)
    created = service.save_memory(owner, memory, "Ответы кратко", "preference",
                                  expected_version=0, confirmed=True)
    assert created["version"] == 1
    assert created["origin"] == "explicit"
    assert service.save_memory(owner, memory, "Ответы кратко", "preference",
                               expected_version=0, confirmed=True) == created
    assert service.list_memory(other)["items"] == []
    with pytest.raises(WorkspaceNotFound):
        service.store.selected_memory(other, [memory])
    with pytest.raises(SettingsVersionConflict):
        service.save_memory(owner, memory, "Другой текст", "context",
                            expected_version=0, confirmed=True)
    service.store.claim(owner, conversation, request, message="Вопрос", input_hash="a" * 64,
                        expected_version=0, connection_version=0, model="test", context_used=True,
                        daily_limit=30, memory_versions={str(memory): 1})
    assert service.store.update_stream(owner, request, "Черновик", []) == 1
    with pytest.raises(WorkspaceNotFound):
        service.stream_request(other, request)
    with pytest.raises(WorkspaceNotFound):
        service.cancel_request(other, request)
    assert service.delete_memory(owner, memory, expected_version=1)
    assert service.stream_request(owner, request)["status"] == "cancelled"
    with pytest.raises(AssistantRequestConflict):
        service.store.finish(owner, request, {"reply": "Late result"})
    assert service.list_memory(owner)["items"] == []
    with database.pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other),))
        assert conn.execute(
            "SELECT 1 FROM assistant_memory WHERE user_id = %s", (owner,),
        ).fetchone() is None


def test_memory_update_between_selection_and_claim_cannot_use_deleted_revision(workspace_database):
    service, owner, conversation = setup(workspace_database[0])
    identifier = uuid4()
    service.save_memory(owner, identifier, "Старая заметка", "context", expected_version=0,
                        confirmed=True)
    service.save_memory(owner, identifier, "Новая заметка", "context", expected_version=1,
                        confirmed=True)
    with pytest.raises(AssistantRequestConflict, match="memory_changed"):
        service.store.claim(owner, conversation, uuid4(), message="Вопрос", input_hash="b" * 64,
                            expected_version=0, connection_version=0, model="test",
                            context_used=True,
                            daily_limit=30, memory_versions={str(identifier): 1})
    assert service.conversation(owner, conversation)["version"] == 0
    assert service.store.quota(owner, 30)["used"] == 0


def test_general_question_does_not_receive_previous_attached_personal_context(workspace_database):
    service, owner, conversation = setup(workspace_database[0])
    with patch.object(service.default_client, "chat",
                      return_value={"reply": "Private portfolio text"}):
        service.chat(owner, conversation, message="Мой портфель",
                     context={"overview": {"nav_rub": "1000"}},
                     request_id=uuid4(), expected_version=0)
    with patch.object(service.default_client, "chat",
                      return_value={"reply": "Общее объяснение"}) as model:
        service.chat(owner, conversation, message="Что такое облигация", context=None,
                     request_id=uuid4(), expected_version=2)
    assert model.call_args.kwargs["history"] == []
    history = service.conversation(owner, conversation)
    assert len(history["messages"]) == 4


@pytest.mark.parametrize("next_selection", [
    "general_with_memory", "portfolio_only", "edited_memory", "removed_memory",
])
def test_new_question_carries_only_current_explicit_sources_and_general_history(
    workspace_database, next_selection: str,
):
    service, owner, conversation = setup(workspace_database[0])
    memory, personal_request, next_request = uuid4(), uuid4(), uuid4()
    service.save_memory(owner, memory, "OLD MEMORY NOTE", "context",
                        expected_version=0, confirmed=True)
    with patch.object(service.default_client, "chat", side_effect=[
        {"reply": "GENERAL ANSWER"}, {"reply": "PERSONAL ANSWER"}, {"reply": "CURRENT ANSWER"},
    ]) as provider:
        general = service.chat(owner, conversation, message="GENERAL QUESTION", context=None,
                               request_id=uuid4(), expected_version=0)
        personal = service.chat(owner, conversation, message="PERSONAL QUESTION",
            context={"overview": {"nav_rub": "12345"}, "goals": [{"name": "PRIVATE GOAL"}],
                     "research": {"status": "PRIVATE RESEARCH"}},
            memory_ids=[memory], request_id=personal_request, expected_version=general["version"])
        context = None
        memory_ids = [memory]
        if next_selection == "portfolio_only":
            context, memory_ids = {"overview": {"nav_rub": "1000"}}, []
        elif next_selection == "edited_memory":
            service.save_memory(owner, memory, "NEW MEMORY NOTE", "context",
                                expected_version=1, confirmed=True)
        elif next_selection == "removed_memory":
            assert service.delete_memory(owner, memory, expected_version=1)
            memory_ids = []
        reply = service.chat(owner, conversation, message="CURRENT QUESTION", context=context,
            memory_ids=memory_ids, request_id=next_request, expected_version=personal["version"])
        sent = provider.call_args.kwargs
        assert sent["history"] == [
            {"role": "user", "content": "GENERAL QUESTION"},
            {"role": "assistant", "content": "GENERAL ANSWER"},
        ]
        serialized = json.dumps(sent, ensure_ascii=False)
        for excluded in (
            "PERSONAL QUESTION", "PERSONAL ANSWER", "PRIVATE GOAL", "PRIVATE RESEARCH",
        ):
            assert excluded not in serialized
        if next_selection == "general_with_memory":
            assert sent["context"]["_memory"][0]["content"] == "OLD MEMORY NOTE"
        else:
            assert "OLD MEMORY NOTE" not in serialized
        if next_selection == "edited_memory":
            assert sent["context"]["_memory"][0]["content"] == "NEW MEMORY NOTE"
        if next_selection == "portfolio_only":
            assert sent["context"]["overview"]["nav_rub"] == "1000"
        replay = service.chat(owner, conversation, message="CURRENT QUESTION", context=context,
            memory_ids=memory_ids, request_id=next_request, expected_version=personal["version"])
    assert reply == replay
    assert provider.call_count == 3
    assert reply["version"] == personal["version"] + 2
    assert service.store.quota(owner, 30)["used"] == 3
    assert "PERSONAL ANSWER" in json.dumps(service.conversation(owner, conversation), default=str)
    saved_memory = next(source for source in personal["sources"]
                        if source["kind"] == "explicit_memory")
    saved = service.read_request_source(owner, personal_request, saved_memory["id"])
    assert saved["content"]["content"] == "OLD MEMORY NOTE"


def test_durable_stream_prefix_cancel_and_completed_readback_do_not_restart_provider(
    workspace_database,
):
    service, owner, conversation = setup(workspace_database[0])
    request = uuid4()
    with patch.object(service.default_client, "stream", return_value=iter([
        {"delta": "Первая "}, {"delta": "часть"}, {"result": {"reply": "Первая часть"}},
    ])) as model:
        events = list(service.stream(owner, conversation, message="Вопрос", context=None,
                                     request_id=request, expected_version=0))
        assert events[-1]["event"] == "complete"
        read = service.stream_request(owner, request)
        assert read["status"] == "completed"
        assert read["reply_prefix"] == "Первая часть"
        assert read["stream_sequence"] >= 3
        assert service.cancel_request(owner, request)["status"] == "completed"
        replay = list(service.stream(owner, conversation, message="Вопрос", context=None,
                                     request_id=request, expected_version=0))
        assert replay[-1]["data"]["result"] == read["result"]
    assert model.call_count == 1


def test_completed_evidence_above_legacy_eight_kib_is_readable_and_tenant_scoped(
    workspace_database,
):
    service, owner, conversation = setup(workspace_database[0])
    other, request = user(workspace_database[0]), uuid4()
    context = {"news": [
        {"title": f"Публикация {number}", "summary": "Подтверждённый текст. " * 30,
         "url": f"https://www.cbr.ru/press/{number}", "published_at": "2026-10-07T10:00:00Z"}
        for number in range(10)
    ]}
    with patch.object(service.default_client, "chat", return_value={"reply": "Источник приложен"}):
        result = service.chat(owner, conversation, message="Покажи источники", context=context,
                              request_id=request, expected_version=0)
    assert 8192 < len(json.dumps(result["sources"], ensure_ascii=False).encode()) <= 65536
    source_id = result["sources"][0]["id"]
    record = service.read_request_source(owner, request, source_id)
    assert record["content"] == context["news"][0]
    assert record["immutable"] is True
    with pytest.raises(WorkspaceNotFound):
        service.read_request_source(other, request, source_id)
    assert service.delete_conversation(owner, conversation)
    with pytest.raises(WorkspaceNotFound):
        service.read_request_source(owner, request, source_id)


def test_source_boundary_matches_postgresql_before_quota_and_in_both_durable_copies(
    workspace_database,
):
    service, owner, conversation = setup(workspace_database[0], limit=1)
    context = {"research": {"observations": [1e308] * 200,
                            "description": "Факты ₽ — исходный текст", "padding": ""}}
    with service.store._transaction(owner) as cur:
        cur.execute("SELECT octet_length(%s::jsonb::text) AS size",
                    (json.dumps(_source_catalog(context), ensure_ascii=False),))
        size = cur.fetchone()["size"]
    context["research"]["padding"] = "x" * (65536 - size)
    with service.store._transaction(owner) as cur:
        encoded = json.dumps(_source_catalog(context), ensure_ascii=False)
        cur.execute("SELECT octet_length(%s::jsonb::text) AS size", (encoded,))
        assert cur.fetchone()["size"] == 65536
    assert len(encoded.encode()) < 10000  # E-notation is small on the wire, large in JSONB text.
    oversized = {"research": {**context["research"],
                              "padding": context["research"]["padding"] + "x"}}
    request = uuid4()
    with patch.object(service.default_client, "stream", return_value=iter([
        {"delta": "Источник приложен"}, {"result": {"reply": "Источник приложен"}},
    ])) as provider:
        with pytest.raises(ValueError, match="assistant_sources_too_large"):
            service.stream(owner, conversation, message="Источники", context=oversized,
                           request_id=uuid4(), expected_version=0)
        assert service.store.quota(owner, 1)["used"] == 0
        provider.assert_not_called()
        events = list(service.stream(owner, conversation, message="Источники", context=context,
                                     request_id=request, expected_version=0))
    assert events[-1]["event"] == "complete"
    assert service.store.quota(owner, 1)["used"] == 1
    provider.assert_called_once()
    with service.store._transaction(owner) as cur:
        cur.execute(
            "SELECT octet_length(r.source_refs::text) AS request_size, "
            "octet_length(m.sources::text) AS message_size FROM assistant_requests r "
            "JOIN assistant_messages m ON r.user_id = m.user_id AND r.id = m.request_id "
            "WHERE r.user_id = %s AND r.id = %s AND m.role = 'assistant'",
            (owner, request),
        )
        sizes = cur.fetchone()
    assert sizes["request_size"] == 65536
    assert sizes["message_size"] == 65536
