from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = "docs/architecture/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_CONTRACT.json"
_CONTROLLER = "scripts/timeweb_production_acceptance.py"
_WORKFLOW = ".github/workflows/v10-timeweb-post-merge-production-acceptance.yml"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"TIMEWEB_P6_SOURCE_UNREADABLE:{path.name}") from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_P6_CONTRACT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("TIMEWEB_P6_CONTRACT_INVALID")
    return value


def _markers(source: str, markers: tuple[str, ...], code: str) -> None:
    for marker in markers:
        if marker not in source:
            raise RuntimeError(f"{code}:{marker}")


def _validate_metadata(contract: dict[str, Any]) -> None:
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
        if contract.get(key) != value:
            raise RuntimeError(f"TIMEWEB_P6_CONTRACT_DRIFT:{key}")


def _validate_execution(contract: dict[str, Any]) -> None:
    execution = contract.get("execution")
    if not isinstance(execution, dict):
        raise RuntimeError("TIMEWEB_P6_EXECUTION_DRIFT")
    expected = {
        "manual_only": True,
        "exact_main_required": True,
        "source_mutation_allowed": False,
        "provider_mutation_allowed": False,
        "secret_access_allowed": False,
        "controller": _CONTROLLER,
        "guard": "scripts/check_v10_timeweb_post_merge_production_acceptance.py",
        "workflow": _WORKFLOW,
        "runbook": (
            "docs/operations/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_RUNBOOK.md"
        ),
        "confirmation": "ACCEPT_TIMEWEB_PRODUCTION_RELEASE",
    }
    if execution != expected:
        raise RuntimeError("TIMEWEB_P6_EXECUTION_DRIFT")


def _validate_evidence(contract: dict[str, Any]) -> None:
    evidence = contract.get("required_evidence")
    if not isinstance(evidence, dict):
        raise RuntimeError("TIMEWEB_P6_EVIDENCE_POLICY_DRIFT")
    if any(value is not True for value in evidence.values()):
        raise RuntimeError("TIMEWEB_P6_EVIDENCE_POLICY_DRIFT")


def _validate_live_and_invariants(contract: dict[str, Any]) -> None:
    live = contract.get("live_probes")
    if not isinstance(live, dict):
        raise RuntimeError("TIMEWEB_P6_PROVIDER_DRIFT")
    if live.get("sole_provider") != "telegram" or live.get("provider_enabled") is not True:
        raise RuntimeError("TIMEWEB_P6_PROVIDER_DRIFT")
    protected = contract.get("protected_invariants")
    if not isinstance(protected, dict):
        raise RuntimeError("TIMEWEB_P6_INVARIANTS_INVALID")
    if any(value is not False for value in protected.values()):
        raise RuntimeError("TIMEWEB_P6_AUTHORITY_WIDENED")


def _validate_controller(root: Path) -> None:
    controller = _read(root / _CONTROLLER)
    _markers(
        controller,
        (
            "TIMEWEB_PRODUCTION_ACCEPTANCE=ACCEPTED",
            "omni-cio.v10.timeweb-production-acceptance-seal.v1",
            '"/livez"',
            '"/healthz"',
            '"/api/v10/web/auth/providers"',
            '"provider": "telegram"',
            '"enabled": True',
            "TIMEWEB_PRODUCTION_ACCEPTANCE_MAIN_SHA_DRIFT",
            "TIMEWEB_PRODUCTION_ACCEPTANCE_ROLLBACK_SHA_COLLISION",
        ),
        "TIMEWEB_P6_CONTROLLER_DRIFT",
    )
    for forbidden in ("TIMEWEB_CLOUD_API_TOKEN", "secrets."):
        if forbidden in controller:
            raise RuntimeError(
                f"TIMEWEB_P6_CONTROLLER_SECRET_BOUNDARY_DRIFT:{forbidden}"
            )


def _validate_workflow(root: Path) -> None:
    workflow = _read(root / _WORKFLOW)
    _markers(
        workflow,
        (
            "workflow_dispatch:",
            "contents: read",
            "github.ref == 'refs/heads/main'",
            "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10",
            "scripts.check_v10_timeweb_post_merge_production_acceptance",
            "scripts.timeweb_production_acceptance",
            "git fetch --no-tags --depth=1 origin main",
            "TIMEWEB_PRODUCTION_ACCEPTANCE_EVIDENCE",
        ),
        "TIMEWEB_P6_WORKFLOW_DRIFT",
    )
    soft_fail = "continue-on-" + "error"
    broad_write = "write-" + "all"
    forbidden = (
        "pull_request:",
        "\npush:",
        "workflow_run:",
        "\nschedule:",
        "TIMEWEB_CLOUD_API_TOKEN",
        "secrets.",
        soft_fail,
        broad_write,
    )
    for marker in forbidden:
        if marker in workflow:
            raise RuntimeError(f"TIMEWEB_P6_WORKFLOW_AUTHORITY_WIDENED:{marker}")


def validate(root: Path = ROOT) -> None:
    contract = _json(root / _CONTRACT)
    _validate_metadata(contract)
    _validate_execution(contract)
    _validate_evidence(contract)
    _validate_live_and_invariants(contract)
    _validate_controller(root)
    _validate_workflow(root)


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
