from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path(
    "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
)
CONTROLLER_RELATIVE = Path("scripts/timeweb_public_ingress_acceptance.py")
WORKFLOW_RELATIVE = Path(".github/workflows/v10-timeweb-public-ingress-acceptance.yml")
RUNBOOK_RELATIVE = Path(
    "docs/operations/V10_TIMEWEB_PUBLIC_INGRESS_ACCEPTANCE_RUNBOOK.md"
)
_PROVIDER_BINDING = "TIMEWEB_CLOUD_API_TOKEN"
_CONFIRMATION = "ACCEPT_OMNICIO_RU_TIMEWEB_PUBLIC_INGRESS"


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            f"TIMEWEB_PUBLIC_INGRESS_SOURCE_UNREADABLE:{path.name}"
        ) from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_CONTRACT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_CONTRACT_INVALID")
    return value


def _validate_contract(payload: dict[str, Any]) -> None:
    ingress = payload.get("public_ingress")
    if not isinstance(ingress, dict):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_CONTRACT_INVALID")
    expected = {
        "custom_domain": "omnicio.ru",
        "tls_required": True,
        "cloudflare_required_hop": False,
        "owner_home_network_dependency_allowed": False,
        "representative_russian_no_vpn_evidence_required": True,
        "undocumented_provider_domain_api_allowed": False,
        "controller": CONTROLLER_RELATIVE.as_posix(),
        "workflow": WORKFLOW_RELATIVE.as_posix(),
        "runbook": RUNBOOK_RELATIVE.as_posix(),
        "operations": ["observe", "accept"],
        "provider_api_mode": "READ_ONLY",
        "provider_domain_mutation_by_controller_allowed": False,
        "owner_panel_domain_attachment_when_no_documented_api": True,
        "automatic_lets_encrypt_expected": True,
        "public_https_probe_required": True,
        "exact_release_sha_required": True,
        "database_readiness_required": True,
        "security_headers_required": True,
        "retired_edge_headers_forbidden": True,
        "p3_recovery_evidence_digest_required": True,
        "russian_no_vpn_evidence_digest_required": True,
        "rollback_release_sha_required": True,
        "rollback_evidence_digest_required": True,
        "public_activation_must_remain_false": True,
    }
    if ingress != expected:
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_CONTRACT_DRIFT")

    states = {
        row.get("id"): row.get("state")
        for row in payload.get("branch_milestones", [])
        if isinstance(row, dict)
    }
    if states.get("P3_POSTGRES18_PRODUCTION_CUTOVER") != "CERTIFIED_GREEN_BRANCH_LOCAL":
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_P3_GATE_NOT_GREEN")
    if states.get("P4_OMNICIO_RU_DNS_TLS") != "IMPLEMENTED_VERIFICATION_PENDING":
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_MILESTONE_DRIFT")


def _validate_controller(path: Path) -> None:
    source = _text(path)
    required = (
        'CANONICAL_HOSTNAME = "omnicio.ru"',
        'CANONICAL_ORIGIN = "https://omnicio.ru"',
        f'ACCEPT_CONFIRMATION = "{_CONFIRMATION}"',
        "class TimewebIngressReadApi",
        "def _probe_public_runtime",
        "TIMEWEB_PUBLIC_INGRESS_RELEASE_SHA_DRIFT",
        "TIMEWEB_PUBLIC_INGRESS_CANONICAL_DOMAIN_MISSING",
        "TIMEWEB_PUBLIC_INGRESS_RETIRED_EDGE_HEADER",
        "TIMEWEB_PUBLIC_INGRESS_ROLLBACK_RELEASE_NOT_PROVEN",
        'app_release.PUBLIC_MULTI_USER_ENV: "false"',
        'app_release.TELEGRAM_LOGIN_ENV: "false"',
        "p3_recovery_evidence_sha256",
        "russian_no_vpn_evidence_sha256",
        "rollback_evidence_sha256",
        "TIMEWEB_PUBLIC_INGRESS=ACCEPTED",
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_CONTROLLER_DRIFT")
    forbidden = (
        ".deploy_once(",
        'method="POST"',
        'method="PUT"',
        'method="PATCH"',
        'method="DELETE"',
        "_create_unverified_context",
        "CERT_NONE",
        "check_hostname = False",
        'PUBLIC_MULTI_USER_ENABLED", "true"',
        'OMNI_V10_TELEGRAM_LOGIN_ENABLED", "true"',
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_CONTROLLER_AUTHORITY_WIDENED")


def _validate_workflow(path: Path) -> None:
    source = _text(path)
    binding = f"{_PROVIDER_BINDING}: ${{{{ secrets.{_PROVIDER_BINDING} }}}}"
    required = (
        "workflow_dispatch:",
        "expected_main_sha:",
        "operation:",
        "p3_recovery_evidence_sha256:",
        "russian_no_vpn_evidence_sha256:",
        "rollback_release_sha:",
        "rollback_evidence_sha256:",
        "environment: timeweb-production",
        "refs/heads/main:refs/remotes/origin/main",
        'test "$EXPECTED_HEAD" = "$OBSERVED_MAIN"',
        "python -m scripts.verify_v10_timeweb_github_environment",
        "python -m scripts.check_v10_timeweb_public_ingress_acceptance",
        "python -m scripts.timeweb_public_ingress_acceptance",
        _CONFIRMATION,
        binding,
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_WORKFLOW_DRIFT")
    forbidden = (
        "on:\n  push:",
        "pull_request:",
        "workflow_run:",
        "schedule:",
        "continue-on-error",
        "permissions: write-all",
        "deploy_once",
        "curl -X POST",
        "Invoke-RestMethod",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_WORKFLOW_AUTHORITY_WIDENED")
    if source.count(binding) != 1:
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_PROVIDER_BINDING_SCOPE_INVALID")
    accept_step = source.find("Accept canonical public ingress")
    binding_index = source.find(binding)
    if not (0 <= accept_step < binding_index):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_PROVIDER_BINDING_SCOPE_INVALID")


def _validate_runbook(path: Path) -> None:
    source = _text(path)
    required = (
        "P4_OMNICIO_RU_DNS_TLS",
        "P3 branch-local source checkpoint is certified GREEN",
        "App Platform",
        "Settings",
        "Domains",
        "Let's Encrypt",
        "Do not invent an undocumented provider endpoint",
        "representative Russian ordinary-Internet/no-VPN evidence",
        "PUBLIC_MULTI_USER_ENABLED=false",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED=false",
        "P5 remains blocked",
        "last-known-good",
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_PUBLIC_INGRESS_RUNBOOK_DRIFT")


def validate(root: Path = ROOT) -> None:
    payload = _json(root / CONTRACT_RELATIVE)
    _validate_contract(payload)
    _validate_controller(root / CONTROLLER_RELATIVE)
    _validate_workflow(root / WORKFLOW_RELATIVE)
    _validate_runbook(root / RUNBOOK_RELATIVE)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(f"V10_TIMEWEB_PUBLIC_INGRESS=FAIL code={exc}", file=sys.stderr)
        return 1
    print(
        "V10_TIMEWEB_PUBLIC_INGRESS=PASS "
        "provider_api=read_only external_dns_mutation=fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
