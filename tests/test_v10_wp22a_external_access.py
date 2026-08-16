from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.external_access_v1 import (
    CF_ACCESS_JWT_HEADER,
    CSRF_COOKIE,
    CSRF_HEADER,
    REMOTE_SESSION_COOKIE,
    ExternalAccessPolicyV1,
    FixedWindowLimiterV1,
    install_private_remote_access_v1,
)
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc)
HOST = "owner.omni-cio.example"
ORIGIN = f"https://{HOST}"
ACCESS_JWT = f"{'a' * 24}.{'b' * 24}.{'c' * 32}"
OTHER_JWT = f"{'d' * 24}.{'e' * 24}.{'f' * 32}"
WEB_SOURCE = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"


def make_app(
    *,
    policy: ExternalAccessPolicyV1 | None = None,
) -> FastAPI:
    sessions = SessionRegistryV1()
    app = FastAPI()
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost"],
        www_redirect=False,
    )

    @app.get("/protected")
    def protected(request: Request) -> dict[str, bool]:
        scope = sessions.resolve(request.cookies.get(SESSION_COOKIE), now=NOW)
        return {"authenticated": scope is not None}

    @app.post("/mutate")
    def mutate(request: Request) -> dict[str, bool]:
        scope = sessions.resolve(request.cookies.get(SESSION_COOKIE), now=NOW)
        return {"authenticated": scope is not None}

    @app.post("/issue-local-session")
    def issue_local_session(response: Response) -> dict[str, bool]:
        token, scope = sessions.create(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            now=NOW,
        )
        response.set_cookie(SESSION_COOKIE, token, path="/")
        return {"issued": scope.expires_at > NOW}

    @app.post("/api/v10/web/session/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        sessions.revoke(request.cookies.get(SESSION_COOKIE), now=NOW)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    install_private_remote_access_v1(
        app,
        sessions=sessions,
        policy=policy or ExternalAccessPolicyV1(canonical_host=HOST),
        now=lambda: NOW,
    )
    return app


def remote_client(
    app: FastAPI,
    *,
    assertion: str = ACCESS_JWT,
    client_host: str = "127.0.0.1",
) -> TestClient:
    return TestClient(
        app,
        base_url=ORIGIN,
        client=(client_host, 51000),
        headers={CF_ACCESS_JWT_HEADER: assertion},
    )


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v10/web/private-access-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200


def csrf_token(client: TestClient) -> str:
    value = client.cookies.get(CSRF_COOKIE)
    assert value
    return value


def test_policy_accepts_normal_fqdn_and_rejects_local_ip_or_malformed_host() -> None:
    assert ExternalAccessPolicyV1(canonical_host=HOST).canonical_origin == ORIGIN
    for invalid in (
        "localhost",
        "127.0.0.1",
        "owner",
        "owner..example.com",
        "-owner.example.com",
        "owner.example.com/path",
    ):
        try:
            ExternalAccessPolicyV1(canonical_host=invalid)
        except ValueError as exc:
            assert str(exc) == "WP22A_CANONICAL_HOST_INVALID"
        else:
            raise AssertionError(f"invalid host accepted: {invalid}")


def test_fixed_window_limiter_is_bounded_and_recovers() -> None:
    limiter = FixedWindowLimiterV1()
    assert limiter.admit("k", limit=2, window_seconds=10, now_monotonic=100.0)
    assert limiter.admit("k", limit=2, window_seconds=10, now_monotonic=101.0)
    assert not limiter.admit("k", limit=2, window_seconds=10, now_monotonic=102.0)
    assert limiter.admit("k", limit=2, window_seconds=10, now_monotonic=111.1)


def test_local_status_is_disabled_and_local_app_remains_available() -> None:
    client = TestClient(
        make_app(),
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 51001),
    )
    response = client.get("/api/v10/web/private-access-login/status")
    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_remote_status_requires_loopback_cloudflared_peer_and_access_assertion() -> None:
    app = make_app()
    ok = remote_client(app).get("/api/v10/web/private-access-login/status")
    assert ok.status_code == 200
    assert ok.json() == {"enabled": True}

    missing = remote_client(app, assertion="").get(
        "/api/v10/web/private-access-login/status"
    )
    assert missing.status_code == 403
    assert missing.json()["detail"] == "CLOUDFLARE_ACCESS_REQUIRED"

    malformed = remote_client(app, assertion="not-a-jwt").get(
        "/api/v10/web/private-access-login/status"
    )
    assert malformed.status_code == 403
    assert malformed.json()["detail"] == "CLOUDFLARE_ACCESS_REQUIRED"

    direct = remote_client(app, client_host="192.0.2.10").get(
        "/api/v10/web/private-access-login/status"
    )
    assert direct.status_code == 403
    assert direct.json()["detail"] == "UNTRUSTED_PROXY_PATH"


def test_remote_host_and_default_https_port_are_exactly_bounded() -> None:
    client = remote_client(make_app())
    assert client.get(
        "/api/v10/web/private-access-login/status",
        headers={"Host": f"{HOST}:443"},
    ).status_code == 200
    for invalid in ("attacker.example", f"{HOST}:444", f"{HOST}/path"):
        response = client.get(
            "/api/v10/web/private-access-login/status",
            headers={"Host": invalid},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "INVALID_HOST"


def test_remote_response_security_headers_are_fail_closed() -> None:
    response = remote_client(make_app()).get(
        "/api/v10/web/private-access-login/status"
    )
    assert response.headers["strict-transport-security"].startswith(
        "max-age=31536000"
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_web_source_has_no_inline_style_attributes_blocked_by_remote_csp() -> None:
    offenders = []
    for path in WEB_SOURCE.rglob("*.tsx"):
        if "style={{" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(WEB_SOURCE).as_posix())
    assert offenders == []


def test_private_access_login_sets_host_bound_server_session_and_csrf() -> None:
    client = remote_client(make_app())
    response = client.post(
        "/api/v10/web/private-access-login",
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
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=strict" in session_cookie
    assert "Secure" in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
    assert client.get("/protected").json() == {"authenticated": True}


def test_login_rejects_wrong_origin_and_is_rate_limited() -> None:
    policy = ExternalAccessPolicyV1(
        canonical_host=HOST,
        login_attempts=2,
        login_window_seconds=60,
    )
    client = remote_client(make_app(policy=policy))
    bad = client.post(
        "/api/v10/web/private-access-login",
        headers={"Origin": "https://attacker.example"},
    )
    assert bad.status_code == 403
    assert bad.json()["detail"] == "ORIGIN_REQUIRED"

    assert client.post(
        "/api/v10/web/private-access-login", headers={"Origin": ORIGIN}
    ).status_code == 200
    assert client.post(
        "/api/v10/web/private-access-login", headers={"Origin": ORIGIN}
    ).status_code == 200
    limited = client.post(
        "/api/v10/web/private-access-login", headers={"Origin": ORIGIN}
    )
    assert limited.status_code == 429
    assert limited.json()["detail"] == "RATE_LIMITED"


def test_reauthentication_rotates_and_revokes_previous_session() -> None:
    app = make_app()
    client = remote_client(app)
    login(client)
    first = client.cookies.get(REMOTE_SESSION_COOKIE)
    assert first
    login(client)
    second = client.cookies.get(REMOTE_SESSION_COOKIE)
    assert second and second != first

    replay = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51002),
        headers={
            CF_ACCESS_JWT_HEADER: ACCESS_JWT,
            "Cookie": f"{REMOTE_SESSION_COOKIE}={first}",
        },
    )
    assert replay.get("/protected").json() == {"authenticated": False}


def test_remote_path_ignores_legacy_local_session_cookie() -> None:
    app = make_app()
    local = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 51003),
    )
    assert local.post("/issue-local-session").status_code == 200
    local_token = local.cookies.get(SESSION_COOKIE)
    assert local_token

    remote = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51004),
        headers={
            CF_ACCESS_JWT_HEADER: ACCESS_JWT,
            "Cookie": f"{SESSION_COOKIE}={local_token}",
        },
    )
    assert remote.get("/protected").json() == {"authenticated": False}


def test_unsafe_remote_mutation_requires_origin_and_double_submit_csrf() -> None:
    client = remote_client(make_app())
    login(client)
    no_origin = client.post("/mutate")
    assert no_origin.status_code == 403
    assert no_origin.json()["detail"] == "ORIGIN_REQUIRED"

    no_csrf = client.post("/mutate", headers={"Origin": ORIGIN})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["detail"] == "CSRF_REJECTED"

    token = csrf_token(client)
    wrong_csrf = client.post(
        "/mutate",
        headers={"Origin": ORIGIN, CSRF_HEADER: "wrong"},
    )
    assert wrong_csrf.status_code == 403
    assert wrong_csrf.json()["detail"] == "CSRF_REJECTED"

    ok = client.post(
        "/mutate",
        headers={"Origin": ORIGIN, CSRF_HEADER: token},
    )
    assert ok.status_code == 200
    assert ok.json() == {"authenticated": True}


def test_remote_logout_revokes_session_and_clears_remote_cookies() -> None:
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


def test_assertion_value_is_not_used_as_application_identity_or_returned() -> None:
    client = remote_client(make_app(), assertion=OTHER_JWT)
    response = client.get("/api/v10/web/private-access-login/status")
    assert response.status_code == 200
    assert OTHER_JWT not in response.text
    assert "access-control-allow-origin" not in response.headers
