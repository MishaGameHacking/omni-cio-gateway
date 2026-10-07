"""HTTP authority and optimistic concurrency for the new workspace routes."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from omnicio.assistant import AssistantService
from omnicio.db import Database, UserRecord
from omnicio.main import CANONICAL_ORIGIN, app
from omnicio.market import MarketService
from omnicio.notifications import (
    NotificationConflict,
    NotificationRateLimited,
    NotificationService,
)
from omnicio.portfolio_store import SettingsVersionConflict
from omnicio.research_store import ResearchNotFound, ResearchStore
from omnicio.security import session_digest
from omnicio.service import AuthService
from omnicio.workspace_store import WorkspaceNotFound, WorkspaceStore

OWNER = UserRecord(UUID(int=501), 501, "active", "user")
OTHER = UserRecord(UUID(int=502), 502, "active", "user")
GOAL = UUID(int=601)
EVENT = "a" * 64
HEADERS = {"origin": CANONICAL_ORIGIN, "X-Omnicio-Profile": "000000501"}
WRITES = (
    ("PUT", "/api/preferences", {"document": {}, "expected_version": 3}, "save_preferences"),
    ("POST", "/api/goals", {"document": {}}, "create_goal"),
    ("PUT", f"/api/goals/{GOAL}", {"document": {}, "expected_version": 3}, "update_goal"),
    ("DELETE", f"/api/goals/{GOAL}", {"expected_version": 3}, "delete_goal"),
    ("POST", "/api/events/read", {"ids": [EVENT], "read": True}, "mark_events_read"),
)


@pytest.fixture
def workspace_http() -> Iterator[tuple[TestClient, Mock, Mock, Mock]]:
    auth = Mock(spec=AuthService)
    auth.refresh_session.side_effect = lambda token: {"owner": OWNER, "other": OTHER}.get(token)
    auth.legal_versions.return_value = {"terms": "test-current"}
    database = Mock(spec=Database)
    database.has_legal_versions.return_value = True
    store = Mock(spec=WorkspaceStore)
    for method in (
        "dashboard",
        "preferences",
        "goals",
        "events",
        "save_preferences",
        "create_goal",
        "update_goal",
        "mark_events_read",
    ):
        getattr(store, method).return_value = {"fixture": method}
    store.delete_goal.return_value = True
    # No lifespan: these tests neither open a real database nor run an observer.
    with (
        patch.object(app.state, "auth_service", auth, create=True),
        patch.object(app.state, "database", database, create=True),
        patch.object(app.state, "workspace_store", store, create=True),
    ):
        client = TestClient(app, base_url=CANONICAL_ORIGIN, cookies={"omnicio_session": "owner"})
        try:
            yield client, auth, store, database
        finally:
            client.close()


def test_event_summary_and_filtered_operations_use_the_current_session_owner(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    store.events_summary.return_value = {"unread_total": 82, "categories": {"assets": 2}}
    result = client.get("/api/events/summary", headers=HEADERS)
    assert result.status_code == 200
    assert result.json()["unread_total"] == 82
    store.events_summary.assert_called_once_with(OWNER.id)
    result = client.get("/api/events?important_only=true&category=assets", headers=HEADERS)
    assert result.status_code == 200
    assert store.events.call_args.kwargs["important_only"] is True
    assert store.events.call_args.kwargs["category"] == "assets"
    store.operations.return_value = {"items": [], "next_cursor": None}
    result = client.get("/api/workspace/operations", headers=HEADERS, params={
        "from_at": "2026-09-01T00:00:00Z", "to_at": "2026-10-01T00:00:00Z",
        "limit": 25, "cursor": "saved-cursor", "user_id": str(OTHER.id),
    })
    assert result.status_code == 200
    store.operations.assert_called_once_with(
        OWNER.id, from_at=datetime(2026, 9, 1, tzinfo=UTC),
        to_at=datetime(2026, 10, 1, tzinfo=UTC), limit=25, cursor="saved-cursor",
    )


def test_push_http_binding_comes_from_the_authenticated_session_only(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, _, _ = workspace_http
    service = Mock(spec=NotificationService)
    service.subscribe_push.return_value = {
        "id": str(GOAL), "status": "active", "binding_id": str(UUID(int=900)),
        "current_session": True,
    }
    service.status.return_value = {"channels": [], "push_configured": True}
    service.test_push.return_value = {"id": str(UUID(int=901)), "status": "queued"}
    with patch.object(app.state, "notification_service", service, create=True):
        subscribed = client.post("/api/notifications/push", headers=HEADERS, json={
            "subscription": {"synthetic": True}, "intent": "sync", "label": "My device",
        })
        assert subscribed.status_code == 200
        assert subscribed.json()["current_session"] is True
        service.subscribe_push.assert_called_once_with(
            OWNER.id, {"synthetic": True}, label="My device", intent="sync",
            session_digest=session_digest("owner"),
        )
        assert client.get("/api/notifications", headers=HEADERS).status_code == 200
        service.status.assert_called_once_with(OWNER.id, session_digest=session_digest("owner"))
        assert client.post("/api/notifications/push/test", headers=HEADERS, json={
            "channel_id": str(GOAL),
        }).status_code == 200
        service.test_push.assert_called_once_with(
            OWNER.id, GOAL, session_digest=session_digest("owner"),
        )
        injected = client.post("/api/notifications/push", headers=HEADERS, json={
            "subscription": {}, "session_digest": "other", "user_id": str(OTHER.id),
        })
    assert injected.status_code == 422
    assert service.subscribe_push.call_count == 1


@pytest.mark.parametrize(("error", "status", "detail"), [
    (NotificationConflict("notification_device_conflict"), 409, "notification_device_conflict"),
    (NotificationRateLimited("notification_test_rate_limited"), 429,
     "notification_test_rate_limited"),
    (PermissionError("private-session-details"), 401, "session_expired"),
])
def test_push_http_safe_failures_preserve_explicit_status(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], error: Exception, status: int, detail: str,
) -> None:
    client, _, _, _ = workspace_http
    service = Mock(spec=NotificationService)
    service.test_push.side_effect = error
    with patch.object(app.state, "notification_service", service, create=True):
        response = client.post("/api/notifications/push/test", headers=HEADERS,
                               json={"channel_id": str(GOAL)})
    assert response.status_code == status
    assert response.json()["detail"] == detail
    assert "private-session-details" not in response.text
    if status == 429:
        assert response.headers["retry-after"] == "60"


def test_push_test_requires_current_legal_profile_and_rechecks_after_queueing(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, database = workspace_http
    service = Mock(spec=NotificationService)

    def queued(*args: Any, **kwargs: Any) -> dict[str, Any]:
        auth.refresh_session.side_effect = None
        auth.refresh_session.return_value = OTHER
        return {"id": "private-outbox-id", "status": "queued"}

    service.test_push.side_effect = queued
    with patch.object(app.state, "notification_service", service, create=True):
        body = {"channel_id": str(GOAL)}
        assert client.post("/api/notifications/push/test", json=body).status_code == 403
        database.has_legal_versions.return_value = False
        assert client.post("/api/notifications/push/test", headers=HEADERS,
                           json=body).status_code == 409
        service.test_push.assert_not_called()
        database.has_legal_versions.return_value = True
        response = client.post("/api/notifications/push/test", headers=HEADERS, json=body)
    assert response.status_code == 409
    assert "private-outbox-id" not in response.text


def test_quote_batch_rechecks_profile_before_disclosing_the_result(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, _ = workspace_http
    market = Mock(spec=MarketService)

    def read(owner: UUID, uids: tuple[str, ...]) -> dict[str, Any]:
        assert owner == OWNER.id
        assert uids == ("uid-a", "uid-b")
        auth.refresh_session.side_effect = None
        auth.refresh_session.return_value = OTHER
        return {"private_quote_marker": "100.25"}

    market.batch_quotes.side_effect = read
    with patch.object(app.state, "market_service", market, create=True):
        response = client.get("/api/market/quotes?instrument_uids=uid-a,uid-b", headers=HEADERS)
    assert response.status_code == 409
    assert "private_quote_marker" not in response.text
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("path", ["messages", "messages/stream"])
def test_disabled_assistant_rejects_before_collecting_personal_context(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], path: str,
) -> None:
    client, _, store, _ = workspace_http
    assistant = Mock(spec=AssistantService)
    assistant.status.return_value = {"enabled": False, "configured": True}
    with patch.object(app.state, "assistant_service", assistant, create=True):
        result = client.post(f"/api/assistant/{path}", headers=HEADERS, json={
            "conversation_id": str(UUID(int=700)), "request_id": str(UUID(int=701)),
            "expected_version": 0, "message": "Вопрос о счёте", "context": "portfolio",
        })
    assert result.status_code == 503
    assert result.json()["detail"] == "assistant_activation_disabled"
    store.dashboard.assert_not_called()
    assistant.chat.assert_not_called()
    assistant.stream.assert_not_called()


def test_saved_answer_source_is_owner_bound_and_does_not_rebuild_current_facts(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, store, _ = workspace_http
    assistant = Mock(spec=AssistantService)
    request_id = UUID(int=702)
    assistant.read_request_source.return_value = {"immutable": True, "content": "private-source"}
    body = {"request_id": str(request_id), "source_id": "saved-source"}
    with patch.object(app.state, "assistant_service", assistant, create=True):
        denied = client.post("/api/assistant/sources/read", json=body, headers={
            **HEADERS, "origin": "https://untrusted.invalid",
        })
        assert denied.status_code == 403
        assistant.read_request_source.assert_not_called()
        response = client.post("/api/assistant/sources/read", headers=HEADERS, json=body)
        assert response.status_code == 200
        assert response.json()["immutable"] is True
        assistant.read_request_source.assert_called_once_with(OWNER.id, request_id, "saved-source")
        store.dashboard.assert_not_called()

        def late_source(*args: Any) -> dict[str, str]:
            auth.refresh_session.side_effect = None
            auth.refresh_session.return_value = OTHER
            return {"content": "private-source"}

        assistant.read_request_source.side_effect = late_source
        response = client.post("/api/assistant/sources/read", headers=HEADERS, json=body)
        assert response.status_code == 409
        assert "private-source" not in response.text


def test_assistant_cancel_works_with_old_build_and_stale_consent_without_new_provider_work(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, database = workspace_http
    assistant = Mock(spec=AssistantService)
    request_id = UUID(int=703)
    assistant.cancel_request.return_value = {"id": str(request_id), "status": "cancelled"}
    database.has_legal_versions.return_value = False
    with (
        patch.object(app.state, "assistant_service", assistant, create=True),
        patch.object(app.state, "settings", SimpleNamespace(release_build="a" * 12), create=True),
    ):
        result = client.post(f"/api/assistant/requests/{request_id}/cancel", headers=HEADERS)
    assert result.status_code == 200
    assert result.json()["status"] == "cancelled"
    assistant.cancel_request.assert_called_once_with(OWNER.id, request_id)
    store.dashboard.assert_not_called()
    assistant.stream.assert_not_called()


def test_assistant_memory_version_origin_consent_and_account_loss_boundaries(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, _, database = workspace_http
    assistant = Mock(spec=AssistantService)
    ident = UUID(int=704)
    note = {"id": str(ident), "content": "Предпочитаю краткие ответы", "category": "preference",
            "expected_version": 0, "confirmed": True}
    assistant.save_memory.return_value = {"id": str(ident), "version": 1}
    assistant.delete_memory.return_value = True
    with patch.object(app.state, "assistant_service", assistant, create=True):
        created = client.post("/api/assistant/memory", headers=HEADERS, json=note)
        assert created.status_code == 200
        assistant.save_memory.assert_called_once_with(
            OWNER.id, ident, note["content"], "preference", expected_version=0, confirmed=True,
        )
        rejected = client.put(f"/api/assistant/memory/{ident}", headers=HEADERS, json=note)
        assert rejected.status_code == 422
        assert assistant.save_memory.call_count == 1
        database.has_legal_versions.return_value = False
        rejected = client.delete(f"/api/assistant/memory/{ident}", headers=HEADERS)
        assert rejected.status_code == 422  # The missing version body is never guessed.
        rejected = client.request("DELETE", f"/api/assistant/memory/{ident}", headers=HEADERS,
                                  json={"expected_version": 1})
        assert rejected.status_code == 409
        assistant.delete_memory.assert_not_called()
        assistant.list_memory.side_effect = PermissionError("private database context")
        expired = client.get("/api/assistant/memory", headers=HEADERS)
        assert expired.status_code == 401
        assert expired.json()["detail"] == "authentication required"
        assert "private database context" not in expired.text


@pytest.mark.parametrize(
    ("path", "method"),
    (
        ("/api/workspace", "dashboard"),
        ("/api/preferences", "preferences"),
        ("/api/goals", "goals"),
        ("/api/events", "events"),
    ),
)
def test_workspace_reads_use_session_owner_and_never_query_identity(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
    path: str,
    method: str,
) -> None:
    client, _, store, _ = workspace_http
    first = client.get(path, params={"user_id": str(OTHER.id), "public_id": "000000502"})
    assert first.status_code == 200
    assert first.headers["cache-control"] == "private, no-store"
    assert getattr(store, method).call_args.args == (OWNER.id,)
    client.cookies.set("omnicio_session", "other")
    second = client.get(path, params={"user_id": str(OWNER.id)})
    assert second.status_code == 200
    assert getattr(store, method).call_args.args == (OTHER.id,)
    before = getattr(store, method).call_count
    stale = client.get(path, headers=HEADERS)
    assert stale.status_code == 409
    assert getattr(store, method).call_count == before


def test_workspace_history_period_reaches_only_the_current_owner(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    response = client.get(
        "/api/workspace", params={"history_period": "1d", "user_id": str(OTHER.id)}
    )
    assert response.status_code == 200
    store.dashboard.assert_called_once_with(OWNER.id, history_period="1d")
    store.dashboard.reset_mock()
    response = client.get("/api/workspace")
    assert response.status_code == 200
    store.dashboard.assert_called_once_with(OWNER.id, history_period="all")


@pytest.mark.parametrize("configured_id,expected", [(None, False), (OTHER.id, False),
                                                    (OWNER.id, True)])
def test_operational_capability_comes_from_server_identity_only(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], configured_id: UUID | None,
    expected: bool,
) -> None:
    client = workspace_http[0]
    with patch.object(app.state, "settings", SimpleNamespace(
        operator_user_id=configured_id, session_ttl_seconds=3600,
    ), create=True):
        result = client.get("/api/me", params={
            "can_view_operational_metrics": "true", "operator_user_id": str(OWNER.id),
            "role": "owner",
        })
    assert result.status_code == 200
    assert result.json()["can_view_operational_metrics"] is expected
    assert "operator_user_id" not in result.json()


def test_research_http_uses_real_admission_before_any_provider_or_archive_work(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, database = workspace_http
    document = {"request_id": str(UUID(int=1701)),
                "expected_public_id": "000000501", "expected_version": 3,
                "from_at": "2025-01-01T00:00:00Z", "to_at": "2026-01-01T00:00:00Z",
                "commission_bps": "10", "slippage_bps": "10", "initial_capital_rub": "100000"}
    database.strategy_assessment_slot.return_value = nullcontext(False)
    with patch("omnicio.main.strategy_research") as calculate:
        busy = client.post("/api/profile/strategy/research", json=document, headers=HEADERS)
    assert busy.status_code == 429
    assert busy.headers["retry-after"] == "10"
    calculate.assert_not_called()
    database.strategy_assessment_slot.assert_called_once_with(OWNER.id)

    def changed_profile(**kwargs: Any) -> dict[str, str]:
        assert kwargs["user_id"] == OWNER.id
        assert kwargs["request_id"] == UUID(int=1701)
        auth.refresh_session.side_effect = None
        auth.refresh_session.return_value = OTHER
        return {"private_research": "discard-late-result"}

    database.strategy_assessment_slot.return_value = nullcontext(True)
    with (
        patch("omnicio.main.strategy_research", side_effect=changed_profile),
        patch.object(app.state, "portfolio_store", Mock(), create=True),
        patch.object(app.state, "broker_service", Mock(), create=True),
        patch.object(app.state, "research_store", Mock(), create=True),
        patch.object(app.state, "market_service", Mock(), create=True),
    ):
        late = client.post("/api/profile/strategy/research", json=document, headers=HEADERS)
    assert late.status_code == 409
    assert "private_research" not in late.text


def test_research_archive_page_and_request_status_use_current_owner_and_recheck_session(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, _ = workspace_http
    research = Mock(spec=ResearchStore)
    ident = UUID(int=1702)
    research.runs_page.return_value = {"items": [], "next_cursor": None, "capacity": {
        "runs_used": 0, "runs_limit": 200, "storage_used_bytes": 0,
        "storage_limit_bytes": 256 * 1024 * 1024,
    }, "recent_request": None}
    research.request.return_value = {"id": str(ident), "status": "running", "run_id": None}
    with patch.object(app.state, "research_store", research, create=True):
        page = client.get("/api/research/runs", params={"cursor": str(ident), "limit": 25,
                                                       "user_id": str(OTHER.id)})
        assert page.status_code == 200
        assert page.json()["capacity"]["runs_limit"] == 200
        research.runs_page.assert_called_once_with(OWNER.id, limit=25, cursor=ident)
        request = client.get(f"/api/research/requests/{ident}?user_id={OTHER.id}")
        assert request.status_code == 200
        research.request.assert_called_once_with(OWNER.id, ident)
        research.request.side_effect = ResearchNotFound("research_request_not_found")
        assert client.get(f"/api/research/requests/{ident}").status_code == 404

        def changed_owner(*args: Any, **kwargs: Any) -> dict[str, str]:
            auth.refresh_session.side_effect = None
            auth.refresh_session.return_value = OTHER
            return {"private_request": "must-not-cross-profile"}

        research.request.side_effect = changed_owner
        result = client.get(f"/api/research/requests/{ident}")
        assert result.status_code == 409
        assert "private_request" not in result.text


@pytest.mark.parametrize("code", ["research_archive_capacity", "research_archive_storage_capacity",
                                  "research_archive_too_large", "research_request_capacity",
                                  "research_window_invalid", "research_held_universe_too_large",
                                  "research_cashflow_overlap_requires_complete_history",
                                  "synthetic-private-provider-error"])
def test_research_capacity_errors_are_actionable_without_releasing_arbitrary_exception_text(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], code: str,
) -> None:
    client, _, _, database = workspace_http
    database.strategy_assessment_slot.return_value = nullcontext(True)
    body = {"request_id": str(UUID(int=1703)), "expected_public_id": "000000501",
            "expected_version": 3, "from_at": "2025-01-01T00:00:00Z",
            "to_at": "2026-01-01T00:00:00Z", "commission_bps": "10", "slippage_bps": "10",
            "initial_capital_rub": "100000"}
    with (
        patch("omnicio.main.strategy_research", side_effect=ValueError(code)),
        patch.object(app.state, "portfolio_store", Mock(), create=True),
        patch.object(app.state, "broker_service", Mock(), create=True),
        patch.object(app.state, "research_store", Mock(), create=True),
        patch.object(app.state, "market_service", Mock(), create=True),
    ):
        response = client.post("/api/profile/strategy/research", json=body, headers=HEADERS)
    assert response.status_code == 422
    expected = code if code.startswith("research_") else "research_parameters_invalid"
    assert response.json()["detail"] == expected


def test_workspace_invalid_history_period_does_not_read_storage(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    response = client.get("/api/workspace", params={"history_period": "unbounded"})
    assert response.status_code == 422
    store.dashboard.assert_not_called()


@pytest.mark.parametrize("configured_id", (None, OTHER.id))
def test_metrics_reject_disabled_or_other_operator_even_with_claimed_identity(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], configured_id: UUID | None,
) -> None:
    client, _, _, database = workspace_http
    with patch.object(app.state, "settings", SimpleNamespace(
        operator_user_id=configured_id,
    ), create=True):
        result = client.get("/api/system/metrics", params={
            "user_id": str(OWNER.id), "role": "owner", "operator_user_id": str(OWNER.id),
        })
    assert result.status_code == 403
    database.operational_metrics.assert_not_called()


def test_metrics_require_configured_identity_and_recheck_session_after_collection(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, database = workspace_http
    database.operational_metrics.return_value = {"queues": {"pending": 2}}
    with patch.object(app.state, "settings", SimpleNamespace(
        operator_user_id=OWNER.id,
    ), create=True):
        result = client.get("/api/system/metrics", headers=HEADERS)
        assert result.status_code == 200
        assert result.json() == {"queues": {"pending": 2}}
        database.operational_metrics.assert_called_once_with(
            OWNER.id, session_digest("owner"), configured_operator_id=OWNER.id,
        )
        auth.refresh_session.side_effect = [OWNER, None]
        revoked = client.get("/api/system/metrics", headers=HEADERS)
    assert revoked.status_code == 401
    assert "queues" not in revoked.text
    assert revoked.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(
    ("path", "consumer"),
    (("/api/workspace", "dashboard"), ("/api/preferences", "preferences"),
     ("/api/goals", "goals"), ("/api/events", "events")),
)
@pytest.mark.parametrize(("replacement", "expected_status"), ((None, 401), (OTHER, 409)))
def test_workspace_read_discards_private_payload_after_session_changes_during_storage(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], path: str, consumer: str,
    replacement: UserRecord | None, expected_status: int,
) -> None:
    client, auth, store, _ = workspace_http

    def read(user_id: UUID, **kwargs: object) -> dict[str, str]:
        assert user_id == OWNER.id
        auth.refresh_session.side_effect = None
        auth.refresh_session.return_value = replacement
        return {"private_owner_payload": "synthetic"}

    getattr(store, consumer).side_effect = read
    response = client.get(path, headers=HEADERS)
    assert response.status_code == expected_status
    assert "private_owner_payload" not in response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert getattr(store, consumer).call_count == 1
    assert auth.refresh_session.call_count == 2


@pytest.mark.parametrize(("method", "path", "body", "consumer"), WRITES)
@pytest.mark.parametrize(("change", "expected_status"), (
    ("logout", 401), ("profile", 409), ("consent", 409),
))
def test_workspace_write_rechecks_session_and_consent_before_returning_saved_data(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], method: str, path: str,
    body: dict[str, Any], consumer: str, change: str, expected_status: int,
) -> None:
    client, auth, store, database = workspace_http
    saved_for: list[UUID] = []

    def save(user_id: UUID, *args: object, **kwargs: object) -> dict[str, str] | bool:
        # The initially authorized transaction may already have committed. A
        # late revocation must discard its response, without replaying the write.
        saved_for.append(user_id)
        if change == "consent":
            database.has_legal_versions.return_value = False
        else:
            auth.refresh_session.side_effect = None
            auth.refresh_session.return_value = OTHER if change == "profile" else None
        return True if consumer == "delete_goal" else {"private_owner_payload": "synthetic"}

    getattr(store, consumer).side_effect = save
    response = client.request(method, path, json=body, headers=HEADERS)
    assert response.status_code == expected_status
    if change == "consent":
        # The browser uses this code to require readback after a committed write.
        assert response.json()["detail"] == "updated_legal_consent_required"
    assert "private_owner_payload" not in response.text
    assert "deleted" not in response.json()
    assert saved_for == [OWNER.id]
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(("method", "path", "body", "consumer"), WRITES)
def test_workspace_writes_require_origin_active_session_and_viewed_profile(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
    method: str,
    path: str,
    body: dict[str, Any],
    consumer: str,
) -> None:
    client, _, store, _ = workspace_http
    for headers, expected in (
        ({"X-Omnicio-Profile": "000000501"}, 403),
        ({**HEADERS, "origin": "https://untrusted.invalid"}, 403),
        ({"origin": CANONICAL_ORIGIN}, 409),
        ({**HEADERS, "X-Omnicio-Profile": "000000502"}, 409),
    ):
        response = client.request(method, path, json=body, headers=headers)
        assert response.status_code == expected
    client.cookies.clear()
    rejected = client.request(method, path, json=body, headers=HEADERS)
    assert rejected.status_code == 401
    getattr(store, consumer).assert_not_called()


def test_workspace_crud_forwards_only_session_authority_and_exact_versions(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    for method, path, body, _ in WRITES:
        response = client.request(method, path, json=body, headers=HEADERS)
        assert response.status_code == (201 if path == "/api/goals" else 200)
    store.save_preferences.assert_called_once_with(OWNER.id, {}, expected_version=3)
    store.create_goal.assert_called_once_with(OWNER.id, {})
    store.update_goal.assert_called_once_with(OWNER.id, GOAL, {}, expected_version=3)
    store.delete_goal.assert_called_once_with(OWNER.id, GOAL, expected_version=3)
    store.mark_events_read.assert_called_once_with(OWNER.id, [EVENT], read=True)


@pytest.mark.parametrize(
    ("method", "path", "consumer"),
    (
        ("PUT", "/api/preferences", "save_preferences"),
        ("PUT", f"/api/goals/{GOAL}", "update_goal"),
        ("DELETE", f"/api/goals/{GOAL}", "delete_goal"),
    ),
)
def test_stale_workspace_version_is_409_and_preserves_document(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
    method: str,
    path: str,
    consumer: str,
) -> None:
    client, _, store, _ = workspace_http
    getattr(store, consumer).side_effect = SettingsVersionConflict("settings_version_conflict")
    body: dict[str, Any] = {"expected_version": 3}
    if method == "PUT":
        body["document"] = {}
    response = client.request(method, path, json=body, headers=HEADERS)
    assert response.status_code == 409
    assert response.json() == {"detail": "settings_version_conflict"}


def test_workspace_not_found_and_invalid_document_have_safe_distinct_errors(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    store.update_goal.side_effect = WorkspaceNotFound("private-other-owner-information")
    missing = client.put(
        f"/api/goals/{GOAL}",
        json={"document": {}, "expected_version": 1},
        headers=HEADERS,
    )
    assert missing.status_code == 404
    assert "private-other-owner" not in missing.text
    store.save_preferences.side_effect = ValueError("private-invalid-input")
    invalid = client.put(
        "/api/preferences",
        json={"document": {}, "expected_version": 1},
        headers=HEADERS,
    )
    assert invalid.status_code == 422
    assert "private-invalid-input" not in invalid.text


def test_workspace_rejects_extra_authority_and_coerced_version_before_storage(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    for extra in (
        {"user_id": str(OTHER.id)},
        {"expected_version": True},
        {"expected_version": "1"},
        {"expected_version": -1},
    ):
        response = client.put(
            "/api/preferences",
            json={"document": {}, "expected_version": 1, **extra},
            headers=HEADERS,
        )
        assert response.status_code == 422
    store.save_preferences.assert_not_called()


def test_workspace_writes_require_current_legal_versions(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, database = workspace_http
    database.has_legal_versions.return_value = False
    response = client.put(
        "/api/preferences",
        json={"document": {}, "expected_version": 0},
        headers=HEADERS,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "updated_legal_consent_required"
    store.save_preferences.assert_not_called()


def test_events_filters_and_durable_read_request_reach_the_owner_store(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    response = client.get("/api/events?limit=40&unread_only=true&category=payments")
    assert response.status_code == 200
    store.events.assert_called_once_with(
        OWNER.id, limit=40, unread_only=True, category="payments", cursor=None, query="",
        important_only=False,
    )
    assert client.get("/api/events?category=unknown").status_code == 422
    response = client.post(
        "/api/events/read", json={"ids": [EVENT], "read": False}, headers=HEADERS
    )
    assert response.status_code == 200
    store.mark_events_read.assert_called_once_with(OWNER.id, [EVENT], read=False)
