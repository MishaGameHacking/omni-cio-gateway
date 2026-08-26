from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.external_access_v1 import (
    CF_ACCESS_IDENTITY_HEADER,
    CF_ACCESS_JWT_HEADER,
    CSRF_COOKIE,
    CSRF_HEADER,
    FORWARDED_PROTO_HEADER,
    REMOTE_SESSION_COOKIE,
    REMOTE_SESSION_POLICY,
    ExternalAccessPolicyV1,
    FixedWindowLimiterV1,
    install_external_access_v1,
)
from omni_cio.web.session_v1 import SessionPolicyV1, SessionRegistryV1


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
OWNER_IDENTITY = "owner@example.test"
HOST = "omni.example.test"
ORIGIN = f"https://{HOST}"
OWNER_SHA256 = hashlib.sha256(OWNER_IDENTITY.casefold().encode("utf-8")).hexdigest()
FAKE_ACCESS_JWT = "header.payload.signature"
WEB_SOURCE = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"
REMOTE_HEADERS = {
    CF_ACCESS_IDENTITY_HEADER: OWNER_IDENTITY,
    CF_ACCESS_JWT_HEADER: FAKE_ACCESS_JWT,
    FORWARDED_PROTO_HEADER: "https",
}


def make_app(
    *,
    policy: ExternalAccessPolicyV1 | None = None,
    session_policy: SessionPolicyV1 | None = None,
    current_time: list[datetime] | None = None,
) -> FastAPI:
    sessions = SessionRegistryV1(session_policy or REMOTE_SESSION_POLICY)
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
        return {"authenticated": scope is not None}

    @app.post("/mutate")
    def mutate(request: Request) -> dict[str, bool]:
        scope = sessions.resolve(
            request.cookies.get(SESSION_COOKIE),
            now=(current_time or [NOW])[0],
        )
        return {"authenticated": scope is not None}

    @app.post("/issue-legacy-session")
    def issue_legacy_session(response: Response) -> dict[str, bool]:
        token, scope = sessions.create(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            now=(current_time or [NOW])[0],
        )
        response.set_cookie(SESSION_COOKIE, token, path="/")
        return {"issued": scope.expires_at > (current_time or [NOW])[0]}

    @app.post("/api/v10/web/session/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        sessions.revoke(
            request.cookies.get(SESSION_COOKIE),
            now=(current_time or [NOW])[0],
        )
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    install_external_access_v1(
        app,
        sessions=sessions,
        policy=policy
        or ExternalAccessPolicyV1(
            canonical_host=HOST,
            owner_identity_sha256=OWNER_SHA256,
        ),
        now=lambda: (current_time or [NOW])[0],
    )
    return app


def remote_client(app: FastAPI) -> TestClient:
    return TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51000),
        headers=REMOTE_HEADERS,
    )


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v10/web/private-external-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200


def csrf_token(client: TestClient) -> str:
    value = client.cookies.get(CSRF_COOKIE)
    assert value
    return value


def test_policy_accepts_dns_host_and_rejects_local_or_malformed_host() -> None:
    assert (
        ExternalAccessPolicyV1(
            canonical_host=HOST,
            owner_identity_sha256=OWNER_SHA256,
        ).canonical_origin
        == ORIGIN
    )

    for invalid in ("localhost", "127.0.0.1", "owner..example.test", "no-tld"):
        try:
            ExternalAccessPolicyV1(
                canonical_host=invalid,
                owner_identity_sha256=OWNER_SHA256,
            )
        except ValueError as exc:
            assert str(exc) == "WP22A_CANONICAL_HOST_INVALID"
        else:
            raise AssertionError(f"host must fail closed: {invalid}")

    try:
        ExternalAccessPolicyV1(
            canonical_host=HOST,
            owner_identity_sha256="not-a-digest",
        )
    except ValueError as exc:
        assert str(exc) == "WP22A_OWNER_IDENTITY_FINGERPRINT_INVALID"
    else:
        raise AssertionError("invalid identity binding must fail closed")


def test_remote_session_policy_is_short_and_bounded() -> None:
    assert REMOTE_SESSION_POLICY.idle_lifetime == timedelta(hours=2)
    assert REMOTE_SESSION_POLICY.absolute_lifetime == timedelta(hours=24)


def test_fixed_window_limiter_is_bounded_and_recovers_after_window() -> None:
    limiter = FixedWindowLimiterV1()
    assert limiter.admit("login", limit=2, window_seconds=10, now_monotonic=100.0)
    assert limiter.admit("login", limit=2, window_seconds=10, now_monotonic=101.0)
    assert not limiter.admit("login", limit=2, window_seconds=10, now_monotonic=102.0)
    assert limiter.admit("login", limit=2, window_seconds=10, now_monotonic=111.1)


def test_remote_status_crosses_existing_local_trusted_host_boundary() -> None:
    client = remote_client(make_app())
    response = client.get("/api/v10/web/private-external-login/status")
    assert response.status_code == 200
    assert response.json() == {"enabled": True}
    with_default_https_port = client.get(
        "/api/v10/web/private-external-login/status",
        headers={"Host": f"{HOST}:443"},
    )
    assert with_default_https_port.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert response.headers["cache-control"] == "no-store"
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_remote_scheme_header_is_required_and_must_be_https() -> None:
    app = make_app()
    for value in (None, "http", "https, http"):
        headers = {
            CF_ACCESS_IDENTITY_HEADER: OWNER_IDENTITY,
            CF_ACCESS_JWT_HEADER: FAKE_ACCESS_JWT,
        }
        if value is not None:
            headers[FORWARDED_PROTO_HEADER] = value
        client = TestClient(
            app,
            base_url=ORIGIN,
            client=("127.0.0.1", 51020),
            headers=headers,
        )
        response = client.get("/api/v10/web/private-external-login/status")
        assert response.status_code == 403
        assert response.json()["detail"] == "HTTPS_REQUIRED"


def test_remote_status_requires_outer_access_assertion_and_owner_identity() -> None:
    app = make_app()
    missing_assertion = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51021),
        headers={
            CF_ACCESS_IDENTITY_HEADER: OWNER_IDENTITY,
            FORWARDED_PROTO_HEADER: "https",
        },
    )
    response = missing_assertion.get("/api/v10/web/private-external-login/status")
    assert response.status_code == 403
    assert response.json()["detail"] == "ACCESS_ASSERTION_REQUIRED"

    wrong_owner = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51022),
        headers={
            CF_ACCESS_IDENTITY_HEADER: "other@example.test",
            CF_ACCESS_JWT_HEADER: FAKE_ACCESS_JWT,
            FORWARDED_PROTO_HEADER: "https",
        },
    )
    response = wrong_owner.get("/api/v10/web/private-external-login/status")
    assert response.status_code == 403
    assert response.json()["detail"] == "OWNER_IDENTITY_REQUIRED"


def test_web_source_has_no_inline_style_attributes_blocked_by_remote_csp() -> None:
    offenders = []
    for path in WEB_SOURCE.rglob("*.tsx"):
        if "style={{" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(WEB_SOURCE).as_posix())
    assert offenders == []


def test_owner_login_uses_secure_host_bound_session_and_csrf_cookie() -> None:
    client = remote_client(make_app())
    response = client.post(
        "/api/v10/web/private-external-login",
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
    assert "Max-Age=86400" in session_cookie
    assert "Max-Age=86400" in csrf_cookie
    assert client.get("/protected").json() == {"authenticated": True}


def test_access_assertion_is_required_before_owner_identity_is_trusted() -> None:
    client = TestClient(
        make_app(),
        base_url=ORIGIN,
        client=("127.0.0.1", 51001),
        headers={
            CF_ACCESS_IDENTITY_HEADER: OWNER_IDENTITY,
            FORWARDED_PROTO_HEADER: "https",
        },
    )
    response = client.post(
        "/api/v10/web/private-external-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "ACCESS_ASSERTION_REQUIRED"


def test_reauthentication_rotates_session_and_revokes_previous_token() -> None:
    app = make_app()
    owner = remote_client(app)
    login(owner)
    first = owner.cookies.get(REMOTE_SESSION_COOKIE)
    assert first
    login(owner)
    second = owner.cookies.get(REMOTE_SESSION_COOKIE)
    assert second
    assert second != first
    assert owner.get("/protected").json() == {"authenticated": True}

    replay = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51013),
        headers={
            **REMOTE_HEADERS,
            "Cookie": f"{REMOTE_SESSION_COOKIE}={first}",
        },
    )
    assert replay.get("/protected").json() == {"authenticated": False}


def test_stolen_remote_session_is_rejected_for_different_access_identity() -> None:
    app = make_app()
    owner = remote_client(app)
    login(owner)
    session = owner.cookies.get(REMOTE_SESSION_COOKIE)
    csrf = owner.cookies.get(CSRF_COOKIE)
    assert session
    assert csrf

    attacker = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51012),
        headers={
            **REMOTE_HEADERS,
            CF_ACCESS_IDENTITY_HEADER: "other@example.test",
            "Cookie": f"{REMOTE_SESSION_COOKIE}={session}; {CSRF_COOKIE}={csrf}",
        },
    )
    response = attacker.get("/protected")
    assert response.status_code == 403
    assert response.json()["detail"] == "OWNER_IDENTITY_REQUIRED"


def test_remote_host_ignores_legacy_local_session_cookie() -> None:
    app = make_app()
    local = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 51010),
    )
    issued = local.post("/issue-legacy-session")
    assert issued.status_code == 200
    legacy = local.cookies.get(SESSION_COOKIE)
    assert legacy

    remote = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51011),
        headers={
            **REMOTE_HEADERS,
            "Cookie": f"{SESSION_COOKIE}={legacy}",
        },
    )
    assert remote.get("/protected").json() == {"authenticated": False}


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


def test_wrong_identity_and_non_loopback_proxy_path_fail_closed() -> None:
    app = make_app()
    wrong = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51002),
        headers={
            **REMOTE_HEADERS,
            CF_ACCESS_IDENTITY_HEADER: "other@example.test",
        },
    )
    response = wrong.post(
        "/api/v10/web/private-external-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "OWNER_IDENTITY_REQUIRED"

    direct = TestClient(
        app,
        base_url=ORIGIN,
        client=("192.0.2.10", 51003),
        headers=REMOTE_HEADERS,
    )
    response = direct.get("/api/v10/web/private-external-login/status")
    assert response.status_code == 403
    assert response.json()["detail"] == "UNTRUSTED_PROXY_PATH"


def test_host_origin_and_csrf_abuse_are_rejected() -> None:
    app = make_app()
    hostile_host = TestClient(
        app,
        base_url="https://attacker.example.com",
        client=("127.0.0.1", 51004),
        headers=REMOTE_HEADERS,
    )
    response = hostile_host.get("/api/v10/web/private-external-login/status")
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_HOST"

    client = remote_client(app)
    response = client.post(
        "/api/v10/web/private-external-login",
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
        "/api/v10/web/private-external-login/status",
        headers={"Origin": "https://attacker.example.com"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_login_rate_limit_is_enforced() -> None:
    policy = ExternalAccessPolicyV1(
        canonical_host=HOST,
        owner_identity_sha256=OWNER_SHA256,
        login_attempts=2,
        login_window_seconds=60,
    )
    client = remote_client(make_app(policy=policy))
    headers = {"Origin": ORIGIN}
    assert (
        client.post("/api/v10/web/private-external-login", headers=headers).status_code
        == 200
    )
    assert (
        client.post("/api/v10/web/private-external-login", headers=headers).status_code
        == 200
    )
    response = client.post("/api/v10/web/private-external-login", headers=headers)
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


def test_frontend_remote_mutations_use_transient_session_bootstrap_csrf() -> None:
    api_source = (WEB_SOURCE / "app-shell" / "api.ts").read_text(encoding="utf-8")
    assert "__Host-omni_v10_csrf" not in api_source
    assert "document.cookie" not in api_source
    assert "readCookie(" not in api_source
    assert '"/api/v10/web/session"' in api_source
    assert "csrf_token: csrfToken" in api_source
    assert "csrfHeaderToken" in api_source
    assert "X-Omni-CSRF" in api_source
    assert "localStorage" not in api_source
    assert "sessionStorage" not in api_source
