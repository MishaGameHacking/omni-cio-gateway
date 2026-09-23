from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import time
from typing import Any

from fastapi.testclient import TestClient

from apps.api.app import _SerializedWebConnection
from omni_cio.adapters.tinvest_read_v1 import BrokerAccountBindingV1
from omni_cio.contracts.v1.domain import OWNER_TENANT_ID
from omni_cio.web.api_v1 import WebApiServicesV1, create_web_api
from omni_cio.web.persistence_v1 import BrokerConnectionRecordV1
from omni_cio.web.provisioning_v1 import (
    BrokerProvisioningAccountV1,
    BrokerProvisioningPreviewV1,
)
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 11, 7, 0, tzinfo=timezone.utc)
BINDING = BrokerAccountBindingV1(
    broker_account_id="broker-account:v1:" + "a" * 64,
    account_fingerprint_sha256="b" * 64,
    masked_label="****0017",
    access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
)
OPAQUE_CONNECTION_REF = "read-connection:v1:" + "d" * 64


class FakeBrokerRepository:
    def __init__(self) -> None:
        self.tenant_requests: list[str] = []
        self.record = BrokerConnectionRecordV1(
            connection_id="broker-connection:v1:" + "c" * 64,
            tenant_id=OWNER_TENANT_ID,
            provider="t_invest",
            credential_role="read",
            state="ACTIVE",
            secret_ref=OPAQUE_CONNECTION_REF,
            created_at=NOW,
            last_verified_at=NOW,
            accounts=(BINDING,),
        )

    def list_read_connections(
        self, *, tenant_id: str
    ) -> tuple[BrokerConnectionRecordV1, ...]:
        self.tenant_requests.append(tenant_id)
        return (self.record,) if tenant_id == OWNER_TENANT_ID else ()


class FakeProvisioning:
    def __init__(self, repository: FakeBrokerRepository) -> None:
        self.repository = repository
        self.preview_tokens: list[str] = []
        self.commit_tenants: list[str] = []
        self.revoked_tenants: list[str] = []

    def preview(
        self, *, user_id: str, tenant_id: str, token: str, now: datetime
    ) -> BrokerProvisioningPreviewV1:
        del user_id, tenant_id
        self.preview_tokens.append(token)
        return BrokerProvisioningPreviewV1(
            challenge_id="challenge-opaque-001",
            expires_at=now + timedelta(minutes=5),
            accounts=(
                BrokerProvisioningAccountV1(
                    selection_id="selection-opaque-001",
                    masked_label=BINDING.masked_label,
                ),
            ),
        )

    def commit_new(
        self,
        *,
        user_id: str,
        tenant_id: str,
        challenge_id: str,
        selected_accounts: tuple[str, ...],
        now: datetime,
    ) -> BrokerConnectionRecordV1:
        del user_id, challenge_id, selected_accounts, now
        self.commit_tenants.append(tenant_id)
        return self.repository.record

    def replace_read_credential(self, **kwargs: Any) -> None:
        self.commit_tenants.append(str(kwargs["tenant_id"]))

    def revoke_read_connection(
        self, *, tenant_id: str, connection_id: str, now: datetime
    ) -> bool:
        del connection_id, now
        self.revoked_tenants.append(tenant_id)
        return True


def make_client(
    *, private_test_identity_enabled: bool = True
) -> tuple[TestClient, FakeBrokerRepository, FakeProvisioning]:
    repository = FakeBrokerRepository()
    provisioning = FakeProvisioning(repository)
    sessions = SessionRegistryV1()
    app = create_web_api(
        WebApiServicesV1(
            sessions=sessions,
            broker_repository=repository,  # type: ignore[arg-type]
            provisioning=provisioning,  # type: ignore[arg-type]
            now=lambda: NOW,
            private_test_identity_enabled=private_test_identity_enabled,
        )
    )
    return (
        TestClient(
            app,
            base_url="http://127.0.0.1",
            client=("127.0.0.1", 50000),
        ),
        repository,
        provisioning,
    )


def login(client: TestClient) -> None:
    response = client.post("/api/v10/web/private-test-login")
    assert response.status_code == 200


def test_private_identity_is_disabled_by_default_and_loopback_only() -> None:
    client, _, _ = make_client(private_test_identity_enabled=False)
    status = client.get("/api/v10/web/private-test-login/status")
    assert status.status_code == 200
    assert status.json() == {"enabled": False}
    response = client.post("/api/v10/web/private-test-login")
    assert response.status_code == 404


def test_private_login_sets_httponly_strict_cookie_and_session_is_server_side() -> None:
    client, _, _ = make_client()
    response = client.post("/api/v10/web/private-test-login")
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    session = client.get("/api/v10/web/session")
    assert session.json()["authenticated"] is True
    assert "user_id" not in session.text
    assert "tenant:v1:owner" not in session.text


def test_provider_surface_is_telegram_only_without_password_google_or_vk() -> None:
    client, _, _ = make_client()
    response = client.get("/api/v10/web/auth/providers")
    assert response.status_code == 200
    assert [row["provider"] for row in response.json()] == ["telegram"]
    assert "vk_id" not in response.text.lower()
    assert "google" not in response.text.lower()
    assert "password" not in response.text.lower()


def test_private_data_routes_require_session_and_ignore_client_tenant_authority() -> (
    None
):
    client, repository, _ = make_client()
    assert (
        client.get(
            "/api/v10/web/broker-connections?tenant_id=tenant:v1:other"
        ).status_code
        == 401
    )
    login(client)
    response = client.get("/api/v10/web/broker-connections?tenant_id=tenant:v1:other")
    assert response.status_code == 200
    assert repository.tenant_requests == [OWNER_TENANT_ID]
    assert OWNER_TENANT_ID not in response.text
    assert "secret_ref" not in response.text
    assert BINDING.account_fingerprint_sha256 not in response.text
    assert response.json()[0]["accounts"][0]["masked_label"] == "****0017"


def test_broker_preview_never_returns_raw_token_and_commit_uses_session_tenant() -> (
    None
):
    client, _, provisioning = make_client()
    login(client)
    raw_token = "synthetic-read-credential-value"
    preview = client.post(
        "/api/v10/web/broker-connections/preview",
        json={"token": raw_token, "tenant_id": "tenant:v1:other"},
    )
    assert preview.status_code == 200
    assert raw_token not in preview.text
    assert provisioning.preview_tokens == [raw_token]

    commit = client.post(
        "/api/v10/web/broker-connections/commit",
        json={
            "challenge_id": preview.json()["challenge_id"],
            "selected_accounts": [preview.json()["accounts"][0]["selection_id"]],
            "tenant_id": "tenant:v1:other",
        },
    )
    assert commit.status_code == 200
    assert provisioning.commit_tenants == [OWNER_TENANT_ID]
    assert "secret_ref" not in commit.text
    assert raw_token not in commit.text


def test_logout_and_revoke_all_invalidate_server_side_session() -> None:
    client, _, _ = make_client()
    login(client)
    assert client.post("/api/v10/web/session/revoke-all").status_code == 200
    assert client.get("/api/v10/web/session").json() == {"authenticated": False}


class _ConcurrencyCursor:
    rowcount = 1

    def fetchone(self) -> tuple[int]:
        return (1,)

    def fetchall(self) -> list[tuple[int]]:
        return [(1,)]


class _ConcurrencyTransaction:
    def __init__(self, connection: "_ConcurrencyConnection") -> None:
        self._connection = connection

    def __enter__(self) -> "_ConcurrencyTransaction":
        with self._connection.state_lock:
            self._connection.active_transactions += 1
            self._connection.max_active_transactions = max(
                self._connection.max_active_transactions,
                self._connection.active_transactions,
            )
            if self._connection.active_transactions > 1:
                self._connection.active_transactions -= 1
                raise RuntimeError("OVERLAPPING_TRANSACTION_CONTEXTS")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        with self._connection.state_lock:
            self._connection.active_transactions -= 1


class _ConcurrencyConnection:
    def __init__(self) -> None:
        self.state_lock = threading.Lock()
        self.active_transactions = 0
        self.max_active_transactions = 0

    def transaction(self) -> _ConcurrencyTransaction:
        return _ConcurrencyTransaction(self)

    def execute(
        self,
        query: Any,
        params: Any = None,
        *,
        prepare: bool | None = None,
    ) -> _ConcurrencyCursor:
        del query, params, prepare
        time.sleep(0.003)
        return _ConcurrencyCursor()


def _request_transaction(connection: _SerializedWebConnection) -> tuple[int]:
    with connection.transaction():
        row = connection.execute("SELECT 1").fetchone()
        time.sleep(0.005)
        return row


def test_local_private_shared_db_connection_serializes_parallel_transactions() -> None:
    raw = _ConcurrencyConnection()
    connection = _SerializedWebConnection(raw)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(lambda _: _request_transaction(connection), range(16))
        )

    assert results == [(1,)] * 16
    assert raw.max_active_transactions == 1
    assert raw.active_transactions == 0
