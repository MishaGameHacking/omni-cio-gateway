from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient

from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.external_access_v1 import (
    CSRF_COOKIE,
    CSRF_HEADER,
    REMOTE_SESSION_COOKIE,
    TAILSCALE_LOGIN_HEADER,
    ExternalAccessPolicyV1,
    FixedWindowLimiterV1,
    install_private_remote_access_v1,
)
from omni_cio.web.session_v1 import SessionPolicyV1, SessionRegistryV1


NOW = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
OWNER_LOGIN = "owner@example.test"
HOST = "omni-owner.example-tailnet.ts.net"
ORIGIN = f"https://{HOST}"
OWNER_SHA256 = hashlib.sha256(OWNER_LOGIN.casefold().encode("utf-8")).hexdigest()


def make_app(
    *,
    policy: ExternalAccessPolicyV1 | None = None,
    session_policy: SessionPolicyV1 | None = None,
    current_time: list[datetime] | None = None,
) -> FastAPI:
    sessions = SessionRegistryV1(session_policy)
    app = FastAPI()
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost"],
        www_redirect=False,
    )

    @app.get("/protected")
    def protected(request: Request) -> dict[str, bool]:
        scope = sessions.resolve(
            request.cookies.get(SESSION_COOKIE),
            now=(current_time or [NOW])[0],
        )
        if scope is None:
            return {"authenticated": False}
        return {"authenticated": True}

    @app.post("/mutate")
    def mutate(request: Request) -> dict[str, bool]:
        scope = sessions.resolve(
            request.cookies.get(SESSION_COOKIE),
            now=(current_time or [NOW])[0],
        )
        return {"authenticated": scope is not None}

    @app.post("/api/v10/web/session/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        sessions.revoke(
            request.cookies.get(SESSION_COOKIE),
            now=(current_time or [NOW])[0],
        )
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    install_private_remote_access_v1(
        app,
        sessions=sessions,
        policy=policy
        or ExternalAccessPolicyV1(
            canonical_host=HOST,
            owner_login_sha256=OWNER_SHA256,
        ),
        now=lambda: (current_time or [NOW])[0],
    )
    return app


def remote_client(app: FastAPI) -> TestClient:
    return TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51000),
        headers={TAILSCALE_LOGIN_HEADER: OWNER_LOGIN},
    )


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v10/web/private-tailnet-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200


def csrf_token(client: TestClient) -> str:
    value = client.cookies.get(CSRF_COOKIE)
    assert value
    return value


def test_policy_rejects_non_tailnet_host_and_invalid_owner_fingerprint() -> None:
    try:
        ExternalAccessPolicyV1(
            canonical_host="public.example.com",
            owner_login_sha256=OWNER_SHA256,
        )
    except ValueError as exc:
        assert str(exc) == "WP22A_CANONICAL_HOST_INVALID"
    else:
        raise AssertionError("public host must fail closed")

    try:
        ExternalAccessPolicyV1(
            canonical_host=HOST,
            owner_login_sha256="not-a-digest",
        )
    except ValueError as exc:
        assert str(exc) == "WP22A_OWNER_LOGIN_FINGERPRINT_INVALID"
    else:
        raise AssertionError("invalid identity binding must fail closed")


def test_fixed_window_limiter_is_bounded_and_recovers_after_window() -> None:
    limiter = FixedWindowLimiterV1()
    assert limiter.admit("login", limit=2, window_seconds=10, now_monotonic=100.0)
    assert limiter.admit("login", limit=2, window_seconds=10, now_monotonic=101.0)
    assert not limiter.admit("login", limit=2, window_seconds=10, now_monotonic=102.0)
    assert limiter.admit("login", limit=2, window_seconds=10, now_monotonic=111.1)


def test_tailnet_status_crosses_existing_local_trusted_host_only_after_outer_verification() -> None:
    client = remote_client(make_app())
    response = client.get("/api/v10/web/private-tailnet-login/status")
    assert response.status_code == 200
    assert response.json() == {"enabled": True}
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert response.headers["cache-control"] == "no-store"


def test_owner_login_uses_host_bound_secure_server_side_session_and_csrf_cookie() -> None:
    client = remote_client(make_app())
    response = client.post(
        "/api/v10/web/private-tailnet-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next(
        item for item in cookie_headers if item.startswith(REMOTE_SESSION_COOKIE + "=")
    )
    csrf_cookie = next(
        item for item in cookie_headers if item.startswith(CSRF_COOKIE + "=")
    )
    assert REMOTE_SESSION_COOKIE.startswith("__Host-")
    assert CSRF_COOKIE.startswith("__Host-")
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=strict" in session_cookie
    assert "Secure" in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
    assert client.get("/protected").json() == {"authenticated": True}


def test_remote_logout_revokes_session_and_clears_host_bound_cookies() -> None:
    client = remote_client(make_app())
    login(client)
    token = csrf_token(client)
    response = client.post(
        "/api/v10/web/session/logout",
        headers={"Origin": ORIGIN, CSRF_HEADER: token},
    )
    assert response.status_code == 200
    set_cookies = response.headers.get_list("set-cookie")
    assert any(item.startswith(REMOTE_SESSION_COOKIE + "=") for item in set_cookies)
    assert any(item.startswith(CSRF_COOKIE + "=") for item in set_cookies)
    assert client.get("/protected").json() == {"authenticated": False}


def test_wrong_tailnet_identity_and_non_loopback_proxy_path_fail_closed() -> None:
    app = make_app()
    wrong = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51001),
        headers={TAILSCALE_LOGIN_HEADER: "other@example.test"},
    )
    response = wrong.post(
        "/api/v10/web/private-tailnet-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "OWNER_IDENTITY_REQUIRED"

    direct = TestClient(
        app,
        base_url=ORIGIN,
        client=("100.64.0.10", 51002),
        headers={TAILSCALE_LOGIN_HEADER: OWNER_LOGIN},
    )
    response = direct.get("/api/v10/web/private-tailnet-login/status")
    assert response.status_code == 403
    assert response.json()["detail"] == "UNTRUSTED_PROXY_PATH"


def test_host_origin_and_csrf_abuse_are_rejected() -> None:
    app = make_app()
    hostile_host = TestClient(
        app,
        base_url="https://attacker.example.com",
        client=("127.0.0.1", 51003),
        headers={TAILSCALE_LOGIN_HEADER: OWNER_LOGIN},
    )
    response = hostile_host.get("/api/v10/web/private-tailnet-login/status")
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_HOST"

    client = remote_client(app)
    response = client.post(
        "/api/v10/web/private-tailnet-login",
        headers={"Origin": "https://attacker.example.com"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "ORIGIN_REQUIRED"

    login(client)
    response = client.post("/mutate", headers={"Origin": ORIGIN})
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF_REJECTED"

    token = csrf_token(client)
    response = client.post(
        "/mutate",
        headers={"Origin": ORIGIN, CSRF_HEADER: token},
    )
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_cross_origin_cors_is_not_enabled() -> None:
    client = remote_client(make_app())
    response = client.get(
        "/api/v10/web/private-tailnet-login/status",
        headers={"Origin": "https://attacker.example.com"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_login_rate_limit_is_enforced() -> None:
    policy = ExternalAccessPolicyV1(
        canonical_host=HOST,
        owner_login_sha256=OWNER_SHA256,
        login_attempts=2,
        login_window_seconds=60,
    )
    client = remote_client(make_app(policy=policy))
    headers = {"Origin": ORIGIN}
    assert (
        client.post("/api/v10/web/private-tailnet-login", headers=headers).status_code
        == 200
    )
    assert (
        client.post("/api/v10/web/private-tailnet-login", headers=headers).status_code
        == 200
    )
    response = client.post("/api/v10/web/private-tailnet-login", headers=headers)
    assert response.status_code == 429
    assert response.json()["detail"] == "RATE_LIMITED"


def test_expired_session_is_rejected_server_side() -> None:
    clock = [NOW]
    policy = SessionPolicyV1(
        idle_lifetime=timedelta(minutes=2),
        absolute_lifetime=timedelta(minutes=5),
    )
    client = remote_client(make_app(session_policy=policy, current_time=clock))
    login(client)
    assert client.get("/protected").json() == {"authenticated": True}
    clock[0] = NOW + timedelta(minutes=6)
    assert client.get("/protected").json() == {"authenticated": False}
