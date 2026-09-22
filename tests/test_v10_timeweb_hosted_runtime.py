from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from apps.api.hosted_app import (
    HostedRuntimeServicesV1,
    _system_status,
    create_hosted_app,
)
from apps.api.hosted_database_runtime import (
    probe_hosted_runtime_database,
    validate_hosted_runtime_role,
)
from apps.api.hosted_runtime import HOSTED_SESSION_POLICY
from apps.api.telegram_auth import build_telegram_provider_auth
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import (
    ORDINARY_LOGIN_PROVIDERS,
    IdentityProviderV1,
)
from omni_cio.web.telegram_auth_services_v1 import TelegramAuthRouteServicesV1
from omni_cio.web.session_v1 import SessionRegistryV1


HOSTNAME = "omnicio.ru"
RELEASE_SHA = "a" * 40


def _web_dist(tmp_path: Path) -> Path:
    web_dist = tmp_path / "dist"
    web_dist.mkdir(parents=True)
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body>OMNI-CIO</body></html>",
        encoding="utf-8",
    )
    return web_dist


def _disabled_auth() -> TelegramAuthRouteServicesV1:
    return TelegramAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=BrowserCookiePolicyV1(csrf_binding_key=bytes([19]) * 32),
    )


class _Result:
    def __init__(
        self,
        *,
        one: tuple[object, ...] | None = None,
        rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._one = one
        self._rows = [] if rows is None else rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self._one

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)


class _RuntimeProbeConnection:
    def __init__(self, role: str) -> None:
        self._role = role

    def execute(self, statement: str, params: object = None) -> _Result:
        del params
        if statement == "SHOW server_version_num":
            return _Result(one=("180000",))
        if "FROM pg_catalog.pg_roles" in statement:
            return _Result(
                one=(
                    self._role,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                )
            )
        if "FROM pg_catalog.pg_auth_members" in statement:
            return _Result(one=(0,))
        if "SELECT to_regclass" in statement:
            return _Result(
                one=(
                    "omni_cio_v10.tenants",
                    "omni_cio_v10.users",
                    "omni_cio_v10.web_sessions",
                )
            )
        if "FROM pg_catalog.pg_class" in statement:
            return _Result(
                rows=[
                    ("broker_accounts", True, True),
                    ("broker_connection_accounts", True, True),
                    ("broker_connections", True, True),
                ]
            )
        raise AssertionError(statement)


def test_provider_neutral_runtime_role_probe_accepts_exact_current_user() -> None:
    role = validate_hosted_runtime_role("omni_cio_timeweb_candidate")
    probe_hosted_runtime_database(
        _RuntimeProbeConnection(role),
        expected_runtime_role=role,
    )


def test_provider_neutral_runtime_role_probe_rejects_identity_drift() -> None:
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_DATABASE_ROLE_DRIFT"):
        probe_hosted_runtime_database(
            _RuntimeProbeConnection("omni_cio_other_runtime"),
            expected_runtime_role="omni_cio_timeweb_candidate",
        )


def test_provider_neutral_runtime_role_validation_fails_closed() -> None:
    for role in ("", "OMNI-CIO", "omni cio", "../runtime", "a" * 64):
        with pytest.raises(
            RuntimeError,
            match="HOSTED_RUNTIME_DATABASE_ROLE_INVALID",
        ):
            validate_hosted_runtime_role(role)


def test_livez_is_process_only_after_runtime_startup(tmp_path: Path) -> None:
    state = {"calls": 0, "fail": False}

    def database_probe() -> None:
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("database unavailable")

    app = create_hosted_app(
        HostedRuntimeServicesV1(
            sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
            database_probe=database_probe,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            provider_auth=_disabled_auth(),
            synthetic_preview=False,
        ),
        web_dist=_web_dist(tmp_path),
        additional_hosts=("localhost",),
        trusted_edge_tls_terminated=True,
        provider_start_paths=frozenset(),
        provider_route_installer=lambda app, *, services: None,
    )
    assert state["calls"] == 1
    state["fail"] = True

    client = TestClient(app, base_url="http://localhost")
    live = client.get("/livez")
    assert live.status_code == 200
    assert live.json() == {"status": "ok", "release_sha": RELEASE_SHA}
    assert state["calls"] == 1

    ready = client.get("/healthz")
    assert ready.status_code == 503
    assert ready.json()["status"] == "unavailable"
    assert state["calls"] == 2


def test_non_synthetic_status_is_provider_neutral() -> None:
    services = HostedRuntimeServicesV1(
        sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
        database_probe=lambda: None,
        hostname=HOSTNAME,
        release_sha=RELEASE_SHA,
        provider_auth=_disabled_auth(),
        synthetic_preview=False,
    )

    payload = _system_status(services, now="2026-09-22T12:00:00+00:00")
    database = next(item for item in payload["services"] if item["id"] == "database")
    assert database["label"] == "PostgreSQL 18"
    assert "Neon" not in str(payload)


def test_current_identity_and_cookie_defaults_are_telegram_only() -> None:
    assert ORDINARY_LOGIN_PROVIDERS == (IdentityProviderV1.TELEGRAM,)
    cookies = BrowserCookiePolicyV1(csrf_binding_key=bytes([23]) * 32)
    assert cookies.allowed_providers == (IdentityProviderV1.TELEGRAM,)
    services = TelegramAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=cookies,
    )
    assert [item.provider for item in services.descriptors()] == [
        IdentityProviderV1.TELEGRAM
    ]
    assert services.disabled_reason(IdentityProviderV1.TELEGRAM) == "NOT_CONFIGURED"
    with pytest.raises(ValueError, match="TELEGRAM_AUTH_PROVIDER_INVALID"):
        services.disabled_reason(IdentityProviderV1.VK_ID)


def test_telegram_builder_exposes_only_telegram_when_fail_closed() -> None:
    services = build_telegram_provider_auth(
        connection=object(),  # unused while the provider is unconfigured
        sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
        canonical_origin="https://omnicio.ru",
        env={
            "OMNI_V10_VK_ID_CLIENT_ID": "historical-value-is-ignored",
            "OMNI_V10_VK_ID_LOGIN_ENABLED": "true",
        },
    )

    descriptors = services.descriptors()
    assert [item.provider for item in descriptors] == [IdentityProviderV1.TELEGRAM]
    assert services.runtimes == ()
    assert services.registration_enabled is False
    with pytest.raises(ValueError, match="BROWSER_PROVIDER_INVALID"):
        services.cookies.proof_cookie(IdentityProviderV1.VK_ID)


def test_timeweb_runtime_source_has_no_retired_provider_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    current_sources = (
        root / "apps" / "api" / "hosted_runtime.py",
        root / "apps" / "api" / "hosted_app.py",
        root / "apps" / "api" / "hosted_database_runtime.py",
        root / "apps" / "api" / "telegram_auth.py",
        root / "omni_cio" / "web" / "telegram_auth_routes_v1.py",
        root / "omni_cio" / "web" / "telegram_auth_services_v1.py",
    )
    forbidden = (
        "cf_d_database_bootstrap",
        "wp22a_phase5_auth",
        "vk_id_oauth",
        "RENDER_",
        "CLOUDFLARE_",
        "NEON_",
        "hosted_preview",
        "provider_auth_routes_v1",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in current_sources)
    for marker in forbidden:
        assert marker not in combined

    runtime = current_sources[0].read_text(encoding="utf-8")
    assert "probe_hosted_runtime_database" in runtime
    assert "_probe_runtime_database" not in runtime
    assert "_probe_hosted_preview_database" not in runtime
    assert "OMNI_V10_POSTGRES_RUNTIME_ROLE" in runtime
    assert "omni_cio_hosted_api" not in runtime
    assert "omni_cio_cloudflare_" not in runtime
    assert "HOSTED_SESSION_POLICY" in runtime
    hosted_app = current_sources[1].read_text(encoding="utf-8")
    assert "HOSTED_SESSION_POLICY" not in hosted_app
    assert 'additional_hosts=("localhost",)' in runtime


def test_timeweb_dockerfile_uses_provider_neutral_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert "EXPOSE 8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://localhost:8080/livez" in dockerfile
    assert "apps.api.hosted_runtime:create_app" in dockerfile
    assert "ARG OMNI_V10_RELEASE_SHA" not in dockerfile
    assert "ENV OMNI_V10_RELEASE_SHA" not in dockerfile
    assert "Dockerfile.cloudflare" not in dockerfile
    assert "wrangler" not in dockerfile.lower()
    assert "render" not in dockerfile.lower()
    assert "neon" not in dockerfile.lower()