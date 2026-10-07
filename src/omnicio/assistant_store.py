"""Private assistant history, encrypted-credential records, and durable request admission."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from .db import Database, live_execution_lock_key
from .portfolio_store import SettingsVersionConflict
from .workspace_store import WorkspaceNotFound

_REQUEST_SQL = "SELECT * FROM assistant_requests WHERE user_id = %s AND id = %s"


def _jsonb_text_size(value: Any) -> int:
    """Conservative UTF-8 size of JSONB text, including numeric E-notation expansion."""
    if isinstance(value, Decimal):
        return len(format(value, "f"))
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("assistant_sources_invalid")
        return len(json.dumps(value, ensure_ascii=False).encode())
    if isinstance(value, dict):
        return 2 + max(0, len(value) - 1) * 2 + sum(
            _jsonb_text_size(key) + 2 + _jsonb_text_size(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return 2 + max(0, len(value) - 1) * 2 + sum(_jsonb_text_size(item) for item in value)
    return len(json.dumps(value))


def assistant_sources_json(sources: object) -> str:
    """One representation/bound for pre-admission validation and both durable copies."""
    if not isinstance(sources, list):
        raise ValueError("assistant_sources_invalid")
    try:
        encoded = json.dumps(sources, ensure_ascii=False, default=str, allow_nan=False)
        encoded.encode()  # Reject invalid UTF-8 before admitting any provider work.
        size = _jsonb_text_size(json.loads(encoded, parse_float=Decimal))
    except (ValueError, TypeError) as error:
        raise ValueError("assistant_sources_invalid") from error
    if size > 65536:
        raise ValueError("assistant_sources_too_large")
    return encoded


class AssistantQuotaExceeded(RuntimeError):
    """A durable per-user daily allowance has been exhausted."""


class AssistantRequestConflict(RuntimeError):
    """A request is running, ambiguous, or no longer describes the same input."""


class AssistantStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    @contextmanager
    def _transaction(self, user_id: UUID) -> Iterator[Any]:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (live_execution_lock_key(user_id),),
            )
            cur.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(user_id),))
            cur.execute("SELECT id FROM users WHERE id = %s AND status = 'active'", (user_id,))
            if cur.fetchone() is None:
                raise PermissionError("account_inactive")
            yield cur

    @staticmethod
    def _connection(cur: Any, user_id: UUID) -> dict[str, Any] | None:
        cur.execute("SELECT * FROM assistant_connections WHERE user_id = %s", (user_id,))
        return cast(dict[str, Any] | None, cur.fetchone())

    def connection(self, user_id: UUID) -> dict[str, Any] | None:
        with self._transaction(user_id) as cur:
            return self._connection(cur, user_id)

    def list_memory(self, user_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT id, content, category, origin, version, created_at, updated_at "
                "FROM assistant_memory WHERE user_id = %s ORDER BY updated_at DESC, id LIMIT 100",
                (user_id,),
            )
            rows = [dict(row) for row in cur.fetchall()]
            for row in rows:
                row["id"] = str(row["id"])
            return {"items": rows, "total": len(rows), "automatic_memory": False}

    def selected_memory(self, user_id: UUID, identifiers: Sequence[UUID]) -> list[dict[str, Any]]:
        if len(identifiers) > 20 or len(set(identifiers)) != len(identifiers):
            raise ValueError("assistant_memory_selection_invalid")
        if not identifiers:
            return []
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT id, content, category, version, updated_at FROM assistant_memory "
                "WHERE user_id = %s AND id = ANY (%s::uuid[]) ORDER BY id",
                (user_id, list(identifiers)),
            )
            rows = [dict(row) for row in cur.fetchall()]
            if len(rows) != len(identifiers):
                raise WorkspaceNotFound("assistant_memory_not_found")
            for row in rows:
                row["id"] = str(row["id"])
            return rows

    def save_memory(
        self, user_id: UUID, memory_id: UUID, content: str, category: str, *,
        expected_version: int, confirmed: bool,
    ) -> dict[str, Any]:
        if (confirmed is not True or not isinstance(content, str)
                or not 1 <= len(content.strip()) <= 1000
                or category not in {"preference", "context"}
                or type(expected_version) is not int or expected_version < 0
                or any(ord(char) < 32 and char not in "\n\t" for char in content)):
            raise ValueError("assistant_memory_invalid")
        content = content.strip()
        with self._transaction(user_id) as cur:
            cur.execute("SELECT * FROM assistant_memory WHERE user_id = %s AND id = %s",
                        (user_id, memory_id))
            previous = cur.fetchone()
            if (previous and expected_version == 0 and previous["version"] == 1
                    and previous["content"] == content and previous["category"] == category):
                return {"_changed": False, **{
                    key: str(previous[key]) if key == "id" else previous[key]
                    for key in ("id", "content", "category", "origin", "version",
                                "created_at", "updated_at")
                }}
            if expected_version != (previous["version"] if previous else 0):
                raise SettingsVersionConflict("settings_version_conflict")
            if previous is None:
                cur.execute("SELECT count(*) AS total FROM assistant_memory WHERE user_id = %s",
                            (user_id,))
                if cur.fetchone()["total"] >= 100:
                    raise ValueError("assistant_memory_limit")
            cur.execute(
                "INSERT INTO assistant_memory (user_id, id, content, category, version) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id, id) DO UPDATE SET "
                "content = EXCLUDED.content, category = EXCLUDED.category, "
                "version = EXCLUDED.version, updated_at = now() "
                "RETURNING id, content, category, origin, version, created_at, updated_at",
                (user_id, memory_id, content, category, expected_version + 1),
            )
            result = dict(cur.fetchone())
            # A model must never finish with a context that the owner has edited
            # or removed. The same user lock serializes this with finish().
            self._cancel_running(cur, user_id)
            result["id"] = str(result["id"])
            result["_changed"] = True
            return result

    def delete_memory(self, user_id: UUID, memory_id: UUID, *, expected_version: int) -> bool:
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("assistant_memory_version_invalid")
        with self._transaction(user_id) as cur:
            cur.execute("SELECT version FROM assistant_memory WHERE user_id = %s AND id = %s",
                        (user_id, memory_id))
            previous = cur.fetchone()
            if previous is None:
                raise WorkspaceNotFound("assistant_memory_not_found")
            if previous["version"] != expected_version:
                raise SettingsVersionConflict("settings_version_conflict")
            cur.execute("DELETE FROM assistant_memory WHERE user_id = %s AND id = %s",
                        (user_id, memory_id))
            self._cancel_running(cur, user_id)
            return True

    @staticmethod
    def _cancel_running(cur: Any, user_id: UUID) -> None:
        cur.execute(
            "UPDATE assistant_requests SET status = 'cancelled', finished_at = now(), "
            "updated_at = now() WHERE user_id = %s AND status = 'running'", (user_id,),
        )

    def save_connection(
        self,
        user_id: UUID,
        document: dict[str, Any],
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            previous = self._connection(cur, user_id)
            if expected_version != (previous["version"] if previous else 0):
                raise SettingsVersionConflict("settings_version_conflict")
            cur.execute(
                "INSERT INTO assistant_connections (user_id, version, active, provider, base_url, "
                "model, key_ciphertext) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET version = EXCLUDED.version, "
                "active = EXCLUDED.active, provider = EXCLUDED.provider, "
                "base_url = EXCLUDED.base_url, "
                "model = EXCLUDED.model, key_ciphertext = EXCLUDED.key_ciphertext, "
                "health_status = 'unchecked', checked_at = NULL, updated_at = now() RETURNING *",
                (
                    user_id,
                    expected_version + 1,
                    document["active"],
                    document["provider"],
                    document["base_url"],
                    document["model"],
                    document.get("key_ciphertext"),
                ),
            )
            result = cast(dict[str, Any], cur.fetchone())
            cur.execute(
                "UPDATE assistant_requests SET status = 'cancelled', finished_at = now() "
                "WHERE user_id = %s AND status = 'running'",
                (user_id,),
            )
            return result

    def begin_health(self, user_id: UUID, version: int) -> bool:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE assistant_connections SET checked_at = now(), health_status = 'unchecked' "
                "WHERE user_id = %s AND version = %s AND active "
                "AND (checked_at IS NULL OR checked_at < now() - interval '30 seconds')",
                (user_id, version),
            )
            return bool(cur.rowcount == 1)

    def save_health(self, user_id: UUID, version: int, health: str) -> bool:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE assistant_connections SET health_status = %s, checked_at = now() "
                "WHERE user_id = %s AND version = %s AND active",
                (health, user_id, version),
            )
            return bool(cur.rowcount == 1)

    def conversations(self, user_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT id, title, version, created_at, updated_at, count(*) OVER() AS total "
                "FROM assistant_conversations WHERE user_id = %s "
                "ORDER BY updated_at DESC, id LIMIT 100",
                (user_id,),
            )
            rows = cast(list[dict[str, Any]], cur.fetchall())
            total = int(rows[0]["total"]) if rows else 0
            for row in rows:
                row["id"] = str(row["id"])
                del row["total"]
            return {"items": rows, "total": total, "truncated": total > len(rows)}

    def create_conversation(self, user_id: UUID, title: str) -> dict[str, Any]:
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError("assistant_title_invalid")
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT count(*) AS n FROM assistant_conversations WHERE user_id = %s", (user_id,)
            )
            if cur.fetchone()["n"] >= 100:
                raise ValueError("assistant_conversation_limit")
            cur.execute(
                "INSERT INTO assistant_conversations (user_id, title) VALUES (%s, %s) "
                "RETURNING id, title, version, created_at, updated_at",
                (user_id, title.strip()),
            )
            result = cast(dict[str, Any], cur.fetchone())
            result["id"] = str(result["id"])
            return result

    def conversation(
        self,
        user_id: UUID,
        conversation_id: UUID,
        *,
        before: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100 or (before is not None and before < 1):
            raise ValueError("assistant_history_page_invalid")
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT id, title, version FROM assistant_conversations "
                "WHERE user_id = %s AND id = %s",
                (user_id, conversation_id),
            )
            result = cast(dict[str, Any] | None, cur.fetchone())
            if result is None:
                raise WorkspaceNotFound("assistant_conversation_not_found")
            cur.execute(
                "SELECT m.position, m.role, m.content, m.sources, m.created_at, m.request_id, "
                "r.status AS request_status FROM assistant_messages m "
                "JOIN assistant_requests r ON r.user_id = m.user_id AND r.id = m.request_id "
                "WHERE m.user_id = %s AND m.conversation_id = %s "
                "AND (%s::int IS NULL OR m.position < %s) "
                "ORDER BY position DESC LIMIT %s",
                (user_id, conversation_id, before, before, limit + 1),
            )
            rows = cast(list[dict[str, Any]], cur.fetchall())
            visible = rows[:limit]
            for row in visible:
                row["request_id"] = str(row["request_id"])
            cur.execute(
                "SELECT id FROM assistant_requests WHERE user_id = %s AND conversation_id = %s "
                "ORDER BY created_at DESC, id DESC LIMIT 1", (user_id, conversation_id),
            )
            latest = cur.fetchone()
            return {
                **result,
                "id": str(result["id"]),
                "messages": list(reversed(visible)),
                "next_before": visible[-1]["position"] if len(rows) > limit else None,
                "latest_request": self._read_request(cur, user_id, latest["id"])
                if latest else None,
            }

    def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> bool:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE assistant_requests SET "
                "status = CASE WHEN status = 'running' THEN 'cancelled' ELSE status END, "
                "finished_at = COALESCE(finished_at, now()), updated_at = now(), "
                "reply_prefix = '', source_refs = '[]'::jsonb "
                "WHERE user_id = %s AND conversation_id = %s",
                (user_id, conversation_id),
            )
            cur.execute(
                "DELETE FROM assistant_conversations WHERE user_id = %s AND id = %s",
                (user_id, conversation_id),
            )
            return bool(cur.rowcount == 1)

    def quota(self, user_id: UUID, daily_limit: int) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            return self._quota(cur, user_id, daily_limit)

    @staticmethod
    def _quota(cur: Any, user_id: UUID, daily_limit: int) -> dict[str, Any]:
        cur.execute(
            "SELECT count(*) AS used, "
            "((date_trunc('day', now() AT TIME ZONE 'UTC') + interval '1 day') AT TIME ZONE 'UTC') "
            "AS resets_at FROM assistant_requests WHERE user_id = %s AND created_at >= "
            "(date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')",
            (user_id,),
        )
        row = cast(dict[str, Any], cur.fetchone())
        return {
            "used": int(row["used"]),
            "limit": daily_limit,
            "remaining": max(0, daily_limit - int(row["used"])),
            "resets_at": row["resets_at"],
        }

    @staticmethod
    def _request_result(cur: Any, user_id: UUID, request: dict[str, Any]) -> dict[str, Any]:
        if request["status"] != "completed":
            raise AssistantRequestConflict("assistant_request_" + request["status"])
        cur.execute(
            "SELECT content, sources, created_at FROM assistant_messages "
            "WHERE user_id = %s AND request_id = %s AND role = 'assistant'",
            (user_id, request["id"]),
        )
        message = cur.fetchone()
        if message is None:
            raise WorkspaceNotFound("assistant_conversation_not_found")
        return {
            "reply": message["content"],
            "sources": message["sources"],
            "created_at": message["created_at"],
            "message_id": str(request["id"]),
            "conversation_id": str(request["conversation_id"]),
            "version": request["conversation_version"] + 1,
            "model": request["model"],
            "context_used": "portfolio" if request["context_used"] else "general",
            "usage": {
                "input_tokens": request["input_tokens"],
                "output_tokens": request["output_tokens"],
            },
        }

    def expire_requests(self, user_id: UUID) -> None:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE assistant_requests SET status = 'uncertain', finished_at = now() "
                "WHERE user_id = %s AND status = 'running' "
                "AND (updated_at < now() - interval '2 minutes' "
                "OR created_at < now() - interval '5 minutes')",
                (user_id,),
            )

    def claim(
        self,
        user_id: UUID,
        conversation_id: UUID,
        request_id: UUID,
        *,
        message: str,
        input_hash: str,
        expected_version: int,
        connection_version: int,
        model: str,
        context_used: bool,
        daily_limit: int,
        memory_versions: Mapping[str, int] | None = None,
    ) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            cur.execute(
                _REQUEST_SQL,
                (user_id, request_id),
            )
            previous = cur.fetchone()
            if previous is not None:
                if previous["input_hash"] != input_hash:
                    raise AssistantRequestConflict("assistant_request_input_changed")
                return {"completed": self._request_result(cur, user_id, previous)}
            current_connection = self._connection(cur, user_id)
            if (current_connection["version"] if current_connection else 0) != connection_version:
                raise SettingsVersionConflict("settings_version_conflict")
            if memory_versions:
                cur.execute(
                    "SELECT id, version FROM assistant_memory WHERE user_id = %s "
                    "AND id = ANY (%s::uuid[])", (user_id, list(memory_versions)),
                )
                current = {str(row["id"]): row["version"] for row in cur.fetchall()}
                if current != dict(memory_versions):
                    raise AssistantRequestConflict("assistant_memory_changed")
            cur.execute(
                "SELECT 1 FROM assistant_requests WHERE user_id = %s AND status = 'running'",
                (user_id,),
            )
            if cur.fetchone() is not None:
                raise AssistantRequestConflict("assistant_request_running")
            if self._quota(cur, user_id, daily_limit)["remaining"] == 0:
                raise AssistantQuotaExceeded("assistant_daily_quota_exceeded")
            cur.execute(
                "UPDATE assistant_conversations SET version = version + 1, updated_at = now() "
                "WHERE user_id = %s AND id = %s AND version = %s RETURNING version",
                (user_id, conversation_id, expected_version),
            )
            updated = cur.fetchone()
            if updated is None:
                raise SettingsVersionConflict("settings_version_conflict")
            version = updated["version"]
            # Attached portfolio/memory evidence is authorized for one request.
            # Past private answers stay readable, but cannot widen a later selection.
            cur.execute(
                "SELECT m.role, m.content FROM assistant_messages m JOIN assistant_requests r "
                "ON r.user_id = m.user_id AND r.id = m.request_id WHERE m.user_id = %s "
                "AND m.conversation_id = %s AND r.status = 'completed' "
                "AND NOT r.context_used ORDER BY m.position DESC LIMIT 20",
                (user_id, conversation_id),
            )
            history = list(reversed(cur.fetchall()))
            while sum(len(item["content"]) for item in history) > 24000:
                history.pop(0)
            cur.execute(
                "INSERT INTO assistant_requests (user_id, id, conversation_id, input_hash, "
                "connection_version, conversation_version, status, context_used, model) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'running', %s, %s)",
                (
                    user_id,
                    request_id,
                    conversation_id,
                    input_hash,
                    connection_version,
                    version,
                    context_used,
                    model,
                ),
            )
            cur.execute(
                "INSERT INTO assistant_messages (user_id, conversation_id, position, request_id, "
                "role, content) VALUES (%s, %s, %s, %s, 'user', %s)",
                (user_id, conversation_id, version, request_id, message),
            )
            return {"history": history, "version": version}

    def read_request(self, user_id: UUID, request_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            return self._read_request(cur, user_id, request_id)

    @classmethod
    def _read_request(cls, cur: Any, user_id: UUID, request_id: UUID) -> dict[str, Any]:
        cur.execute(_REQUEST_SQL, (user_id, request_id))
        request = cur.fetchone()
        if request is None or request["conversation_id"] is None:
            raise WorkspaceNotFound("assistant_request_not_found")
        return {
            "request_id": str(request_id), "conversation_id": str(request["conversation_id"]),
            "status": request["status"], "reply_prefix": request["reply_prefix"],
            "stream_sequence": request["stream_sequence"], "sources": request["source_refs"],
            "created_at": request["created_at"], "updated_at": request["updated_at"],
            "finished_at": request["finished_at"], "version": request["conversation_version"],
            "result": cls._request_result(cur, user_id, request)
            if request["status"] == "completed" else None,
            "incomplete": request["status"] != "completed",
        }

    def cancel_request(self, user_id: UUID, request_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE assistant_requests SET status = 'cancelled', finished_at = now(), "
                "updated_at = now() WHERE user_id = %s AND id = %s AND status = 'running'",
                (user_id, request_id),
            )
            return self._read_request(cur, user_id, request_id)

    def update_stream(
        self, user_id: UUID, request_id: UUID, prefix: str, sources: list[dict[str, Any]],
    ) -> int:
        if len(prefix) > 16000:
            raise ValueError("assistant_stream_invalid")
        source_json = assistant_sources_json(sources)
        with self._transaction(user_id) as cur:
            connection = self._connection(cur, user_id)
            cur.execute(
                "UPDATE assistant_requests SET reply_prefix = %s, source_refs = %s::jsonb, "
                "stream_sequence = stream_sequence + 1, updated_at = now() "
                "WHERE user_id = %s AND id = %s AND status = 'running' "
                "AND connection_version = %s RETURNING stream_sequence",
                (prefix, source_json, user_id, request_id,
                 connection["version"] if connection else 0),
            )
            updated = cur.fetchone()
            if updated is None:
                raise AssistantRequestConflict("assistant_context_changed")
            return int(updated["stream_sequence"])

    def finish(
        self,
        user_id: UUID,
        request_id: UUID,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        source_json = assistant_sources_json(result.get("sources", []))
        with self._transaction(user_id) as cur:
            cur.execute(
                _REQUEST_SQL,
                (user_id, request_id),
            )
            request = cur.fetchone()
            connection = self._connection(cur, user_id)
            if (
                request is None
                or request["status"] != "running"
                or request["conversation_id"] is None
                or request["connection_version"] != (connection["version"] if connection else 0)
            ):
                raise AssistantRequestConflict("assistant_context_changed")
            cur.execute(
                "UPDATE assistant_conversations SET version = version + 1, updated_at = now() "
                "WHERE user_id = %s AND id = %s AND version = %s RETURNING version",
                (user_id, request["conversation_id"], request["conversation_version"]),
            )
            updated = cur.fetchone()
            if updated is None:
                raise AssistantRequestConflict("assistant_context_changed")
            usage = result.get("usage") or {}
            cur.execute(
                "INSERT INTO assistant_messages (user_id, conversation_id, position, request_id, "
                "role, content, sources) VALUES (%s, %s, %s, %s, 'assistant', %s, %s::jsonb)",
                (
                    user_id,
                    request["conversation_id"],
                    updated["version"],
                    request_id,
                    result["reply"],
                    source_json,
                ),
            )
            cur.execute(
                "UPDATE assistant_requests SET status = 'completed', finished_at = now(), "
                "input_tokens = %s, output_tokens = %s, reply_prefix = %s, "
                "source_refs = %s::jsonb, stream_sequence = stream_sequence + 1, "
                "updated_at = now() "
                "WHERE user_id = %s AND id = %s RETURNING *",
                (usage.get("input_tokens"), usage.get("output_tokens"), result["reply"],
                 source_json,
                 user_id, request_id),
            )
            return self._request_result(cur, user_id, cast(dict[str, Any], cur.fetchone()))

    def uncertain(self, user_id: UUID, request_id: UUID) -> None:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE assistant_requests SET status = 'uncertain', finished_at = now() "
                "WHERE user_id = %s AND id = %s AND status = 'running'",
                (user_id, request_id),
            )
