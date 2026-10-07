"""HTTP authority and optimistic concurrency for the new workspace routes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from omnicio.db import Database, UserRecord
from omnicio.main import CANONICAL_ORIGIN, app
from omnicio.portfolio_store import SettingsVersionConflict
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


def test_workspace_invalid_history_period_does_not_read_storage(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, _ = workspace_http
    response = client.get("/api/workspace", params={"history_period": "unbounded"})
    assert response.status_code == 422
    store.dashboard.assert_not_called()


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
    store.events.assert_called_once_with(OWNER.id, limit=40, unread_only=True, category="payments")
    assert client.get("/api/events?category=unknown").status_code == 422
    response = client.post(
        "/api/events/read", json={"ids": [EVENT], "read": False}, headers=HEADERS
    )
    assert response.status_code == 200
    store.mark_events_read.assert_called_once_with(OWNER.id, [EVENT], read=False)
