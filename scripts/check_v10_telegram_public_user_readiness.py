from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
from typing import Any

if __package__:
    from .v10_jsonc import loads_jsonc
else:
    from v10_jsonc import loads_jsonc


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path(
    "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
)
LEDGER = Path("docs/updates/V10_CAPABILITY_ACTIVATION_TELEGRAM_LOGIN.md")
RUNBOOK = Path("docs/operations/V10_TELEGRAM_LOGIN_PRODUCTION_ACTIVATION_RUNBOOK.md")
TELEGRAM = Path("omni_cio/web/telegram_oidc_v1.py")
IDENTITY = Path("omni_cio/web/product_identity_v1.py")
TRANSACTION_MIGRATION = Path(
    "omni_cio/persistence/migrations/0005_browser_bound_provider_auth.sql"
)
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

_EXPECTED_REGISTRATION = {
    "owner_attested_in_accepted_pr_551": True,
    "allowed_origin_attested": True,
    "redirect_uri_attested": True,
    "provider_secret_values_recorded": False,
}

_EXPECTED_MINIMIZATION = {
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

_EXPECTED_CAPACITY = {
    **EXPECTED_LIMITS,
    "production_container_max_instances": 1,
    "production_container_instance_type": "lite",
    "automatic_capacity_expansion_authorized": False,
    "real_user_capacity_claim": False,
}

_EXPECTED_RELEASE_EVIDENCE = {
    "release_number": 84,
    "workflow_run": "35379210101",
    "source_sha": "66ef57dedd07ad68d472cb205da6bb8e87528e94",
    "conclusion": "success",
    "production_promotion": "success",
    "terminal_release_dag": "success",
    "rollback_required": False,
}

_REQUIRED_TRUE_OPERATIONS = (
    "workers_metrics_baseline_required",
    "healthz_release_acceptance_required",
    "rollback_path_required",
    "post_activation_provider_availability_evidence_required",
    "post_activation_real_user_isolation_evidence_required",
)

_REQUIRED_FALSE_OPERATIONS = (
    "stored_workers_logs_required_for_activation",
    "workers_tracing_required_for_activation",
    "paid_observability_expansion_authorized",
)

_EXPECTED_INVARIANTS = {
    "PUBLIC_MULTI_USER_ENABLED": False,
    "OMNI_V10_TELEGRAM_LOGIN_ENABLED": False,
    "OMNI_V10_VK_ID_LOGIN_ENABLED": False,
    "trading_methods": False,
    "REAL_TRADING_ENABLED": False,
    "broker_write": False,
    "gateway_entrypoint": "app:app",
}

_EXPECTED_SOURCE_FLAGS = {
    "PUBLIC_MULTI_USER_ENABLED": "false",
    "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "false",
    "OMNI_V10_VK_ID_LOGIN_ENABLED": "false",
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


def _require_equal(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise RuntimeError(code)


def _require_text_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    for marker in markers:
        if marker not in source:
            raise RuntimeError(code)


def _validate_contract_identity(contract: dict[str, Any]) -> None:
    _require_equal(
        contract.get("schema"),
        "omni-cio.v10.telegram-public-user-activation-readiness.v1",
        "TELEGRAM_PUBLIC_USER_READINESS_SCHEMA_INVALID",
    )
    _require_equal(
        contract.get("status"),
        "ENGINEERING_PRE_ACTIVATION_READY_EXTERNAL_SIGNOFF_REQUIRED",
        "TELEGRAM_PUBLIC_USER_READINESS_STATUS_INVALID",
    )
    _require_equal(
        contract.get("capability_id"),
        "telegram_login",
        "TELEGRAM_PUBLIC_USER_READINESS_CAPABILITY_INVALID",
    )
    _require_equal(
        contract.get("accepted_base_main_sha"),
        "66ef57dedd07ad68d472cb205da6bb8e87528e94",
        "TELEGRAM_PUBLIC_USER_READINESS_BASE_SHA_INVALID",
    )
    _require_equal(
        contract.get("canonical_origin"),
        "https://omnicio.ru",
        "TELEGRAM_PUBLIC_USER_READINESS_ORIGIN_INVALID",
    )
    _require_equal(
        contract.get("canonical_redirect_uri"),
        "https://omnicio.ru/api/v10/web/auth/telegram/callback",
        "TELEGRAM_PUBLIC_USER_READINESS_REDIRECT_INVALID",
    )
    _require_equal(
        contract.get("activation_allowed"),
        False,
        "TELEGRAM_PUBLIC_USER_READINESS_PREMATURE_ACTIVATION",
    )


def _validate_provider_registration(contract: dict[str, Any]) -> None:
    registration = _mapping(
        contract.get("provider_registration"),
        "TELEGRAM_PUBLIC_USER_READINESS_REGISTRATION_INVALID",
    )
    _require_equal(
        registration,
        _EXPECTED_REGISTRATION,
        "TELEGRAM_PUBLIC_USER_READINESS_REGISTRATION_INVALID",
    )


def _validate_provider_secret_readiness(contract: dict[str, Any]) -> None:
    readiness = _mapping(
        contract.get("provider_secret_readiness"),
        "TELEGRAM_PUBLIC_USER_READINESS_BINDINGS_INVALID",
    )
    _require_equal(
        readiness.get("accepted"),
        True,
        "TELEGRAM_PUBLIC_USER_READINESS_BINDINGS_INVALID",
    )
    _require_equal(
        readiness.get("workflow_run"),
        "35367055812",
        "TELEGRAM_PUBLIC_USER_READINESS_BINDINGS_INVALID",
    )
    _require_equal(
        readiness.get("marker"),
        (
            "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=READY "
            "production_bindings=4 staging_bindings=0"
        ),
        "TELEGRAM_PUBLIC_USER_READINESS_BINDINGS_INVALID",
    )


def _validate_data_minimization(contract: dict[str, Any]) -> None:
    minimization = _mapping(
        contract.get("data_minimization"),
        "TELEGRAM_PUBLIC_USER_READINESS_MINIMIZATION_INVALID",
    )
    _require_equal(
        minimization,
        _EXPECTED_MINIMIZATION,
        "TELEGRAM_PUBLIC_USER_READINESS_MINIMIZATION_INVALID",
    )


def _validate_capacity(contract: dict[str, Any]) -> None:
    capacity = _mapping(
        contract.get("capacity_and_abuse"),
        "TELEGRAM_PUBLIC_USER_READINESS_CAPACITY_INVALID",
    )
    _require_equal(
        capacity,
        _EXPECTED_CAPACITY,
        "TELEGRAM_PUBLIC_USER_READINESS_CAPACITY_INVALID",
    )


def _validate_operations(contract: dict[str, Any]) -> None:
    operations = _mapping(
        contract.get("operations"),
        "TELEGRAM_PUBLIC_USER_READINESS_OPERATIONS_INVALID",
    )
    evidence = _mapping(
        operations.get("exact_main_release_evidence"),
        "TELEGRAM_PUBLIC_USER_READINESS_RELEASE_EVIDENCE_INVALID",
    )
    _require_equal(
        evidence,
        _EXPECTED_RELEASE_EVIDENCE,
        "TELEGRAM_PUBLIC_USER_READINESS_RELEASE_EVIDENCE_INVALID",
    )
    for key in _REQUIRED_TRUE_OPERATIONS:
        _require_equal(
            operations.get(key),
            True,
            "TELEGRAM_PUBLIC_USER_READINESS_OPERATIONS_INVALID",
        )
    for key in _REQUIRED_FALSE_OPERATIONS:
        _require_equal(
            operations.get(key),
            False,
            "TELEGRAM_PUBLIC_USER_READINESS_OPERATIONS_INVALID",
        )


def _validate_legal_gate(contract: dict[str, Any]) -> None:
    legal = _mapping(
        contract.get("legal_privacy_gate"),
        "TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID",
    )
    _require_equal(
        legal.get("accepted"),
        False,
        "TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID",
    )
    _require_equal(
        legal.get("status"),
        "OWNER_OR_QUALIFIED_REVIEW_REQUIRED",
        "TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID",
    )
    required = legal.get("required_before_activation")
    if not isinstance(required, list):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID")
    if len(required) < 6:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID")
    if not all(isinstance(item, str) and item for item in required):
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID")
    _require_equal(
        legal.get("no_legal_conclusion_inferred_from_pseudonymization"),
        True,
        "TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID",
    )


def _validate_invariants(contract: dict[str, Any]) -> None:
    invariants = _mapping(
        contract.get("protected_invariants"),
        "TELEGRAM_PUBLIC_USER_READINESS_INVARIANTS_INVALID",
    )
    _require_equal(
        invariants,
        _EXPECTED_INVARIANTS,
        "TELEGRAM_PUBLIC_USER_READINESS_INVARIANTS_INVALID",
    )


def _validate_contract(contract: dict[str, Any]) -> None:
    _validate_contract_identity(contract)
    _validate_provider_registration(contract)
    _validate_provider_secret_readiness(contract)
    _validate_data_minimization(contract)
    _validate_capacity(contract)
    _validate_operations(contract)
    _validate_legal_gate(contract)
    _validate_invariants(contract)


def _parse_python(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise RuntimeError(
            "TELEGRAM_PUBLIC_USER_READINESS_LIMIT_SOURCE_INVALID"
        ) from exc


def _find_class(tree: ast.Module, class_name: str) -> ast.ClassDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(matches) != 1:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LIMIT_SOURCE_INVALID")
    return matches[0]


def _annotated_int_default(statement: ast.stmt) -> tuple[str, int] | None:
    if not isinstance(statement, ast.AnnAssign):
        return None
    if not isinstance(statement.target, ast.Name):
        return None
    value = statement.value
    if not isinstance(value, ast.Constant):
        return None
    if isinstance(value.value, bool) or not isinstance(value.value, int):
        return None
    return statement.target.id, value.value


def _class_defaults(source: str, class_name: str) -> dict[str, int]:
    class_node = _find_class(_parse_python(source), class_name)
    result: dict[str, int] = {}
    for statement in class_node.body:
        entry = _annotated_int_default(statement)
        if entry is not None:
            name, value = entry
            result[name] = value
    return result


def _validate_telegram_source(root: Path) -> None:
    telegram = _read(root, TELEGRAM)
    scopes = re.findall(r'"scope"\s*:\s*"([^"]+)"', telegram)
    _require_equal(
        scopes,
        ["openid"],
        "TELEGRAM_PUBLIC_USER_READINESS_SCOPE_DRIFT",
    )


def _validate_identity_source(root: Path) -> None:
    identity = _read(root, IDENTITY)
    _require_text_markers(
        identity,
        (
            "protected_identity_binding_hmac_sha256",
            "hmac.new(binding_key, payload, hashlib.sha256).hexdigest()",
            "PostgreSQL receives no raw Telegram/VK subject",
        ),
        "TELEGRAM_PUBLIC_USER_READINESS_IDENTITY_MINIMIZATION_DRIFT",
    )


def _validate_transaction_source(root: Path) -> None:
    migration = _read(root, TRANSACTION_MIGRATION)
    _require_text_markers(
        migration,
        (
            "state_sha256 char(64) PRIMARY KEY",
            "browser_proof_sha256 char(64) NOT NULL UNIQUE",
            "Raw provider state and the raw initiating-browser proof are never persisted.",
            "expires_at <= created_at + interval '15 minutes'",
        ),
        "TELEGRAM_PUBLIC_USER_READINESS_TRANSACTION_DRIFT",
    )


def _validate_rate_policy_source(root: Path) -> None:
    defaults = _class_defaults(_read(root, LIMITS), "RequestRatePolicyV1")
    for name, value in EXPECTED_LIMITS.items():
        _require_equal(
            defaults.get(name),
            value,
            "TELEGRAM_PUBLIC_USER_READINESS_RATE_POLICY_DRIFT",
        )


def _load_wrangler(root: Path) -> dict[str, Any]:
    try:
        value = loads_jsonc(_read(root, WRANGLER))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_WRANGLER_INVALID") from exc
    return _mapping(
        value,
        "TELEGRAM_PUBLIC_USER_READINESS_WRANGLER_INVALID",
    )


def _validate_activation_flags(wrangler: dict[str, Any]) -> None:
    production_vars = _mapping(
        wrangler.get("vars"),
        "TELEGRAM_PUBLIC_USER_READINESS_PRODUCTION_FLAG_DRIFT",
    )
    for name, value in _EXPECTED_SOURCE_FLAGS.items():
        _require_equal(
            production_vars.get(name),
            value,
            "TELEGRAM_PUBLIC_USER_READINESS_PRODUCTION_FLAG_DRIFT",
        )

    environments = _mapping(
        wrangler.get("env"),
        "TELEGRAM_PUBLIC_USER_READINESS_STAGING_FLAG_DRIFT",
    )
    staging = _mapping(
        environments.get("staging"),
        "TELEGRAM_PUBLIC_USER_READINESS_STAGING_FLAG_DRIFT",
    )
    staging_vars = _mapping(
        staging.get("vars"),
        "TELEGRAM_PUBLIC_USER_READINESS_STAGING_FLAG_DRIFT",
    )
    for name, value in _EXPECTED_SOURCE_FLAGS.items():
        _require_equal(
            staging_vars.get(name),
            value,
            "TELEGRAM_PUBLIC_USER_READINESS_STAGING_FLAG_DRIFT",
        )


def _validate_container_envelope(wrangler: dict[str, Any]) -> None:
    containers = wrangler.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_CONTAINER_ENVELOPE_DRIFT")
    container = _mapping(
        containers[0],
        "TELEGRAM_PUBLIC_USER_READINESS_CONTAINER_ENVELOPE_DRIFT",
    )
    _require_equal(
        container.get("max_instances"),
        1,
        "TELEGRAM_PUBLIC_USER_READINESS_CONTAINER_ENVELOPE_DRIFT",
    )
    _require_equal(
        container.get("instance_type"),
        "lite",
        "TELEGRAM_PUBLIC_USER_READINESS_CONTAINER_ENVELOPE_DRIFT",
    )


def _validate_wrangler_source(root: Path) -> None:
    wrangler = _load_wrangler(root)
    _validate_activation_flags(wrangler)
    _validate_container_envelope(wrangler)


def _validate_ledger_source(root: Path) -> None:
    ledger = _read(root, LEDGER)
    _require_text_markers(
        ledger,
        (
            "Current accepted capability state: `BLOCKED_EXTERNAL`",
            "Public-user legal/operator/privacy-notice sign-off",
        ),
        "TELEGRAM_PUBLIC_USER_READINESS_LEDGER_STATE_INVALID",
    )
    if "TO: LIVE_OPERABLE\nDECISION: ACCEPTED" in ledger:
        raise RuntimeError("TELEGRAM_PUBLIC_USER_READINESS_LEDGER_PREMATURE_ACCEPTANCE")


def _validate_runbook_source(root: Path) -> None:
    runbook = _read(root, RUNBOOK)
    _require_text_markers(
        runbook,
        (
            "OWNER attestation already preserved in merged PR #551",
            "repository pre-activation readiness contract passes",
            "public-user legal/operator/privacy-notice sign-off",
        ),
        "TELEGRAM_PUBLIC_USER_READINESS_RUNBOOK_DRIFT",
    )


def _validate_sources(root: Path) -> None:
    _validate_telegram_source(root)
    _validate_identity_source(root)
    _validate_transaction_source(root)
    _validate_rate_policy_source(root)
    _validate_wrangler_source(root)
    _validate_ledger_source(root)
    _validate_runbook_source(root)


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
    print(
        "V10 Telegram public-user pre-activation readiness contract passed; "
        "external legal gate remains fail-closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
