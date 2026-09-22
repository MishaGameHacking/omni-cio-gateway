from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_PLATFORM_PROVIDER_INVENTORY.json"
ALLOWED_CLASSES = {
    "KEEP",
    "TIMEWEB_REPLACE",
    "RETIRE_AFTER_CUTOVER",
    "RETIRE_NOW_AFTER_AUTHORITY",
    "HISTORY",
}
_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".wrangler",
        "__pycache__",
        "artifacts",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "playwright-report",
        "test-results",
        "venv",
    }
)
_CONTENT_SCAN_PREFIXES = (
    ".github/workflows/",
    "apps/api/",
    "apps/web/src/",
    "infrastructure/windows/",
    "omni_cio/observability/",
    "omni_cio/persistence/",
    "omni_cio/web/",
)
_CONTENT_SCAN_SUFFIXES = frozenset(
    {
        ".js",
        ".json",
        ".jsonc",
        ".mjs",
        ".ps1",
        ".py",
        ".sql",
        ".ts",
        ".tsx",
        ".yml",
        ".yaml",
    }
)
_RETIRED_RUNTIME_MARKERS = (
    re.compile(r"from\s+apps\.api\.cf_d_database_bootstrap\s+import"),
    re.compile(r"\bRENDER_EXTERNAL_HOSTNAME\b"),
    re.compile(r"\bRENDER_GIT_COMMIT\b"),
    re.compile(r"from\s+omni_cio\.web\.vk_id_oauth_v1\s+import"),
    re.compile(r"\bBrowserBoundVkIdOauthRuntimeV1\b"),
    re.compile(r"\bVkIdOauthConfigV1\b"),
    re.compile(r"\bVK_ID_START_PATH\b"),
    re.compile(r"\bVK_ID_CALLBACK_PATH\b"),
    re.compile(r"\bvk_id\b", re.IGNORECASE),
    re.compile(r"\bOMNI_V10_WEB_EXTERNAL_PROVIDER\b"),
    re.compile(r"\bOMNI_V10_CLOUDFLARE_OWNER_IDENTITY_SHA256\b"),
    re.compile(r"\bCF_ACCESS_JWT_HEADER\b"),
    re.compile(r"infrastructure[/\\\\]cloudru[/\\\\]wp22a", re.IGNORECASE),
    re.compile(r"check_v10_wp22a_phase4_public_acceptance\.py"),
    re.compile(r"Probe exact public Render preview", re.IGNORECASE),
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"TIMEWEB_INVENTORY_SOURCE_UNREADABLE:{path.name}") from exc


def _load() -> dict[str, Any]:
    try:
        payload = json.loads(_read(CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_INVENTORY_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_INVENTORY_CONTRACT_INVALID")
    return payload


def _repository_files(root: Path = ROOT) -> tuple[str, ...]:
    result: list[str] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name for name in directories if name not in _IGNORED_DIRECTORIES
        )
        current_path = Path(current)
        for filename in sorted(filenames):
            path = current_path / filename
            try:
                relative = path.relative_to(root)
            except ValueError as exc:
                raise RuntimeError("TIMEWEB_INVENTORY_PATH_ESCAPE") from exc
            result.append(relative.as_posix())
    return tuple(sorted(result))


def _classification(entry: object) -> str:
    if not isinstance(entry, dict):
        raise RuntimeError("TIMEWEB_INVENTORY_CLASSIFICATION_INVALID")
    value = entry.get("classification")
    if value not in ALLOWED_CLASSES:
        raise RuntimeError("TIMEWEB_INVENTORY_CLASSIFICATION_INVALID")
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError("TIMEWEB_INVENTORY_REASON_REQUIRED")
    return str(value)


def _classify_path(path: str, payload: dict[str, Any]) -> str | None:
    explicit = payload.get("explicit_paths")
    rules = payload.get("path_rules")
    if not isinstance(explicit, dict) or not isinstance(rules, list):
        raise RuntimeError("TIMEWEB_INVENTORY_CONTRACT_INVALID")
    if path in explicit:
        return _classification(explicit[path])
    for rule in rules:
        if not isinstance(rule, dict):
            raise RuntimeError("TIMEWEB_INVENTORY_RULE_INVALID")
        pattern = rule.get("regex")
        if not isinstance(pattern, str):
            raise RuntimeError("TIMEWEB_INVENTORY_RULE_INVALID")
        try:
            matched = re.search(pattern, path) is not None
        except re.error as exc:
            raise RuntimeError("TIMEWEB_INVENTORY_RULE_INVALID") from exc
        if matched:
            return _classification(rule)
    return None


def _validate_contract(payload: dict[str, Any]) -> re.Pattern[str]:
    if payload.get("schema") != "omni-cio.v10.timeweb-platform-inventory.v1":
        raise RuntimeError("TIMEWEB_INVENTORY_SCHEMA_INVALID")
    if payload.get("milestone") != "TW-A_INVENTORY_AND_AUTHORITY":
        raise RuntimeError("TIMEWEB_INVENTORY_MILESTONE_INVALID")
    if payload.get("owning_issue") != 580:
        raise RuntimeError("TIMEWEB_INVENTORY_ISSUE_INVALID")
    if payload.get("classification_vocabulary") != [
        "KEEP",
        "TIMEWEB_REPLACE",
        "RETIRE_AFTER_CUTOVER",
        "RETIRE_NOW_AFTER_AUTHORITY",
        "HISTORY",
    ]:
        raise RuntimeError("TIMEWEB_INVENTORY_VOCABULARY_INVALID")
    detector = payload.get("provider_path_detector_regex")
    if not isinstance(detector, str):
        raise RuntimeError("TIMEWEB_INVENTORY_DETECTOR_INVALID")
    try:
        compiled = re.compile(detector)
    except re.error as exc:
        raise RuntimeError("TIMEWEB_INVENTORY_DETECTOR_INVALID") from exc
    expected_count = payload.get("expected_provider_named_file_count")
    if not isinstance(expected_count, int) or expected_count <= 0:
        raise RuntimeError("TIMEWEB_INVENTORY_EXPECTED_COUNT_INVALID")
    protected = payload.get("protected_invariants")
    if not isinstance(protected, dict):
        raise RuntimeError("TIMEWEB_INVENTORY_INVARIANTS_INVALID")
    for key in (
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "web_visual_started",
        "wp23_unlocked",
    ):
        if protected.get(key) is not False:
            raise RuntimeError("TIMEWEB_INVENTORY_AUTHORITY_WIDENED")
    if protected.get("protected_v9_entrypoint") != "app:app":
        raise RuntimeError("TIMEWEB_INVENTORY_V9_DRIFT")
    return compiled


def _validate_coverage(
    payload: dict[str, Any],
    detector: re.Pattern[str],
    files: tuple[str, ...],
) -> None:
    explicit = payload.get("explicit_paths")
    if not isinstance(explicit, dict):
        raise RuntimeError("TIMEWEB_INVENTORY_CONTRACT_INVALID")
    file_set = set(files)
    missing_explicit = sorted(set(explicit) - file_set)
    if missing_explicit:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_EXPLICIT_PATH_MISSING:" + ",".join(missing_explicit)
        )
    provider_named = tuple(path for path in files if detector.search(path))
    expected_count = payload.get("expected_provider_named_file_count")
    if len(provider_named) != expected_count:
        raise RuntimeError("TIMEWEB_INVENTORY_PROVIDER_SURFACE_COUNT_DRIFT")
    unclassified = sorted(
        path for path in provider_named if _classify_path(path, payload) is None
    )
    if unclassified:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_UNCLASSIFIED_PROVIDER_PATH:" + ",".join(unclassified)
        )
    for path in explicit:
        if _classify_path(path, payload) is None:
            raise RuntimeError("TIMEWEB_INVENTORY_EXPLICIT_PATH_UNCLASSIFIED")


def _should_scan_content(path: str) -> bool:
    return path.endswith(tuple(_CONTENT_SCAN_SUFFIXES)) and path.startswith(
        _CONTENT_SCAN_PREFIXES
    )


def _validate_content_consumers(
    payload: dict[str, Any],
    files: tuple[str, ...],
) -> None:
    for relative in files:
        if not _should_scan_content(relative):
            continue
        source = _read(ROOT / relative)
        if not any(pattern.search(source) for pattern in _RETIRED_RUNTIME_MARKERS):
            continue
        if _classify_path(relative, payload) is None:
            raise RuntimeError(
                "TIMEWEB_INVENTORY_UNCLASSIFIED_RETIRED_CONSUMER:" + relative
            )


def _validate_known_transitive_consumers(payload: dict[str, Any]) -> None:
    replacement_required = {
        "apps/api/hosted_preview.py",
        "apps/api/wp22a_phase5_auth.py",
        "apps/web/e2e/app-shell.spec.ts",
        "apps/web/e2e/system-admin.spec.ts",
        "apps/web/src/app-shell/api.ts",
        "apps/web/src/app-shell/app-shell.tsx",
        "apps/web/src/app-shell/contracts.ts",
        "apps/web/tests/app_shell_contract.test.ts",
        "omni_cio/observability/hosted_readiness_v1.py",
        "omni_cio/persistence/_hosted_recovery_contract_v1.py",
        "omni_cio/persistence/hosted_postgres_runtime_v1.py",
        "omni_cio/web/browser_security_v1.py",
        "omni_cio/web/identity_v1.py",
        "omni_cio/web/provider_auth_routes_v1.py",
        "omni_cio/web/provider_start_adapter_v1.py",
        "scripts/check_v10_ru_postgres_timeweb_parity.py",
        "scripts/check_v10_wp17_web_security.py",
        "scripts/prove_v10_ru_postgres_timeweb_parity.py",
        "scripts/provision_v10_cloudflare_neon_runtime.py",
        "scripts/provision_v10_render_neon_preview.py",
        "wrangler.jsonc",
    }
    for path in replacement_required:
        if _classify_path(path, payload) != "TIMEWEB_REPLACE":
            raise RuntimeError("TIMEWEB_INVENTORY_TRANSITIVE_CONSUMER_UNBOUND:" + path)

    historical_required = {
        ".github/workflows/v10-wp22a-phase4-public-acceptance.yml",
        "apps/api/cf_d_database_bootstrap.py",
        "apps/api/wp22a_remote.py",
        "infrastructure/windows/run_wp22a_clientless_remote_runtime.ps1",
        "omni_cio/persistence/migrations/0004_product_identity_multi_tenant.sql",
        "omni_cio/persistence/migrations/0005_browser_bound_provider_auth.sql",
        "omni_cio/web/external_access_v1.py",
        "scripts/check_v10_wp22a_phase4_public_acceptance.py",
    }
    for path in historical_required:
        if _classify_path(path, payload) != "HISTORY":
            raise RuntimeError("TIMEWEB_INVENTORY_HISTORY_CLASSIFICATION_DRIFT:" + path)

    for path in (
        ".github/workflows/live-gateway-authority.yml",
        ".github/workflows/regression-shield.yml",
        ".github/workflows/self-hosted-windows-smoke.yml",
        ".github/workflows/v10-wp22a-clientless-access-audit.yml",
        "render.yaml",
    ):
        if _classify_path(path, payload) != "KEEP":
            raise RuntimeError("TIMEWEB_INVENTORY_KEEP_CLASSIFICATION_DRIFT:" + path)

    render = _read(ROOT / "render.yaml")
    if "uvicorn app:app" not in render:
        raise RuntimeError("TIMEWEB_INVENTORY_V9_ENTRYPOINT_DRIFT")
    if (
        _classify_path("omni_cio/web/vk_id_oauth_v1.py", payload)
        != "RETIRE_NOW_AFTER_AUTHORITY"
    ):
        raise RuntimeError("TIMEWEB_INVENTORY_VK_RETIREMENT_INVALID")


def _validate_external_surfaces(payload: dict[str, Any]) -> None:
    rows = payload.get("external_surfaces")
    if not isinstance(rows, list):
        raise RuntimeError("TIMEWEB_INVENTORY_EXTERNAL_SURFACES_INVALID")
    by_surface: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("TIMEWEB_INVENTORY_EXTERNAL_SURFACES_INVALID")
        name = row.get("surface")
        classification = row.get("classification")
        if not isinstance(name, str) or classification not in ALLOWED_CLASSES:
            raise RuntimeError("TIMEWEB_INVENTORY_EXTERNAL_SURFACES_INVALID")
        by_surface[name] = str(classification)
    expected = {
        "Timeweb Cloud App Platform": "KEEP",
        "Timeweb Cloud Managed PostgreSQL 18": "KEEP",
        "Telegram Login": "KEEP",
        "Cloudflare V10 resources": "HISTORY",
        "Neon V10 resources": "HISTORY",
        "Protected V9 Render app:app": "KEEP",
        "VK ID": "RETIRE_NOW_AFTER_AUTHORITY",
    }
    for name, classification in expected.items():
        if by_surface.get(name) != classification:
            raise RuntimeError("TIMEWEB_INVENTORY_EXTERNAL_SURFACE_DRIFT:" + name)


def main() -> int:
    payload = _load()
    detector = _validate_contract(payload)
    files = _repository_files()
    _validate_coverage(payload, detector, files)
    _validate_content_consumers(payload, files)
    _validate_known_transitive_consumers(payload)
    _validate_external_surfaces(payload)
    print("V10_TIMEWEB_PLATFORM_INVENTORY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
