from __future__ import annotations

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


HOSTNAME = "omni-cio-v10-web.onrender.com"
ORIGIN = f"https://{HOSTNAME}"
COOKIES = BrowserCookiePolicyV1(csrf_binding_key=bytes([91]) * 32)


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/test")
    def api_test() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    policy = RequestRatePolicyV1(
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
        abuse=HostedRequestAbuseControlV1(policy),
    )
    return app


def test_anonymous_api_rate_limit_returns_retry_after() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    assert client.get("/api/test").status_code == 200
    limited = client.get("/api/test")

    assert limited.status_code == 429
    assert limited.json() == {"detail": "RATE_LIMITED"}
    assert limited.headers["retry-after"] == "1"


def test_session_cookie_gets_separate_bounded_request_dimension() -> None:
    client = TestClient(_app(), base_url=ORIGIN)
    client.cookies.set(BROWSER_SESSION_COOKIE, "s" * 43)

    assert client.get("/api/test").status_code == 200
    assert client.get("/api/test").status_code == 200
    limited = client.get("/api/test")

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "1"


def test_invalid_session_cookie_cannot_escape_anonymous_bucket() -> None:
    client = TestClient(_app(), base_url=ORIGIN)
    client.cookies.set(BROWSER_SESSION_COOKIE, "not-a-valid-session-token")

    assert client.get("/api/test").status_code == 200
    limited = client.get("/api/test")

    assert limited.status_code == 429


def test_health_has_independent_bounded_monitoring_capacity() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    assert client.get("/api/test").status_code == 200
    assert client.get("/api/test").status_code == 429
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").status_code == 200
    limited = client.get("/healthz")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "1"
