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
from apps.api.hosted_runtime import (
    HOSTED_SESSION_POLICY,
    _trusted_edge_tls_terminated,
)
from apps.api.telegram_auth import (
    TelegramAuthConfigurationError,
    build_telegram_provider_auth,
)
from omni_cio.persistence.migration import discover_migrations
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
    def __init__(
        self,
        role: str,
        *,
        missing_relation: str | None = None,
        extra_relation_privilege: bool = False,
        policy_drift: bool = False,
    ) -> None:
        self._role = role
        self._missing_relation = missing_relation
        self._extra_relation_privilege = extra_relation_privilege
        self._policy_drift = policy_drift

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
        if "AS database_owned" in statement:
            return _Result(one=(0, 0, 0, 0))
        if "has_database_privilege" in statement:
            return _Result(one=(True, False, False))
        if "has_schema_privilege" in statement:
            return _Result(one=(True, False, False))
        if "aclexplode" in statement:
            return _Result(one=(0,))
        if "information_schema.role_table_grants" in statement:
            rows = [
                    ("broker_accounts", "INSERT", "NO"),
                    ("broker_accounts", "SELECT", "NO"),
                    ("broker_connection_accounts", "INSERT", "NO"),
                    ("broker_connection_accounts", "SELECT", "NO"),
                    ("broker_connections", "INSERT", "NO"),
                    ("broker_connections", "SELECT", "NO"),
                    ("broker_connections", "UPDATE", "NO"),
                    ("external_identity_bindings", "INSERT", "NO"),
                    ("external_identity_bindings", "SELECT", "NO"),
                    ("provider_auth_transactions", "DELETE", "NO"),
                    ("provider_auth_transactions", "INSERT", "NO"),
                    ("provider_auth_transactions", "SELECT", "NO"),
                    ("tenants", "INSERT", "NO"),
                    ("users", "INSERT", "NO"),
                    ("users", "SELECT", "NO"),
                    ("web_sessions", "DELETE", "NO"),
                    ("web_sessions", "INSERT", "NO"),
                    ("web_sessions", "SELECT", "NO"),
                    ("web_sessions", "UPDATE", "NO"),
            ]
            if self._extra_relation_privilege:
                rows.append(("tenants", "SELECT", "NO"))
            return _Result(rows=rows)
        if "information_schema.table_privileges" in statement:
            return _Result(rows=[])
        if "information_schema.role_routine_grants" in statement:
            return _Result(rows=[("current_tenant_scope", "EXECUTE", "NO")])
        if "information_schema.routine_privileges" in statement:
            return _Result(rows=[])
        if "c.relkind = 'S'" in statement:
            return _Result(one=(0,))
        if "SELECT to_regclass" in statement:
            relations: list[object | None] = [
                "omni_cio_v10.tenants",
                "omni_cio_v10.users",
                "omni_cio_v10.external_identity_bindings",
                "omni_cio_v10.web_sessions",
                "omni_cio_v10.provider_auth_transactions",
            ]
            if self._missing_relation is not None:
                relations[relations.index(self._missing_relation)] = None
            return _Result(one=tuple(relations))
        if "FROM pg_catalog.pg_proc function_record" in statement:
            return _Result(
                one=(
                    "sql",
                    "s",
                    False,
                    False,
                    "SELECT NULLIF("
                    "pg_catalog.current_setting('omni_cio.tenant_id', true), '')",
                )
            )
        if "FROM pg_catalog.pg_policy p" in statement:
            expression = (
                "tenant_id = 'tenant:v1:owner'"
                if self._policy_drift
                else "tenant_id = omni_cio_v10.current_tenant_scope()"
            )
            return _Result(
                rows=[
                    (
                        "broker_accounts",
                        "broker_accounts_tenant_isolation",
                        "*",
                        True,
                        True,
                        expression,
                        expression,
                    ),
                    (
                        "broker_connection_accounts",
                        "broker_connection_accounts_tenant_isolation",
                        "*",
                        True,
                        True,
                        expression,
                        expression,
                    ),
                    (
                        "broker_connections",
                        "broker_connections_tenant_isolation",
                        "*",
                        True,
                        True,
                        expression,
                        expression,
                    ),
                ]
            )
        if "FROM pg_catalog.pg_class c" in statement:
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
    connection = _RuntimeProbeConnection("omni_cio_other_runtime")
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_DATABASE_ROLE_DRIFT"):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role="omni_cio_timeweb_candidate",
        )


def test_provider_neutral_runtime_probe_rejects_incomplete_auth_schema() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(
        role,
        missing_relation="omni_cio_v10.provider_auth_transactions",
    )
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_DATABASE_SCHEMA_INCOMPLETE"):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_probe_rejects_extra_relation_authority() -> None:
    role = "omni_cio_timeweb_candidate"
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_RELATION_PRIVILEGE_DRIFT",
    ):
        probe_hosted_runtime_database(
            _RuntimeProbeConnection(role, extra_relation_privilege=True),
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_probe_rejects_rls_policy_drift() -> None:
    role = "omni_cio_timeweb_candidate"
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_TENANT_POLICY_DRIFT"):
        probe_hosted_runtime_database(
            _RuntimeProbeConnection(role, policy_drift=True),
            expected_runtime_role=role,
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


def test_livez_can_use_plain_http_only_from_explicit_loopback(tmp_path: Path) -> None:
    app = create_hosted_app(
        HostedRuntimeServicesV1(
            sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
            database_probe=lambda: None,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            provider_auth=_disabled_auth(),
            synthetic_preview=False,
        ),
        web_dist=_web_dist(tmp_path),
        additional_hosts=("localhost",),
        trusted_edge_tls_terminated=False,
        allow_insecure_loopback_livez=True,
        provider_start_paths=frozenset(),
        provider_route_installer=lambda app, *, services: None,
    )
    loopback = TestClient(
        app,
        base_url="http://localhost",
        client=("127.0.0.1", 50000),
    )
    assert loopback.get("/livez").status_code == 200
    assert loopback.get("/healthz").status_code == 403

    non_loopback = TestClient(
        app,
        base_url="http://localhost",
        client=("203.0.113.10", 50000),
    )
    assert non_loopback.get("/livez").status_code == 403


def test_timeweb_trusted_edge_flag_is_explicit_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED", raising=False)
    assert _trusted_edge_tls_terminated() is False

    monkeypatch.setenv("OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED", "true")
    assert _trusted_edge_tls_terminated() is True

    monkeypatch.setenv("OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED", "unexpected")
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_TRUSTED_EDGE_TLS_FLAG_INVALID",
    ):
        _trusted_edge_tls_terminated()


def test_private_routes_fail_closed_without_session(tmp_path: Path) -> None:
    app = create_hosted_app(
        HostedRuntimeServicesV1(
            sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
            database_probe=lambda: None,
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
    client = TestClient(app, base_url="http://localhost")

    response = client.get("/api/v10/web/portfolio-dashboard")

    assert response.status_code == 401
    assert response.json() == {"detail": "AUTHENTICATION_REQUIRED"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


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
    expected_series = discover_migrations()
    expected_latest = expected_series[-1]
    expected_label = f"{expected_latest.version:04d}_{expected_latest.name}"
    assert database["label"] == "PostgreSQL 18"
    assert payload["database"]["current_migration"] is None
    assert payload["database"]["expected_migration"] == expected_label
    assert payload["database"]["migration_count"] == len(expected_series)
    assert payload["database"]["exact_migration_state"] is False
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


def test_telegram_public_and_login_flags_must_transition_together() -> None:
    for env in (
        {"PUBLIC_MULTI_USER_ENABLED": "true"},
        {"OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true"},
    ):
        connection = object()
        sessions = SessionRegistryV1(HOSTED_SESSION_POLICY)
        with pytest.raises(
            TelegramAuthConfigurationError,
            match="TELEGRAM_AUTH_ACTIVATION_FLAGS_MISMATCH",
        ):
            build_telegram_provider_auth(
                connection=connection,
                sessions=sessions,
                canonical_origin="https://omnicio.ru",
                env=env,
            )


def test_telegram_activation_pair_requires_provider_configuration() -> None:
    connection = object()
    sessions = SessionRegistryV1(HOSTED_SESSION_POLICY)
    with pytest.raises(
        TelegramAuthConfigurationError,
        match="TELEGRAM_AUTH_ACTIVATION_CONFIGURATION_REQUIRED",
    ):
        build_telegram_provider_auth(
            connection=connection,
            sessions=sessions,
            canonical_origin="https://omnicio.ru",
            env={
                "PUBLIC_MULTI_USER_ENABLED": "true",
                "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true",
            },
        )


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

    for marker in (
        "omni_cio.real_trading",
        "TINVEST_TRADING_TOKEN",
        "REAL_TRADING_ENABLED",
        "PostOrder",
    ):
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
    assert "from apps.api.app import" not in runtime
    assert "trusted_edge_tls_terminated=True" not in runtime
    assert "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED" in runtime
    assert "allow_insecure_loopback_livez=True" in runtime

    postgres_connection = (
        root / "apps" / "api" / "postgres_web_connection.py"
    ).read_text(encoding="utf-8")
    assert "t_tech" not in postgres_connection
    assert "grpc" not in postgres_connection


def test_timeweb_dockerfile_uses_provider_neutral_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert "EXPOSE 8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://localhost:8080/livez" in dockerfile
    assert "apps.api.hosted_runtime:create_app" in dockerfile
    assert "ARG OMNI_V10_RELEASE_SHA" not in dockerfile
    assert "ENV OMNI_V10_RELEASE_SHA" not in dockerfile
    assert "SSL_TBANK_VERIFY=True" in dockerfile
    assert "prepare_v10_tbank_pip_ca_bundle.py" in dockerfile
    assert 'PIP_CERT="$PIP_CERT_PATH" python -m pip install' in dockerfile
    for secret_name in (
        "OMNI_V10_POSTGRES_DSN",
        "TELEGRAM_BOT_TOKEN",
        "TINVEST_TOKEN",
        "TINVEST_TRADING_TOKEN",
    ):
        assert f"ARG {secret_name}" not in dockerfile
        assert f"ENV {secret_name}" not in dockerfile
    assert "Dockerfile.cloudflare" not in dockerfile
    assert "wrangler" not in dockerfile.lower()
    assert "render" not in dockerfile.lower()
    assert "neon" not in dockerfile.lower()
