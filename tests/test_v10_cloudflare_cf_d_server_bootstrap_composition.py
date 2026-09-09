from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from apps.api.cf_d_database_bootstrap import (
    CF_D_DATABASE_BOOTSTRAP_PATH,
    install_cf_d_database_bootstrap_route,
)
from apps.api.hosted_preview import HostedPreviewServicesV1, create_hosted_preview_app
from omni_cio.web.session_v1 import SessionScopeV1


_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
_RELEASE_SHA = "a" * 40
_HOSTNAME = "omni-cio.example.com"
_STAGING_ROLE = "omni_cio_cloudflare_staging"
# Keep the tracked fixture free of any Basic-Auth-shaped credential literal.
_STAGING_DSN = "".join(
    (
        "postgresql://",
        _STAGING_ROLE,
        ":",
        "synthetic-credential-marker",
        "@",
        "ep-example.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require",
    )
)


class _Sessions:
    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]:
        del user_id, tenant_id, now
        raise AssertionError("session creation is not part of CF-D bootstrap")

    def resolve(
        self,
        token: str | None,
        *,
        now: datetime,
    ) -> SessionScopeV1 | None:
        del token, now
        return None

    def revoke(self, token: str | None, *, now: datetime) -> bool:
        del token, now
        return False

    def revoke_all_for_user(self, user_id: str, *, now: datetime) -> int:
        del user_id, now
        return 0


def _composed_app(web_dist: Path) -> Any:
    app = create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=_Sessions(),
            database_probe=lambda: None,
            hostname=_HOSTNAME,
            release_sha=_RELEASE_SHA,
        ),
        web_dist=web_dist,
    )
    install_cf_d_database_bootstrap_route(
        app,
        connection=object(),
        runtime_dsn=_STAGING_DSN,
        release_sha=_RELEASE_SHA,
        runtime_role=_STAGING_ROLE,
    )
    return app


def test_server_bootstrap_reaches_oidc_guard_without_browser_origin_or_csrf(
    tmp_path: Path,
) -> None:
    web_dist = tmp_path / "dist"
    web_dist.mkdir()
    (web_dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = _composed_app(web_dist)

    paths = [getattr(route, "path", "") for route in app.router.routes]
    assert paths.index(CF_D_DATABASE_BOOTSTRAP_PATH) < paths.index("/api/{path:path}")

    with TestClient(app, base_url=f"https://{_HOSTNAME}") as client:
        response = client.post(
            CF_D_DATABASE_BOOTSTRAP_PATH,
            headers={"X-Omni-Expected-Sha": _RELEASE_SHA},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "CLOUDFLARE_CF_D_OIDC_REQUIRED"}
    assert response.headers["cache-control"] == "no-store"


def test_server_bootstrap_exception_is_exact_post_path_only(tmp_path: Path) -> None:
    web_dist = tmp_path / "dist"
    web_dist.mkdir()
    (web_dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = _composed_app(web_dist)

    with TestClient(app, base_url=f"https://{_HOSTNAME}") as client:
        near_miss = client.post(
            f"{CF_D_DATABASE_BOOTSTRAP_PATH}-near-miss",
            headers={"X-Omni-Expected-Sha": _RELEASE_SHA},
        )
        wrong_method = client.put(
            CF_D_DATABASE_BOOTSTRAP_PATH,
            headers={"X-Omni-Expected-Sha": _RELEASE_SHA},
        )

    assert near_miss.status_code == 403
    assert near_miss.json() == {"detail": "ORIGIN_REQUIRED"}
    assert wrong_method.status_code == 403
    assert wrong_method.json() == {"detail": "ORIGIN_REQUIRED"}


def test_release_contract_freezes_server_bootstrap_composition() -> None:
    contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    cutover = contract["cutover"]
    assert cutover["production_database_bootstrap_route"] == (
        CF_D_DATABASE_BOOTSTRAP_PATH
    )
    assert cutover[
        "production_database_bootstrap_server_to_server_browser_mutation_exemption"
    ] is True
    assert cutover[
        "production_database_bootstrap_browser_mutation_exemption_exact_method"
    ] == "POST"
    assert cutover[
        "production_database_bootstrap_browser_mutation_exemption_exact_path_only"
    ] is True
    assert cutover[
        "production_database_bootstrap_route_priority_before_api_catchall_required"
    ] is True
    assert cutover["production_database_bootstrap_exact_sha_required"] is True
    assert cutover["production_database_bootstrap_github_oidc_required"] is True
