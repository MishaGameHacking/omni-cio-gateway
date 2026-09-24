from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import tomllib
from typing import Any
from xml.parsers import expat


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_PLATFORM_PROVIDER_INVENTORY.json"
_CLASS_TIMEWEB_REPLACE = "TIMEWEB_REPLACE"
_CLASS_RETIRE_NOW_AFTER_AUTHORITY = "RETIRE_NOW_AFTER_AUTHORITY"
_RENDER_CONFIG_PATH = "render.yaml"
_WRANGLER_CONFIG_PATH = "wrangler.jsonc"
_JSON_SUFFIX = ".json"
ALLOWED_CLASSES = {
    "KEEP",
    _CLASS_TIMEWEB_REPLACE,
    "RETIRE_AFTER_CUTOVER",
    _CLASS_RETIRE_NOW_AFTER_AUTHORITY,
    "HISTORY",
}
_RULE_INVALID = "TIMEWEB_INVENTORY_RULE_INVALID"
_RULE_MATCH_KEYS = frozenset(
    {
        "prefix",
        "suffix",
        "contains",
        "contains_any",
        "case_sensitive",
    }
)
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
_BINARY_REPOSITORY_SUFFIXES = frozenset({".der", ".ico", ".pdf", ".png"})
_CONFLICT_GUARD_SUFFIXES = frozenset(
    {
        ".cmd",
        ".css",
        ".hcl",
        ".html",
        ".js",
        _JSON_SUFFIX,
        ".jsonc",
        ".mjs",
        ".ps1",
        ".py",
        ".pyfrag",
        ".sh",
        ".sql",
        ".tf",
        ".toml",
        ".ts",
        ".tsx",
        ".xml",
        ".yaml",
        ".yml",
    }
)
_CONFLICT_GUARD_FILENAMES = frozenset({"Dockerfile", "Dockerfile.cloudflare"})
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
        _JSON_SUFFIX,
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
    "from apps.api.hosted_preview import",
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
    "https://cloudflare.com/cdn-cgi/trace",
)
_STALE_CURRENT_DATABASE_AUTHORITY_MARKERS_CASEFOLD = (
    '"current_neon_production_authority_preserved": true',
    '"neon_production_authority_preserved": true',
    "neon production authority remains",
)
_CURRENT_DATABASE_AUTHORITY_SOURCES = (
    "docs/architecture/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_PARITY_CONTRACT.json",
    "docs/architecture/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_CREATE_CONTRACT.json",
    "docs/architecture/V10_RU_POSTGRES_TIMEWEB_IPV4_ALLOCATION_CONTRACT.json",
    "docs/architecture/V10_RU_POSTGRES_TIMEWEB_PUBLIC_IPV4_TLS_CONTRACT.json",
    "docs/operations/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_CREATE_RUNBOOK.md",
    "docs/operations/V10_RU_POSTGRES_TIMEWEB_PUBLIC_IPV4_TLS_RUNBOOK.md",
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


def _has_conflict_marker(source: str) -> bool:
    return any(
        line == "=======" or line.startswith(("<<<<<<< ", ">>>>>>> "))
        for line in source.splitlines()
    )


def _validate_repository_xml(source: str) -> None:
    normalized = source.casefold()
    if "<!doctype" in normalized or "<!entity" in normalized:
        raise ValueError("TIMEWEB_INVENTORY_REPOSITORY_XML_DECLARATION_FORBIDDEN")

    parser = expat.ParserCreate()
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)

    def reject_declaration(*args: object) -> None:
        raise ValueError("TIMEWEB_INVENTORY_REPOSITORY_XML_DECLARATION_FORBIDDEN")

    def reject_external_entity(*args: object) -> int:
        return 0

    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_external_entity
    parser.Parse(source, True)


def _validate_structured_repository_text(relative: str, source: str) -> str | None:
    suffix = Path(relative).suffix.lower()
    try:
        if suffix == ".py":
            ast.parse(source, filename=relative)
            return "python_files"
        if suffix == _JSON_SUFFIX:
            json.loads(source)
            return "json_files"
        if suffix == ".toml":
            tomllib.loads(source)
            return "toml_files"
        if suffix == ".xml":
            _validate_repository_xml(source)
            return "xml_files"
    except (SyntaxError, ValueError, expat.ExpatError) as exc:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_REPOSITORY_SYNTAX_INVALID:" + relative
        ) from exc
    return None


def _read_repository_file(relative: str) -> tuple[int, str | None]:
    path = ROOT / relative
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_REPOSITORY_FILE_UNREADABLE:" + relative
        ) from exc

    if path.suffix.lower() in _BINARY_REPOSITORY_SUFFIXES:
        return len(content), None

    try:
        return len(content), content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_REPOSITORY_TEXT_ENCODING_INVALID:" + relative
        ) from exc


def _validate_repository_text(relative: str, source: str) -> str | None:
    path = Path(relative)
    if "\x00" in source:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_REPOSITORY_TEXT_NUL_FORBIDDEN:" + relative
        )
    if (
        path.suffix.lower() in _CONFLICT_GUARD_SUFFIXES
        or path.name in _CONFLICT_GUARD_FILENAMES
    ) and _has_conflict_marker(source):
        raise RuntimeError("TIMEWEB_INVENTORY_REPOSITORY_CONFLICT_MARKER:" + relative)
    return _validate_structured_repository_text(relative, source)


def _repository_integrity_stats() -> dict[str, int]:
    return {
        "files": 0,
        "bytes": 0,
        "text_files": 0,
        "binary_files": 0,
        "python_files": 0,
        "json_files": 0,
        "toml_files": 0,
        "xml_files": 0,
    }


def _validate_repository_integrity(files: tuple[str, ...]) -> dict[str, int]:
    stats = _repository_integrity_stats()
    for relative in files:
        size, source = _read_repository_file(relative)
        stats["files"] += 1
        stats["bytes"] += size
        if stats["bytes"] > _MAX_TOTAL_SCANNED_SOURCE_BYTES:
            raise RuntimeError("TIMEWEB_INVENTORY_REPOSITORY_TOTAL_SIZE_LIMIT")

        if source is None:
            stats["binary_files"] += 1
            continue

        stats["text_files"] += 1
        structured_kind = _validate_repository_text(relative, source)
        if structured_kind is not None:
            stats[structured_kind] += 1

    return stats


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
    if not isinstance(value, str) or not value or len(value) > _MAX_MATCH_TEXT_LENGTH:
        raise RuntimeError(code)
    return value if case_sensitive else value.casefold()


def _rule_match_mapping(rule: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    match = rule.get("match")
    if not isinstance(match, dict) or set(match) - _RULE_MATCH_KEYS:
        raise RuntimeError(_RULE_INVALID)
    case_sensitive = match.get("case_sensitive", True)
    if not isinstance(case_sensitive, bool):
        raise RuntimeError(_RULE_INVALID)
    return match, case_sensitive


def _scalar_selectors_match(
    candidate: str,
    match: dict[str, Any],
    *,
    case_sensitive: bool,
) -> tuple[bool, int]:
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
            return False, selector_count
    return True, selector_count


def _contains_any_selector_matches(
    candidate: str,
    match: dict[str, Any],
    *,
    case_sensitive: bool,
) -> tuple[bool, int]:
    contains_any = match.get("contains_any")
    if contains_any is None:
        return True, 0
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
    return any(value in candidate for value in expected_any), 1


def _rule_matches(path: str, rule: dict[str, Any]) -> bool:
    match, case_sensitive = _rule_match_mapping(rule)
    candidate = path if case_sensitive else path.casefold()

    scalar_matches, scalar_count = _scalar_selectors_match(
        candidate,
        match,
        case_sensitive=case_sensitive,
    )
    if not scalar_matches:
        return False

    contains_any_matches, contains_any_count = _contains_any_selector_matches(
        candidate,
        match,
        case_sensitive=case_sensitive,
    )
    if not contains_any_matches:
        return False

    if scalar_count + contains_any_count == 0:
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
    if not isinstance(value, list) or not value or len(value) > _MAX_PROVIDER_KEYWORDS:
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
        name in _CONTENT_SCAN_FILENAMES or path.endswith(tuple(_CONTENT_SCAN_SUFFIXES))
    ) and path.startswith(_CONTENT_SCAN_PREFIXES)


def _contains_retired_execution_marker(source: str) -> bool:
    if any(marker in source for marker in _RETIRED_EXECUTION_MARKERS):
        return True
    normalized = source.replace("\\", "/").casefold()
    return any(marker in normalized for marker in _RETIRED_EXECUTION_MARKERS_CASEFOLD)


def _contains_stale_current_database_authority_marker(source: str) -> bool:
    normalized = source.casefold()
    return any(
        marker in normalized
        for marker in _STALE_CURRENT_DATABASE_AUTHORITY_MARKERS_CASEFOLD
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


def _require_classification(
    payload: dict[str, Any],
    paths: frozenset[str],
    *,
    expected: str,
    code: str,
) -> None:
    for path in paths:
        if _classify_path(path, payload) != expected:
            raise RuntimeError(code + ":" + path)


def _validate_historical_cloudflare_guard_detached() -> None:
    source = _read(ROOT / "scripts/check_v10_cloudflare_runtime_compatibility.py")
    forbidden_markers = (
        'WEB_CONFIG = ROOT / "apps/web/vite.config.ts"',
        "_validate_web_config()",
    )
    if any(marker in source for marker in forbidden_markers):
        raise RuntimeError("TIMEWEB_INVENTORY_HISTORICAL_GUARD_CURRENT_WEB_COUPLING")


def _validate_protected_v9_render_entrypoint() -> None:
    render = _read(ROOT / _RENDER_CONFIG_PATH)
    if "uvicorn app:app" not in render:
        raise RuntimeError("TIMEWEB_INVENTORY_V9_ENTRYPOINT_DRIFT")


def _validate_vk_retirement(payload: dict[str, Any]) -> None:
    classification = _classify_path("omni_cio/web/vk_id_oauth_v1.py", payload)
    if classification != _CLASS_RETIRE_NOW_AFTER_AUTHORITY:
        raise RuntimeError("TIMEWEB_INVENTORY_VK_RETIREMENT_INVALID")


def _validate_current_database_authority_sources() -> None:
    for relative in _CURRENT_DATABASE_AUTHORITY_SOURCES:
        source = _read(ROOT / relative)
        if _contains_stale_current_database_authority_marker(source):
            raise RuntimeError(
                "TIMEWEB_INVENTORY_RETIRED_DATABASE_AUTHORITY_DRIFT:" + relative
            )


def _validate_known_transitive_consumers(payload: dict[str, Any]) -> None:
    current_required = frozenset(
        {
            "Dockerfile",
            "apps/api/hosted_app.py",
            "apps/api/hosted_database_runtime.py",
            "apps/api/hosted_runtime.py",
            "apps/api/postgres_web_connection.py",
            "apps/api/telegram_auth.py",
            "apps/web/e2e/app-shell.spec.ts",
            "apps/web/e2e/system-admin.spec.ts",
            "apps/web/src/app-shell/api.ts",
            "apps/web/src/app-shell/app-shell.tsx",
            "apps/web/src/app-shell/contracts.ts",
            "apps/web/tests/app_shell_contract.test.ts",
            "apps/web/vite.config.ts",
            "infrastructure/hosted/hosted-readiness-contract.json",
            "infrastructure/postgres/hosted-postgres-runtime-contract.json",
            "infrastructure/postgres/hosted-postgres-runtime.sql",
            "infrastructure/postgres/hosted-recovery-contract.json",
            "omni_cio/observability/hosted_readiness_v1.py",
            "omni_cio/persistence/_hosted_recovery_contract_v1.py",
            "omni_cio/persistence/hosted_postgres_runtime_v1.py",
            "omni_cio/persistence/hosted_synthetic_scope_v1.py",
            "omni_cio/web/browser_security_v1.py",
            "omni_cio/web/identity_v1.py",
            "omni_cio/web/telegram_auth_routes_v1.py",
            "omni_cio/web/telegram_auth_services_v1.py",
            "scripts/check_v10_ru_postgres_data_residency_migration.py",
            "scripts/check_v10_ru_postgres_timeweb_parity.py",
            "scripts/check_v10_wp17_web_security.py",
            "scripts/discover_v10_ru_pg_verifier_ipv4.py",
            "scripts/postgres_runtime_primitives.py",
            "scripts/probe_v10_timeweb_ipv4_custody.py",
            "scripts/probe_v10_timeweb_postgres_control_plane.py",
            "scripts/prove_v10_ru_postgres_timeweb_parity.py",
            "scripts/provider_runtime_primitives.py",
            "scripts/provision_v10_timeweb_postgres_public_ipv4_tls.py",
            "scripts/provision_v10_timeweb_postgres_synthetic.py",
            "scripts/rehearse_v10_wp22a_phase4_runtime_role.py",
            "scripts/timeweb_ipv4_allocation_provider.py",
        }
    )
    historical_required = frozenset(
        {
            ".github/workflows/v10-wp22a-phase4-public-acceptance.yml",
            ".github/workflows/v10-wp22a-phase5-technical-closeout.yml",
            "apps/api/cf_d_database_bootstrap.py",
            "apps/api/hosted_preview.py",
            "apps/api/wp22a_phase5_auth.py",
            "apps/api/wp22a_remote.py",
            "infrastructure/cloudru/wp22a/hosted-postgres-runtime-contract.json",
            "infrastructure/cloudru/wp22a/hosted-postgres-runtime.sql",
            "infrastructure/windows/run_wp22a_clientless_remote_runtime.ps1",
            "omni_cio/persistence/migrations/0004_product_identity_multi_tenant.sql",
            "omni_cio/persistence/migrations/0005_browser_bound_provider_auth.sql",
            "omni_cio/web/external_access_v1.py",
            "omni_cio/web/provider_auth_routes_v1.py",
            "omni_cio/web/provider_start_adapter_v1.py",
            "scripts/check_v10_wp22a_phase4_public_acceptance.py",
            "scripts/check_v10_cloudflare_runtime_compatibility.py",
            "scripts/provision_v10_cloudflare_neon_runtime.py",
            "scripts/provision_v10_render_neon_preview.py",
            _WRANGLER_CONFIG_PATH,
        }
    )
    keep_required = frozenset(
        {
            ".github/workflows/live-gateway-authority.yml",
            ".github/workflows/regression-shield.yml",
            ".github/workflows/self-hosted-windows-smoke.yml",
            ".github/workflows/v10-wp22a-clientless-access-audit.yml",
            _RENDER_CONFIG_PATH,
        }
    )

    _require_classification(
        payload,
        current_required,
        expected="KEEP",
        code="TIMEWEB_INVENTORY_CURRENT_SURFACE_NOT_KEEP",
    )
    _require_classification(
        payload,
        historical_required,
        expected="HISTORY",
        code="TIMEWEB_INVENTORY_HISTORY_CLASSIFICATION_DRIFT",
    )
    _require_classification(
        payload,
        keep_required,
        expected="KEEP",
        code="TIMEWEB_INVENTORY_KEEP_CLASSIFICATION_DRIFT",
    )
    _validate_historical_cloudflare_guard_detached()
    _validate_protected_v9_render_entrypoint()
    _validate_vk_retirement(payload)
    _validate_current_database_authority_sources()


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
    integrity = _validate_repository_integrity(files)
    _validate_coverage(payload, keywords, files)
    _validate_content_consumers(payload, files)
    _validate_known_transitive_consumers(payload)
    _validate_external_surfaces(payload)
    print(
        "V10_TIMEWEB_REPOSITORY_INTEGRITY=PASS "
        f"files={integrity['files']} "
        f"text={integrity['text_files']} "
        f"binary={integrity['binary_files']} "
        f"python={integrity['python_files']} "
        f"json={integrity['json_files']}"
    )
    print("V10_TIMEWEB_PLATFORM_INVENTORY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
