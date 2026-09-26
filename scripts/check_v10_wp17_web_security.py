from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP17_APPLICATION_SHELL_CONTRACT.json"
WP22A_EXECUTION_CONTRACT = (
    ROOT / "docs" / "architecture" / "V10_WP22A_EXECUTION_CONTRACT.md"
)
WEB_SHELL = ROOT / "apps" / "web" / "src" / "app-shell"
API_ROOT = ROOT / "apps" / "api"
WEB_BACKEND = ROOT / "omni_cio" / "web"
MIGRATION = (
    ROOT
    / "omni_cio"
    / "persistence"
    / "migrations"
    / "0003_web_identity_connections.sql"
)
OWNER_EVIDENCE_FINALIZER = (
    ROOT / "infrastructure" / "windows" / "finalize_wp17_web_read_vault_evidence.ps1"
)
_READ_VAULT_AUDITOR_SCRIPT = "audit_wp17_read_vault_runner.ps1"
RUNNER_READ_VAULT_AUDITOR = (
    ROOT / "infrastructure" / "windows" / _READ_VAULT_AUDITOR_SCRIPT
)
OWNER_READ_VAULT_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp17-owner-read-vault-audit.yml"
)
HISTORICAL_OWNER_READ_VAULT_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp17-local-read-vault-historical-audit.yml"
)
TIMEWEB_SOURCE_SECURITY_AUDIT = "TIMEWEB_SOURCE_SECURITY_AUDIT"
TIMEWEB_CUSTODY_PENDING = "FAIL_CLOSED_PENDING_HOSTED_BACKEND"


def _text_tree(root: Path) -> str:
    parts: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".css"}:
            continue
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _wp22a_source_gate_active(failures: list[str]) -> bool:
    if not WP22A_EXECUTION_CONTRACT.is_file():
        return False
    try:
        text = WP22A_EXECUTION_CONTRACT.read_text(encoding="utf-8")
    except OSError as exc:
        failures.append(f"WP22A execution contract unreadable: {type(exc).__name__}")
        return False

    required_markers = (
        "CORRECTED PUBLIC-HOSTED TARGET",
        "Owning package: **WP22A — External Web Access / Product Authentication Security Gate**",
        "WP23+: LOCKED",
        "`PUBLIC_MULTI_USER_ENABLED=false`",
        "must not depend on PROJECT OWNER home public IP",
    )
    if all(marker in text for marker in required_markers):
        return True
    failures.append(
        "WP22A execution contract present but corrected source-gate markers are incomplete"
    )
    return False


def _validate_login_and_public_activation(
    contract: dict[str, Any],
    failures: list[str],
) -> None:
    if contract.get("ordinary_login_providers") != ["telegram"]:
        failures.append("ordinary login providers drifted")
    if contract.get("local_password_allowed") is not False:
        failures.append("local password must remain disabled")
    public_activation = contract.get("public_activation", {})
    if not isinstance(public_activation, dict):
        failures.append("public activation contract must be an object")
    elif public_activation.get("public_internet_ingress") is not False:
        failures.append("public ingress must remain disabled in WP17")


def _validate_timeweb_broker_custody(
    contract: dict[str, Any],
    failures: list[str],
) -> None:
    custody = contract.get("timeweb_broker_custody")
    if not isinstance(custody, dict):
        failures.append("Timeweb broker custody contract must be an object")
        return
    expected = {
        "mode": TIMEWEB_CUSTODY_PENDING,
        "local_windows_vault_dependency_allowed": False,
        "owner_admin_acl_evidence_required_for_timeweb_pr": False,
        "broker_mutation_enabled": False,
        "global_shared_credential_allowed": False,
        "required_pr_gate": TIMEWEB_SOURCE_SECURITY_AUDIT,
    }
    for key, value in expected.items():
        if custody.get(key) != value:
            failures.append(f"Timeweb broker custody drifted: {key}")


def _validate_historical_acceptance_values(
    acceptance: dict[str, Any],
    failures: list[str],
) -> None:
    if acceptance.get("authority") != "HISTORICAL_LOCAL_ONLY":
        failures.append("historical READ-vault authority classification drifted")
    if acceptance.get("blocks_timeweb_pr") is not False:
        failures.append("historical READ-vault may not block the Timeweb PR")

    for key in (
        "owner_admin_verify_required",
        "exact_head_binding_required",
        "script_hash_binding_required",
        "non_admin_runner_negative_probe_required",
    ):
        if acceptance.get(key) is not True:
            failures.append(f"historical READ-vault protection disabled: {key}")
    for key in (
        "runner_payload_read_allowed",
        "runner_payload_write_allowed",
        "runner_evidence_write_allowed",
    ):
        if acceptance.get(key) is not False:
            failures.append(f"historical READ-vault runner authority widened: {key}")


def _validate_read_vault_components(failures: list[str]) -> None:
    for component in (
        OWNER_EVIDENCE_FINALIZER,
        RUNNER_READ_VAULT_AUDITOR,
        HISTORICAL_OWNER_READ_VAULT_WORKFLOW,
        OWNER_READ_VAULT_WORKFLOW,
    ):
        if not component.is_file():
            failures.append(f"READ-vault evidence component missing: {component.name}")


def _validate_active_wp17_workflow(failures: list[str]) -> None:
    active_workflow = OWNER_READ_VAULT_WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "runs-on: ubuntu-latest",
        "python scripts/check_v10_timeweb_no_owner_laptop_dependency.py",
        "python -m unittest tests.test_v10_timeweb_no_owner_laptop_dependency",
    ):
        if marker not in active_workflow:
            failures.append(f"Timeweb WP17 source-security gate missing: {marker}")
    for forbidden in (
        _READ_VAULT_AUDITOR_SCRIPT,
        "owner-read-vault-evidence.sanitized.local.json",
        "runs-on: [self-hosted",
    ):
        if forbidden in active_workflow:
            failures.append(
                f"Timeweb WP17 gate regained local-vault dependency: {forbidden}"
            )


def _validate_historical_wp17_workflow(failures: list[str]) -> None:
    historical_workflow = HISTORICAL_OWNER_READ_VAULT_WORKFLOW.read_text(
        encoding="utf-8"
    )
    for marker in (
        "workflow_dispatch:",
        _READ_VAULT_AUDITOR_SCRIPT,
        "-ExpectedImplementationSha",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    ):
        if marker not in historical_workflow:
            failures.append(f"historical READ-vault evidence drifted: {marker}")
    if "pull_request:" in historical_workflow or "push:" in historical_workflow:
        failures.append("historical READ-vault workflow must remain manual-only")


def _validate_historical_read_vault(
    contract: dict[str, Any],
    failures: list[str],
) -> None:
    acceptance = contract.get("read_vault_acceptance", {})
    if not isinstance(acceptance, dict):
        failures.append("historical READ-vault acceptance contract must be an object")
        return
    _validate_historical_acceptance_values(acceptance, failures)
    _validate_read_vault_components(failures)
    _validate_active_wp17_workflow(failures)
    _validate_historical_wp17_workflow(failures)


def _validate_invariants(contract: dict[str, Any], failures: list[str]) -> None:
    invariants = contract.get("invariants", {})
    if not isinstance(invariants, dict):
        failures.append("WP17 invariants contract must be an object")
        return
    if invariants.get("gateway_entrypoint") != "app:app":
        failures.append("gateway entrypoint drifted")
    if invariants.get("trading_methods") is not False:
        failures.append("trading_methods must remain false")
    if invariants.get("REAL_TRADING_ENABLED") is not False:
        failures.append("REAL_TRADING_ENABLED must remain false")
    if invariants.get("broker_write_authority_added") is not False:
        failures.append("WP17 may not add broker write authority")


def _validate_browser_surface(failures: list[str]) -> None:
    web_text = _text_tree(WEB_SHELL)
    for marker in ("localStorage", "sessionStorage", "dangerouslySetInnerHTML"):
        if marker in web_text:
            failures.append(f"forbidden browser persistence/render primitive: {marker}")
    if "google" in web_text.lower():
        failures.append("Google login marker present in WP17 shell")
    if 'type="password"' not in web_text:
        failures.append("masked broker credential input is missing")


def _validate_backend_surface(
    failures: list[str],
    *,
    wp22a_source_gate: bool,
) -> None:
    backend_text = _text_tree(WEB_BACKEND) + "\n" + _text_tree(API_ROOT)
    lowered_backend = backend_text.lower()
    for marker in (
        "broker_trading",
        "stop_orders",
        ".orders",
        "withdraw",
        "currency_transfer",
        "pay_in",
    ):
        if marker in lowered_backend:
            failures.append(
                f"broker write/transfer marker present in WP17 backend: {marker}"
            )

    bind_all_marker = ".".join(("0", "0", "0", "0"))
    if bind_all_marker in lowered_backend:
        failures.append(
            f"public bind marker forbidden by Web boundary: {bind_all_marker}"
        )
    if "tailscale funnel" in lowered_backend:
        failures.append("superseded Tailscale Funnel marker present in Web backend")
    for marker in ("cloudflared", "cloudflare tunnel"):
        if marker in lowered_backend and not wp22a_source_gate:
            failures.append(
                "external-access marker present without reviewed WP22A "
                f"source gate: {marker}"
            )


def _validate_api_surface(failures: list[str]) -> None:
    api_text = (WEB_BACKEND / "api_v1.py").read_text(encoding="utf-8")
    if "private_test_identity_enabled: bool = False" not in api_text:
        failures.append("private test identity must default disabled")
    if "_is_loopback_request" not in api_text:
        failures.append("private test identity must require loopback")
    safe_connection_block = api_text.split("def _safe_connection", 1)[-1].split(
        "async def _json_object",
        1,
    )[0]
    if "secret_ref" in safe_connection_block or "tenant_id" in safe_connection_block:
        failures.append(
            "browser connection response exposes secret or tenant scope internals"
        )


def _validate_historical_vault_surface(failures: list[str]) -> None:
    vault_text = (WEB_BACKEND / "broker_vault_v1.py").read_text(encoding="utf-8")
    if r"secrets\read-broker\connections" not in vault_text:
        failures.append("historical connection vault lost accepted read-broker root")
    if "_CRYPTPROTECT_LOCAL_MACHINE = 0x4" not in vault_text:
        failures.append(
            "historical connection vault lost DPAPI LocalMachine protection"
        )


def _validate_timeweb_runtime_surface(failures: list[str]) -> None:
    runtime_text = "\n".join(
        (API_ROOT / name).read_text(encoding="utf-8")
        for name in ("hosted_runtime.py", "hosted_app.py", "telegram_auth.py")
    )
    for forbidden in (
        "broker_vault_v1",
        "ReadBrokerConnectionVaultV1",
        r"C:\\ProgramData\\OmniCIO",
    ):
        if forbidden in runtime_text:
            failures.append(f"Timeweb runtime depends on local READ vault: {forbidden}")
    hosted_app = (API_ROOT / "hosted_app.py").read_text(encoding="utf-8")
    for marker in (
        "broker_mutation_disabled",
        "BROKER_CREDENTIALS_DISABLED_IN_HOSTED_RUNTIME",
    ):
        if marker not in hosted_app:
            failures.append(
                f"Timeweb broker mutation fail-closed marker missing: {marker}"
            )


def _validate_persistence_surface(failures: list[str]) -> None:
    migration_text = MIGRATION.read_text(encoding="utf-8").lower()
    if (
        "web_sessions" not in migration_text
        or "broker_connections" not in migration_text
    ):
        failures.append("WP17 persistence migration is incomplete")
    for marker in (" raw_token", " token text", "ciphertext bytea", "broker_token"):
        if marker in migration_text:
            failures.append(
                "PostgreSQL migration contains forbidden credential storage field: "
                f"{marker.strip()}"
            )


def _emit_result(failures: list[str], *, wp22a_source_gate: bool) -> int:
    if failures:
        print("V10 WP17 Web/security boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 WP17 Web/security boundary check passed.")
    print("Ordinary auth: Telegram only; local password absent")
    print("Sessions: server-side / private test identity disabled by default")
    print("Timeweb broker custody: fail-closed pending hosted backend")
    print("Timeweb WP17 gate: GitHub-hosted source-security audit; no OWNER laptop")
    print("Historical local READ-vault: DPAPI/ACL evidence preserved, non-blocking")
    if wp22a_source_gate:
        print(
            "External access: corrected WP22A source contract present / "
            "live activation not implied"
        )
    else:
        print("Public ingress: OFF / WP22A gated")
    return 0


def main() -> int:
    failures: list[str] = []
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WP17 contract unavailable: {type(exc).__name__}", file=sys.stderr)
        return 1
    if not isinstance(contract, dict):
        print("WP17 contract unavailable: invalid root object", file=sys.stderr)
        return 1

    wp22a_source_gate = _wp22a_source_gate_active(failures)
    _validate_login_and_public_activation(contract, failures)
    _validate_timeweb_broker_custody(contract, failures)
    _validate_historical_read_vault(contract, failures)
    _validate_invariants(contract, failures)
    _validate_browser_surface(failures)
    _validate_backend_surface(failures, wp22a_source_gate=wp22a_source_gate)
    _validate_api_surface(failures)
    _validate_historical_vault_surface(failures)
    _validate_timeweb_runtime_surface(failures)
    _validate_persistence_surface(failures)
    return _emit_result(failures, wp22a_source_gate=wp22a_source_gate)


if __name__ == "__main__":
    raise SystemExit(main())
