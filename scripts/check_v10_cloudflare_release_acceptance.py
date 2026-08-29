from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from scripts.v10_jsonc import loads_jsonc


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
WRANGLER = ROOT / "wrangler.jsonc"
LIVE_VERIFIER = ROOT / "scripts/check_v10_cloudflare_live_release.py"
PACKAGE = ROOT / "package.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        source = path.read_text(encoding="utf-8")
        value = loads_jsonc(source) if path.suffix == ".jsonc" else json.loads(source)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_RELEASE_CONTRACT_UNREADABLE:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RELEASE_OBJECT_REQUIRED:{path}")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RELEASE_{label}_INVALID")
    return value


def validate() -> None:
    contract = _load(CONTRACT)
    if contract.get("schema") != "omni-cio.v10.cloudflare-release-acceptance.v1":
        raise RuntimeError("CLOUDFLARE_RELEASE_SCHEMA_INVALID")

    candidate = _object(contract.get("candidate"), "CANDIDATE")
    cutover = _object(contract.get("cutover"), "CUTOVER")
    live = _object(contract.get("live_assertions"), "LIVE_ASSERTIONS")
    fail_closed = _object(contract.get("fail_closed"), "FAIL_CLOSED")
    protected = _object(contract.get("protected_invariants"), "PROTECTED_INVARIANTS")

    if candidate.get("milestone") != "CF-C":
        raise RuntimeError("CLOUDFLARE_RELEASE_CANDIDATE_MILESTONE_INVALID")
    if candidate.get("provider_mutation_allowed") is not True:
        raise RuntimeError("CLOUDFLARE_RELEASE_CANDIDATE_MUTATION_INVALID")
    if candidate.get("production_promotion_allowed") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_CANDIDATE_PROMOTION_INVALID")
    if cutover.get("milestone") != "CF-D" or cutover.get("production_branch") != "main":
        raise RuntimeError("CLOUDFLARE_RELEASE_CUTOVER_INVALID")
    if cutover.get("automatic_git_deploy_required") is not True:
        raise RuntimeError("CLOUDFLARE_RELEASE_AUTOMATIC_DEPLOY_REQUIRED")
    if cutover.get("default_deploy_command") != "npx wrangler deploy":
        raise RuntimeError("CLOUDFLARE_RELEASE_DEPLOY_COMMAND_INVALID")

    expected_live = {
        "https_only": True,
        "redirects_followed": False,
        "max_response_bytes": 65536,
        "release_platform": "cloudflare",
        "release_backend": "container",
        "release_static_assets": True,
        "public_multi_user_enabled": False,
        "real_trading_enabled": False,
        "health_status": "ok",
        "health_database": "READY",
    }
    for key, expected in expected_live.items():
        if live.get(key) != expected:
            raise RuntimeError(f"CLOUDFLARE_RELEASE_LIVE_{key.upper()}_INVALID")
    if any(value is not False for value in fail_closed.values()):
        raise RuntimeError("CLOUDFLARE_RELEASE_FAIL_CLOSED_INVALID")
    if protected.get("broker_write") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_BROKER_WRITE_INVALID")
    if protected.get("trading_methods") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_TRADING_METHODS_INVALID")
    if protected.get("REAL_TRADING_ENABLED") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_REAL_TRADING_INVALID")

    wrangler = _load(WRANGLER)
    build = _object(wrangler.get("build"), "WRANGLER_BUILD")
    expected_build = (
        "python scripts/write_v10_cloudflare_build_info.py && "
        "npm ci --prefix apps/web && npm run --prefix apps/web build"
    )
    if build.get("command") != expected_build:
        raise RuntimeError("CLOUDFLARE_RELEASE_SELF_CONTAINED_BUILD_INVALID")
    if wrangler.get("workers_dev") is not True:
        raise RuntimeError("CLOUDFLARE_RELEASE_WORKERS_DEV_REQUIRED")

    package = _load(PACKAGE)
    if package.get("engines") != {"node": "24.18.0", "npm": "11.16.0"}:
        raise RuntimeError("CLOUDFLARE_RELEASE_NODE_BASELINE_INVALID")
    dependencies = _object(package.get("dependencies"), "DEPENDENCIES")
    dev_dependencies = _object(package.get("devDependencies"), "DEV_DEPENDENCIES")
    if dependencies.get("@cloudflare/containers") != "0.3.7":
        raise RuntimeError("CLOUDFLARE_RELEASE_CONTAINERS_VERSION_INVALID")
    if dev_dependencies.get("wrangler") != "4.127.1":
        raise RuntimeError("CLOUDFLARE_RELEASE_WRANGLER_VERSION_INVALID")

    try:
        verifier = LIVE_VERIFIER.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("CLOUDFLARE_RELEASE_VERIFIER_UNREADABLE") from exc
    for marker in (
        "CLOUDFLARE_RELEASE_ORIGIN_INVALID",
        "CLOUDFLARE_RELEASE_HEALTH_SHA_MISMATCH",
        "CLOUDFLARE_RELEASE_DATABASE_NOT_READY",
        '"/api/v10/release"',
        '"/healthz"',
        "HTTPRedirectHandler",
        "_MAX_BYTES = 65_536",
    ):
        if marker not in verifier:
            raise RuntimeError("CLOUDFLARE_RELEASE_VERIFIER_GUARD_MISSING")


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare CF-C/CF-D release acceptance contract passed.")
    print("Production branch: main")
    print("Automatic deploy command: npx wrangler deploy")
    print("Live exact-SHA/database acceptance remains fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
