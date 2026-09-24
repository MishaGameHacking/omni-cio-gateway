from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT / "docs/master-plan/OMNI_CIO_V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_AMENDMENT.md"
)
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
RUNTIME = ROOT / "apps/api/hosted_runtime.py"
TELEGRAM_AUTH = ROOT / "apps/api/telegram_auth.py"
TELEGRAM_READINESS = (
    ROOT
    / "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
)
DOCKERFILE = ROOT / "Dockerfile"

_CANONICAL_ORIGIN = "https://omnicio.ru"
_CANONICAL_CALLBACK = "https://omnicio.ru/api/v10/web/auth/telegram/callback"
_EXPECTED_BRANCH = "system/timeweb-platform-consolidation-tw-b"
_SECRET_ENV_NAMES = {
    "OMNI_V10_POSTGRES_DSN",
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID",
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET",
    "OMNI_V10_IDENTITY_BINDING_KEY_HEX",
    "OMNI_V10_CSRF_BINDING_KEY_HEX",
}


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            f"TIMEWEB_FULL_DELIVERY_SOURCE_UNREADABLE:{path.relative_to(ROOT)}"
        ) from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"TIMEWEB_FULL_DELIVERY_JSON_INVALID:{path.relative_to(ROOT)}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_JSON_ROOT_INVALID")
    return payload


def _require_equal(payload: dict[str, Any], key: str, expected: Any) -> None:
    if payload.get(key) != expected:
        raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_CONTRACT_DRIFT:{key}")


def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_SECTION_INVALID:{key}")
    return value


def _validate_authority(payload: dict[str, Any]) -> None:
    _require_equal(
        payload,
        "schema",
        "omni-cio.v10.timeweb-full-production-delivery.v1",
    )
    _require_equal(
        payload,
        "status",
        "OWNER_APPROVED_BRANCH_LOCAL_IMPLEMENTATION_ACCEPTANCE_PENDING",
    )
    _require_equal(payload, "owning_issue", 580)
    _require_equal(payload, "owning_pr", 584)
    _require_equal(payload, "branch", _EXPECTED_BRANCH)
    _require_equal(payload, "canonical_domain", "omnicio.ru")
    _require_equal(payload, "canonical_origin", _CANONICAL_ORIGIN)
    _require_equal(payload, "telegram_redirect_uri", _CANONICAL_CALLBACK)

    amendment = _text(AMENDMENT)
    required = (
        "OWNER-APPROVED BRANCH-LOCAL IMPLEMENTATION AUTHORITY",
        "PR #584",
        "exact-SHA Timeweb App Platform candidate/release control",
        "Timeweb PostgreSQL 18 production cutover/recovery control",
        "canonical `omnicio.ru` DNS/TLS/public-ingress acceptance",
        "Telegram-only production login readiness and activation control",
        "does not authorize",
        "broker write",
        "a merge of PR #584 without the required exact-head landing confirmation",
    )
    for marker in required:
        if marker not in amendment:
            raise RuntimeError(
                f"TIMEWEB_FULL_DELIVERY_AMENDMENT_MARKER_MISSING:{marker}"
            )


def _validate_release(payload: dict[str, Any]) -> None:
    release = _section(payload, "release")
    expected = {
        "source_authority": "GITHUB_PROTECTED_MAIN",
        "deployment_platform": "TIMEWEB_APP_PLATFORM",
        "exact_commit_sha_required": True,
        "production_autodeploy_allowed": False,
        "runtime_release_env": "OMNI_V10_RELEASE_SHA",
        "liveness_path": "/livez",
        "database_readiness_path": "/healthz",
        "deployed_sha_must_equal_accepted_main_sha": True,
        "last_known_good_rollback_required": True,
        "mismatch_state": "OUT_OF_SYNC/DEPLOYMENT_BLOCKED",
    }
    for key, value in expected.items():
        if release.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_RELEASE_DRIFT:{key}")


def _validate_runtime(payload: dict[str, Any]) -> None:
    runtime = _section(payload, "runtime")
    if runtime.get("dockerfile") != "Dockerfile" or runtime.get("port") != 8080:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_RUNTIME_SOURCE_DRIFT")
    if runtime.get("app_factory") != "apps.api.hosted_runtime:create_app":
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_RUNTIME_ENTRYPOINT_DRIFT")
    if runtime.get("secret_values_in_repository_allowed") is not False:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_SECRET_POLICY_DRIFT")
    names = runtime.get("secret_env_names")
    if not isinstance(names, list) or set(names) != _SECRET_ENV_NAMES:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_SECRET_ENV_DRIFT")

    dockerfile = _text(DOCKERFILE)
    for marker in (
        "EXPOSE 8080",
        "apps.api.hosted_runtime:create_app",
        "http://localhost:8080/livez",
    ):
        if marker not in dockerfile:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_DOCKER_DRIFT:{marker}")

    hosted_runtime = _text(RUNTIME)
    for marker in (
        "OMNI_V10_HOSTED_RUNTIME",
        "OMNI_V10_PUBLIC_HOSTNAME",
        "OMNI_V10_RELEASE_SHA",
        "OMNI_V10_POSTGRES_DSN",
        "OMNI_V10_POSTGRES_RUNTIME_ROLE",
        'canonical_origin=f"https://{hostname}"',
        "provider_route_installer=install_telegram_auth_routes_v1",
    ):
        if marker not in hosted_runtime:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_HOSTED_RUNTIME_DRIFT:{marker}")


def _validate_postgres(payload: dict[str, Any]) -> None:
    postgres = _section(payload, "postgres")
    expected = {
        "engine": "PostgreSQL",
        "major_version": 18,
        "migrations_required": True,
        "least_privilege_required": True,
        "rls_required": True,
        "force_rls_required": True,
        "cross_tenant_negative_required": True,
        "backup_restore_required": True,
        "production_cutover_requires_independent_acceptance": True,
    }
    for key, value in expected.items():
        if postgres.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_POSTGRES_DRIFT:{key}")


def _validate_public_ingress(payload: dict[str, Any]) -> None:
    ingress = _section(payload, "public_ingress")
    expected = {
        "custom_domain": "omnicio.ru",
        "tls_required": True,
        "cloudflare_required_hop": False,
        "owner_home_network_dependency_allowed": False,
        "representative_russian_no_vpn_evidence_required": True,
        "undocumented_provider_domain_api_allowed": False,
    }
    for key, value in expected.items():
        if ingress.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_INGRESS_DRIFT:{key}")


def _validate_telegram(payload: dict[str, Any]) -> None:
    telegram = _section(payload, "telegram")
    expected = {
        "provider": "TELEGRAM",
        "oidc_authorization_code_pkce_required": True,
        "allowed_scope": ["openid"],
        "bot_access_scope_allowed": False,
        "public_multi_user_flag": "PUBLIC_MULTI_USER_ENABLED",
        "provider_activation_flag": "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "flags_must_transition_together": True,
        "current_public_multi_user_enabled": False,
        "current_telegram_login_enabled": False,
        "provider_secret_custody": "TIMEWEB_APP_PLATFORM_ENVIRONMENT",
        "real_login_account_tenant_session_proof_required": True,
        "cross_tenant_negative_required": True,
    }
    for key, value in expected.items():
        if telegram.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_TELEGRAM_DRIFT:{key}")

    source = _text(TELEGRAM_AUTH)
    for marker in (
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "TELEGRAM_AUTH_ACTIVATION_FLAGS_MISMATCH",
        "allowed_providers=(IdentityProviderV1.TELEGRAM,)",
    ):
        if marker not in source:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_TELEGRAM_SOURCE_DRIFT:{marker}")

    readiness = _json(TELEGRAM_READINESS)
    if readiness.get("activation_allowed") is not False:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_PREMATURE_PUBLIC_ACTIVATION")
    if readiness.get("canonical_origin") != _CANONICAL_ORIGIN:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_TELEGRAM_ORIGIN_DRIFT")
    if readiness.get("canonical_redirect_uri") != _CANONICAL_CALLBACK:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_TELEGRAM_CALLBACK_DRIFT")


def _validate_external_gates(payload: dict[str, Any]) -> None:
    gates = _section(payload, "external_action_gates")
    required = {
        "app_creation_or_paid_capacity",
        "immutable_network_selection",
        "production_database_cutover",
        "dns_tls_cutover",
        "telegram_registration_and_secrets",
        "legal_privacy_regulatory",
        "public_activation",
        "destructive_decommission",
    }
    if set(gates) != required:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_EXTERNAL_GATE_SET_DRIFT")
    for key, value in gates.items():
        if not isinstance(value, str) or not value.endswith(("REQUIRED", "ONLY")):
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_EXTERNAL_GATE_INVALID:{key}")


def _validate_protected_invariants(payload: dict[str, Any]) -> None:
    protected = _section(payload, "protected_invariants")
    for key in (
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "transfer_withdrawal",
        "margin_leverage",
        "uncovered_short",
        "browser_tenant_selection",
        "web_visual_started",
        "wp23_unlocked",
        "merge_without_exact_head_confirmation",
    ):
        if protected.get(key) is not False:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_AUTHORITY_WIDENED:{key}")


def validate(root: Path = ROOT) -> None:
    global \
        ROOT, \
        AMENDMENT, \
        CONTRACT, \
        RUNTIME, \
        TELEGRAM_AUTH, \
        TELEGRAM_READINESS, \
        DOCKERFILE
    original = (
        ROOT,
        AMENDMENT,
        CONTRACT,
        RUNTIME,
        TELEGRAM_AUTH,
        TELEGRAM_READINESS,
        DOCKERFILE,
    )
    if root != ROOT:
        ROOT = root
        AMENDMENT = (
            root
            / "docs/master-plan/OMNI_CIO_V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_AMENDMENT.md"
        )
        CONTRACT = (
            root
            / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
        )
        RUNTIME = root / "apps/api/hosted_runtime.py"
        TELEGRAM_AUTH = root / "apps/api/telegram_auth.py"
        TELEGRAM_READINESS = (
            root
            / "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
        )
        DOCKERFILE = root / "Dockerfile"
    try:
        payload = _json(CONTRACT)
        _validate_authority(payload)
        _validate_release(payload)
        _validate_runtime(payload)
        _validate_postgres(payload)
        _validate_public_ingress(payload)
        _validate_telegram(payload)
        _validate_external_gates(payload)
        _validate_protected_invariants(payload)
    finally:
        (
            ROOT,
            AMENDMENT,
            CONTRACT,
            RUNTIME,
            TELEGRAM_AUTH,
            TELEGRAM_READINESS,
            DOCKERFILE,
        ) = original


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(f"V10_TIMEWEB_FULL_PRODUCTION_DELIVERY=FAIL code={exc}", file=sys.stderr)
        return 1
    print(
        "V10_TIMEWEB_FULL_PRODUCTION_DELIVERY=PASS "
        "scope=PR584 repository_implementation external_actions=fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
