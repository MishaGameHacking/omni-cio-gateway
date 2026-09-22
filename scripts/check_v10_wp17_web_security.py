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
RUNNER_READ_VAULT_AUDITOR = (
    ROOT / "infrastructure" / "windows" / "audit_wp17_read_vault_runner.ps1"
)
OWNER_READ_VAULT_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp17-owner-read-vault-audit.yml"
)


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

    # WP17 only needs proof that a reviewed corrected WP22A source contract owns
    # the already-accepted external-access markers. The contract lifecycle may
    # advance from planning hold to current implementation without changing the
    # durable public/no-home/source-gate semantics. live ingress or provider
    # activation is never inferred from source-marker presence.
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


def _validate_read_vault_acceptance(
    contract: dict[str, Any],
    failures: list[str],
) -> None:
    read_vault_acceptance = contract.get("read_vault_acceptance", {})
    if not isinstance(read_vault_acceptance, dict):
        failures.append("READ-vault acceptance contract must be an object")
        return

    for key in (
        "owner_admin_verify_required",
        "exact_head_binding_required",
        "script_hash_binding_required",
        "non_admin_runner_negative_probe_required",
    ):
        if read_vault_acceptance.get(key) is not True:
            failures.append(f"READ-vault acceptance requirement disabled: {key}")
    for key in (
        "runner_payload_read_allowed",
        "runner_payload_write_allowed",
        "runner_evidence_write_allowed",
    ):
        if read_vault_acceptance.get(key) is not False:
            failures.append(f"READ-vault runner authority must remain denied: {key}")
    for component in (
        OWNER_EVIDENCE_FINALIZER,
        RUNNER_READ_VAULT_AUDITOR,
        OWNER_READ_VAULT_WORKFLOW,
    ):
        if not component.is_file():
            failures.append(
                f"READ-vault acceptance component missing: {component.name}"
            )


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


def _validate_vault_surface(failures: list[str]) -> None:
    vault_text = (WEB_BACKEND / "broker_vault_v1.py").read_text(encoding="utf-8")
    if r"secrets\read-broker\connections" not in vault_text:
        failures.append("connection vault is not under accepted read-broker root")
    if "_CRYPTPROTECT_LOCAL_MACHINE = 0x4" not in vault_text:
        failures.append("connection vault must use DPAPI LocalMachine protection")


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
                "PostgreSQL migration contains forbidden secret storage field: "
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
    print("Broker provisioning: WP8 read-broker connection child / no TRADE authority")
    print("READ-vault acceptance: exact-head OWNER evidence + non-admin runner probe")
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
    _validate_read_vault_acceptance(contract, failures)
    _validate_invariants(contract, failures)
    _validate_browser_surface(failures)
    _validate_backend_surface(failures, wp22a_source_gate=wp22a_source_gate)
    _validate_api_surface(failures)
    _validate_vault_surface(failures)
    _validate_persistence_surface(failures)
    return _emit_result(failures, wp22a_source_gate=wp22a_source_gate)


if __name__ == "__main__":
    raise SystemExit(main())
