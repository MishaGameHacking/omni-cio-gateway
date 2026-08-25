from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from omni_cio.web.browser_security_v1 import (
    BROWSER_SESSION_COOKIE,
    BrowserCookiePolicyV1,
)
from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.product_identity_v1 import ProductAccountScopeV1
from omni_cio.web.provider_auth_routes_v1 import (
    TELEGRAM_CALLBACK_PATH,
    TELEGRAM_START_PATH,
    ProviderAuthRouteServicesV1,
)
from omni_cio.web.provider_auth_v1 import ProviderAuthorizationStartV1
from omni_cio.web.session_v1 import SessionRegistryV1, SessionScopeV1
from omni_cio.web.telegram_oidc_v1 import TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT


HOSTNAME = "omni-cio-v10-web.onrender.com"
ORIGIN = f"https://{HOSTNAME}"
RELEASE_SHA = "a" * 40
FIXED_NOW = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)
PREVIEW_CREATED_AT = datetime(2026, 8, 21, tzinfo=timezone.utc)
CSRF_KEY = bytes([61]) * 32


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


@dataclass(slots=True)
class _FakeProviderRuntime:
    provider: IdentityProviderV1 = IdentityProviderV1.TELEGRAM
    started_browser_proof: str | None = None

    def start(
        self,
        *,
        now: datetime,
        browser_proof: str | None = None,
    ) -> ProviderAuthorizationStartV1:
        assert now == FIXED_NOW
        assert browser_proof is not None
        self.started_browser_proof = browser_proof
        return ProviderAuthorizationStartV1(
            authorization_url=TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT,
            browser_proof=browser_proof,
            expires_at=FIXED_NOW + timedelta(minutes=5),
            authorization_query="fixture=1",
        )

    def complete(
        self,
        *,
        state: str,
        code: str,
        browser_proof: str,
        now: datetime,
        device_id: str | None = None,
    ) -> VerifiedExternalIdentityV1:
        assert state == "a" * 43
        assert code == "accepted"
        assert browser_proof == self.started_browser_proof
        assert now == FIXED_NOW
        assert device_id is None
        return VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.TELEGRAM,
            subject="phase5-test-subject",
        )


class _FakeProductAuthentication:
    def __init__(self, sessions: SessionRegistryV1) -> None:
        self._sessions = sessions

    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        assert identity.provider == IdentityProviderV1.TELEGRAM
        assert now == FIXED_NOW
        return ProductAccountScopeV1(
            user_id="user:v1:phase5_test",
            tenant_id="tenant:v1:phase5_test",
        )

    def revoke_session(self, token: str | None, *, now: datetime) -> bool:
        return self._sessions.revoke(token, now=now)

    def bind_session(
        self,
        token: str,
        account_scope: ProductAccountScopeV1,
        *,
        now: datetime,
    ) -> SessionScopeV1:
        return self._sessions.bind(
            token=token,
            user_id=account_scope.user_id,
            tenant_id=account_scope.tenant_id,
            now=now,
        )


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
        "<!doctype html><html><body>OMNI-CIO TECHNICAL</body></html>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('technical')", encoding="utf-8")
    return web_dist


def _provider_services(
    sessions: SessionRegistryV1,
    *,
    configured: bool = False,
) -> tuple[ProviderAuthRouteServicesV1, BrowserCookiePolicyV1]:
    cookies = BrowserCookiePolicyV1(csrf_binding_key=CSRF_KEY)
    return (
        ProviderAuthRouteServicesV1(
            runtimes=(_FakeProviderRuntime(),) if configured else (),
            authentication=(
                _FakeProductAuthentication(sessions) if configured else None
            ),
            cookies=cookies,
            now=lambda: FIXED_NOW,
        ),
        cookies,
    )


def _app(
    tmp_path: Path,
    *,
    database_probe=lambda: None,
    sessions: SessionRegistryV1 | None = None,
    provider_configured: bool = False,
):
    session_registry = sessions or SessionRegistryV1(PREVIEW_SESSION_POLICY)
    provider_auth, cookies = _provider_services(
        session_registry,
        configured=provider_configured,
    )
    app = create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=session_registry,
            database_probe=database_probe,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            now=lambda: FIXED_NOW,
            provider_auth=provider_auth,
        ),
        web_dist=_web_dist(tmp_path),
    )
    return app, session_registry, cookies


def _client(tmp_path: Path, *, database_probe=lambda: None) -> TestClient:
    app, _, _ = _app(tmp_path, database_probe=database_probe)
    return TestClient(app, base_url=ORIGIN)


def _set_authenticated_session(
    client: TestClient,
    sessions: SessionRegistryV1,
    cookies: BrowserCookiePolicyV1,
    *,
    user_id: str = "user:v1:phase5_test",
    tenant_id: str = "tenant:v1:phase5_test",
) -> str:
    token, _ = sessions.create(user_id=user_id, tenant_id=tenant_id, now=FIXED_NOW)
    csrf = cookies.csrf_token(token)
    client.cookies.set(BROWSER_SESSION_COOKIE, token)
    client.cookies.set(CSRF_COOKIE, csrf)
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
    assert params == (PREVIEW_USER_ID,)


def test_synthetic_scope_startup_verification_fails_closed_on_drift() -> None:
    connection = _ScopeConnection(
        (PREVIEW_TENANT_ID, "1.0", 1, "user", "0" * 64)
    )
    with pytest.raises(RuntimeError, match="HOSTED_PREVIEW_SYNTHETIC_SCOPE_DRIFT"):
        _verify_synthetic_scope(connection)


def test_public_health_and_mode_metadata_are_hardened(tmp_path: Path) -> None:
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

    mode = client.get("/api/v10/web/preview-mode")
    assert mode.json() == {
        "enabled": False,
        "synthetic": True,
        "broker_credentials_enabled": False,
        "registration_enabled": False,
        "label": "Synthetic technical boundary",
    }


def test_deployed_human_session_bypass_routes_are_absent(tmp_path: Path) -> None:
    app, sessions, cookies = _app(tmp_path)
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v10/web/preview-login" not in paths
    assert "/api/v10/web/private-test-login" not in paths
    assert "/api/v10/web/private-external-login" not in paths

    client = TestClient(app, base_url=ORIGIN)
    csrf = _set_authenticated_session(client, sessions, cookies)
    for path in (
        "/api/v10/web/preview-login",
        "/api/v10/web/private-test-login",
        "/api/v10/web/private-external-login",
    ):
        response = client.post(path, headers={"Origin": ORIGIN, CSRF_HEADER: csrf})
        assert response.status_code == 404
        assert response.json() == {"detail": "NOT_FOUND"}


def test_unconfigured_provider_routes_exist_but_fail_closed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    providers = client.get("/api/v10/web/auth/providers").json()
    assert providers == [
        {"provider": "telegram", "enabled": False, "reason": "NOT_CONFIGURED"},
        {"provider": "vk_id", "enabled": False, "reason": "NOT_CONFIGURED"},
    ]

    assert client.get(TELEGRAM_START_PATH).status_code == 404
    rejected_origin = client.post(TELEGRAM_START_PATH)
    assert rejected_origin.status_code == 403
    configured_absent = client.post(
        TELEGRAM_START_PATH,
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    assert configured_absent.status_code == 503
    assert configured_absent.json() == {"detail": "IDENTITY_PROVIDER_NOT_CONFIGURED"}


def test_hosted_provider_callback_composes_verified_identity_to_session(
    tmp_path: Path,
) -> None:
    app, _, cookies = _app(tmp_path, provider_configured=True)
    client = TestClient(app, base_url=ORIGIN)

    start = client.post(
        TELEGRAM_START_PATH,
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    assert start.status_code == 303
    assert start.headers["location"] == (
        TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT + "?fixture=1"
    )
    proof_cookie = cookies.proof_cookie(IdentityProviderV1.TELEGRAM)
    proof = client.cookies.get(proof_cookie)
    assert proof is not None
    assert len(proof) == 43

    callback = client.get(
        TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "/"
    assert client.cookies.get(proof_cookie) is None
    assert client.cookies.get(BROWSER_SESSION_COOKIE)
    assert client.cookies.get(CSRF_COOKIE)

    session = client.get("/api/v10/web/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is True
    assert session.json()["expires_at"]
    assert session.headers[CSRF_HEADER] == client.cookies.get(CSRF_COOKIE)


def test_authenticated_technical_boundary_returns_safe_empty_product_views(
    tmp_path: Path,
) -> None:
    app, sessions, cookies = _app(tmp_path)
    client = TestClient(app, base_url=ORIGIN)
    _set_authenticated_session(client, sessions, cookies)

    health = client.get("/api/v10/web/health")
    assert health.status_code == 200
    assert health.json()["state"] == "READY"

    portfolio = client.get("/api/v10/web/portfolio-dashboard").json()
    assert portfolio["state"] == "EMPTY"
    assert portfolio["accounts"] == []
    assert portfolio["warnings"][0]["code"] == "SYNTHETIC_PREVIEW_NO_BROKER_DATA"

    assert client.get("/api/v10/web/watchtower-incidents").json()["incidents"] == []
    assert client.get("/api/v10/web/research-dossiers").json()["dossiers"] == []
    decision = client.get("/api/v10/web/decision-plan").json()
    assert decision["execution_authorized"] is False
    assert decision["trading_methods"] is False

    system = client.get("/api/v10/web/system-status").json()
    assert system["release"]["git_sha"] == RELEASE_SHA
    assert system["safety"]["real_execution_enabled"] is False
    assert system["safety"]["broker_write_authority"] is False


def test_csrf_logout_revokes_server_session(tmp_path: Path) -> None:
    app, sessions, cookies = _app(tmp_path)
    client = TestClient(app, base_url=ORIGIN)
    csrf = _set_authenticated_session(client, sessions, cookies)

    no_origin = client.post("/api/v10/web/session/logout")
    assert no_origin.status_code == 403
    no_csrf = client.post("/api/v10/web/session/logout", headers={"Origin": ORIGIN})
    assert no_csrf.status_code == 403

    accepted = client.post(
        "/api/v10/web/session/logout",
        headers={"Origin": ORIGIN, CSRF_HEADER: csrf},
    )
    assert accepted.status_code == 200
    assert client.get("/api/v10/web/session").json() == {"authenticated": False}


def test_revoke_all_is_true_user_wide_revocation(tmp_path: Path) -> None:
    sessions = SessionRegistryV1(PREVIEW_SESSION_POLICY)
    app, _, cookies = _app(tmp_path, sessions=sessions)
    first = TestClient(app, base_url=ORIGIN)
    second = TestClient(app, base_url=ORIGIN)
    first_csrf = _set_authenticated_session(first, sessions, cookies)
    _set_authenticated_session(second, sessions, cookies)

    accepted = first.post(
        "/api/v10/web/session/revoke-all",
        headers={"Origin": ORIGIN, CSRF_HEADER: first_csrf},
    )
    assert accepted.status_code == 200
    assert first.get("/api/v10/web/session").json() == {"authenticated": False}
    assert second.get("/api/v10/web/session").json() == {"authenticated": False}


def test_database_failure_is_fail_closed_without_raw_diagnostics(tmp_path: Path) -> None:
    state = {"failed": False}

    def probe() -> None:
        if state["failed"]:
            raise RuntimeError("database-secret-should-never-escape")

    client = _client(tmp_path, database_probe=probe)
    state["failed"] = True
    health = client.get("/healthz")
    assert health.status_code == 503
    assert "database-secret" not in health.text


def test_untrusted_host_plain_http_and_cross_origin_are_rejected(tmp_path: Path) -> None:
    app, _, _ = _app(tmp_path)
    client = TestClient(app, base_url=ORIGIN)
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400

    plain = TestClient(app, base_url=f"http://{HOSTNAME}")
    assert plain.get("/healthz").status_code == 403

    cross_origin = client.post(
        TELEGRAM_START_PATH,
        headers={"Origin": "https://evil.example"},
    )
    assert cross_origin.status_code == 403
    assert cross_origin.json() == {"detail": "ORIGIN_REQUIRED"}


def test_unknown_api_path_fails_closed_instead_of_serving_spa(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/v10/web/not-a-real-route")
    assert response.status_code == 404
    assert response.json() == {"detail": "NOT_FOUND"}
    assert response.headers["cache-control"] == "no-store"


def test_spa_fallback_and_assets_are_served_from_reviewed_build(tmp_path: Path) -> None:
    client = _client(tmp_path)
    fallback = client.get("/portfolio")
    assert fallback.status_code == 200
    assert "OMNI-CIO TECHNICAL" in fallback.text
    assert fallback.headers["cache-control"] == "no-cache"

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "technical" in asset.text
