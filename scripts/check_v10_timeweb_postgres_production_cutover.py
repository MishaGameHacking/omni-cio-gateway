from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json"
RUNBOOK = ROOT / "docs/operations/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_RUNBOOK.md"
CONTROLLER = ROOT / "scripts/timeweb_postgres_production_cutover.py"
WORKFLOW = ROOT / ".github/workflows/v10-timeweb-postgres-production-cutover.yml"
RUNTIME = ROOT / "infrastructure/postgres/hosted-postgres-runtime-contract.json"
RECOVERY = ROOT / "infrastructure/postgres/hosted-recovery-contract.json"


class CutoverContractError(RuntimeError):
    pass


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CutoverContractError(f"TIMEWEB_PG_CUTOVER_SOURCE_UNREADABLE:{path.name}") from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_JSON_INVALID")
    return value


def _markers(source: str, required: tuple[str, ...], code: str) -> None:
    missing = [item for item in required if item not in source]
    if missing:
        raise CutoverContractError(f"{code}:{missing[0]}")


def _false_map(value: object, keys: tuple[str, ...], code: str) -> None:
    if not isinstance(value, dict) or any(value.get(key) is not False for key in keys):
        raise CutoverContractError(code)


def _validate_contract(payload: dict[str, Any]) -> None:
    expected_root = {
        "schema": "omni-cio.v10.timeweb-postgres-production-cutover.v1",
        "status": "OWNER_APPROVED_BRANCH_LOCAL_IMPLEMENTATION_VERIFICATION_PENDING",
        "owning_system_update": "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "owning_pr": 584,
        "milestone": "P3_POSTGRES18_PRODUCTION_CUTOVER",
    }
    if any(payload.get(k) != v for k, v in expected_root.items()):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_IDENTITY_DRIFT")
    target = payload.get("target")
    if not isinstance(target, dict) or target.get("postgres_major") != 18:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_TARGET_INVALID")
    if target.get("synthetic_fixture_promotion_allowed") is not False:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_TARGET_INVALID")
    role = payload.get("runtime_role")
    if not isinstance(role, dict) or role.get("name") != "omni_cio_hosted_api":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_RUNTIME_ROLE_INVALID")
    _false_map(
        role,
        (
            "controller_creates_login", "controller_alters_login_password",
            "superuser_allowed", "createdb_allowed", "createrole_allowed",
            "replication_allowed", "bypassrls_allowed", "membership_widening_allowed",
            "database_owner_allowed", "schema_owner_allowed", "object_owner_allowed",
        ),
        "TIMEWEB_PG_CUTOVER_RUNTIME_ROLE_WIDENED",
    )
    prepare = payload.get("prepare")
    if not isinstance(prepare, dict) or prepare.get("confirmation") != "PREPARE_TIMEWEB_PRODUCTION_POSTGRES":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_PREPARE_INVALID")
    _false_map(
        prepare,
        ("data_deletion_allowed", "drop_schema_allowed", "truncate_allowed"),
        "TIMEWEB_PG_CUTOVER_DESTRUCTIVE_AUTHORITY",
    )
    binding = payload.get("app_binding")
    if not isinstance(binding, dict):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_APP_BINDING_INVALID")
    _false_map(
        binding,
        ("runtime_dsn_promotion_by_controller_allowed", "undocumented_timeweb_app_settings_api_allowed"),
        "TIMEWEB_PG_CUTOVER_APP_BINDING_INVALID",
    )
    _false_map(
        payload.get("protected_invariants"),
        (
            "PUBLIC_MULTI_USER_ENABLED", "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
            "OMNI_V10_VK_ID_LOGIN_ENABLED", "broker_write", "trading_methods",
            "REAL_TRADING_ENABLED", "canonical_domain_mutation", "web_visual_started",
            "wp23_unlocked",
        ),
        "TIMEWEB_PG_CUTOVER_AUTHORITY_WIDENED",
    )


def _validate_sources() -> None:
    controller = _text(CONTROLLER)
    _markers(
        controller,
        (
            'PREPARE_CONFIRMATION = "PREPARE_TIMEWEB_PRODUCTION_POSTGRES"',
            'RUNTIME_ROLE = "omni_cio_hosted_api"', '"verify-full"',
            "require_postgres_18", "apply_migrations(bootstrap)",
            "postgres_runtime.render_runtime_sql(RUNTIME_ROLE)",
            "probe_hosted_runtime_database", "_verify_cross_tenant_negative(runtime)",
            "TIMEWEB_PG_PRODUCTION_TARGET_NOT_CLEAN",
            "TIMEWEB_PG_PRODUCTION_APP_DSN_NOT_PROMOTED",
            "TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=ACCEPTED",
        ),
        "TIMEWEB_PG_CUTOVER_CONTROLLER_DRIFT",
    )
    if any(item in controller for item in ("DROP DATABASE", "DROP SCHEMA", "TRUNCATE ", "sslmode=disable", "CREATE ROLE", "ALTER ROLE")):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_CONTROLLER_AUTHORITY_WIDENED")
    workflow = _text(WORKFLOW)
    _markers(
        workflow,
        (
            "workflow_dispatch:", "expected_main_sha:", "timeweb-production",
            "PREPARE_TIMEWEB_PRODUCTION_POSTGRES", "OMNI_V10_TIMEWEB_PROD_BOOTSTRAP_DSN",
            "OMNI_V10_TIMEWEB_PROD_RUNTIME_DSN", "OMNI_V10_TIMEWEB_PG_RECOVERY_ATTESTATION",
            "TIMEWEB_CLOUD_API_TOKEN", "scripts.timeweb_postgres_production_cutover",
        ),
        "TIMEWEB_PG_CUTOVER_WORKFLOW_DRIFT",
    )
    if any(item in workflow for item in ("\n  push:", "\n  pull_request:", "schedule:")):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_WORKFLOW_AUTO_TRIGGER_FORBIDDEN")
    _markers(
        _text(RUNBOOK),
        (
            "distinct from the historical synthetic parity target",
            "physical backup recovery point", "separate restore rehearsal",
            "Do not invent an undocumented endpoint", "Only after P3 acceptance may P4",
        ),
        "TIMEWEB_PG_CUTOVER_RUNBOOK_DRIFT",
    )
    if _json(RUNTIME).get("schema_version") != "v10.hosted-postgres-runtime.v5":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_RUNTIME_CONTRACT_INVALID")
    if _json(RECOVERY).get("schema_version") != "v10.hosted-recovery.v2":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_RECOVERY_CONTRACT_INVALID")


def validate(root: Path = ROOT) -> None:
    global ROOT, CONTRACT, RUNBOOK, CONTROLLER, WORKFLOW, RUNTIME, RECOVERY
    old = (ROOT, CONTRACT, RUNBOOK, CONTROLLER, WORKFLOW, RUNTIME, RECOVERY)
    if root != ROOT:
        ROOT = root
        CONTRACT = root / "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json"
        RUNBOOK = root / "docs/operations/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_RUNBOOK.md"
        CONTROLLER = root / "scripts/timeweb_postgres_production_cutover.py"
        WORKFLOW = root / ".github/workflows/v10-timeweb-postgres-production-cutover.yml"
        RUNTIME = root / "infrastructure/postgres/hosted-postgres-runtime-contract.json"
        RECOVERY = root / "infrastructure/postgres/hosted-recovery-contract.json"
    try:
        _validate_contract(_json(CONTRACT))
        _validate_sources()
    finally:
        ROOT, CONTRACT, RUNBOOK, CONTROLLER, WORKFLOW, RUNTIME, RECOVERY = old


def main() -> int:
    try:
        validate()
    except CutoverContractError as exc:
        print(f"V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=FAIL code={exc}", file=sys.stderr)
        return 1
    print("V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=PASS repository_implementation=bounded external_cutover=fail_closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
