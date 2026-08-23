from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from apps.api.hosted_preview import (
    CSRF_COOKIE,
    CSRF_HEADER,
    HostedPreviewServicesV1,
    PREVIEW_SESSION_POLICY,
    PREVIEW_TENANT_ID,
    PREVIEW_USER_ID,
    _record_sha256,
    _verify_synthetic_scope,
    create_hosted_preview_app,
)
from omni_cio.web.session_v1 import SessionRegistryV1


HOSTNAME = "omni-cio-v10-web.onrender.com"
ORIGIN = f"https://{HOSTNAME}"
RELEASE_SHA = "a" * 40
FIXED_NOW = datetime(2026, 8, 21, 6, 0, tzinfo=timezone.utc)
PREVIEW_CREATED_AT = datetime(2026, 8, 21, tzinfo=timezone.utc)


class _RowCursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _ScopeConnection:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row
        self.statements: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
        **_: Any,
    ) -> _RowCursor:
        self.statements.append((query, params))
        return _RowCursor(self.row)


def _preview_user_digest() -> str:
    return _record_sha256(
        {
            "schema_version": "1.0",
            "identity_version": 1,
            "user_id": PREVIEW_USER_ID,
            "tenant_id": PREVIEW_TENANT_ID,
            "role": "user",
            "created_at": PREVIEW_CREATED_AT.isoformat(),
        }
    )


def _web_dist(tmp_path: Path) -> Path:
    web_dist = tmp_path / "dist"
    assets = web_dist / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body>OMNI-CIO PREVIEW</body></html>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('preview')", encoding="utf-8")
    return web_dist


def _app(
    tmp_path: Path,
    *,
    database_probe=lambda: None,
    sessions: SessionRegistryV1 | None = None,
):
    return create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=sessions or SessionRegistryV1(PREVIEW_SESSION_POLICY),
            database_probe=database_probe,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            now=lambda: FIXED_NOW,
        ),
        web_dist=_web_dist(tmp_path),
    )


def _client(tmp_path: Path, *, database_probe=lambda: None) -> TestClient:
    return TestClient(
        _app(tmp_path, database_probe=database_probe),
        base_url=ORIGIN,
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v10/web/preview-login",
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    csrf = response.headers.get(CSRF_HEADER)
    assert csrf
    assert csrf == client.cookies.get(CSRF_COOKIE)
    csrf_cookies = [
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{CSRF_COOKIE}=")
    ]
    assert len(csrf_cookies) == 1
    assert "HttpOnly" in csrf_cookies[0]
    return csrf


def test_synthetic_scope_startup_verification_is_read_only() -> None:
    connection = _ScopeConnection(
        (
            PREVIEW_TENANT_ID,
            "1.0",
            1,
            "user",
            _preview_user_digest(),
        )
    )

    _verify_synthetic_scope(connection)

    assert len(connection.statements) == 1
    query, params = connection.statements[0]
    assert query.lstrip().upper().startswith("SELECT ")
    assert "INSERT" not in query.upper()
    assert "ON CONFLICT" not in query.upper()
    assert params == (PREVIEW_USER_ID,)


def test_synthetic_scope_startup_verification_fails_closed_on_drift() -> None:
    connection = _ScopeConnection(
        (
            PREVIEW_TENANT_ID,
            "1.0",
            1,
            "user",
            "0" * 64,
        )
    )

    with pytest.raises(RuntimeError, match="HOSTED_PREVIEW_SYNTHETIC_SCOPE_DRIFT"):
        _verify_synthetic_scope(connection)


def test_public_health_and_preview_metadata_are_hardened(tmp_path: Path) -> None:
    client = _client(tmp_path)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "release_sha": RELEASE_SHA,
        "database": "READY",
        "synthetic_preview": True,
    }
    assert health.headers["strict-transport-security"] == "max-age=31536000"
    assert health.headers["cache-control"] == "no-store"
    assert "default-src 'self'" in health.headers["content-security-policy"]
    assert "access-control-allow-origin" not in health.headers

    preview = client.get("/api/v10/web/preview-mode")
    assert preview.status_code == 200
    assert preview.json() == {
        "enabled": True,
        "synthetic": True,
        "broker_credentials_enabled": False,
        "registration_enabled": False,
        "label": "Безопасная публичная демонстрация",
    }


def test_preview_login_requires_https_origin_and_issues_server_session(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    anonymous = client.get("/api/v10/web/session")
    assert anonymous.json() == {"authenticated": False}
    assert CSRF_HEADER not in anonymous.headers
    rejected = client.post("/api/v10/web/preview-login")
    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "ORIGIN_REQUIRED"}

    csrf = _login(client)
    session = client.get("/api/v10/web/session")
    assert session.status_code == 200
    assert session.json() == {
        "authenticated": True,
        "user_label": "DEMO USER",
        "tenant_label": "SYNTHETIC PREVIEW",
        "expires_at": "2026-08-21T08:00:00+00:00",
    }
    assert session.headers[CSRF_HEADER] == csrf
    assert csrf == client.cookies.get(CSRF_COOKIE)


def test_authenticated_preview_returns_safe_empty_product_views(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    csrf = _login(client)

    health = client.get("/api/v10/web/health")
    assert health.status_code == 200
    assert health.json()["state"] == "READY"

    portfolio = client.get("/api/v10/web/portfolio-dashboard").json()
    assert portfolio["state"] == "EMPTY"
    assert portfolio["accounts"] == []
    assert portfolio["warnings"][0]["code"] == (
        "SYNTHETIC_PREVIEW_NO_BROKER_DATA"
    )

    watchtower = client.get("/api/v10/web/watchtower-incidents").json()
    assert watchtower["state"] == "EMPTY"
    assert watchtower["incidents"] == []

    research = client.get("/api/v10/web/research-dossiers").json()
    assert research["state"] == "EMPTY"
    assert research["dossiers"] == []

    decision = client.get("/api/v10/web/decision-plan").json()
    assert decision["state"] == "EMPTY"
    assert decision["execution_authorized"] is False
    assert decision["trading_methods"] is False

    system = client.get("/api/v10/web/system-status").json()
    assert system["state"] == "READY"
    assert system["release"]["git_sha"] == RELEASE_SHA
    assert system["database"]["exact_migration_state"] is True
    assert system["safety"] == {
        "mode": "READ_ONLY_DIAGNOSTIC",
        "real_execution_enabled": False,
        "trading_methods": False,
        "broker_write_authority": False,
        "public_ingress": False,
        "watchtower_enabled": False,
    }

    broker = client.post(
        "/api/v10/web/broker-connections/preview",
        headers={"Origin": ORIGIN, CSRF_HEADER: csrf},
        json={"token": "never-used"},
    )
    assert broker.status_code == 403
    assert broker.json() == {
        "detail": "BROKER_CREDENTIALS_DISABLED_IN_SYNTHETIC_PREVIEW"
    }
    assert client.get("/api/v10/web/broker-connections").json() == []
    assert client.get("/api/v10/web/wp15-live-acceptance/status").json() == {
        "enabled": False
    }


def test_csrf_logout_revokes_preview_session(tmp_path: Path) -> None:
    client = _client(tmp_path)
    csrf = _login(client)

    rejected = client.post(
        "/api/v10/web/session/logout",
        headers={"Origin": ORIGIN},
    )
    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "CSRF_REJECTED"}

    accepted = client.post(
        "/api/v10/web/session/logout",
        headers={"Origin": ORIGIN, CSRF_HEADER: csrf},
    )
    assert accepted.status_code == 200
    assert accepted.json() == {"ok": True}
    assert client.get("/api/v10/web/session").json() == {
        "authenticated": False
    }


def test_revoke_all_preview_route_cannot_revoke_another_visitors_session(
    tmp_path: Path,
) -> None:
    sessions = SessionRegistryV1(PREVIEW_SESSION_POLICY)
    app = _app(tmp_path, sessions=sessions)
    first = TestClient(app, base_url=ORIGIN)
    second = TestClient(app, base_url=ORIGIN)
    first_csrf = _login(first)
    _login(second)

    accepted = first.post(
        "/api/v10/web/session/revoke-all",
        headers={"Origin": ORIGIN, CSRF_HEADER: first_csrf},
    )

    assert accepted.status_code == 200
    assert accepted.json() == {"ok": True}
    assert first.get("/api/v10/web/session").json() == {
        "authenticated": False
    }
    assert second.get("/api/v10/web/session").json()["authenticated"] is True


def test_database_failure_is_fail_closed_without_raw_diagnostics(
    tmp_path: Path,
) -> None:
    state = {"failed": False}

    def probe() -> None:
        if state["failed"]:
            raise RuntimeError("database-secret-should-never-escape")

    client = _client(tmp_path, database_probe=probe)
    state["failed"] = True
    health = client.get("/healthz")
    assert health.status_code == 503
    assert health.json() == {
        "status": "unavailable",
        "release_sha": RELEASE_SHA,
        "synthetic_preview": True,
    }
    assert "database-secret" not in health.text


def test_untrusted_host_plain_http_and_cross_origin_are_rejected(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400

    plain = TestClient(_app(tmp_path), base_url=f"http://{HOSTNAME}")
    assert plain.get("/healthz").status_code == 403

    cross_origin = client.post(
        "/api/v10/web/preview-login",
        headers={"Origin": "https://evil.example"},
    )
    assert cross_origin.status_code == 403
    assert cross_origin.json() == {"detail": "ORIGIN_REQUIRED"}


def test_unknown_api_path_fails_closed_instead_of_serving_spa(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get("/api/v10/web/not-a-real-route")

    assert response.status_code == 404
    assert response.json() == {"detail": "NOT_FOUND"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/json")


def test_spa_fallback_and_assets_are_served_from_reviewed_build(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    fallback = client.get("/portfolio")
    assert fallback.status_code == 200
    assert "OMNI-CIO PREVIEW" in fallback.text
    assert fallback.headers["cache-control"] == "no-cache"

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "preview" in asset.text
