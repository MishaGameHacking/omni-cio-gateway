"""Actual FORCE-RLS history, quota, and credential custody on disposable PostgreSQL."""

from __future__ import annotations

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
            "UPDATE assistant_requests SET created_at = now() - interval '3 minutes' "
            "WHERE user_id = %s AND id = %s",
            (owner, expired),
        )
    history = service.conversation(owner, conversation)
    assert history["messages"][-1]["request_status"] == "uncertain"
    assert service.store.quota(owner, 30)["used"] == 2
