from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_PLATFORM_PROVIDER_INVENTORY.json"
_CLASS_TIMEWEB_REPLACE = "TIMEWEB_REPLACE"
_CLASS_RETIRE_NOW_AFTER_AUTHORITY = "RETIRE_NOW_AFTER_AUTHORITY"
_RENDER_CONFIG_PATH = "render.yaml"
_WRANGLER_CONFIG_PATH = "wrangler.jsonc"
ALLOWED_CLASSES = {
    "KEEP",
    _CLASS_TIMEWEB_REPLACE,
    "RETIRE_AFTER_CUTOVER",
    _CLASS_RETIRE_NOW_AFTER_AUTHORITY,
    "HISTORY",
}
_RULE_INVALID = "TIMEWEB_INVENTORY_RULE_INVALID"
_CONTRACT_INVALID = "TIMEWEB_INVENTORY_CONTRACT_INVALID"
_PROVIDER_KEYWORDS_INVALID = "TIMEWEB_INVENTORY_PROVIDER_KEYWORDS_INVALID"
_EXTERNAL_SURFACES_INVALID = "TIMEWEB_INVENTORY_EXTERNAL_SURFACES_INVALID"
_MAX_PROVIDER_KEYWORDS = 32
_MAX_PROVIDER_KEYWORD_LENGTH = 64
_MAX_PATH_RULES = 64
_MAX_EXPLICIT_PATHS = 512
_MAX_MATCH_VALUES = 32
_MAX_MATCH_TEXT_LENGTH = 256
_MAX_REPOSITORY_FILES = 5_000
_MAX_TOTAL_SCANNED_SOURCE_BYTES = 100_000_000
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
    "apps/",
    "broker_report_reconciliation/",
    "cloudflare/",
    "infrastructure/",
    "omni_cio/",
    "scripts/",
)
_CONTENT_SCAN_SUFFIXES = frozenset(
    {
        ".js",
        ".json",
        ".jsonc",
        ".mjs",
        ".ps1",
        ".py",
        ".sh",
        ".sql",
        ".tf",
        ".ts",
        ".tsx",
        ".yml",
        ".yaml",
    }
)
_CONTENT_SCAN_FILENAMES = frozenset(
    {
        "Dockerfile",
        "Dockerfile.cloudflare",
        _RENDER_CONFIG_PATH,
        _WRANGLER_CONFIG_PATH,
    }
)
_STATIC_EVIDENCE_PATHS = frozenset(
    {
        "scripts/check_v10_ru_public_registration_ingress.py",
        "scripts/check_v10_timeweb_platform_inventory.py",
    }
)
_MAX_SCANNED_SOURCE_BYTES = 1_000_000
_RETIRED_EXECUTION_MARKERS = (
    "from apps.api.cf_d_database_bootstrap import",
    "RENDER_EXTERNAL_HOSTNAME",
    "RENDER_GIT_COMMIT",
    "from omni_cio.web.vk_id_oauth_v1 import",
    "BrowserBoundVkIdOauthRuntimeV1",
    "VkIdOauthConfigV1",
    "VK_ID_START_PATH",
    "VK_ID_CALLBACK_PATH",
    "OMNI_V10_WEB_EXTERNAL_PROVIDER",
    "CLOUDFLARE_OWNER_IDENTITY",
    "CF_ACCESS_JWT_HEADER",
    "provision_v10_cloudflare_neon_runtime",
    "provision_v10_render_neon_preview",
    _WRANGLER_CONFIG_PATH,
)
_RETIRED_EXECUTION_MARKERS_CASEFOLD = (
    "infrastructure/cloudru/wp22a",
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
        raise RuntimeError(_CONTRACT_INVALID) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(_CONTRACT_INVALID)
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
            if path.is_symlink():
                raise RuntimeError("TIMEWEB_INVENTORY_SYMLINK_FORBIDDEN")
            try:
                relative = path.relative_to(root)
            except ValueError as exc:
                raise RuntimeError("TIMEWEB_INVENTORY_PATH_ESCAPE") from exc
            result.append(relative.as_posix())
            if len(result) > _MAX_REPOSITORY_FILES:
                raise RuntimeError("TIMEWEB_INVENTORY_REPOSITORY_FILE_LIMIT")
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


def _normalized_text(value: object, *, case_sensitive: bool, code: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_MATCH_TEXT_LENGTH
    ):
        raise RuntimeError(code)
    return value if case_sensitive else value.casefold()


def _rule_matches(path: str, rule: dict[str, Any]) -> bool:
    match = rule.get("match")
    if not isinstance(match, dict):
        raise RuntimeError(_RULE_INVALID)
    case_sensitive = match.get("case_sensitive", True)
    if not isinstance(case_sensitive, bool):
        raise RuntimeError(_RULE_INVALID)
    candidate = path if case_sensitive else path.casefold()
    selector_count = 0

    for key, predicate in (
        ("prefix", str.startswith),
        ("suffix", str.endswith),
        ("contains", lambda value, expected: expected in value),
    ):
        value = match.get(key)
        if value is None:
            continue
        selector_count += 1
        expected = _normalized_text(
            value,
            case_sensitive=case_sensitive,
            code=_RULE_INVALID,
        )
        if not predicate(candidate, expected):
            return False

    contains_any = match.get("contains_any")
    if contains_any is not None:
        selector_count += 1
        if (
            not isinstance(contains_any, list)
            or not contains_any
            or len(contains_any) > _MAX_MATCH_VALUES
        ):
            raise RuntimeError(_RULE_INVALID)
        expected_any = tuple(
            _normalized_text(
                value,
                case_sensitive=case_sensitive,
                code=_RULE_INVALID,
            )
            for value in contains_any
        )
        if len(expected_any) != len(set(expected_any)):
            raise RuntimeError(_RULE_INVALID)
        if not any(value in candidate for value in expected_any):
            return False

    if selector_count == 0:
        raise RuntimeError(_RULE_INVALID)
    extra = set(match) - {
        "prefix",
        "suffix",
        "contains",
        "contains_any",
        "case_sensitive",
    }
    if extra:
        raise RuntimeError(_RULE_INVALID)
    return True


def _classify_path(path: str, payload: dict[str, Any]) -> str | None:
    explicit = payload.get("explicit_paths")
    rules = payload.get("path_rules")
    if not isinstance(explicit, dict) or not isinstance(rules, list):
        raise RuntimeError(_CONTRACT_INVALID)
    if len(explicit) > _MAX_EXPLICIT_PATHS or len(rules) > _MAX_PATH_RULES:
        raise RuntimeError(_CONTRACT_INVALID)
    if path in explicit:
        return _classification(explicit[path])
    for rule in rules:
        if not isinstance(rule, dict):
            raise RuntimeError(_RULE_INVALID)
        if _rule_matches(path, rule):
            return _classification(rule)
    return None


def _provider_keywords(payload: dict[str, Any]) -> tuple[str, ...]:
    value = payload.get("provider_path_keywords")
    if (
        not isinstance(value, list)
        or not value
        or len(value) > _MAX_PROVIDER_KEYWORDS
    ):
        raise RuntimeError(_PROVIDER_KEYWORDS_INVALID)
    keywords: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or len(item) > _MAX_PROVIDER_KEYWORD_LENGTH
            or item != item.casefold()
        ):
            raise RuntimeError(_PROVIDER_KEYWORDS_INVALID)
        keywords.append(item)
    if len(keywords) != len(set(keywords)):
        raise RuntimeError(_PROVIDER_KEYWORDS_INVALID)
    return tuple(keywords)


def _provider_named_path(path: str, keywords: tuple[str, ...]) -> bool:
    candidate = path.casefold()
    return any(keyword in candidate for keyword in keywords)


def _validate_contract(payload: dict[str, Any]) -> tuple[str, ...]:
    if payload.get("schema") != "omni-cio.v10.timeweb-platform-inventory.v2":
        raise RuntimeError("TIMEWEB_INVENTORY_SCHEMA_INVALID")
    if payload.get("milestone") != "TW-A_INVENTORY_AND_AUTHORITY":
        raise RuntimeError("TIMEWEB_INVENTORY_MILESTONE_INVALID")
    if payload.get("owning_issue") != 580:
        raise RuntimeError("TIMEWEB_INVENTORY_ISSUE_INVALID")
    if payload.get("accepted_base_pr") != 582:
        raise RuntimeError("TIMEWEB_INVENTORY_BASE_PROVENANCE_INVALID")
    if "accepted_base_sha" in payload or "provider_path_detector_regex" in payload:
        raise RuntimeError("TIMEWEB_INVENTORY_UNSAFE_LEGACY_FIELD")
    if payload.get("classification_vocabulary") != [
        "KEEP",
        _CLASS_TIMEWEB_REPLACE,
        "RETIRE_AFTER_CUTOVER",
        _CLASS_RETIRE_NOW_AFTER_AUTHORITY,
        "HISTORY",
    ]:
        raise RuntimeError("TIMEWEB_INVENTORY_VOCABULARY_INVALID")
    keywords = _provider_keywords(payload)
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
    return keywords


def _validate_coverage(
    payload: dict[str, Any],
    keywords: tuple[str, ...],
    files: tuple[str, ...],
) -> None:
    explicit = payload.get("explicit_paths")
    if not isinstance(explicit, dict):
        raise RuntimeError(_CONTRACT_INVALID)
    file_set = set(files)
    missing_explicit = sorted(set(explicit) - file_set)
    if missing_explicit:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_EXPLICIT_PATH_MISSING:" + ",".join(missing_explicit)
        )
    provider_named = tuple(
        path for path in files if _provider_named_path(path, keywords)
    )
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
    if path in _STATIC_EVIDENCE_PATHS:
        return False
    name = Path(path).name
    return (
        name in _CONTENT_SCAN_FILENAMES
        or path.endswith(tuple(_CONTENT_SCAN_SUFFIXES))
    ) and path.startswith(_CONTENT_SCAN_PREFIXES)


def _contains_retired_execution_marker(source: str) -> bool:
    if any(marker in source for marker in _RETIRED_EXECUTION_MARKERS):
        return True
    normalized = source.replace("\\", "/").casefold()
    return any(
        marker in normalized for marker in _RETIRED_EXECUTION_MARKERS_CASEFOLD
    )


def _validate_content_consumers(
    payload: dict[str, Any],
    files: tuple[str, ...],
) -> None:
    total_source_bytes = 0
    for relative in files:
        if not _should_scan_content(relative):
            continue
        path = ROOT / relative
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise RuntimeError("TIMEWEB_INVENTORY_SOURCE_STAT_FAILED") from exc
        if size > _MAX_SCANNED_SOURCE_BYTES:
            raise RuntimeError("TIMEWEB_INVENTORY_SOURCE_TOO_LARGE:" + relative)
        total_source_bytes += size
        if total_source_bytes > _MAX_TOTAL_SCANNED_SOURCE_BYTES:
            raise RuntimeError("TIMEWEB_INVENTORY_TOTAL_SOURCE_LIMIT")
        source = _read(path)
        if not _contains_retired_execution_marker(source):
            continue
        classification = _classify_path(relative, payload)
        if classification is None:
            raise RuntimeError(
                "TIMEWEB_INVENTORY_UNCLASSIFIED_RETIRED_CONSUMER:" + relative
            )
        if classification == "KEEP":
            raise RuntimeError(
                "TIMEWEB_INVENTORY_RETIRED_DEPENDENCY_MARKED_KEEP:" + relative
            )


def _validate_known_transitive_consumers(payload: dict[str, Any]) -> None:
    replacement_required = {
        "apps/api/hosted_preview.py",
        "apps/api/cf_d_database_bootstrap.py",
        "apps/api/wp22a_phase5_auth.py",
        "apps/web/e2e/app-shell.spec.ts",
        "apps/web/e2e/system-admin.spec.ts",
        "apps/web/src/app-shell/api.ts",
        "apps/web/src/app-shell/app-shell.tsx",
        "apps/web/src/app-shell/contracts.ts",
        "apps/web/tests/app_shell_contract.test.ts",
        "apps/web/vite.config.ts",
        "omni_cio/observability/hosted_readiness_v1.py",
        "omni_cio/persistence/_hosted_recovery_contract_v1.py",
        "omni_cio/persistence/hosted_postgres_runtime_v1.py",
        "omni_cio/web/browser_security_v1.py",
        "omni_cio/web/identity_v1.py",
        "omni_cio/web/provider_auth_routes_v1.py",
        "omni_cio/web/provider_start_adapter_v1.py",
        "scripts/check_v10_ru_postgres_data_residency_migration.py",
        "scripts/check_v10_ru_postgres_timeweb_parity.py",
        "scripts/check_v10_wp17_web_security.py",
        "scripts/discover_v10_ru_pg_verifier_ipv4.py",
        "scripts/probe_v10_timeweb_ipv4_custody.py",
        "scripts/probe_v10_timeweb_postgres_control_plane.py",
        "scripts/prove_v10_ru_postgres_timeweb_parity.py",
        "scripts/rehearse_v10_wp22a_phase4_runtime_role.py",
        "scripts/provision_v10_cloudflare_neon_runtime.py",
        "scripts/provision_v10_render_neon_preview.py",
        "scripts/provision_v10_timeweb_postgres_public_ipv4_tls.py",
        "scripts/provision_v10_timeweb_postgres_synthetic.py",
        "scripts/timeweb_ipv4_allocation_provider.py",
        _WRANGLER_CONFIG_PATH,
    }
    for path in replacement_required:
        if _classify_path(path, payload) != _CLASS_TIMEWEB_REPLACE:
            raise RuntimeError("TIMEWEB_INVENTORY_TRANSITIVE_CONSUMER_UNBOUND:" + path)

    historical_required = {
        ".github/workflows/v10-wp22a-phase4-public-acceptance.yml",
        ".github/workflows/v10-wp22a-phase5-technical-closeout.yml",
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
        _RENDER_CONFIG_PATH,
    ):
        if _classify_path(path, payload) != "KEEP":
            raise RuntimeError("TIMEWEB_INVENTORY_KEEP_CLASSIFICATION_DRIFT:" + path)

    render = _read(ROOT / _RENDER_CONFIG_PATH)
    if "uvicorn app:app" not in render:
        raise RuntimeError("TIMEWEB_INVENTORY_V9_ENTRYPOINT_DRIFT")
    if (
        _classify_path("omni_cio/web/vk_id_oauth_v1.py", payload)
        != _CLASS_RETIRE_NOW_AFTER_AUTHORITY
    ):
        raise RuntimeError("TIMEWEB_INVENTORY_VK_RETIREMENT_INVALID")


def _validate_external_surfaces(payload: dict[str, Any]) -> None:
    rows = payload.get("external_surfaces")
    if not isinstance(rows, list):
        raise RuntimeError(_EXTERNAL_SURFACES_INVALID)
    by_surface: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError(_EXTERNAL_SURFACES_INVALID)
        name = row.get("surface")
        classification = row.get("classification")
        if not isinstance(name, str) or classification not in ALLOWED_CLASSES:
            raise RuntimeError(_EXTERNAL_SURFACES_INVALID)
        by_surface[name] = str(classification)
    expected = {
        "Timeweb Cloud App Platform": "KEEP",
        "Timeweb Cloud Managed PostgreSQL 18": "KEEP",
        "Telegram Login": "KEEP",
        "Cloudflare V10 resources": "HISTORY",
        "Neon V10 resources": "HISTORY",
        "Protected V9 Render app:app": "KEEP",
        "VK ID": _CLASS_RETIRE_NOW_AFTER_AUTHORITY,
    }
    for name, classification in expected.items():
        if by_surface.get(name) != classification:
            raise RuntimeError("TIMEWEB_INVENTORY_EXTERNAL_SURFACE_DRIFT:" + name)


def main() -> int:
    payload = _load()
    keywords = _validate_contract(payload)
    files = _repository_files()
    _validate_coverage(payload, keywords, files)
    _validate_content_consumers(payload, files)
    _validate_known_transitive_consumers(payload)
    _validate_external_surfaces(payload)
    print("V10_TIMEWEB_PLATFORM_INVENTORY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
