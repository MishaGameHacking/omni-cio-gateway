"""Refresh HTTP ownership, first-connect behavior and worker lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_tid import configuration

from omnicio.broker import BrokerConnectionStatus, BrokerService
from omnicio.db import Database, UserRecord
from omnicio.main import CANONICAL_ORIGIN, app, lifespan
from omnicio.observer import PortfolioRefreshBusy, PortfolioRefreshCoordinator
from omnicio.service import AuthService
from omnicio.tbank import TBankAccount

OWNER = UserRecord(UUID(int=1801), 1801, "active", "user")
OTHER = UserRecord(UUID(int=1802), 1802, "active", "user")
HEADERS = {"origin": CANONICAL_ORIGIN, "X-Omnicio-Profile": "000001801"}
BODY = {"expected_public_id": "000001801"}
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
JOB = {
    "status": "queued", "job_id": "private-owner-job", "requested_at": NOW.isoformat(),
    "started_at": None, "finished_at": None, "observed_at": None, "snapshot_saved": False,
    "history_status": None, "history_pages": 0, "can_refresh": False,
    "retry_after_seconds": 120, "cooldown_until": "2026-10-06T12:02:00+00:00", "reason": None,
}
CONNECT = {
    "credential": "synthetic-user-provider-token", "environment": "prod",
    "account_id": "synthetic-selected-account", "accept_personal_terms": True,
}
PREVIEW = {key: value for key, value in CONNECT.items() if key != "account_id"}


@pytest.fixture
def refresh_http() -> Iterator[tuple[TestClient, Mock, Mock, Mock, Mock]]:
    auth, database = Mock(spec=AuthService), Mock(spec=Database)
    sessions = {"owner": OWNER, "other": OTHER}
    auth.refresh_session.side_effect = sessions.get
    auth.legal_versions.return_value = {"terms": "current"}
    database.has_legal_versions.return_value = True
    refresh = Mock(spec=PortfolioRefreshCoordinator)
    refresh.request.return_value = refresh.status.return_value = JOB
    broker = Mock(spec=BrokerService)
    broker.preview_accounts.return_value = ()
    broker.connect.return_value = BrokerConnectionStatus(
        True, "prod", CONNECT["account_id"], "Synthetic", NOW,
    )
    with (
        patch.object(app.state, "auth_service", auth, create=True),
        patch.object(app.state, "database", database, create=True),
        patch.object(app.state, "settings", configuration(), create=True),
        patch.object(app.state, "portfolio_refresh", refresh, create=True),
        patch.object(app.state, "broker_service", broker, create=True),
    ):
        client = TestClient(app, base_url=CANONICAL_ORIGIN, cookies={"omnicio_session": "owner"})
        try:
            yield client, auth, database, refresh, broker
        finally:
            client.close()


def test_refresh_get_post_are_bound_to_session_and_return_private_status(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock],
) -> None:
    client, _, _, refresh, broker = refresh_http
    response = client.post("/api/workspace/refresh", json=BODY, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {**JOB, "public_id": "000001801"}
    assert response.headers["cache-control"] == "private, no-store"
    refresh.request.assert_called_once_with(OWNER.id)
    response = client.get(
        "/api/workspace/refresh", params={"user_id": str(OTHER.id)}, headers=HEADERS,
    )
    assert response.status_code == 200
    refresh.status.assert_called_once_with(OWNER.id)
    assert broker.mock_calls == []


@pytest.mark.parametrize(
    ("headers", "body", "expected"),
    [
        ({"X-Omnicio-Profile": "000001801"}, BODY, 403),
        ({**HEADERS, "origin": "https://untrusted.invalid"}, BODY, 403),
        (HEADERS, {"expected_public_id": "000001802"}, 409),
        ({**HEADERS, "X-Omnicio-Profile": "000001802"}, BODY, 409),
        (HEADERS, {**BODY, "user_id": str(OTHER.id)}, 422),
        (HEADERS, {**BODY, "account_id": "arbitrary-account"}, 422),
    ],
)
def test_refresh_rejects_origin_stale_owner_and_browser_selected_authority(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock],
    headers: dict[str, str], body: dict[str, Any], expected: int,
) -> None:
    client, _, _, refresh, _ = refresh_http
    response = client.post("/api/workspace/refresh", json=body, headers=headers)
    assert response.status_code == expected
    refresh.request.assert_not_called()


def test_refresh_requires_session_and_current_consent_before_enqueue(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock],
) -> None:
    client, _, database, refresh, _ = refresh_http
    database.has_legal_versions.return_value = False
    assert client.post("/api/workspace/refresh", json=BODY, headers=HEADERS).status_code == 409
    client.cookies.clear()
    assert client.post("/api/workspace/refresh", json=BODY, headers=HEADERS).status_code == 401
    assert client.get("/api/workspace/refresh", headers=HEADERS).status_code == 401
    refresh.request.assert_not_called()
    refresh.status.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("change", ["logout", "other_user"])
def test_refresh_discards_status_after_session_changes_during_store_io(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock], method: str, change: str,
) -> None:
    client, auth, _, refresh, _ = refresh_http

    def revoked(owner: UUID) -> dict[str, Any]:
        auth.refresh_session.side_effect = None
        auth.refresh_session.return_value = None if change == "logout" else OTHER
        return JOB

    action = refresh.status if method == "GET" else refresh.request
    action.side_effect = revoked
    kwargs = {"json": BODY} if method == "POST" else {}
    response = client.request(method, "/api/workspace/refresh", headers=HEADERS, **kwargs)
    assert response.status_code == (401 if change == "logout" else 409)
    assert "job_id" not in response.json()
    action.assert_called_once_with(OWNER.id)


def test_refresh_rechecks_consent_after_enqueue_and_reports_busy_without_new_authority(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock],
) -> None:
    client, _, database, refresh, _ = refresh_http

    def revoked(owner: UUID) -> dict[str, Any]:
        database.has_legal_versions.return_value = False
        return JOB

    refresh.request.side_effect = revoked
    response = client.post("/api/workspace/refresh", json=BODY, headers=HEADERS)
    assert response.status_code == 409
    assert "job_id" not in response.json()
    database.has_legal_versions.return_value = True
    refresh.request.side_effect = PortfolioRefreshBusy("portfolio_refresh_busy")
    response = client.post("/api/workspace/refresh", json=BODY, headers=HEADERS)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "2"
    assert response.json()["detail"] == "portfolio_refresh_busy"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/broker/tbank/accounts", PREVIEW),
        ("PUT", "/api/broker/tbank", CONNECT),
    ],
)
def test_broker_token_requires_current_consent_before_provider_access_or_storage(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock],
    method: str, path: str, body: dict[str, Any],
) -> None:
    client, _, database, refresh, broker = refresh_http
    database.has_legal_versions.return_value = False
    response = client.request(method, path, json=body, headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["detail"] == "updated_legal_consent_required"
    assert response.headers["cache-control"] == "private, no-store"
    assert CONNECT["credential"] not in response.text
    assert broker.mock_calls == []
    refresh.request.assert_not_called()


def test_broker_preview_returns_account_metadata_with_current_consent(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock],
) -> None:
    client, _, _, refresh, broker = refresh_http
    broker.preview_accounts.return_value = (
        TBankAccount(CONNECT["account_id"], "Synthetic", "BROKER", "OPEN"),
    )
    response = client.post("/api/broker/tbank/accounts", json=PREVIEW, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"accounts": [{
        "id": CONNECT["account_id"], "name": "Synthetic", "type": "BROKER", "status": "OPEN",
    }]}
    assert CONNECT["credential"] not in response.text
    broker.preview_accounts.assert_called_once_with(
        credential=CONNECT["credential"], environment=CONNECT["environment"],
    )
    broker.connect.assert_not_called()
    refresh.request.assert_not_called()


@pytest.mark.parametrize("change", ["logout", "other_user", "consent"])
def test_broker_preview_discards_accounts_after_authority_changes_during_provider_read(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock], change: str,
) -> None:
    client, auth, database, refresh, broker = refresh_http

    def changed(**kwargs: Any) -> tuple[TBankAccount, ...]:
        if change == "consent":
            database.has_legal_versions.return_value = False
        else:
            auth.refresh_session.side_effect = None
            auth.refresh_session.return_value = None if change == "logout" else OTHER
        return (TBankAccount(CONNECT["account_id"], "Synthetic", "BROKER", "OPEN"),)

    broker.preview_accounts.side_effect = changed
    response = client.post("/api/broker/tbank/accounts", json=PREVIEW, headers=HEADERS)
    assert response.status_code == (401 if change == "logout" else 409)
    assert "accounts" not in response.json()
    assert CONNECT["account_id"] not in response.text
    broker.connect.assert_not_called()
    refresh.request.assert_not_called()


@pytest.mark.parametrize("busy", [False, True])
def test_first_broker_connect_queues_observation_without_rolling_back_valid_connection(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock], busy: bool,
) -> None:
    client, _, _, refresh, broker = refresh_http
    if busy:
        refresh.request.side_effect = PortfolioRefreshBusy("portfolio_refresh_busy")
    response = client.put("/api/broker/tbank", json=CONNECT, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["account_id"] == CONNECT["account_id"]
    assert response.json()["refresh"] == (
        {"status": "busy", "retry_after_seconds": 2} if busy else JOB
    )
    assert broker.connect.call_args.kwargs["user_id"] == OWNER.id
    refresh.request.assert_called_once_with(OWNER.id)
    broker.disconnect.assert_not_called()


@pytest.mark.parametrize("change", ["logout", "other_user", "consent"])
def test_broker_connect_does_not_queue_when_authority_changes_during_provider_read(
    refresh_http: tuple[TestClient, Mock, Mock, Mock, Mock], change: str,
) -> None:
    client, auth, database, refresh, broker = refresh_http
    connection = broker.connect.return_value

    def replace_session(**kwargs: Any) -> BrokerConnectionStatus:
        if change == "consent":
            database.has_legal_versions.return_value = False
        else:
            auth.refresh_session.side_effect = None
            auth.refresh_session.return_value = None if change == "logout" else OTHER
        return connection

    broker.connect.side_effect = replace_session
    response = client.put("/api/broker/tbank", json=CONNECT, headers=HEADERS)
    assert response.status_code == (401 if change == "logout" else 409)
    assert "account_id" not in response.json()
    refresh.request.assert_not_called()


@pytest.mark.parametrize("failure", [None, "start", "close"])
def test_lifespan_starts_worker_after_database_and_always_closes_database_last(
    failure: str | None,
) -> None:
    database, refresh = Mock(spec=Database), Mock(spec=PortfolioRefreshCoordinator)
    calls: list[str] = []
    database.open.side_effect = lambda: calls.append("database.open")
    database.close.side_effect = lambda: calls.append("database.close")

    def invoke(name: str) -> None:
        calls.append(name)
        if name == f"refresh.{failure}":
            raise RuntimeError("synthetic lifecycle failure")

    refresh.start.side_effect = lambda: invoke("refresh.start")
    refresh.close.side_effect = lambda: invoke("refresh.close")
    isolated = FastAPI()

    async def enter() -> None:
        async with lifespan(isolated):
            calls.append("body")

    with (
        patch("omnicio.main.load_settings", return_value=configuration()),
        patch("omnicio.main.Database", return_value=database),
        patch("omnicio.main.PortfolioRefreshCoordinator", return_value=refresh),
    ):
        coroutine = enter()
        if failure is None:
            asyncio.run(coroutine)
        else:
            with pytest.raises(RuntimeError, match="synthetic lifecycle"):
                asyncio.run(coroutine)
    expected = ["database.open", "refresh.start"]
    if failure != "start":
        expected.append("body")
    assert calls == [*expected, "refresh.close", "database.close"]
