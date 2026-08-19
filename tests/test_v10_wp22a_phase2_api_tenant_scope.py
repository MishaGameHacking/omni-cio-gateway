from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from omni_cio.web.api_v1 import SESSION_COOKIE, WebApiServicesV1, create_web_api
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 19, 4, 0, tzinfo=timezone.utc)
USER_A = "user:v1:product_a"
TENANT_A = "tenant:v1:product_a"
TENANT_B = "tenant:v1:product_b"


class _BrokerRepository:
    def __init__(self) -> None:
        self.tenant_requests: list[str] = []

    def list_read_connections(self, *, tenant_id: str) -> tuple[object, ...]:
        self.tenant_requests.append(tenant_id)
        return ()


class _Provisioning:
    def revoke_read_connection(self, **kwargs: Any) -> bool:
        del kwargs
        return False


def _client() -> tuple[TestClient, _BrokerRepository, SessionRegistryV1, str]:
    sessions = SessionRegistryV1()
    token, _ = sessions.create(user_id=USER_A, tenant_id=TENANT_A, now=NOW)
    repository = _BrokerRepository()
    app = create_web_api(
        WebApiServicesV1(
            sessions=sessions,
            broker_repository=repository,  # type: ignore[arg-type]
            provisioning=_Provisioning(),  # type: ignore[arg-type]
            now=lambda: NOW,
        )
    )
    client = TestClient(app, base_url="http://127.0.0.1")
    client.cookies.set(SESSION_COOKIE, token)
    return client, repository, sessions, token


def test_product_session_view_exposes_no_owner_or_tenant_authority_labels() -> None:
    client, _, _, _ = _client()

    response = client.get("/api/v10/web/session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert "expires_at" in payload
    assert "user_label" not in payload
    assert "tenant_label" not in payload
    assert "user_id" not in payload
    assert "tenant_id" not in payload
    assert "OWNER" not in response.text
    assert "Personal" not in response.text


def test_product_private_api_ignores_client_user_and_tenant_selectors() -> None:
    client, repository, _, _ = _client()

    response = client.get(
        "/api/v10/web/broker-connections"
        "?tenant_id=tenant:v1:product_b&user_id=user:v1:product_b"
    )

    assert response.status_code == 200
    assert response.json() == []
    assert repository.tenant_requests == [TENANT_A]
    assert TENANT_A not in response.text
    assert TENANT_B not in response.text
