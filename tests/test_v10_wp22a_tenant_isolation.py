from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.web.remote_security_v1 import (
    TAILSCALE_LOGIN_HEADER,
    PrivateRemoteSecurityMiddlewareV1,
    PrivateRemoteSecurityPolicyV1,
    install_private_remote_session_routes,
    tailscale_login_sha256,
)
from omni_cio.web.session_v1 import SessionRegistryV1


_HOST = "omni-owner.synthetic-tailnet.ts.net"
_OWNER_LOGIN = "owner@example.test"
_COOKIE = "omni_v10_session"
_ORIGIN = f"https://{_HOST}"
_NOW = datetime(2026, 8, 14, 16, 30, tzinfo=timezone.utc)


def _client() -> tuple[TestClient, SessionRegistryV1]:
    sessions = SessionRegistryV1()
    app = FastAPI()
    install_private_remote_session_routes(
        app,
        sessions=sessions,
        session_cookie_name=_COOKIE,
        now=lambda: _NOW,
    )

    @app.get("/monitor")
    def monitor() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        PrivateRemoteSecurityMiddlewareV1,
        policy=PrivateRemoteSecurityPolicyV1(
            expected_host=_HOST,
            owner_login_sha256=tailscale_login_sha256(_OWNER_LOGIN),
        ),
        session_cookie_name=_COOKIE,
        sessions=sessions,
        now=lambda: _NOW,
    )
    return TestClient(app, base_url=_ORIGIN, client=("127.0.0.1", 50000)), sessions


def _owner_headers(*, origin: bool = False) -> dict[str, str]:
    headers = {TAILSCALE_LOGIN_HEADER: _OWNER_LOGIN}
    if origin:
        headers["Origin"] = _ORIGIN
    return headers


def test_foreign_tenant_session_is_rejected_on_owner_private_path() -> None:
    client, sessions = _client()
    foreign_token, _ = sessions.create(
        user_id="user:v2:synthetic-foreign",
        tenant_id="tenant:v2:synthetic-foreign",
        now=_NOW,
    )
    client.cookies.set(_COOKIE, foreign_token)

    response = client.get("/monitor", headers=_owner_headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "PRIVATE_REMOTE_OWNER_SESSION_REQUIRED"


def test_owner_private_bootstrap_can_replace_a_foreign_session() -> None:
    client, sessions = _client()
    foreign_token, _ = sessions.create(
        user_id="user:v2:synthetic-foreign",
        tenant_id="tenant:v2:synthetic-foreign",
        now=_NOW,
    )
    client.cookies.set(_COOKIE, foreign_token)

    response = client.post(
        "/api/v10/web/private-remote-login",
        headers=_owner_headers(origin=True),
        json={},
    )

    assert response.status_code == 200
    replacement = client.cookies.get(_COOKIE)
    assert replacement is not None
    assert replacement != foreign_token
    assert sessions.resolve(foreign_token, now=_NOW) is None
