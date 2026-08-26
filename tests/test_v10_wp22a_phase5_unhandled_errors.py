from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from apps.api.hosted_preview import (
    HostedPreviewServicesV1,
    PREVIEW_SESSION_POLICY,
    create_hosted_preview_app,
)
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.provider_auth_routes_v1 import ProviderAuthRouteServicesV1
from omni_cio.web.session_v1 import SessionRegistryV1


HOSTNAME = "omni-cio-v10-web.onrender.com"
ORIGIN = f"https://{HOSTNAME}"
RELEASE_SHA = "a" * 40
FIXED_NOW = datetime(2026, 8, 25, 21, 0, tzinfo=timezone.utc)
SENSITIVE_MARKER = "unhandled-sensitive-diagnostic"


def _web_dist(tmp_path: Path) -> Path:
    web_dist = tmp_path / "dist"
    web_dist.mkdir(parents=True)
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body>OMNI-CIO TECHNICAL</body></html>",
        encoding="utf-8",
    )
    return web_dist


def _app_with_unhandled_routes(tmp_path: Path):
    sessions = SessionRegistryV1(PREVIEW_SESSION_POLICY)
    provider_auth = ProviderAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=BrowserCookiePolicyV1(csrf_binding_key=bytes([73]) * 32),
        now=lambda: FIXED_NOW,
    )
    app = create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=sessions,
            database_probe=lambda: None,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            now=lambda: FIXED_NOW,
            provider_auth=provider_auth,
        ),
        web_dist=_web_dist(tmp_path),
    )

    def crash() -> None:
        raise RuntimeError(SENSITIVE_MARKER)

    app.router.routes.insert(
        0,
        APIRoute(
            "/api/v10/web/__test-unhandled",
            endpoint=crash,
            methods=["GET"],
        ),
    )
    app.router.routes.insert(
        0,
        APIRoute(
            "/__test-unhandled-web",
            endpoint=crash,
            methods=["GET"],
        ),
    )
    return app


@pytest.mark.parametrize(
    ("path", "expected_cache_control"),
    (
        ("/api/v10/web/__test-unhandled", "no-store"),
        ("/__test-unhandled-web", "no-cache"),
    ),
)
def test_unhandled_errors_preserve_hardened_response_envelope(
    tmp_path: Path,
    path: str,
    expected_cache_control: str,
) -> None:
    app = _app_with_unhandled_routes(tmp_path)
    client = TestClient(
        app,
        base_url=ORIGIN,
        raise_server_exceptions=False,
    )

    response = client.get(path)

    assert response.status_code == 500
    assert response.json() == {"detail": "INTERNAL_ERROR"}
    assert SENSITIVE_MARKER not in response.text
    assert response.headers["cache-control"] == expected_cache_control
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    vary = {
        value.strip().lower()
        for value in response.headers["vary"].split(",")
        if value.strip()
    }
    assert {"origin", "sec-fetch-site"} <= vary
