from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_CREATE_CONTRACT.json"
)
PROVISIONER = ROOT / "scripts/provision_v10_timeweb_postgres_synthetic.py"
READ_ONLY_PROBE = ROOT / "scripts/probe_v10_timeweb_postgres_control_plane.py"
ENVIRONMENT_VERIFIER = ROOT / "scripts/verify_v10_timeweb_github_environment.py"
RUNBOOK = ROOT / "docs/operations/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_CREATE_RUNBOOK.md"
WORKFLOW = ROOT / ".github/workflows/v10-timeweb-postgres-synthetic-create.yml"

_SCHEMA = "omni-cio.v10.ru-postgres-timeweb-synthetic-create.v1"
_STAGE = "RU-PG-B_TIMEWEB_SYNTHETIC_CLUSTER_CREATE"
_STATUS = "SOURCE_READY_PAID_MUTATION_PENDING_MAIN_ACCEPTANCE"
_TIMEWEB_BINDING = "TIMEWEB_CLOUD_API_" + "TOKEN"
_CONFIRMATION = "CREATE_TIMEWEB_RU_PG_SYNTHETIC_790_RUB_MONTH"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_SOURCE_UNREADABLE") from exc


def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(_read(CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_CONTRACT_INVALID")
    return payload


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise RuntimeError(code)


def _require_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    for marker in markers:
        if marker not in source:
            raise RuntimeError(code)


def _validate_contract(payload: dict[str, Any]) -> None:
    _require(payload.get("schema"), _SCHEMA, "TIMEWEB_SYNTHETIC_CREATE_SCHEMA_INVALID")
    _require(payload.get("stage"), _STAGE, "TIMEWEB_SYNTHETIC_CREATE_STAGE_INVALID")
    _require(payload.get("status"), _STATUS, "TIMEWEB_SYNTHETIC_CREATE_STATUS_INVALID")
    _require(payload.get("owning_issue"), 559, "TIMEWEB_SYNTHETIC_CREATE_ISSUE_INVALID")
    _require(
        payload.get("accepted_base_sha_parts"),
        ["4987d5ad", "ced8f449", "b482ec1a", "d4165a01", "30c995d3"],
        "TIMEWEB_SYNTHETIC_CREATE_BASE_INVALID",
    )

    prerequisite = _mapping(
        payload.get("prerequisite_evidence"),
        "TIMEWEB_SYNTHETIC_CREATE_PREREQUISITE_INVALID",
    )
    expected_prerequisite = {
        "read_only_workflow_run": 35465650177,
        "environment_gate_marker": "TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY",
        "read_only_marker": "TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY",
        "postgres_major": 18,
        "terraform_location": "ru-3",
        "cpu": 1,
        "ram_mb": 2048,
        "disk_mb": 20480,
        "base_monthly_price_rub": 790,
        "target_cluster_name_available": True,
    }
    _require(
        prerequisite,
        expected_prerequisite,
        "TIMEWEB_SYNTHETIC_CREATE_PREREQUISITE_INVALID",
    )

    authority = _mapping(
        payload.get("authority"),
        "TIMEWEB_SYNTHETIC_CREATE_AUTHORITY_INVALID",
    )
    expected_authority = {
        "owner_base_cost_approval_recorded": True,
        "authorized_base_monthly_price_rub": 790,
        "fresh_cost_revalidation_before_post_required": True,
        "paid_mutation_allowed_only_after_source_checkpoint_accepted_on_main": True,
        "manual_workflow_dispatch_required": True,
        "exact_main_ref_required": True,
        "environment": "timeweb-synthetic",
        "environment_machine_gate_required": True,
        "provider_secret_step_scope_required": True,
    }
    _require(
        authority,
        expected_authority,
        "TIMEWEB_SYNTHETIC_CREATE_AUTHORITY_INVALID",
    )

    target = _mapping(payload.get("target"), "TIMEWEB_SYNTHETIC_CREATE_TARGET_INVALID")
    expected_target = {
        "provider": "Timeweb Cloud",
        "service": "Managed PostgreSQL",
        "cluster_name": "omni-cio-v10-ru-pg-synthetic",
        "postgres_major": 18,
        "location": "ru-3",
        "availability_zone": "msk-1",
        "cpu": 1,
        "ram_mb": 2048,
        "disk_mb": 20480,
        "public_ipv4_authorized": False,
        "public_ipv6_authorized": False,
        "backup_addon_authorized": False,
        "replicas_authorized": False,
        "disk_autoscaling_authorized": False,
        "production_data_allowed": False,
    }
    _require(target, expected_target, "TIMEWEB_SYNTHETIC_CREATE_TARGET_INVALID")

    api = _mapping(
        payload.get("api_boundary"),
        "TIMEWEB_SYNTHETIC_CREATE_API_BOUNDARY_INVALID",
    )
    _require(
        api.get("create_endpoint"),
        "POST /api/v1/databases",
        "TIMEWEB_SYNTHETIC_CREATE_ENDPOINT_INVALID",
    )
    for key in (
        "post_retry_allowed",
        "put_allowed",
        "patch_allowed",
        "delete_allowed",
        "redirects_allowed",
        "response_body_logging_allowed",
        "provider_identifiers_in_output_allowed",
    ):
        _require(api.get(key), False, "TIMEWEB_SYNTHETIC_CREATE_API_BOUNDARY_INVALID")
    _require(
        api.get("ambiguous_post_requires_get_reconciliation"),
        True,
        "TIMEWEB_SYNTHETIC_CREATE_RECONCILIATION_INVALID",
    )
    _require(
        api.get("max_response_bytes"),
        1048576,
        "TIMEWEB_SYNTHETIC_CREATE_API_BOUNDARY_INVALID",
    )

    request = _mapping(
        payload.get("request_shape"),
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        set(request.get("forbidden_fields", [])),
        {
            "admin",
            "instance",
            "network",
            "replication",
            "auto_backups",
            "backup_schedule",
            "maintenance_slot",
            "configuration",
            "config_parameters",
        },
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        request.get("exact_availability_zone"),
        "msk-1",
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        request.get("is_public_ipv6"),
        False,
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        request.get("disk_autoscaling_enabled"),
        False,
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )

    verification = _mapping(
        payload.get("post_create_verification"),
        "TIMEWEB_SYNTHETIC_CREATE_VERIFICATION_INVALID",
    )
    _require(
        verification.get("sanitized_marker"),
        "TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY",
        "TIMEWEB_SYNTHETIC_CREATE_VERIFICATION_INVALID",
    )
    for key in (
        "exact_cluster_get_required",
        "exact_project_membership_recheck_required",
        "started_status_required",
        "public_network_must_be_disabled",
        "public_ipv6_must_be_disabled",
        "autobackups_must_be_disabled",
        "backup_schedule_must_be_disabled",
        "replica_list_must_be_empty",
        "disk_autoscaling_must_be_disabled",
    ):
        _require(
            verification.get(key),
            True,
            "TIMEWEB_SYNTHETIC_CREATE_VERIFICATION_INVALID",
        )

    invariants = _mapping(
        payload.get("protected_invariants"),
        "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
    )
    _require(
        invariants.get("current_neon_production_authority_preserved"),
        True,
        "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
    )
    _require(
        invariants.get("protected_v9_entrypoint"),
        "app:app",
        "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
    )
    for key in (
        "production_postgres_dsn_mutation_allowed",
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "OMNI_V10_VK_ID_LOGIN_ENABLED",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "ru_pg_c_allowed",
    ):
        _require(
            invariants.get(key),
            False,
            "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
        )


def _validate_read_only_probe_reuse() -> None:
    source = _read(READ_ONLY_PROBE)
    _require_markers(
        source,
        (
            'TARGET_CLUSTER_NAME = "omni-cio-v10-ru-pg-synthetic"',
            'TARGET_LOCATION = "ru-3"',
            'TARGET_PRICE_RUB = Decimal("790")',
            "def _select_target_preset(payload: object, provider_type: str) -> int:",
            "TIMEWEB_BETA_PRESET_NOT_UNIQUE_OR_PRICE_DRIFT",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_READ_ONLY_REUSE_DRIFT",
    )


def _validate_provisioner() -> None:
    source = _read(PROVISIONER)
    _require_markers(
        source,
        (
            'CREATE_PATH = "/api/v1/databases"',
            'TARGET_AVAILABILITY_ZONE = "msk-1"',
            f'CREATE_CONFIRMATION = "{_CONFIRMATION}"',
            'method="POST"',
            "def post_once(",
            "class AmbiguousCreate",
            "TIMEWEB_CLUSTER_CREATE_AMBIGUOUS_RECONCILIATION_REQUIRED",
            "def _reconcile_cluster_id(",
            "def _create_or_reconcile(",
            '"disk_autoscaling": {"is_enabled": False}',
            '"is_public_ipv6": False',
            '"is_enabled_public_network": False',
            '"is_autobackups_enabled": False',
            '"is_backup_schedule_enabled": False',
            '"TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY "',
            "create_mode={create_mode}",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_PROVISIONER_DRIFT",
    )
    forbidden = (
        'method="PUT"',
        'method="PATCH"',
        'method="DELETE"',
        ".put(",
        ".patch(",
        ".delete(",
        "OMNI_V10_POSTGRES_DSN",
        "NEON_API_KEY",
        '"auto_backups":',
        '"backup_schedule":',
        '"replication":',
        '"network":',
        '"admin":',
        '"instance":',
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_AUTHORITY_WIDENED")
    if source.count('method="POST"') != 1:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_POST_SURFACE_INVALID")


def _validate_environment_verifier() -> None:
    source = _read(ENVIRONMENT_VERIFIER)
    _require_markers(
        source,
        (
            'ENVIRONMENT_NAME = "timeweb-synthetic"',
            'EXPECTED_BRANCH_PATTERN = "main"',
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_ENVIRONMENT_GATE_DRIFT",
    )


def _validate_workflow() -> None:
    source = _read(WORKFLOW)
    _require_markers(
        source,
        (
            "workflow_dispatch:",
            "confirmation:",
            _CONFIRMATION,
            "actions: read",
            "contents: read",
            "if: github.ref == 'refs/heads/main'",
            "environment-policy-proof:",
            "needs: environment-policy-proof",
            "environment: timeweb-synthetic",
            "python scripts/check_v10_timeweb_postgres_synthetic_create.py",
            "python -m scripts.verify_v10_timeweb_github_environment",
            "python -m scripts.provision_v10_timeweb_postgres_synthetic",
            f"{_TIMEWEB_BINDING}: ${{{{ secrets.{_TIMEWEB_BINDING} }}}}",
            "git clean -ffdx",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_WORKFLOW_DRIFT",
    )
    if source.count(f"secrets.{_TIMEWEB_BINDING}") != 1:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_SECRET_SCOPE_INVALID")
    forbidden = (
        "on:\n  push:",
        "pull_request:",
        "schedule:",
        "curl ",
        "Invoke-RestMethod",
        "Invoke-WebRequest",
        "OMNI_V10_POSTGRES_DSN",
        "method=PUT",
        "method=PATCH",
        "method=DELETE",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_WORKFLOW_AUTHORITY_WIDENED")


def _validate_runbook() -> None:
    source = _read(RUNBOOK)
    _require_markers(
        source,
        (
            "RU-PG-B",
            "790 RUB/month",
            "POST /api/v1/databases",
            "never automatically retried",
            "Reconciliation",
            _CONFIRMATION,
            "TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY",
            "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
            "Neon production authority",
            "RU-PG-C remains",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_RUNBOOK_DRIFT",
    )


def validate() -> None:
    _validate_contract(_load_contract())
    _validate_read_only_probe_reuse()
    _validate_provisioner()
    _validate_environment_verifier()
    _validate_workflow()
    _validate_runbook()


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Timeweb RU-PG-B synthetic create source contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
