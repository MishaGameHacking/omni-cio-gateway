from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_HOSTED_CUSTODY_RELATIVE = Path("omni_cio/web/hosted_secret_custody_v1.py")
_HOSTED_APP_RELATIVE = Path("apps/api/hosted_app.py")
_HOSTED_RUNTIME_RELATIVE = Path("apps/api/hosted_runtime.py")
_TELEGRAM_AUTH_RELATIVE = Path("apps/api/telegram_auth.py")

CONTRACT = (
    ROOT / "docs/architecture/V10_TIMEWEB_NO_OWNER_LAPTOP_DEPENDENCY_CONTRACT.json"
)
HOSTED_CUSTODY = ROOT / _HOSTED_CUSTODY_RELATIVE
HOSTED_APP = ROOT / _HOSTED_APP_RELATIVE
HOSTED_RUNTIME = ROOT / _HOSTED_RUNTIME_RELATIVE
TELEGRAM_AUTH = ROOT / _TELEGRAM_AUTH_RELATIVE
WP17_CONTRACT = ROOT / "docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json"
WP17_SECURITY_GUARD = ROOT / "scripts/check_v10_wp17_web_security.py"
CURRENT_WORKFLOW = ROOT / ".github/workflows/v10-wp17-owner-read-vault-audit.yml"
HISTORICAL_WORKFLOW = (
    ROOT / ".github/workflows/v10-wp17-local-read-vault-historical-audit.yml"
)
PUBLIC_RUNTIME = (
    ROOT / "docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json"
)

FORBIDDEN_CURRENT_MARKERS = (
    "broker_vault_v1",
    "ReadBrokerConnectionVaultV1",
    r"C:\\ProgramData\\OmniCIO",
    "TINVEST_TRADING_TOKEN",
    "PostOrder",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(_text(path))
    if not isinstance(payload, dict):
        raise RuntimeError(f"TIMEWEB_NO_LAPTOP_JSON_ROOT_INVALID:{path.name}")
    return payload


def _validate_wp17_transition(
    root: Path,
    contract: dict[str, Any],
) -> None:
    transition = contract.get("wp17_transition")
    if not isinstance(transition, dict):
        raise RuntimeError("TIMEWEB_NO_LAPTOP_WP17_TRANSITION_INVALID")
    expected = {
        "required_check_mode": "TIMEWEB_SOURCE_SECURITY_AUDIT",
        "required_check_runner": "ubuntu-latest",
        "historical_local_audit_mode": "MANUAL_ONLY",
        "old_owner_evidence_blocks_timeweb_pr": False,
        "active_wp17_contract_owner_acl_required": False,
        "active_wp17_security_guard_local_vault_required": False,
        "historical_local_vault_tests_preserved": True,
        "historical_local_evidence_blocks_timeweb_pr": False,
    }
    for key, value in expected.items():
        if transition.get(key) != value:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_WP17_TRANSITION_DRIFT:{key}")

    wp17 = _json(root / WP17_CONTRACT.relative_to(ROOT))
    custody = wp17.get("timeweb_broker_custody")
    if not isinstance(custody, dict):
        raise RuntimeError("TIMEWEB_NO_LAPTOP_WP17_CUSTODY_INVALID")
    expected_custody = {
        "mode": "FAIL_CLOSED_PENDING_HOSTED_BACKEND",
        "local_windows_vault_dependency_allowed": False,
        "owner_admin_acl_evidence_required_for_timeweb_pr": False,
        "broker_mutation_enabled": False,
        "global_shared_credential_allowed": False,
        "required_pr_gate": "TIMEWEB_SOURCE_SECURITY_AUDIT",
    }
    for key, value in expected_custody.items():
        if custody.get(key) != value:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_WP17_CUSTODY_DRIFT:{key}")

    historical = wp17.get("read_vault_acceptance")
    if not isinstance(historical, dict):
        raise RuntimeError("TIMEWEB_NO_LAPTOP_WP17_HISTORICAL_VAULT_INVALID")
    if (
        historical.get("authority") != "HISTORICAL_LOCAL_ONLY"
        or historical.get("blocks_timeweb_pr") is not False
    ):
        raise RuntimeError("TIMEWEB_NO_LAPTOP_WP17_HISTORICAL_VAULT_DRIFT")

    security_guard = _text(root / WP17_SECURITY_GUARD.relative_to(ROOT))
    for marker in (
        "timeweb_broker_custody",
        "HISTORICAL_OWNER_READ_VAULT_WORKFLOW",
        "TIMEWEB_SOURCE_SECURITY_AUDIT",
        "FAIL_CLOSED_PENDING_HOSTED_BACKEND",
    ):
        if marker not in security_guard:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_WP17_GUARD_DRIFT:{marker}")


def _mapping(value: object, error: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(error)
    return value


def _validate_contract_identity(contract: dict[str, Any]) -> None:
    if contract.get("schema") != "omni-cio.v10.timeweb-no-owner-laptop-dependency.v1":
        raise RuntimeError("TIMEWEB_NO_LAPTOP_CONTRACT_SCHEMA_INVALID")


def _validate_owner_boundary(contract: dict[str, Any]) -> None:
    owner = _mapping(
        contract.get("owner_manual_boundary"),
        "TIMEWEB_NO_LAPTOP_OWNER_BOUNDARY_INVALID",
    )
    for key in (
        "owner_laptop_manual_shell_required_for_timeweb_pr",
        "owner_admin_acl_evidence_required_for_timeweb_pr",
        "secrets_sent_to_chat_or_github_allowed",
    ):
        if owner.get(key) is not False:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_OWNER_BOUNDARY_DRIFT:{key}")


def _validate_runtime_boundary(contract: dict[str, Any]) -> None:
    runtime = _mapping(
        contract.get("current_timeweb_runtime"),
        "TIMEWEB_NO_LAPTOP_RUNTIME_BOUNDARY_INVALID",
    )
    expected_runtime = {
        "provider": "TIMEWEB_APP_PLATFORM",
        "local_windows_vault_dependency_allowed": False,
        "windows_dpapi_dependency_allowed": False,
        "broker_mutation_enabled": False,
        "global_shared_broker_token_allowed": False,
        "hosted_custody_contract": _HOSTED_CUSTODY_RELATIVE.as_posix(),
    }
    for key, expected in expected_runtime.items():
        if runtime.get(key) != expected:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_RUNTIME_BOUNDARY_DRIFT:{key}")


def _validate_current_runtime_sources(root: Path) -> None:
    current_sources = "\n".join(
        _text(root / path)
        for path in (
            _HOSTED_APP_RELATIVE,
            _HOSTED_RUNTIME_RELATIVE,
            _TELEGRAM_AUTH_RELATIVE,
        )
    )
    for marker in FORBIDDEN_CURRENT_MARKERS:
        if marker in current_sources:
            raise RuntimeError(
                f"TIMEWEB_NO_LAPTOP_CURRENT_LOCAL_VAULT_DEPENDENCY:{marker}"
            )

    hosted_app = _text(root / _HOSTED_APP_RELATIVE)
    for marker in (
        "BROKER_CREDENTIALS_DISABLED_IN_HOSTED_RUNTIME",
        "broker_mutation_disabled",
    ):
        if marker not in hosted_app:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_BROKER_FAIL_CLOSED_DRIFT:{marker}")


def _validate_hosted_custody(root: Path) -> None:
    custody = _text(root / _HOSTED_CUSTODY_RELATIVE)
    for marker in (
        "class HostedReadSecretBackendV1(Protocol)",
        "cross-tenant access",
        "tenant_id",
        "secret_ref",
        "HOSTED_SECRET_TENANT_INVALID",
        "HOSTED_SECRET_REF_INVALID",
    ):
        if marker not in custody:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_HOSTED_CUSTODY_DRIFT:{marker}")


def _validate_required_workflow(root: Path) -> None:
    workflow = _text(root / CURRENT_WORKFLOW.relative_to(ROOT))
    for marker in (
        "name: V10 WP17 OWNER Read Vault Audit",
        "name: OWNER read-vault and runner-isolation evidence",
        "runs-on: ubuntu-latest",
        "python scripts/check_v10_timeweb_no_owner_laptop_dependency.py",
        "python -m unittest tests.test_v10_timeweb_no_owner_laptop_dependency",
        "persist-credentials: false",
    ):
        if marker not in workflow:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_REQUIRED_WORKFLOW_DRIFT:{marker}")
    for forbidden in (
        "runs-on: [self-hosted",
        "audit_wp17_read_vault_runner.ps1",
        "owner-read-vault-evidence.sanitized.local.json",
    ):
        if forbidden in workflow:
            raise RuntimeError(
                f"TIMEWEB_NO_LAPTOP_REQUIRED_WORKFLOW_LOCAL_DEPENDENCY:{forbidden}"
            )


def _validate_historical_workflow(root: Path) -> None:
    historical = _text(root / HISTORICAL_WORKFLOW.relative_to(ROOT))
    if "workflow_dispatch:" not in historical:
        raise RuntimeError("TIMEWEB_NO_LAPTOP_HISTORICAL_WORKFLOW_NOT_MANUAL")
    if "pull_request:" in historical or "push:" in historical:
        raise RuntimeError("TIMEWEB_NO_LAPTOP_HISTORICAL_WORKFLOW_AUTO_TRIGGERED")
    if "audit_wp17_read_vault_runner.ps1" not in historical:
        raise RuntimeError("TIMEWEB_NO_LAPTOP_HISTORICAL_EVIDENCE_REMOVED")


def _validate_public_runtime(root: Path) -> None:
    public = _json(root / PUBLIC_RUNTIME.relative_to(ROOT))
    hosting = _mapping(
        public.get("production_hosting"),
        "TIMEWEB_NO_LAPTOP_PUBLIC_HOSTING_CONTRACT_INVALID",
    )
    for key in (
        "home_public_ip_dependency_allowed",
        "home_wifi_dependency_allowed",
        "home_router_dependency_allowed",
        "owner_lan_dependency_allowed",
        "lenovo_as_public_production_origin_allowed",
        "owner_home_power_or_internet_may_be_public_sla_dependency",
    ):
        if hosting.get(key) is not False:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_PUBLIC_HOSTING_DRIFT:{key}")


def validate(root: Path = ROOT) -> None:
    contract = _json(root / CONTRACT.relative_to(ROOT))
    _validate_contract_identity(contract)
    _validate_owner_boundary(contract)
    _validate_runtime_boundary(contract)
    _validate_wp17_transition(root, contract)
    _validate_current_runtime_sources(root)
    _validate_hosted_custody(root)
    _validate_required_workflow(root)
    _validate_historical_workflow(root)
    _validate_public_runtime(root)


def main() -> int:
    try:
        validate()
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"V10_TIMEWEB_NO_OWNER_LAPTOP=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("V10_TIMEWEB_NO_OWNER_LAPTOP=PASS")
    print("Current Timeweb runtime: no Windows local-vault dependency")
    print("Broker credential mutation: fail-closed until hosted custody gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
