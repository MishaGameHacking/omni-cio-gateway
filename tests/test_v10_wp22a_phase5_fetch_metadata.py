from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.hosted_preview import HostedPreviewSecurityMiddlewareV1
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.provider_auth_routes_v1 import TELEGRAM_START_PATH
from omni_cio.web.session_v1 import SessionRegistryV1


HOSTNAME = "omni-cio-v10-web.onrender.com"
ORIGIN = f"https://{HOSTNAME}"
COOKIES = BrowserCookiePolicyV1(csrf_binding_key=bytes([71]) * 32)
FIXED_NOW = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/safe")
    def safe() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/preexisting-vary")
    def preexisting_vary() -> JSONResponse:
        return JSONResponse(
            {"ok": True},
            headers={"Vary": "Accept-Encoding, origin"},
        )

    @app.post(TELEGRAM_START_PATH)
    def provider_start() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/unsafe")
    def unsafe() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        HostedPreviewSecurityMiddlewareV1,
        hostname=HOSTNAME,
        cookies=COOKIES,
        sessions=SessionRegistryV1(),
        now=lambda: FIXED_NOW,
    )
    return app


def test_cross_site_fetch_metadata_blocks_unsafe_provider_start() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    response = client.post(
        TELEGRAM_START_PATH,
        headers={
            "Origin": ORIGIN,
            "Sec-Fetch-Site": "cross-site",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FETCH_METADATA_REJECTED"}


def test_same_site_is_not_trusted_as_same_origin_for_unsafe_request() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    response = client.post(
        TELEGRAM_START_PATH,
        headers={
            "Origin": ORIGIN,
            "Sec-Fetch-Site": "same-site",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FETCH_METADATA_REJECTED"}


def test_same_origin_provider_start_uses_origin_fallback_without_session_csrf() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    response = client.post(
        TELEGRAM_START_PATH,
        headers={
            "Origin": ORIGIN,
            "Sec-Fetch-Site": "same-origin",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_missing_fetch_metadata_falls_back_to_exact_origin_and_csrf_policy() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    response = client.post("/unsafe", headers={"Origin": ORIGIN})

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF_REJECTED"}


def test_security_response_varies_on_origin_and_fetch_metadata() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    response = client.get("/safe")

    assert response.status_code == 200
    assert response.headers["vary"] == "Origin, Sec-Fetch-Site"


def test_security_response_preserves_existing_vary_without_duplicates() -> None:
    client = TestClient(_app(), base_url=ORIGIN)

    response = client.get("/preexisting-vary")

    assert response.status_code == 200
    assert response.headers["vary"] == "Accept-Encoding, origin, Sec-Fetch-Site"
