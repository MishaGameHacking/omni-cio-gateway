from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP17_APPLICATION_SHELL_CONTRACT.json"
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


def _text_tree(root: Path) -> str:
    parts: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".css"}:
            continue
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def main() -> int:
    failures: list[str] = []
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WP17 contract unavailable: {type(exc).__name__}", file=sys.stderr)
        return 1

    if contract.get("ordinary_login_providers") != ["telegram", "vk_id"]:
        failures.append("ordinary login providers drifted")
    if contract.get("local_password_allowed") is not False:
        failures.append("local password must remain disabled")
    if (
        contract.get("public_activation", {}).get("public_internet_ingress")
        is not False
    ):
        failures.append("public ingress must remain disabled in WP17")
    invariants = contract.get("invariants", {})
    if invariants.get("gateway_entrypoint") != "app:app":
        failures.append("gateway entrypoint drifted")
    if invariants.get("trading_methods") is not False:
        failures.append("trading_methods must remain false")
    if invariants.get("REAL_TRADING_ENABLED") is not False:
        failures.append("REAL_TRADING_ENABLED must remain false")
    if invariants.get("broker_write_authority_added") is not False:
        failures.append("WP17 may not add broker write authority")

    web_text = _text_tree(WEB_SHELL)
    backend_text = _text_tree(WEB_BACKEND) + "\n" + _text_tree(API_ROOT)
    forbidden_web = ("localStorage", "sessionStorage", "dangerouslySetInnerHTML")
    for marker in forbidden_web:
        if marker in web_text:
            failures.append(f"forbidden browser persistence/render primitive: {marker}")
    if "google" in web_text.lower():
        failures.append("Google login marker present in WP17 shell")
    if 'type="password"' not in web_text:
        failures.append("masked broker credential input is missing")

    forbidden_backend = (
        "broker_trading",
        "stop_orders",
        ".orders",
        "withdraw",
        "currency_transfer",
        "pay_in",
    )
    lowered_backend = backend_text.lower()
    for marker in forbidden_backend:
        if marker in lowered_backend:
            failures.append(
                f"broker write/transfer marker present in WP17 backend: {marker}"
            )
    bind_all_marker = ".".join(("0", "0", "0", "0"))
    for marker in (
        bind_all_marker,
        "cloudflared",
        "cloudflare tunnel",
        "tailscale funnel",
    ):
        if marker in lowered_backend:
            failures.append(
                f"public/external bind marker present before WP22A: {marker}"
            )

    api_text = (WEB_BACKEND / "api_v1.py").read_text(encoding="utf-8")
    if "private_test_identity_enabled: bool = False" not in api_text:
        failures.append("private test identity must default disabled")
    if "_is_loopback_request" not in api_text:
        failures.append("private test identity must require loopback")
    safe_connection_block = api_text.split("def _safe_connection", 1)[-1].split(
        "async def _json_object", 1
    )[0]
    if "secret_ref" in safe_connection_block or "tenant_id" in safe_connection_block:
        failures.append(
            "browser connection response exposes secret or tenant scope internals"
        )

    vault_text = (WEB_BACKEND / "broker_vault_v1.py").read_text(encoding="utf-8")
    if r"secrets\read-broker\connections" not in vault_text:
        failures.append("connection vault is not under accepted read-broker root")
    if "_CRYPTPROTECT_LOCAL_MACHINE = 0x4" not in vault_text:
        failures.append("connection vault must use DPAPI LocalMachine protection")

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

    if failures:
        print("V10 WP17 Web/security boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("V10 WP17 Web/security boundary check passed.")
    print("Ordinary auth: Telegram + VK ID only; local password absent")
    print("Sessions: server-side / private test identity disabled by default")
    print("Broker provisioning: WP8 read-broker connection child / no TRADE authority")
    print("Public ingress: OFF / WP22A gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
