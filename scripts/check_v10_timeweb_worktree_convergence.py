from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json"
_MAX_PATHS = 128
_MAX_MARKERS = 64
_EXPECTED_SCHEMA = "omni-cio.v10.timeweb-worktree-convergence.v1"
_EXPECTED_CHECKPOINT = "P5_5_TIMEWEB_WORKTREE_CONVERGENCE"
_EXPECTED_PHASE = "ALL_INTERNAL_PHASES_COMPLETE"
_EXPECTED_STATUS = (
    "BRANCH_LOCAL_IMPLEMENTATION_COMPLETE_FINAL_EXACT_HEAD_VERIFICATION_REQUIRED"
)
_EXPECTED_INTERNAL_PHASES = (
    "CLIENTLESS_CLOUDFLARE_REMOVAL",
    "RENDER_NEON_CLOUDFLARE_RUNTIME_REMOVAL",
    "WP22A_AUTH_TELEGRAM_ONLY_CONVERGENCE",
    "LEGACY_DOCUMENTATION_PRUNE_AND_CANONICALIZATION",
)
_EXPECTED_COMPLETION_GUARDS = {
    "provider_inventory": "scripts/check_v10_timeweb_platform_inventory.py",
    "runtime_reachability": "scripts/check_v10_timeweb_runtime_reachability.py",
    "documentation_consistency": "scripts/check_v10_documentation_consistency.py",
    "telegram_only_runtime": "apps/api/telegram_auth.py",
}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"TIMEWEB_WORKTREE_SOURCE_UNREADABLE:{path.name}") from exc


def _load_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_WORKTREE_CONTRACT_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_WORKTREE_CONTRACT_INVALID")
    return payload


def _safe_relative(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(code)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(code)
    return path.as_posix()


def _string_list(
    payload: dict[str, Any],
    key: str,
    *,
    maximum: int,
) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise RuntimeError(f"TIMEWEB_WORKTREE_LIST_INVALID:{key}")
    rows = tuple(
        _safe_relative(item, f"TIMEWEB_WORKTREE_PATH_INVALID:{key}") for item in value
    )
    if len(rows) != len(set(rows)):
        raise RuntimeError(f"TIMEWEB_WORKTREE_LIST_DUPLICATE:{key}")
    return rows


def _marker_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value or len(value) > _MAX_MARKERS:
        raise RuntimeError(f"TIMEWEB_WORKTREE_MARKERS_INVALID:{key}")
    markers = tuple(str(item) for item in value if isinstance(item, str) and item)
    if len(markers) != len(value) or len(markers) != len(set(markers)):
        raise RuntimeError(f"TIMEWEB_WORKTREE_MARKERS_INVALID:{key}")
    return markers


def _validate_contract(payload: dict[str, Any]) -> None:
    expected = {
        "schema": _EXPECTED_SCHEMA,
        "status": _EXPECTED_STATUS,
        "owning_system_update": "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "owning_pr": 584,
        "checkpoint": _EXPECTED_CHECKPOINT,
        "phase": _EXPECTED_PHASE,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise RuntimeError(f"TIMEWEB_WORKTREE_CONTRACT_DRIFT:{key}")

    completed = payload.get("completed_internal_phases")
    if completed != list(_EXPECTED_INTERNAL_PHASES):
        raise RuntimeError("TIMEWEB_WORKTREE_COMPLETED_PHASES_DRIFT")

    guards = payload.get("completion_guards")
    if guards != _EXPECTED_COMPLETION_GUARDS:
        raise RuntimeError("TIMEWEB_WORKTREE_COMPLETION_GUARDS_DRIFT")

    policy = payload.get("history_policy")
    if policy != {
        "current_worktree_deletion_required": True,
        "non_sensitive_legacy_history_rewrite_required": False,
        "sensitive_data_history_rewrite_requires_separate_incident_response": True,
    }:
        raise RuntimeError("TIMEWEB_WORKTREE_HISTORY_POLICY_DRIFT")

    protected = payload.get("protected_invariants")
    if not isinstance(protected, dict):
        raise RuntimeError("TIMEWEB_WORKTREE_INVARIANTS_INVALID")
    if protected.get("protected_v9_entrypoint") != "app:app":
        raise RuntimeError("TIMEWEB_WORKTREE_V9_RECOVERY_DRIFT")
    if protected.get("immutable_accepted_migrations") is not True:
        raise RuntimeError("TIMEWEB_WORKTREE_MIGRATION_POLICY_DRIFT")
    for key in (
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "OMNI_V10_VK_ID_LOGIN_ENABLED",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
    ):
        if protected.get(key) is not False:
            raise RuntimeError(f"TIMEWEB_WORKTREE_AUTHORITY_WIDENED:{key}")


def _assert_absent(root: Path, relative_paths: tuple[str, ...]) -> None:
    for relative in relative_paths:
        path = root / relative
        if path.exists() or path.is_symlink():
            raise RuntimeError(f"TIMEWEB_WORKTREE_RETIRED_PATH_PRESENT:{relative}")


def _assert_absent_prefixes(root: Path, prefixes: tuple[str, ...]) -> None:
    for prefix in prefixes:
        directory = root / prefix.rstrip("/")
        if directory.exists() or directory.is_symlink():
            raise RuntimeError(f"TIMEWEB_WORKTREE_RETIRED_PREFIX_PRESENT:{prefix}")


def _assert_present(root: Path, relative_paths: tuple[str, ...]) -> None:
    for relative in relative_paths:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"TIMEWEB_WORKTREE_PROTECTED_PATH_MISSING:{relative}")


def _scan_sources(
    root: Path,
    paths: tuple[str, ...],
    markers: tuple[str, ...],
    *,
    code: str,
) -> None:
    for relative in paths:
        source = _read(root / relative)
        for marker in markers:
            if marker in source:
                raise RuntimeError(f"{code}:{relative}:{marker}")


def _workflow_paths(root: Path) -> tuple[str, ...]:
    directory = root / ".github" / "workflows"
    if not directory.is_dir():
        raise RuntimeError("TIMEWEB_WORKTREE_WORKFLOW_DIRECTORY_MISSING")
    rows = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    return tuple(path.relative_to(root).as_posix() for path in rows)


def validate(root: Path = ROOT) -> None:
    contract_path = (
        root / "docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json"
    )
    payload = _load_contract(contract_path)
    _validate_contract(payload)

    absent = _string_list(payload, "required_absent_paths", maximum=_MAX_PATHS)
    absent_prefixes = _string_list(
        payload,
        "required_absent_prefixes",
        maximum=_MAX_PATHS,
    )
    present = _string_list(payload, "protected_present_paths", maximum=_MAX_PATHS)
    runtime_paths = _string_list(payload, "runtime_scan_paths", maximum=_MAX_PATHS)
    runtime_markers = _marker_list(payload, "runtime_forbidden_markers")
    workflow_markers = _marker_list(payload, "workflow_forbidden_markers")

    _assert_absent(root, absent)
    _assert_absent_prefixes(root, absent_prefixes)
    _assert_present(root, present)
    _scan_sources(
        root,
        runtime_paths,
        runtime_markers,
        code="TIMEWEB_WORKTREE_RETIRED_RUNTIME_REFERENCE",
    )
    _scan_sources(
        root,
        _workflow_paths(root),
        workflow_markers,
        code="TIMEWEB_WORKTREE_RETIRED_WORKFLOW_REFERENCE",
    )

    render = _read(root / "render.yaml")
    if "uvicorn app:app" not in render:
        raise RuntimeError("TIMEWEB_WORKTREE_V9_ENTRYPOINT_DRIFT")


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10_TIMEWEB_WORKTREE_CONVERGENCE=PASS phase=ALL_INTERNAL_PHASES_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
