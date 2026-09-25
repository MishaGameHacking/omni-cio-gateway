from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path(
    "docs/architecture/V10_TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION_CONTRACT.json"
)
CONTROLLER_RELATIVE = Path("scripts/timeweb_telegram_public_activation.py")
WORKFLOW_RELATIVE = Path(".github/workflows/v10-timeweb-telegram-public-activation.yml")
RUNBOOK_RELATIVE = Path(
    "docs/operations/V10_TELEGRAM_LOGIN_PRODUCTION_ACTIVATION_RUNBOOK.md"
)
READINESS_RELATIVE = Path(
    "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
)
AUTH_RUNTIME_RELATIVE = Path("apps/api/telegram_auth.py")
FULL_DELIVERY_RELATIVE = Path(
    "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
)

_EXPECTED_SCHEMA = "omni-cio.v10.timeweb-telegram-public-activation.v1"
_EXPECTED_ORIGIN = "https://omnicio.ru"
_EXPECTED_CALLBACK = "https://omnicio.ru/api/v10/web/auth/telegram/callback"
_REQUIRED_CREDENTIAL_NAMES = {
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID",
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET",
    "OMNI_V10_IDENTITY_BINDING_KEY_HEX",
    "OMNI_V10_CSRF_BINDING_KEY_HEX",
}
_FORBIDDEN_WORKFLOW_MARKERS = (
    "permissions: write-all",
    "continue-on-error: true",
    "sslverify false",
    "ssl_verify=false",
    "cert_none",
    "_create_unverified_context",
    "secrets.",
    "secrets[",
)
_FORBIDDEN_CONTROLLER_MARKERS = (
    "deploy_once(",
    'method="post"',
    "ssl._create_unverified_context",
    "ssl.cert_none",
)


def _read(root: Path, relative: Path) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            f"TIMEWEB_TELEGRAM_ACTIVATION_SOURCE_UNREADABLE:{relative.as_posix()}"
        ) from exc


def _json(root: Path, relative: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(root, relative))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_JSON_INVALID")
    return value


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _validate_contract(root: Path) -> None:
    contract = _json(root, CONTRACT_RELATIVE)
    expected_scalars = {
        "schema": _EXPECTED_SCHEMA,
        "status": "OWNER_APPROVED_BRANCH_LOCAL_IMPLEMENTATION_VERIFICATION_PENDING",
        "owning_pr": 584,
        "milestone": "P5_TELEGRAM_PUBLIC_ACTIVATION",
        "canonical_origin": _EXPECTED_ORIGIN,
        "canonical_redirect_uri": _EXPECTED_CALLBACK,
    }
    for key, expected in expected_scalars.items():
        if contract.get(key) != expected:
            raise RuntimeError(f"TIMEWEB_TELEGRAM_ACTIVATION_CONTRACT_DRIFT:{key}")

    activation = _mapping(
        contract.get("activation"),
        "TIMEWEB_TELEGRAM_ACTIVATION_CONTRACT_INVALID",
    )
    expected_activation = {
        "public_multi_user_flag": "PUBLIC_MULTI_USER_ENABLED",
        "telegram_login_flag": "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "vk_login_flag": "OMNI_V10_VK_ID_LOGIN_ENABLED",
        "preactivation_public_multi_user": False,
        "preactivation_telegram_login": False,
        "accepted_public_multi_user": True,
        "accepted_telegram_login": True,
        "vk_login_must_remain_false": True,
        "pair_transition_required": True,
        "provider_side_mutation_by_controller_allowed": False,
        "source_hardcoded_true_allowed": False,
    }
    if activation != expected_activation:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_ACTIVATION_DRIFT")

    credentials = _mapping(
        contract.get("runtime_credentials"),
        "TIMEWEB_TELEGRAM_ACTIVATION_CREDENTIAL_POLICY_INVALID",
    )
    names = credentials.get("required_names")
    if not isinstance(names, list) or set(names) != _REQUIRED_CREDENTIAL_NAMES:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_CREDENTIAL_POLICY_INVALID")
    if credentials.get("values_in_repository_allowed") is not False:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_CREDENTIAL_POLICY_INVALID")
    if credentials.get("sanitized_runtime_probe_required") is not True:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_CREDENTIAL_POLICY_INVALID")

    phases = contract.get("operations")
    if phases != ["observe", "ready", "accept"]:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_OPERATIONS_INVALID")
    if contract.get("readiness_evidence_seal_required") is not True:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_SEAL_POLICY_INVALID")
    if contract.get("provider_api_required") is not False:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_PROVIDER_API_POLICY_INVALID")


def _validate_controller(root: Path) -> None:
    source = _read(root, CONTROLLER_RELATIVE)
    required = (
        "READY_TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION",
        "ACCEPT_TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION",
        "readiness_seal",
        "PREACTIVATION_READY",
        "TELEGRAM_LIVE",
        "/api/v10/web/auth/providers",
        "PUBLIC_MULTI_USER_DISABLED",
        "LIVE_OPERABLE",
        "hashlib.sha256",
    )
    for marker in required:
        if marker not in source:
            raise RuntimeError(
                f"TIMEWEB_TELEGRAM_ACTIVATION_CONTROLLER_MARKER_MISSING:{marker}"
            )
    lowered = source.casefold()
    for marker in _FORBIDDEN_CONTROLLER_MARKERS:
        if marker in lowered:
            raise RuntimeError(
                "TIMEWEB_TELEGRAM_ACTIVATION_CONTROLLER_MUTATION_FORBIDDEN"
            )


def _validate_workflow(root: Path) -> None:
    source = _read(root, WORKFLOW_RELATIVE)
    lowered = source.casefold()
    required = (
        "workflow_dispatch:",
        "environment: timeweb-production",
        "contents: read",
        "expected_main_sha",
        "external_readiness_evidence_sha256",
        "readiness_sha256",
        "live_acceptance_evidence_sha256",
        "python -m scripts.check_v10_timeweb_telegram_public_activation",
        "python -m scripts.timeweb_telegram_public_activation",
    )
    for marker in required:
        if marker.casefold() not in lowered:
            raise RuntimeError(
                f"TIMEWEB_TELEGRAM_ACTIVATION_WORKFLOW_MARKER_MISSING:{marker}"
            )
    for marker in _FORBIDDEN_WORKFLOW_MARKERS:
        if marker in lowered:
            raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_WORKFLOW_UNSAFE")
    if source.count("type: string") + source.count("type: choice") > 10:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_WORKFLOW_INPUT_LIMIT")


def _validate_composition(root: Path) -> None:
    auth_source = _read(root, AUTH_RUNTIME_RELATIVE)
    for marker in (
        "TELEGRAM_AUTH_ACTIVATION_FLAGS_MISMATCH",
        "if public_enabled != login_enabled:",
        "allowed_providers=(IdentityProviderV1.TELEGRAM,)",
    ):
        if marker not in auth_source:
            raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_AUTH_RUNTIME_DRIFT")

    readiness = _json(root, READINESS_RELATIVE)
    if readiness.get("activation_allowed") is not False:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_PREMATURE_SOURCE_ACTIVATION")
    if readiness.get("canonical_origin") != _EXPECTED_ORIGIN:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_READINESS_ORIGIN_DRIFT")
    if readiness.get("canonical_redirect_uri") != _EXPECTED_CALLBACK:
        raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_READINESS_CALLBACK_DRIFT")

    full_delivery = _json(root, FULL_DELIVERY_RELATIVE)
    telegram = _mapping(
        full_delivery.get("telegram"),
        "TIMEWEB_TELEGRAM_ACTIVATION_FULL_DELIVERY_DRIFT",
    )
    expected_paths = {
        "activation_contract": CONTRACT_RELATIVE.as_posix(),
        "activation_controller": CONTROLLER_RELATIVE.as_posix(),
        "activation_workflow": WORKFLOW_RELATIVE.as_posix(),
        "activation_runbook": RUNBOOK_RELATIVE.as_posix(),
    }
    for key, expected in expected_paths.items():
        if telegram.get(key) != expected:
            raise RuntimeError("TIMEWEB_TELEGRAM_ACTIVATION_FULL_DELIVERY_DRIFT")


def _validate_runbook(root: Path) -> None:
    source = _read(root, RUNBOOK_RELATIVE)
    required = (
        "Two-phase Timeweb activation evidence seal",
        "READY_TO_ACTIVATE",
        "PUBLIC_MULTI_USER_ENABLED=true",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED=true",
        "OMNI_V10_VK_ID_LOGIN_ENABLED=false",
        "LIVE_OPERABLE",
        "No workflow in this gate mutates Timeweb App Platform settings",
    )
    for marker in required:
        if marker not in source:
            raise RuntimeError(
                f"TIMEWEB_TELEGRAM_ACTIVATION_RUNBOOK_MARKER_MISSING:{marker}"
            )


def validate(root: Path = ROOT) -> None:
    _validate_contract(root)
    _validate_controller(root)
    _validate_workflow(root)
    _validate_composition(root)
    _validate_runbook(root)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "V10_TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION=PASS "
        "two_phase=evidence_sealed provider_mutation=fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
