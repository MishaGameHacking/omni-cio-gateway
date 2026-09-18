from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
from typing import Any

from scripts.v10_jsonc import loads_jsonc


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json")
LEDGER = Path("docs/updates/V10_CAPABILITY_ACTIVATION_TELEGRAM_LOGIN.md")
RUNBOOK = Path("docs/operations/V10_TELEGRAM_LOGIN_PRODUCTION_ACTIVATION_RUNBOOK.md")
TELEGRAM = Path("omni_cio/web/telegram_oidc_v1.py")
IDENTITY = Path("omni_cio/web/product_identity_v1.py")
TRANSACTION_MIGRATION = Path("omni_cio/persistence/migrations/0005_browser_bound_provider_auth.sql")
LIMITS = Path("omni_cio/web/request_limits_v1.py")
WRANGLER = Path("wrangler.jsonc")

EXPECTED_LIMITS = {
    "window_seconds": 60,
    "global_api_requests": 5000,
    "health_requests": 120,
    "anonymous_requests": 300,
    "authenticated_session_requests": 600,
    "provider_starts": 60,
    "provider_callbacks": 120,
    "outbound_provider_concurrency": 8,
    "max_session_keys": 4096,
    "retry_after_seconds": 1,
}


def _read(root: Path, relative: Path) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_SOURCE_UNREADABLE") from exc


def _load_contract(root: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(root, CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_CONTRACT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_CONTRACT_INVALID")
    return value


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema") != "omni-cio.v10.telegram-public-user-activation-readiness.v1":
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_SCHEMA_INVALID")
    if contract.get("status") != "ENGINEERING_PRE_ACTIVATION_READY_EXTERNAL_SIGNOFF_REQUIRED":
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_STATUS_INVALID")
    if contract.get("capability_id") != "telegram_login":
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_CAPABILITY_INVALID")
    if contract.get("canonical_origin") != "https://omnicio.ru":
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_ORIGIN_INVALID")
    if contract.get("canonical_redirect_uri") != "https://omnicio.ru/api/v10/web/auth/telegram/callback":
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_REDIRECT_INVALID")
    if contract.get("activation_allowed") is not False:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_PREMATURE_ACTIVATION")

    registration = _mapping(contract.get("provider_registration"), "TELEGRAM_PUBLIC_USER_READINESS_REGISTRATION_INVALID")
    if registration != {
        "owner_attested_in_accepted_pr_551": True,
        "allowed_origin_attested": True,
        "redirect_uri_attested": True,
        "provider_secret_values_recorded": False,
    }:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_REGISTRATION_INVALID")

    readiness = _mapping(contract.get("provider_secret_readiness"), "TELEGRAM_PUBLIC_USER_READINESS_BINDINGS_INVALID")
    if (
        readiness.get("accepted") is not True
        or readiness.get("workflow_run") != "35367055812"
        or readiness.get("marker")
        != "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=READY production_bindings=4 staging_bindings=0"
    ):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_BINDINGS_INVALID")

    minimization = _mapping(contract.get("data_minimization"), "TELEGRAM_PUBLIC_USER_READINESS_MINIMIZATION_INVALID")
    expected_minimization = {
        "telegram_oidc_scopes": ["openid"],
        "profile_scope_requested": False,
        "phone_scope_requested": False,
        "raw_telegram_subject_persisted": False,
        "external_identity_binding": "HMAC_SHA256_KEYED",
        "raw_oauth_state_persisted": False,
        "raw_browser_proof_persisted": False,
        "provider_auth_transaction_max_minutes": 15,
        "session_authority": "SERVER_SIDE_OPAQUE_TOKEN_SHA256",
    }
    if minimization != expected_minimization:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_MINIMIZATION_INVALID")

    capacity = _mapping(contract.get("capacity_and_abuse"), "TELEGRAM_PUBLIC_USER_READINESS_CAPACITY_INVALID")
    expected_capacity = {
        **EXPECTED_LIMITS,
        "production_container_max_instances": 1,
        "production_container_instance_type": "lite",
        "automatic_capacity_expansion_authorized": False,
        "real_user_capacity_claim": False,
    }
    if capacity != expected_capacity:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_CAPACITY_INVALID")

    operations = _mapping(contract.get("operations"), "TELEGRAM_PUBLIC_USER_READINESS_OPERATIONS_INVALID")
    evidence = _mapping(operations.get("exact_main_release_evidence"), "TELEGRAM_PUBLIC_USER_READINESS_RELEASE_EVIDENCE_INVALID")
    if evidence != {
        "release_number": 84,
        "workflow_run": "35379210101",
        "source_sha": "66ef57dedd07ad68d472cb205da6bb8e87528e94",
        "conclusion": "success",
        "production_promotion": "success",
        "terminal_release_dag": "success",
        "rollback_required": False,
    }:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_RELEASE_EVIDENCE_INVALID")
    for key in (
        "workers_metrics_baseline_required",
        "healthz_release_acceptance_required",
        "rollback_path_required",
        "post_activation_provider_availability_evidence_required",
        "post_activation_real_user_isolation_evidence_required",
    ):
        if operations.get(key) is not True:
            raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_OPERATIONS_INVALID")
    for key in (
        "stored_workers_logs_required_for_activation",
        "workers_tracing_required_for_activation",
        "paid_observability_expansion_authorized",
    ):
        if operations.get(key) is not False:
            raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_OPERATIONS_INVALID")

    legal = _mapping(contract.get("legal_privacy_gate"), "TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID")
    if legal.get("accepted") is not False or legal.get("status") != "OWNER_OR_QUALIFIED_REVIEW_REQUIRED":
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID")
    required = legal.get("required_before_activation")
    if not isinstance(required, list) or len(required) < 6 or not all(isinstance(item, str) and item for item in required):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID")
    if legal.get("no_legal_conclusion_inferred_from_pseudonymization") is not True:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID")

    invariants = _mapping(contract.get("protected_invariants"), "TELEGRAM_PUBLIC_USER_READINESS_INVARIANTS_INVALID")
    if invariants != {
        "PUBLIC_MULTI_USER_ENABLED": False,
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED": False,
        "OMNI_V10_VK_ID_LOGIN_ENABLED": False,
        "trading_methods": False,
        "REAL_TRADING_ENABLED": False,
        "broker_write": False,
        "gateway_entrypoint": "app:app",
    }:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_INVARIANTS_INVALID")


def _class_defaults(source: str, class_name: str) -> dict[str, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LIMIT_SOURCE_INVALID") from exc
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            result: dict[str, int] = {}
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, int):
                    result[statement.target.id] = statement.value.value
            return result
    raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LIMIT_SOURCE_INVALID")


def _validate_sources(root: Path) -> None:
    telegram = _read(root, TELEGRAM)
    scopes = re.findall(r'"scope"\s*:\s*"([^"]+)"', telegram)
    if scopes != ["openid"]:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_SCOPE_DRIFT")

    identity = _read(root, IDENTITY)
    for marker in (
        "protected_identity_binding_hmac_sha256",
        "hmac.new(binding_key, payload, hashlib.sha256).hexdigest()",
        "PostgreSQL receives no raw Telegram/VK subject",
    ):
        if marker not in identity:
            raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_IDENTITY_MINIMIZATION_DRIFT")

    migration = _read(root, TRANSACTION_MIGRATION)
    for marker in (
        "state_sha256 char(64) PRIMARY KEY",
        "browser_proof_sha256 char(64) NOT NULL UNIQUE",
        "Raw provider state and the raw initiating-browser proof are never persisted.",
        "expires_at <= created_at + interval '15 minutes'",
    ):
        if marker not in migration:
            raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_TRANSACTION_DRIFT")

    defaults = _class_defaults(_read(root, LIMITS), "RequestRatePolicyV1")
    if any(defaults.get(name) != value for name, value in EXPECTED_LIMITS.items()):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_RATE_POLICY_DRIFT")

    try:
        wrangler = loads_jsonc(_read(root, WRANGLER))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_WRANGLER_INVALID") from exc
    if not isinstance(wrangler, dict):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_WRANGLER_INVALID")
    expected_flags = {
        "PUBLIC_MULTI_USER_ENABLED": "false",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "false",
        "OMNI_V10_VK_ID_LOGIN_ENABLED": "false",
    }
    if wrangler.get("vars", {}) | {} and any(wrangler.get("vars", {}).get(k) != v for k, v in expected_flags.items()):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_PRODUCTION_FLAG_DRIFT")
    staging = wrangler.get("env", {}).get("staging", {})
    if any(staging.get("vars", {}).get(k) != v for k, v in expected_flags.items()):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_STAGING_FLAG_DRIFT")
    containers = wrangler.get("containers")
    if (
        not isinstance(containers, list)
        or len(containers) != 1
        or not isinstance(containers[0], dict)
        or containers[0].get("max_instances") != 1
        or containers[0].get("instance_type") != "lite"
    ):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_CONTAINER_ENVELOPE_DRIFT")

    ledger = _read(root, LEDGER)
    if "Current accepted capability state: `BLOCKED_EXTERNAL`" not in ledger:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEDGER_STATE_INVALID")
    if "Public-user legal/operator/privacy-notice sign-off" not in ledger:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEDGER_LEGAL_GATE_MISSING")
    if "TO: LIVE_OPERABLE\nDECISION: ACCEPTED" in ledger:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEDGER_PREMATURE_ACCEPTANCE")

    runbook = _read(root, RUNBOOK)
    for marker in (
        "OWNER attestation already preserved in merged PR #551",
        "repository pre-activation readiness contract passes",
        "public-user legal/operator/privacy-notice sign-off",
    ):
        if marker not in runbook:
            raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_RUNBOOK_DRIFT")


def validate(root: Path = ROOT) -> None:
    contract = _load_contract(root)
    _validate_contract(contract)
    _validate_sources(root)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Telegram public-user pre-activation readiness contract passed; external legal gate remains fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
