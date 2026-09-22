from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from apps.api.hosted_preview import (
    PREVIEW_SESSION_POLICY,
    HostedPreviewServicesV1,
    _system_status,
    create_hosted_preview_app,
)
from apps.api.telegram_auth import build_telegram_provider_auth
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.provider_auth_routes_v1 import ProviderAuthRouteServicesV1
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


def _disabled_auth() -> ProviderAuthRouteServicesV1:
    return ProviderAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=BrowserCookiePolicyV1(csrf_binding_key=bytes([19]) * 32),
        descriptor_providers=(IdentityProviderV1.TELEGRAM,),
    )


def test_livez_is_process_only_after_runtime_startup(tmp_path: Path) -> None:
    state = {"calls": 0, "fail": False}

    def database_probe() -> None:
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("database unavailable")

    app = create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=SessionRegistryV1(PREVIEW_SESSION_POLICY),
            database_probe=database_probe,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            provider_auth=_disabled_auth(),
            synthetic_preview=False,
        ),
        web_dist=_web_dist(tmp_path),
        additional_hosts=("localhost",),
        trusted_edge_tls_terminated=True,
        trusted_edge_hostname_suffix=None,
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
    services = HostedPreviewServicesV1(
        sessions=SessionRegistryV1(PREVIEW_SESSION_POLICY),
        database_probe=lambda: None,
        hostname=HOSTNAME,
        release_sha=RELEASE_SHA,
        provider_auth=_disabled_auth(),
        synthetic_preview=False,
    )

    payload = _system_status(services, now="2026-09-22T12:00:00+00:00")
    database = next(
        item for item in payload["services"] if item["id"] == "database"
    )
    assert database["label"] == "PostgreSQL 18"
    assert "Neon" not in str(payload)


def test_telegram_builder_exposes_only_telegram_when_fail_closed() -> None:
    services = build_telegram_provider_auth(
        connection=object(),  # unused while the provider is unconfigured
        sessions=SessionRegistryV1(PREVIEW_SESSION_POLICY),
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
        root / "apps" / "api" / "telegram_auth.py",
        root / "omni_cio" / "web" / "telegram_auth_routes_v1.py",
    )
    forbidden = (
        "cf_d_database_bootstrap",
        "wp22a_phase5_auth",
        "vk_id_oauth",
        "RENDER_",
        "CLOUDFLARE_",
        "NEON_",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in current_sources)
    for marker in forbidden:
        assert marker not in combined

    runtime = current_sources[0].read_text(encoding="utf-8")
    assert "_probe_runtime_database" in runtime
    assert "_probe_hosted_preview_database" not in runtime
    assert "HOSTED_SESSION_POLICY" in runtime
    assert "PREVIEW_SESSION_POLICY" not in runtime
    assert 'additional_hosts=("localhost",)' in runtime


def test_timeweb_dockerfile_uses_provider_neutral_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert "EXPOSE 8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://localhost:8080/livez" in dockerfile
    assert "apps.api.hosted_runtime:create_app" in dockerfile
    assert "Dockerfile.cloudflare" not in dockerfile
    assert "wrangler" not in dockerfile.lower()
    assert "render" not in dockerfile.lower()
    assert "neon" not in dockerfile.lower()
