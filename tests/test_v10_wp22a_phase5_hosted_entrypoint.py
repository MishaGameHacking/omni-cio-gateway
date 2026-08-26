from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI

import apps.api.hosted_preview as hosted_preview
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.provider_auth_routes_v1 import ProviderAuthRouteServicesV1
from omni_cio.web.session_v1 import SessionRegistryV1


def test_render_entrypoint_wires_phase5_provider_auth_builder(monkeypatch) -> None:
    monkeypatch.setenv("OMNI_V10_HOSTED_PREVIEW", "1")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "omni-cio-v10-web.onrender.com")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a" * 40)
    monkeypatch.setenv("OMNI_V10_POSTGRES_DSN", "postgresql://placeholder.invalid/db")

    raw_connection = SimpleNamespace(autocommit=False)
    serialized_connection = SimpleNamespace()
    sessions = SessionRegistryV1(hosted_preview.PREVIEW_SESSION_POLICY)
    provider_auth = ProviderAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=BrowserCookiePolicyV1(csrf_binding_key=bytes([31]) * 32),
    )
    captured: dict[str, Any] = {}

    monkeypatch.setattr(hosted_preview, "connect_postgres", lambda _: raw_connection)
    monkeypatch.setattr(
        hosted_preview,
        "_configure_long_lived_web_connection",
        lambda connection: setattr(connection, "autocommit", True),
    )
    monkeypatch.setattr(
        hosted_preview,
        "_SerializedWebConnection",
        lambda connection: serialized_connection,
    )
    monkeypatch.setattr(hosted_preview, "_probe_hosted_preview_database", lambda _: None)
    monkeypatch.setattr(
        hosted_preview,
        "PostgresWebSessionRegistryV1",
        lambda connection, policy: sessions,
    )

    def build_provider_auth(**kwargs: Any) -> ProviderAuthRouteServicesV1:
        captured["builder"] = kwargs
        return provider_auth

    monkeypatch.setattr(
        hosted_preview,
        "build_wp22a_phase5_provider_auth",
        build_provider_auth,
    )

    expected_app = FastAPI()

    def create_hosted(
        services: hosted_preview.HostedPreviewServicesV1,
        **kwargs: Any,
    ) -> FastAPI:
        captured["services"] = services
        captured["create_hosted_kwargs"] = kwargs
        return expected_app

    monkeypatch.setattr(hosted_preview, "create_hosted_preview_app", create_hosted)

    app = hosted_preview.create_app()

    assert app is expected_app
    builder = captured["builder"]
    assert builder["connection"] is serialized_connection
    assert builder["sessions"] is sessions
    assert builder["canonical_origin"] == "https://omni-cio-v10-web.onrender.com"
    services = captured["services"]
    assert services.provider_auth is provider_auth
    assert services.sessions is sessions
    assert captured["create_hosted_kwargs"] == {
        "trusted_edge_tls_terminated": True,
    }
    assert raw_connection.autocommit is True
