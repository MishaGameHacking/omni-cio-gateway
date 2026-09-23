from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_NO_OWNER_LAPTOP_DEPENDENCY_CONTRACT.json"
HOSTED_CUSTODY = ROOT / "omni_cio/web/hosted_secret_custody_v1.py"
HOSTED_APP = ROOT / "apps/api/hosted_app.py"
HOSTED_RUNTIME = ROOT / "apps/api/hosted_runtime.py"
TELEGRAM_AUTH = ROOT / "apps/api/telegram_auth.py"
CURRENT_WORKFLOW = ROOT / ".github/workflows/v10-wp17-owner-read-vault-audit.yml"
HISTORICAL_WORKFLOW = ROOT / ".github/workflows/v10-wp17-local-read-vault-historical-audit.yml"
PUBLIC_RUNTIME = ROOT / "docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json"

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


def validate(root: Path = ROOT) -> None:
    contract = _json(root / CONTRACT.relative_to(ROOT))
    if contract.get("schema") != "omni-cio.v10.timeweb-no-owner-laptop-dependency.v1":
        raise RuntimeError("TIMEWEB_NO_LAPTOP_CONTRACT_SCHEMA_INVALID")

    owner = contract.get("owner_manual_boundary")
    if not isinstance(owner, dict):
        raise RuntimeError("TIMEWEB_NO_LAPTOP_OWNER_BOUNDARY_INVALID")
    for key in (
        "owner_laptop_manual_shell_required_for_timeweb_pr",
        "owner_admin_acl_evidence_required_for_timeweb_pr",
        "secrets_sent_to_chat_or_github_allowed",
    ):
        if owner.get(key) is not False:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_OWNER_BOUNDARY_DRIFT:{key}")

    runtime = contract.get("current_timeweb_runtime")
    if not isinstance(runtime, dict):
        raise RuntimeError("TIMEWEB_NO_LAPTOP_RUNTIME_BOUNDARY_INVALID")
    expected_runtime = {
        "provider": "TIMEWEB_APP_PLATFORM",
        "local_windows_vault_dependency_allowed": False,
        "windows_dpapi_dependency_allowed": False,
        "broker_mutation_enabled": False,
        "global_shared_broker_token_allowed": False,
        "hosted_secret_contract": "omni_cio/web/hosted_secret_custody_v1.py",
    }
    for key, expected in expected_runtime.items():
        if runtime.get(key) != expected:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_RUNTIME_BOUNDARY_DRIFT:{key}")

    current_sources = "\n".join(
        _text(root / path)
        for path in (
            Path("apps/api/hosted_app.py"),
            Path("apps/api/hosted_runtime.py"),
            Path("apps/api/telegram_auth.py"),
        )
    )
    for marker in FORBIDDEN_CURRENT_MARKERS:
        if marker in current_sources:
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_CURRENT_LOCAL_VAULT_DEPENDENCY:{marker}")
    for marker in (
        "BROKER_CREDENTIALS_DISABLED_IN_HOSTED_RUNTIME",
        "broker_mutation_disabled",
    ):
        if marker not in _text(root / "apps/api/hosted_app.py"):
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_BROKER_FAIL_CLOSED_DRIFT:{marker}")

    custody = _text(root / "omni_cio/web/hosted_secret_custody_v1.py")
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
            raise RuntimeError(f"TIMEWEB_NO_LAPTOP_REQUIRED_WORKFLOW_LOCAL_DEPENDENCY:{forbidden}")

    historical = _text(root / HISTORICAL_WORKFLOW.relative_to(ROOT))
    if "workflow_dispatch:" not in historical:
        raise RuntimeError("TIMEWEB_NO_LAPTOP_HISTORICAL_WORKFLOW_NOT_MANUAL")
    if "pull_request:" in historical or "push:" in historical:
        raise RuntimeError("TIMEWEB_NO_LAPTOP_HISTORICAL_WORKFLOW_AUTO_TRIGGERED")
    if "audit_wp17_read_vault_runner.ps1" not in historical:
        raise RuntimeError("TIMEWEB_NO_LAPTOP_HISTORICAL_EVIDENCE_REMOVED")

    public = _json(root / PUBLIC_RUNTIME.relative_to(ROOT))
    hosting = public.get("production_hosting")
    if not isinstance(hosting, dict):
        raise RuntimeError("TIMEWEB_NO_LAPTOP_PUBLIC_HOSTING_CONTRACT_INVALID")
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
