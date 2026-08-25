from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.hosted_preview import HostedPreviewSecurityMiddlewareV1
from omni_cio.web.browser_security_v1 import (
    BROWSER_SESSION_COOKIE,
    BrowserCookiePolicyV1,
)
from omni_cio.web.request_limits_v1 import (
    HostedRequestAbuseControlV1,
    RequestRatePolicyV1,
)
from omni_cio.web.session_v1 import SessionRegistryV1, SessionScopeV1


HOSTNAME = "omni-cio-v10-web.onrender.com"
ORIGIN = f"https://{HOSTNAME}"
COOKIES = BrowserCookiePolicyV1(csrf_binding_key=bytes([91]) * 32)
FIXED_NOW = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)


class _CountingSessions:
    def __init__(self) -> None:
        self.resolve_calls = 0

    def resolve(
        self,
        token: str | None,
        *,
        now: datetime,
    ) -> SessionScopeV1 | None:
        assert now == FIXED_NOW
        assert token
        self.resolve_calls += 1
        return None


def _app(
    *,
    policy: RequestRatePolicyV1 | None = None,
    sessions: SessionRegistryV1 | _CountingSessions | None = None,
    trusted_edge_tls_terminated: bool = False,
) -> tuple[FastAPI, SessionRegistryV1 | _CountingSessions]:
    app = FastAPI()

    @app.get("/api/test")
    def api_test() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    registry = sessions or SessionRegistryV1()
    effective_policy = policy or RequestRatePolicyV1(
        global_api_requests=8,
        health_requests=2,
        anonymous_requests=1,
        authenticated_session_requests=2,
        max_session_keys=8,
    )
    app.add_middleware(
        HostedPreviewSecurityMiddlewareV1,
        hostname=HOSTNAME,
        cookies=COOKIES,
        sessions=registry,
        now=lambda: FIXED_NOW,
        trusted_edge_tls_terminated=trusted_edge_tls_terminated,
        abuse=HostedRequestAbuseControlV1(effective_policy),
    )
    return app, registry


def test_anonymous_api_rate_limit_returns_retry_after() -> None:
    app, _ = _app()
    client = TestClient(app, base_url=ORIGIN)

    assert client.get("/api/test").status_code == 200
    limited = client.get("/api/test")

    assert limited.status_code == 429
    assert limited.json() == {"detail": "RATE_LIMITED"}
    assert limited.headers["retry-after"] == "1"


def test_live_session_gets_separate_bounded_request_dimension() -> None:
    app, sessions = _app()
    assert isinstance(sessions, SessionRegistryV1)
    token, _ = sessions.create(
        user_id="user:v1:rate_test",
        tenant_id="tenant:v1:rate_test",
        now=FIXED_NOW,
    )
    client = TestClient(app, base_url=ORIGIN)
    client.cookies.set(BROWSER_SESSION_COOKIE, token)

    assert client.get("/api/test").status_code == 200
    assert client.get("/api/test").status_code == 200
    limited = client.get("/api/test")

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "1"


def test_shape_valid_but_unresolved_session_stays_in_anonymous_bucket() -> None:
    app, _ = _app()
    client = TestClient(app, base_url=ORIGIN)
    client.cookies.set(BROWSER_SESSION_COOKIE, "s" * 43)

    assert client.get("/api/test").status_code == 200
    limited = client.get("/api/test")

    assert limited.status_code == 429


def test_global_cap_runs_before_attacker_controlled_session_lookup() -> None:
    sessions = _CountingSessions()
    app, _ = _app(
        policy=RequestRatePolicyV1(
            global_api_requests=1,
            anonymous_requests=10,
            authenticated_session_requests=10,
            max_session_keys=8,
        ),
        sessions=sessions,
    )
    client = TestClient(app, base_url=ORIGIN)
    client.cookies.set(BROWSER_SESSION_COOKIE, "a" * 43)

    assert client.get("/api/test").status_code == 200
    assert sessions.resolve_calls == 1

    client.cookies.set(BROWSER_SESSION_COOKIE, "b" * 43)
    limited = client.get("/api/test")
    assert limited.status_code == 429
    assert sessions.resolve_calls == 1


def test_malformed_session_cookie_skips_session_store_lookup() -> None:
    sessions = _CountingSessions()
    app, _ = _app(sessions=sessions)
    client = TestClient(app, base_url=ORIGIN)
    client.cookies.set(BROWSER_SESSION_COOKIE, "not-a-valid-session-token")

    assert client.get("/api/test").status_code == 200
    assert sessions.resolve_calls == 0
    assert client.get("/api/test").status_code == 429
    assert sessions.resolve_calls == 0


def test_client_forwarded_proto_cannot_bypass_direct_http_gate() -> None:
    app, _ = _app()
    client = TestClient(app, base_url=f"http://{HOSTNAME}")

    response = client.get("/healthz", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 403
    assert response.json() == {"detail": "HTTPS_REQUIRED"}


def test_source_declared_trusted_edge_accepts_edge_terminated_http_hop() -> None:
    app, _ = _app(trusted_edge_tls_terminated=True)
    client = TestClient(app, base_url=f"http://{HOSTNAME}")

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_has_independent_bounded_monitoring_capacity() -> None:
    app, _ = _app()
    client = TestClient(app, base_url=ORIGIN)

    assert client.get("/api/test").status_code == 200
    assert client.get("/api/test").status_code == 429
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").status_code == 200
    limited = client.get("/healthz")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "1"
