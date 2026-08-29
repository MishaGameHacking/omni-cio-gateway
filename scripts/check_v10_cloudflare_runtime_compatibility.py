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


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_FILE_UNREADABLE:{path}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        source = _read(path)
        value = loads_jsonc(source) if path.suffix == ".jsonc" else json.loads(source)
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_JSON_INVALID:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_OBJECT_REQUIRED:{path}")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RUNTIME_{label}_INVALID")
    return value


def validate() -> None:
    contract = _load_json(CONTRACT)
    if contract.get("schema") != "omni-cio.v10.cloudflare-runtime-compatibility.v1":
        raise RuntimeError("CLOUDFLARE_RUNTIME_SCHEMA_INVALID")
    if contract.get("milestone") != "CF-B":
        raise RuntimeError("CLOUDFLARE_RUNTIME_MILESTONE_INVALID")

    frontend = _object(contract.get("frontend"), "FRONTEND")
    backend = _object(contract.get("backend"), "BACKEND")
    database = _object(contract.get("database"), "DATABASE")
    security = _object(contract.get("security"), "SECURITY")
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
    if database.get("hyperdrive_used") is not False or database.get("d1_used") is not False:
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_SUBSTITUTION_FORBIDDEN")
    for key in (
        "telegram_vk_provider_auth_enabled",
        "public_multi_user_enabled",
        "broker_write",
        "trading_methods",
        "real_trading_enabled",
    ):
        if security.get(key) is not False:
            raise RuntimeError(f"CLOUDFLARE_RUNTIME_{key.upper()}_MUST_BE_FALSE")
    if cost.get("automatic_paid_overage_authorized") is not False:
        raise RuntimeError("CLOUDFLARE_RUNTIME_PAID_OVERAGE_FORBIDDEN")
    if release.get("worker_name") != "omni-cio-v10-web":
        raise RuntimeError("CLOUDFLARE_RUNTIME_WORKER_NAME_INVALID")

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
    containers = wrangler.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        raise RuntimeError("CLOUDFLARE_RUNTIME_CONTAINER_CONFIG_INVALID")
    container = _object(containers[0], "CONTAINER")
    if (
        container.get("image") != "./Dockerfile.cloudflare"
        or container.get("instance_type") != "lite"
        or container.get("max_instances") != 1
    ):
        raise RuntimeError("CLOUDFLARE_RUNTIME_CONTAINER_LIMIT_INVALID")

    worker = _read(WORKER)
    for marker in (
        'INTERNAL_HOST = "omni-cio.internal"',
        'sleepAfter = "1m"',
        'headers.delete("x-forwarded-proto")',
        'headers.set("x-forwarded-proto", "https")',
        'headers.set("x-forwarded-for", clientIp)',
        "CLOUDFLARE_RUNTIME_DATABASE_NOT_CONFIGURED",
        'url.pathname === "/api/v10/release"',
        "public_multi_user_enabled: false",
        "real_trading_enabled: false",
    ):
        if marker not in worker:
            raise RuntimeError("CLOUDFLARE_RUNTIME_WORKER_GUARD_MISSING")

    dockerfile = _read(DOCKERFILE)
    for marker in (
        "FROM python:3.14.6-slim-bookworm",
        "python -m pip install --require-hashes -r requirements.txt",
        "USER omni",
        "apps.api.cloudflare_runtime:create_app",
        '"--forwarded-allow-ips", "*"',
    ):
        if marker not in dockerfile:
            raise RuntimeError("CLOUDFLARE_RUNTIME_DOCKER_GUARD_MISSING")

    runtime = _read(RUNTIME)
    for marker in (
        'OMNI_V10_CLOUDFLARE_RUNTIME", ""',
        '"CLOUDFLARE_RUNTIME_NOT_ENABLED"',
        '"OMNI_V10_POSTGRES_DSN"',
        '_probe_hosted_preview_database(connection)',
        'provider_auth=None',
        'trusted_edge_tls_terminated=False',
    ):
        if marker not in runtime:
            raise RuntimeError("CLOUDFLARE_RUNTIME_FASTAPI_GUARD_MISSING")

    web = _read(WEB_CONFIG)
    workers_index = web.find("process.env.WORKERS_CI_COMMIT_SHA")
    github_index = web.find("process.env.GITHUB_SHA")
    render_index = web.find("process.env.RENDER_GIT_COMMIT")
    if min(workers_index, github_index, render_index) < 0:
        raise RuntimeError("CLOUDFLARE_RUNTIME_WEB_SHA_SOURCE_MISSING")
    if not workers_index < github_index < render_index:
        raise RuntimeError("CLOUDFLARE_RUNTIME_WEB_SHA_PRECEDENCE_INVALID")


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare runtime compatibility contract passed.")
    print("Frontend: Workers Static Assets")
    print("Backend: Cloudflare Container / Python 3.14.6")
    print("Database: direct Neon PostgreSQL 18; Hyperdrive disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
