from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json"
RUNBOOK = ROOT / "docs" / "operations" / "V10_WP15_OWNER_LIVE_READ_RUNBOOK.md"
SERVICE = ROOT / "omni_cio" / "web" / "live_acceptance_v1.py"
API = ROOT / "omni_cio" / "web" / "api_v1.py"
LOCAL_APP = ROOT / "apps" / "api" / "app.py"
WEB_SHELL = ROOT / "apps" / "web" / "src" / "app-shell"
PROVISIONER = ROOT / "infrastructure" / "windows" / "provision_wp15_live_web_acceptance.ps1"
LAUNCHER = ROOT / "infrastructure" / "windows" / "run_wp15_live_web_runtime.ps1"
DB_BOOTSTRAP = ROOT / "infrastructure" / "windows" / "bootstrap_wp15_live_database.py"
FINALIZER = ROOT / "infrastructure" / "windows" / "finalize_wp15_live_web_evidence.ps1"
AUDITOR = ROOT / "infrastructure" / "windows" / "audit_wp15_live_web_runner.ps1"
SUPPORT_WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp15-live-web-support-audit.yml"
OWNER_WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp15-live-web-owner-audit.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    required_paths = (
        CONTRACT,
        RUNBOOK,
        SERVICE,
        API,
        LOCAL_APP,
        PROVISIONER,
        LAUNCHER,
        DB_BOOTSTRAP,
        FINALIZER,
        AUDITOR,
        SUPPORT_WORKFLOW,
        OWNER_WORKFLOW,
    )
    for path in required_paths:
        if not path.is_file():
            failures.append(f"required live-acceptance component missing: {path.relative_to(ROOT)}")
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    try:
        contract = json.loads(_read(CONTRACT))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WP15 live contract unavailable: {type(exc).__name__}", file=sys.stderr)
        return 1

    scope = contract.get("scope", {})
    _require(scope.get("acceptance_only") is True, "support path must remain acceptance-only", failures)
    _require(scope.get("portfolio_dashboard_feature_work") is False, "WP18 feature work must remain false", failures)
    _require(scope.get("public_ingress") is False, "public ingress must remain disabled", failures)
    _require(scope.get("public_multi_user") is False, "public multi-user activation must remain disabled", failures)
    _require(scope.get("loopback_bind") == "127.0.0.1", "live runtime must bind exact loopback", failures)

    broker = contract.get("broker", {})
    _require(broker.get("credential_role") == "READ", "credential role drifted from READ", failures)
    _require(broker.get("required_account_access_level") == "READ_ONLY", "broker authority drifted from READ_ONLY", failures)
    for key in ("full_access_fallback", "trade_credential_allowed", "write_authority_added", "transfer_withdrawal_authority"):
        _require(broker.get(key) is False, f"broker authority must remain disabled: {key}", failures)

    challenge = contract.get("private_browser_challenge", {})
    _require(challenge.get("durable") is False, "private browser challenge must not be durable", failures)
    _require(challenge.get("cache_control") == "no-store", "private browser challenge must be no-store", failures)
    _require(challenge.get("ttl_seconds") == 600, "reviewed live challenge TTL drifted", failures)
    _require(challenge.get("maximum_ttl_seconds") <= 1800, "live challenge maximum TTL widened", failures)

    owner = contract.get("owner_confirmation", {})
    _require(owner.get("all_must_be_true") is True, "OWNER parity confirmations must all be true", failures)
    _require(owner.get("synthetic_substitution_allowed") is False, "synthetic OWNER evidence must remain forbidden", failures)

    pending = contract.get("pending_evidence", {})
    _require(pending.get("runner_can_read") is False, "runner must not read pending private boundary", failures)
    _require(pending.get("runner_can_write") is False, "runner must not write pending private boundary", failures)
    _require(pending.get("contains_private_values") is False, "pending durable evidence may not contain private values", failures)
    _require(pending.get("contains_raw_secret") is False, "pending durable evidence may not contain raw secret", failures)

    final = contract.get("final_evidence", {})
    _require(final.get("runtime_write_allowed") is False, "runtime must not write final evidence", failures)
    _require(final.get("runner_write_allowed") is False, "runner must not write final evidence", failures)
    _require(final.get("implementation_sha_required") is True, "final evidence must bind implementation SHA", failures)
    _require(final.get("script_hash_binding_required") is True, "final evidence must bind script hashes", failures)
    required_forbidden = {
        "token",
        "secret",
        "ciphertext",
        "broker_account_id",
        "account_fingerprint",
        "portfolio_total",
        "quantity",
        "unit_price",
        "market_value",
        "private_portfolio_payload",
    }
    _require(required_forbidden.issubset(set(final.get("forbidden_fields", []))), "final evidence forbidden-field set was weakened", failures)

    windows_runtime = contract.get("windows_runtime", {})
    _require(windows_runtime.get("principal") == "omni-cio-runtime", "runtime principal drifted", failures)
    _require(windows_runtime.get("administrator_allowed") is False, "runtime administrator authority forbidden", failures)
    _require(windows_runtime.get("task_logon") == "PASSWORD", "temporary task logon contract drifted", failures)
    _require(windows_runtime.get("s4u_allowed") is False, "S4U must remain disabled for network/DPAPI acceptance runtime", failures)
    _require(windows_runtime.get("permanent_wp9_web_slot_modified") is False, "permanent WP9 task must remain untouched", failures)

    postgres = contract.get("postgresql", {})
    _require(postgres.get("major") == 18, "PostgreSQL major drifted", failures)
    _require(postgres.get("database") == "omni_cio_v10", "PostgreSQL database drifted", failures)
    _require(postgres.get("role") == "omni_cio_runtime", "PostgreSQL runtime role drifted", failures)
    _require(postgres.get("host") == "127.0.0.1", "PostgreSQL host must remain loopback", failures)
    _require(postgres.get("authentication") == "SSPI", "PostgreSQL auth must remain SSPI", failures)
    _require(postgres.get("trust_allowed") is False, "PostgreSQL trust auth must remain forbidden", failures)
    _require(postgres.get("database_password_persisted") is False, "database password persistence forbidden", failures)
    _require(postgres.get("runtime_ddl_authority") is False, "runtime must not receive migration/DDL authority", failures)
    _require(postgres.get("sspi_include_realm") is True, "SSPI realm must remain included", failures)
    _require(postgres.get("sspi_compat_realm") is True, "SSPI SAM-compatible realm must remain explicit", failures)
    _require(postgres.get("sspi_upn_username") is False, "SSPI username must remain SAM-compatible", failures)
    _require(postgres.get("principal_mapping_form") == "SAM_USERNAME@SAM_REALM", "SSPI principal mapping form drifted", failures)

    exit_gate = contract.get("exit_gate", {})
    for key in (
        "code_security_ci_before_owner_action",
        "support_pr_merged_and_post_merge_regression_green_before_real_token",
        "owner_live_evidence_required",
        "independent_non_admin_runner_audit_required",
    ):
        _require(exit_gate.get(key) is True, f"Exit Gate requirement disabled: {key}", failures)
    _require(exit_gate.get("block_d_credit_before_live_evidence") is False, "Block D credit may not precede live evidence", failures)
    _require(exit_gate.get("wp18_unlock_before_live_evidence") is False, "WP18 may not unlock before live evidence", failures)

    invariants = contract.get("invariants", {})
    _require(invariants.get("gateway_entrypoint") == "app:app", "gateway entrypoint drifted", failures)
    _require(invariants.get("trading_methods") is False, "trading_methods must remain false", failures)
    _require(invariants.get("real_trading_enabled") is False, "REAL_TRADING_ENABLED must remain false", failures)
    _require(invariants.get("broker_write_authority_added") is False, "broker write authority must remain false", failures)
    _require(invariants.get("protected_v9_rollback") is True, "protected V9 rollback must remain true", failures)

    service_text = _read(SERVICE)
    _require("TInvestConnectionReadAdapter" in service_text, "live service must reuse connection-scoped WP15 adapter", failures)
    _require("def load(self, *, secret_ref: str) -> str" in service_text, "live vault protocol must match keyword-only accepted vault API", failures)
    _require("self._vault.load(secret_ref=record.secret_ref)" in service_text, "live service must load only the selected BrokerConnection secret ref", failures)
    _require("read_snapshot(allow_partial=False)" in service_text, "live snapshot must fail closed on partial data", failures)
    _require("ACCOUNT_ACCESS_LEVEL_READ_ONLY" in service_text, "live service must enforce broker READ_ONLY authority", failures)
    payload = service_text.split("payload: dict[str, Any] = {", 1)[-1].split("self._evidence_writer.write(payload)", 1)[0]
    for key in ("portfolio_total\"", "quantity\"", "unit_price\"", "market_value\"", "masked_account\""):
        if key in payload:
            failures.append(f"durable pending evidence contains private-value field: {key[:-2]}")

    api_text = _read(API)
    _require("def _require_live_acceptance" in api_text and "_is_loopback_request(request)" in api_text, "live API must fail closed outside loopback", failures)
    _require(api_text.count('headers={"Cache-Control": "no-store"}') >= 2, "live API private responses must be no-store", failures)

    app_text = _read(LOCAL_APP)
    _require("WP15_LIVE_REQUIRES_PRIVATE_ACCEPTANCE" in app_text, "live app must require private acceptance mode", failures)
    _require("def _verify_live_database" in app_text and "current_migration_state" in app_text, "runtime must verify migrations without DDL authority", failures)

    web_text = "\n".join(_read(path) for path in sorted(WEB_SHELL.rglob("*.ts*")))
    for marker in ("localStorage", "sessionStorage", "dangerouslySetInnerHTML"):
        if marker in web_text:
            failures.append(f"forbidden browser primitive present: {marker}")
    _require('type="password"' in web_text, "broker token input must remain masked", failures)
    _require("WP15 deferred live acceptance" in web_text, "acceptance-only UI marker missing", failures)

    provisioner_text = _read(PROVISIONER)
    lowered_provisioner = provisioner_text.lower()
    normalized_provisioner = lowered_provisioner.replace("-", "")
    _require("convertntaccounttosspiprincipal" in normalized_provisioner, "SSPI principal conversion helper missing", failures)
    for marker in ("include_realm=1", "compat_realm=1", "upn_username=0", "map=omni_cio_runtime_map"):
        _require(marker in provisioner_text, f"explicit SSPI mapping option missing: {marker}", failures)
    _require('postgres_trust_used = $false' in provisioner_text, "provisioning evidence must assert PostgreSQL trust was not used", failures)
    _require("OmniCIO.V10.WP15LiveAcceptance" in provisioner_text, "temporary task identity missing", failures)
    _require("-RunLevel Limited" in provisioner_text, "temporary runtime task must remain non-elevated", failures)

    launcher_text = _read(LAUNCHER)
    _require("--host 127.0.0.1" in launcher_text, "uvicorn live runtime must bind loopback", failures)
    _require('$env:PGREQUIREAUTH = "sspi"' in launcher_text, "runtime must require SSPI", failures)
    _require("Test-Administrator" in launcher_text, "runtime must reject administrator identity", failures)

    combined_runtime = (service_text + "\n" + api_text + "\n" + app_text).lower()
    for marker in ("client.orders", "stop_orders", "withdraw", "currency_transfer", "pay_in"):
        if marker in combined_runtime:
            failures.append(f"broker write/transfer surface present in live runtime: {marker}")

    if failures:
        print("V10 WP15 live Web acceptance boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 WP15 live Web acceptance boundary check passed.")
    print("Scope: acceptance-only / loopback / WP18 locked")
    print("Broker: T-Invest READ_ONLY / exact BrokerConnection binding / no write authority")
    print("Evidence: private browser challenge -> sanitized exact-head OWNER evidence")
    print("Runtime: temporary non-admin Windows task / PostgreSQL SSPI / no trust or DB password")
    print("Independent final gate: non-admin runner audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
