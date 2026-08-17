from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.web.external_access_v1 import (
    CF_ACCESS_IDENTITY_HEADER,
    CF_ACCESS_JWT_HEADER,
    CSRF_COOKIE,
    CSRF_HEADER,
    FORWARDED_PROTO_HEADER,
    ExternalAccessPolicyV1,
    install_external_access_v1,
)
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc)
OWNER_IDENTITY = "owner@example.test"
HOST = "omni.example.test"
ORIGIN = f"https://{HOST}"
OWNER_SHA256 = hashlib.sha256(OWNER_IDENTITY.casefold().encode("utf-8")).hexdigest()
REMOTE_HEADERS = {
    CF_ACCESS_IDENTITY_HEADER: OWNER_IDENTITY,
    CF_ACCESS_JWT_HEADER: "header.payload.signature",
    FORWARDED_PROTO_HEADER: "https",
}


def test_authenticated_mutation_rate_limit_fails_closed_without_blocking_status() -> (
    None
):
    sessions = SessionRegistryV1()
    app = FastAPI()

    @app.post("/mutate")
    def mutate() -> dict[str, bool]:
        return {"ok": True}

    install_external_access_v1(
        app,
        sessions=sessions,
        policy=ExternalAccessPolicyV1(
            canonical_host=HOST,
            owner_identity_sha256=OWNER_SHA256,
            mutation_attempts=2,
            mutation_window_seconds=60,
        ),
        now=lambda: NOW,
    )
    client = TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 51100),
        headers=REMOTE_HEADERS,
    )

    login = client.post(
        "/api/v10/web/private-external-login",
        headers={"Origin": ORIGIN},
    )
    assert login.status_code == 200
    csrf = client.cookies.get(CSRF_COOKIE)
    assert csrf
    mutation_headers = {"Origin": ORIGIN, CSRF_HEADER: csrf}

    assert client.post("/mutate", headers=mutation_headers).status_code == 200
    assert client.post("/mutate", headers=mutation_headers).status_code == 200
    limited = client.post("/mutate", headers=mutation_headers)
    assert limited.status_code == 429
    assert limited.json()["detail"] == "RATE_LIMITED"

    status = client.get("/api/v10/web/private-external-login/status")
    assert status.status_code == 200
    assert status.json() == {"enabled": True}
