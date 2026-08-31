from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

if __package__:
    from .v10_jsonc import loads_jsonc
else:
    from v10_jsonc import loads_jsonc


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RUNTIME_COMPATIBILITY_CONTRACT.json"
WRANGLER = ROOT / "wrangler.jsonc"
WORKER = ROOT / "cloudflare/src/index.js"
DOCKERFILE = ROOT / "Dockerfile.cloudflare"
RUNTIME = ROOT / "apps/api/cloudflare_runtime.py"
WEB_CONFIG = ROOT / "apps/web/vite.config.ts"
_RUNTIME_ROLE_BINDING = "OMNI_V10_POSTGRES_RUNTIME_ROLE"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_FILE_UNREADABLE:{path}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        source = _read(path)
        value = loads_jsonc(source) if path.suffix == ".jsonc" else json.loads(source)
    except ValueError as exc:
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_JSON_INVALID:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_OBJECT_REQUIRED:{path}")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_{label}_INVALID")
    return value


def _single_object(value: object, label: str, code: str) -> dict[str, Any]:
    if not isinstance(value, list) or len(value) != 1:
        raise RuntimeError(code)
    return _object(value[0], label)


def _require_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker not in source for marker in markers):
        raise RuntimeError(code)


def _forbid_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker in source for marker in markers):
        raise RuntimeError(code)


def _runtime_roles(contract: dict[str, Any]) -> dict[str, Any]:
    database = _object(contract.get("database"), "DATABASE")
    roles = _object(database.get("runtime_roles"), "DATABASE_RUNTIME_ROLES")
    expected = {
        "production": "omni_cio_cloudflare_prod",
        "staging": "omni_cio_cloudflare_staging",
        "historical_hosted_preview_preserved": "omni_cio_hosted_api",
    }
    if roles != expected:
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_ROLES_INVALID")
    return roles


def _validate_contract_identity(contract: dict[str, Any]) -> None:
    if contract.get("schema") != "omni-cio.v10.cloudflare-runtime-compatibility.v1":
        raise RuntimeError("CLOUDFLARE_RUNTIME_SCHEMA_INVALID")
    if contract.get("milestone") != "CF-B":
        raise RuntimeError("CLOUDFLARE_RUNTIME_MILESTONE_INVALID")


def _validate_contract_runtime(contract: dict[str, Any]) -> None:
    frontend = _object(contract.get("frontend"), "FRONTEND")
    backend = _object(contract.get("backend"), "BACKEND")
    database = _object(contract.get("database"), "DATABASE")
    cost = _object(contract.get("cost"), "COST")
    release = _object(contract.get("release"), "RELEASE")
    if frontend.get("placement") != "WORKERS_STATIC_ASSETS":
        raise RuntimeError("CLOUDFLARE_RUNTIME_FRONTEND_PLACEMENT_INVALID")
    if backend.get("placement") != "CLOUDFLARE_CONTAINER":
        raise RuntimeError("CLOUDFLARE_RUNTIME_BACKEND_PLACEMENT_INVALID")
    if backend.get("python") != "3.14.6":
        raise RuntimeError("CLOUDFLARE_RUNTIME_PYTHON_BASELINE_INVALID")
    if backend.get("instance_type") != "lite" or backend.get("max_instances") != 1:
        raise RuntimeError("CLOUDFLARE_RUNTIME_CONTAINER_BOUND_INVALID")
    if database.get("major") != 18 or database.get("provider") != "Neon":
        raise RuntimeError("CLOUDFLARE_RUNTIME_POSTGRES18_INVALID")
    if (
        database.get("hyperdrive_used") is not False
        or database.get("d1_used") is not False
    ):
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_SUBSTITUTION_FORBIDDEN")
    _runtime_roles(contract)
    if cost.get("automatic_paid_overage_authorized") is not False:
        raise RuntimeError("CLOUDFLARE_RUNTIME_PAID_OVERAGE_FORBIDDEN")
    if release.get("worker_name") != "omni-cio-v10-web":
        raise RuntimeError("CLOUDFLARE_RUNTIME_WORKER_NAME_INVALID")


def _validate_contract_security(contract: dict[str, Any]) -> None:
    security = _object(contract.get("security"), "SECURITY")
    expected_true = (
        "incoming_forwarded_headers_are_stripped_at_worker",
        "container_forwarded_header_trust_disabled",
        "client_ip_forwarded_via_internal_edge_header",
        "asgi_scheme_restored_from_fixed_cloudflare_edge",
        "container_is_not_direct_public_ingress",
        "container_transport_uses_fixed_internal_url",
        "public_route_is_encoded_in_internal_headers",
        "public_route_is_validated_before_asgi_restore",
        "internal_route_headers_are_removed_before_app",
        "runtime_database_secret_required",
        "database_secret_absence_returns_503_before_container_start",
        "runtime_database_role_source_controlled",
        "runtime_database_role_validated_at_worker_and_container",
    )
    for key in expected_true:
        if security.get(key) is not True:
            raise RuntimeError(f"CLOUDFLARE_RUNTIME_{key.upper()}_MUST_BE_TRUE")
    if (
        security.get("container_transport_url")
        != "https://omni-cio.internal/_omni/cloudflare-proxy"
    ):
        raise RuntimeError("CLOUDFLARE_RUNTIME_CONTAINER_TRANSPORT_URL_INVALID")
    expected_false = (
        "telegram_vk_provider_auth_enabled",
        "public_multi_user_enabled",
        "broker_write",
        "trading_methods",
        "real_trading_enabled",
    )
    for key in expected_false:
        if security.get(key) is not False:
            raise RuntimeError(f"CLOUDFLARE_RUNTIME_{key.upper()}_MUST_BE_FALSE")


def _validate_wrangler(contract: dict[str, Any]) -> None:
    release = _object(contract.get("release"), "RELEASE")
    roles = _runtime_roles(contract)
    wrangler = _load_json(WRANGLER)
    if wrangler.get("name") != release["worker_name"]:
        raise RuntimeError("CLOUDFLARE_RUNTIME_WRANGLER_NAME_MISMATCH")
    if wrangler.get("main") != "./cloudflare/src/index.js":
        raise RuntimeError("CLOUDFLARE_RUNTIME_WORKER_ENTRY_INVALID")
    assets = _object(wrangler.get("assets"), "ASSETS")
    if assets.get("directory") != "./apps/web/dist":
        raise RuntimeError("CLOUDFLARE_RUNTIME_ASSET_DIRECTORY_INVALID")
    if assets.get("not_found_handling") != "single-page-application":
        raise RuntimeError("CLOUDFLARE_RUNTIME_SPA_FALLBACK_INVALID")
    if assets.get("run_worker_first") != ["/api/*", "/healthz"]:
        raise RuntimeError("CLOUDFLARE_RUNTIME_EDGE_ROUTING_INVALID")
    production_vars = _object(wrangler.get("vars"), "VARS")
    if production_vars != {_RUNTIME_ROLE_BINDING: roles["production"]}:
        raise RuntimeError("CLOUDFLARE_RUNTIME_PRODUCTION_ROLE_BINDING_INVALID")
    environments = _object(wrangler.get("env"), "ENV")
    staging = _object(environments.get("staging"), "STAGING")
    staging_vars = _object(staging.get("vars"), "STAGING_VARS")
    if staging_vars != {_RUNTIME_ROLE_BINDING: roles["staging"]}:
        raise RuntimeError("CLOUDFLARE_RUNTIME_STAGING_ROLE_BINDING_INVALID")
    container = _single_object(
        wrangler.get("containers"),
        "CONTAINER",
        "CLOUDFLARE_RUNTIME_CONTAINER_CONFIG_INVALID",
    )
    if (
        container.get("image") != "./Dockerfile.cloudflare"
        or container.get("instance_type") != "lite"
        or container.get("max_instances") != 1
    ):
        raise RuntimeError("CLOUDFLARE_RUNTIME_CONTAINER_LIMIT_INVALID")


def _validate_worker() -> None:
    worker = _read(WORKER)
    required = (
        'INTERNAL_HOST = "omni-cio.internal"',
        'INTERNAL_PROXY_URL = "https://omni-cio.internal/_omni/cloudflare-proxy"',
        'REQUIRED_DATABASE_ROLE_ENV_NAME = "OMNI_V10_POSTGRES_RUNTIME_ROLE"',
        '"omni_cio_cloudflare_prod"',
        '"omni_cio_cloudflare_staging"',
        "ALLOWED_DATABASE_RUNTIME_ROLES.has(value)",
        "OMNI_V10_POSTGRES_RUNTIME_ROLE: runtimeRole",
        "CLOUDFLARE_RUNTIME_DATABASE_ROLE_NOT_CONFIGURED",
        'sleepAfter = "1m"',
        'headers.delete("x-forwarded-for")',
        'headers.delete("x-forwarded-host")',
        'headers.delete("forwarded")',
        'headers.delete("x-forwarded-proto")',
        'headers.delete("x-omni-client-ip")',
        'headers.delete("x-omni-route-path")',
        'headers.delete("x-omni-route-query")',
        'headers.delete("x-omni-edge-provider")',
        'headers.delete("x-omni-source-sha")',
        'headers.set("x-omni-client-ip", clientIp)',
        'headers.set("x-omni-route-path", encodeURIComponent(routeUrl.pathname))',
        'headers.set("x-omni-route-query", encodeURIComponent(query))',
        "return new Request(INTERNAL_PROXY_URL, {",
        'duplex: "half"',
        "CLOUDFLARE_RUNTIME_DATABASE_NOT_CONFIGURED",
        'url.pathname === "/api/v10/release"',
        "public_multi_user_enabled: false",
        "real_trading_enabled: false",
    )
    _require_markers(worker, required, "CLOUDFLARE_RUNTIME_WORKER_GUARD_MISSING")
    _forbid_markers(
        worker,
        (
            'headers.set("x-forwarded-for"',
            'headers.set("x-forwarded-host"',
            'headers.set("x-forwarded-proto"',
            "new Request(request,",
            "url.pathname = routeUrl.pathname",
            "url.search = routeUrl.search",
        ),
        "CLOUDFLARE_RUNTIME_DYNAMIC_BACKEND_ORIGIN_INVALID",
    )


def _validate_dockerfile() -> None:
    dockerfile = _read(DOCKERFILE)
    _require_markers(
        dockerfile,
        (
            "FROM python:3.14.6-slim-bookworm",
            "RUN npm ci --ignore-scripts --prefix apps/web",
            "python -m pip install --require-hashes -r requirements.txt",
            "USER omni",
            "apps.api.cloudflare_runtime:create_app",
        ),
        "CLOUDFLARE_RUNTIME_DOCKER_GUARD_MISSING",
    )
    _forbid_markers(
        dockerfile,
        ("--proxy-headers", "--forwarded-allow-ips"),
        "CLOUDFLARE_RUNTIME_PROXY_HEADER_TRUST_FORBIDDEN",
    )


def _validate_runtime() -> None:
    runtime = _read(RUNTIME)
    required = (
        'OMNI_V10_CLOUDFLARE_RUNTIME", ""',
        '"CLOUDFLARE_RUNTIME_NOT_ENABLED"',
        '"OMNI_V10_POSTGRES_DSN"',
        '"OMNI_V10_POSTGRES_RUNTIME_ROLE"',
        '"omni_cio_cloudflare_prod"',
        '"omni_cio_cloudflare_staging"',
        '"CLOUDFLARE_RUNTIME_DATABASE_ROLE_INVALID"',
        '"CLOUDFLARE_RUNTIME_DATABASE_ROLE_DRIFT"',
        '"CLOUDFLARE_RUNTIME_DATABASE_MEMBERSHIP_FORBIDDEN"',
        '"CLOUDFLARE_RUNTIME_DATABASE_FORCE_RLS_REQUIRED"',
        "_verify_synthetic_scope(connection)",
        '"/_omni/cloudflare-proxy"',
        "_validated_client_ip(headers)",
        'restored_scope["scheme"] = "https"',
        'restored_scope["client"] = (client_ip, 0)',
        "_INTERNAL_EDGE_HEADERS = frozenset(",
        "if bytes(key).lower() not in _INTERNAL_EDGE_HEADERS",
        'scope_type == "websocket"',
        '"type": "websocket.close"',
        '"code": 1008',
        "CloudflareEdgeRouteRestoreV1",
        "runtime_role = _runtime_database_role()",
        "_probe_cloudflare_database(",
        "expected_runtime_role=runtime_role",
        "provider_auth=None",
        "trusted_edge_tls_terminated=False",
    )
    _require_markers(runtime, required, "CLOUDFLARE_RUNTIME_FASTAPI_GUARD_MISSING")
    _forbid_markers(
        runtime,
        ("_probe_hosted_preview_database(connection)", '"omni_cio_hosted_api"'),
        "CLOUDFLARE_RUNTIME_HISTORICAL_ROLE_REUSE_FORBIDDEN",
    )


def _validate_web_config() -> None:
    web = _read(WEB_CONFIG)
    indexes = (
        web.find("process.env.WORKERS_CI_COMMIT_SHA"),
        web.find("process.env.GITHUB_SHA"),
        web.find("process.env.RENDER_GIT_COMMIT"),
    )
    if min(indexes) < 0:
        raise RuntimeError("CLOUDFLARE_RUNTIME_WEB_SHA_SOURCE_MISSING")
    if not indexes[0] < indexes[1] < indexes[2]:
        raise RuntimeError("CLOUDFLARE_RUNTIME_WEB_SHA_PRECEDENCE_INVALID")


def validate() -> None:
    contract = _load_json(CONTRACT)
    _validate_contract_identity(contract)
    _validate_contract_runtime(contract)
    _validate_contract_security(contract)
    _validate_wrangler(contract)
    _validate_worker()
    _validate_dockerfile()
    _validate_runtime()
    _validate_web_config()


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare runtime compatibility contract passed.")
    print("Frontend: Workers Static Assets")
    print("Backend: Cloudflare Container / Python 3.14.6")
    print("Dependency install lifecycle scripts: DISABLED")
    print("Streaming request bodies: EXPLICIT HALF-DUPLEX")
    print("Incoming forwarded headers: STRIPPED; UVICORN TRUST DISABLED")
    print("Client IP + TLS scheme: RESTORED FROM INTERNAL CLOUDFLARE CONTRACT")
    print("WebSocket direct ingress: PROTOCOL-SAFE REJECTION")
    print("Database: direct Neon PostgreSQL 18; environment role BOUND+VALIDATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
