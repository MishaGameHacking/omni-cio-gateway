from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
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


def _tracked_files() -> tuple[str, ...]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("TIMEWEB_INVENTORY_GIT_FILES_UNAVAILABLE") from exc
    return tuple(
        part.decode("utf-8")
        for part in output.split(b"\0")
        if part
    )


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


def _validate_coverage(payload: dict[str, Any], detector: re.Pattern[str]) -> None:
    files = _tracked_files()
    explicit = payload.get("explicit_paths")
    if not isinstance(explicit, dict):
        raise RuntimeError("TIMEWEB_INVENTORY_CONTRACT_INVALID")
    missing_explicit = sorted(set(explicit) - set(files))
    if missing_explicit:
        raise RuntimeError(
            "TIMEWEB_INVENTORY_EXPLICIT_PATH_MISSING:" + ",".join(missing_explicit)
        )
    provider_named = tuple(path for path in files if detector.search(path))
    minimum = payload.get("minimum_provider_named_file_count")
    if not isinstance(minimum, int) or len(provider_named) < minimum:
        raise RuntimeError("TIMEWEB_INVENTORY_PROVIDER_SURFACE_SHRANK_UNREVIEWED")
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


def _validate_known_transitive_consumers(payload: dict[str, Any]) -> None:
    required = {
        "apps/api/hosted_preview.py",
        "apps/api/cf_d_database_bootstrap.py",
        "apps/api/wp22a_phase5_auth.py",
        "omni_cio/web/provider_auth_routes_v1.py",
        "apps/web/src/app-shell/app-shell.tsx",
        "apps/web/src/app-shell/api.ts",
        "apps/web/src/app-shell/contracts.ts",
        "wrangler.jsonc",
        "scripts/check_v10_ru_postgres_timeweb_parity.py",
        "scripts/prove_v10_ru_postgres_timeweb_parity.py",
        "scripts/provision_v10_cloudflare_neon_runtime.py",
        "scripts/provision_v10_render_neon_preview.py",
    }
    for path in required:
        if _classify_path(path, payload) != "TIMEWEB_REPLACE":
            raise RuntimeError("TIMEWEB_INVENTORY_TRANSITIVE_CONSUMER_UNBOUND:" + path)
    if _classify_path("render.yaml", payload) != "KEEP":
        raise RuntimeError("TIMEWEB_INVENTORY_V9_RENDER_BOUNDARY_INVALID")
    render = _read(ROOT / "render.yaml")
    if "uvicorn app:app" not in render:
        raise RuntimeError("TIMEWEB_INVENTORY_V9_ENTRYPOINT_DRIFT")
    if _classify_path("omni_cio/web/vk_id_oauth_v1.py", payload) != "RETIRE_NOW_AFTER_AUTHORITY":
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
    _validate_coverage(payload, detector)
    _validate_known_transitive_consumers(payload)
    _validate_external_surfaces(payload)
    print("V10_TIMEWEB_PLATFORM_INVENTORY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
