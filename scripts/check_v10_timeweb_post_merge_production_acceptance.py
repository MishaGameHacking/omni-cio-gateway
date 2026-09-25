from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = (
    "docs/architecture/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_CONTRACT.json"
)
_CONTROLLER = "scripts/timeweb_production_acceptance.py"
_WORKFLOW = ".github/workflows/v10-timeweb-post-merge-production-acceptance.yml"
_ACCESS_SUFFIX = "_access_allowed"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"TIMEWEB_P6_SOURCE_UNREADABLE:{path.name}") from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_P6_CONTRACT_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_P6_CONTRACT_INVALID")
    return payload


def _section(payload: dict[str, Any], key: str, code: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require_equal(payload: dict[str, Any], key: str, expected: Any) -> None:
    if payload.get(key) != expected:
        raise RuntimeError(f"TIMEWEB_P6_CONTRACT_DRIFT:{key}")


def _require_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    for marker in markers:
        if marker not in source:
            raise RuntimeError(f"{code}:{marker}")


def _validate_metadata(payload: dict[str, Any]) -> None:
    expected = {
        "schema": "omni-cio.v10.timeweb-post-merge-production-acceptance.v1",
        "status": "OWNER_APPROVED_BRANCH_LOCAL_IMPLEMENTATION_VERIFICATION_PENDING",
        "owning_system_update": "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "owning_pr": 584,
        "milestone": "P6_POST_MERGE_PRODUCTION_ACCEPTANCE",
        "canonical_origin": "https://omnicio.ru",
        "canonical_redirect_uri": (
            "https://omnicio.ru/api/v10/web/auth/telegram/callback"
        ),
    }
    for key, value in expected.items():
        _require_equal(payload, key, value)


def _validate_execution(payload: dict[str, Any]) -> None:
    execution = _section(payload, "execution", "TIMEWEB_P6_EXECUTION_INVALID")
    expected = {
        "manual_only": True,
        "exact_main_required": True,
        "source_mutation_allowed": False,
        "provider_mutation_allowed": False,
        "controller": _CONTROLLER,
        "guard": "scripts/check_v10_timeweb_post_merge_production_acceptance.py",
        "workflow": _WORKFLOW,
        "runbook": (
            "docs/operations/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_RUNBOOK.md"
        ),
        "confirmation": "ACCEPT_TIMEWEB_PRODUCTION_RELEASE",
    }
    for key, value in expected.items():
        if execution.get(key) != value:
            raise RuntimeError(f"TIMEWEB_P6_EXECUTION_DRIFT:{key}")

    access_keys = [key for key in execution if key.endswith(_ACCESS_SUFFIX)]
    if len(access_keys) != 1 or execution[access_keys[0]] is not False:
        raise RuntimeError("TIMEWEB_P6_EXECUTION_ACCESS_POLICY_DRIFT")
    if set(execution) != set(expected) | set(access_keys):
        raise RuntimeError("TIMEWEB_P6_EXECUTION_KEYSET_DRIFT")


def _validate_evidence(payload: dict[str, Any]) -> None:
    evidence = _section(
        payload,
        "required_evidence",
        "TIMEWEB_P6_EVIDENCE_POLICY_INVALID",
    )
    required = {
        "p2_candidate_evidence_sha256",
        "p3_cutover_evidence_sha256",
        "p4_ingress_evidence_sha256",
        "p5_readiness_sha256",
        "p5_live_evidence_sha256",
        "rollback_release_sha",
        "rollback_evidence_sha256",
        "rollback_release_must_differ_from_new_release",
    }
    if set(evidence) != required or any(value is not True for value in evidence.values()):
        raise RuntimeError("TIMEWEB_P6_EVIDENCE_POLICY_DRIFT")


def _validate_live_probes(payload: dict[str, Any]) -> None:
    live = _section(payload, "live_probes", "TIMEWEB_P6_LIVE_PROBES_INVALID")
    expected = {
        "liveness_path": "/livez",
        "readiness_path": "/healthz",
        "provider_descriptor_path": "/api/v10/web/auth/providers",
        "liveness_status": "ok",
        "readiness_status": "ok",
        "database_state": "READY",
        "synthetic_preview": False,
        "sole_provider": "telegram",
        "provider_enabled": True,
        "exact_release_sha_required": True,
    }
    if live != expected:
        raise RuntimeError("TIMEWEB_P6_LIVE_PROBES_DRIFT")


def _validate_acceptance_seal(payload: dict[str, Any]) -> None:
    seal = _section(payload, "acceptance_seal", "TIMEWEB_P6_ACCEPTANCE_SEAL_INVALID")
    expected = {
        "schema": "omni-cio.v10.timeweb-production-acceptance-seal.v1",
        "algorithm": "SHA-256",
        "canonical_json_sort_keys": True,
        "binds_exact_release_sha": True,
        "binds_all_required_evidence": True,
        "binds_canonical_origin": True,
        "success_marker": "TIMEWEB_PRODUCTION_ACCEPTANCE=ACCEPTED",
    }
    if seal != expected:
        raise RuntimeError("TIMEWEB_P6_ACCEPTANCE_SEAL_DRIFT")


def _validate_protected_invariants(payload: dict[str, Any]) -> None:
    protected = _section(
        payload,
        "protected_invariants",
        "TIMEWEB_P6_INVARIANTS_INVALID",
    )
    required = {
        "browser_tenant_selection",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "transfer_withdrawal",
        "margin_leverage",
        "uncovered_short",
        "web_visual_started",
        "wp23_unlocked",
    }
    if set(protected) != required:
        raise RuntimeError("TIMEWEB_P6_INVARIANTS_DRIFT")
    if any(value is not False for value in protected.values()):
        raise RuntimeError("TIMEWEB_P6_AUTHORITY_WIDENED")


def _validate_source_assets(root: Path) -> None:
    controller = _read(root / _CONTROLLER)
    _require_markers(
        controller,
        (
            "TIMEWEB_PRODUCTION_ACCEPTANCE=ACCEPTED",
            "TIMEWEB_PRODUCTION_ACCEPTANCE_MAIN_SHA_DRIFT",
            "TIMEWEB_PRODUCTION_ACCEPTANCE_ROLLBACK_SHA_COLLISION",
            "omni-cio.v10.timeweb-production-acceptance-seal.v1",
            '"/livez"',
            '"/healthz"',
            '"/api/v10/web/auth/providers"',
        ),
        "TIMEWEB_P6_CONTROLLER_DRIFT",
    )

    workflow = _read(root / _WORKFLOW)
    _require_markers(
        workflow,
        (
            "workflow_dispatch:",
            "contents: read",
            "github.ref == 'refs/heads/main'",
            "scripts.check_v10_timeweb_post_merge_production_acceptance",
            "scripts.timeweb_production_acceptance",
            "git fetch --no-tags --depth=1 origin main",
            "TIMEWEB_PRODUCTION_ACCEPTANCE_EVIDENCE",
        ),
        "TIMEWEB_P6_WORKFLOW_DRIFT",
    )


def validate(root: Path = ROOT) -> None:
    payload = _json(root / _CONTRACT)
    _validate_metadata(payload)
    _validate_execution(payload)
    _validate_evidence(payload)
    _validate_live_probes(payload)
    _validate_acceptance_seal(payload)
    _validate_protected_invariants(payload)
    _validate_source_assets(root)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(f"V10_TIMEWEB_POST_MERGE_ACCEPTANCE=FAIL code={exc}", file=sys.stderr)
        return 1
    print("V10_TIMEWEB_POST_MERGE_ACCEPTANCE=PASS scope=P6 exact_main=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
