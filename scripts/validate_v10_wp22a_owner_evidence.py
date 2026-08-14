from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "execution_contract_sha256": ROOT
    / "docs"
    / "architecture"
    / "V10_WP22A_EXECUTION_CONTRACT.md",
    "external_access_sha256": ROOT / "omni_cio" / "web" / "external_access_v1.py",
    "remote_factory_sha256": ROOT / "apps" / "api" / "wp22a_remote.py",
    "provisioner_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "provision_wp22a_private_remote_access.ps1",
    "runtime_launcher_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "run_wp22a_private_remote_runtime.ps1",
    "runner_auditor_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "audit_wp22a_runner_loopback.ps1",
    "owner_finalizer_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "finalize_wp22a_owner_evidence.ps1",
}


class EvidenceError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("WP22A_OWNER_EVIDENCE_READ_INVALID") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("WP22A_OWNER_EVIDENCE_NOT_OBJECT")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_true(payload: dict[str, Any], key: str) -> None:
    if payload.get(key) is not True:
        raise EvidenceError(f"WP22A_OWNER_EVIDENCE_TRUE_REQUIRED:{key.upper()}")


def _require_false(payload: dict[str, Any], key: str) -> None:
    if payload.get(key) is not False:
        raise EvidenceError(f"WP22A_OWNER_EVIDENCE_FALSE_REQUIRED:{key.upper()}")


def validate(payload: dict[str, Any], *, expected_sha: str) -> dict[str, Any]:
    expected_top = {
        "schema_version",
        "work_package",
        "evidence_class",
        "captured_at_utc",
        "implementation_sha",
        "implementation_fingerprint",
        "exact_implementation_binding",
        "backend_loopback_only",
        "runner_loopback_firewall_bound",
        "tailscale_serve_private",
        "funnel_public_ingress",
        "owner_identity_binding",
        "secure_server_session",
        "phone_https_reachability_confirmed",
        "logout_session_revocation_confirmed",
        "public_multi_user_enabled",
        "broker_write_authority_added",
        "trading_methods",
        "real_trading_enabled",
        "raw_owner_login_collected",
        "tailscale_auth_material_collected",
        "private_url_collected",
        "broker_secret_collected",
        "private_portfolio_payload_collected",
        "status",
        "reason_code",
    }
    if set(payload) != expected_top:
        raise EvidenceError("WP22A_OWNER_EVIDENCE_FIELDS_INVALID")
    if payload["schema_version"] != "1" or payload["work_package"] != "WP22A":
        raise EvidenceError("WP22A_OWNER_EVIDENCE_IDENTITY_INVALID")
    if payload["evidence_class"] != "OWNER_PRIVATE_REMOTE_REHEARSAL":
        raise EvidenceError("WP22A_OWNER_EVIDENCE_CLASS_INVALID")
    if payload["status"] != "PASS":
        raise EvidenceError("WP22A_OWNER_EVIDENCE_NOT_PASS")
    if payload["reason_code"] != "WP22A_OWNER_PRIVATE_REMOTE_PHONE_ACCEPTED":
        raise EvidenceError("WP22A_OWNER_EVIDENCE_REASON_INVALID")

    normalized_expected = expected_sha.strip().lower()
    if len(normalized_expected) != 40 or any(
        ch not in "0123456789abcdef" for ch in normalized_expected
    ):
        raise EvidenceError("WP22A_EXPECTED_SHA_INVALID")
    if str(payload["implementation_sha"]).lower() != normalized_expected:
        raise EvidenceError("WP22A_OWNER_EVIDENCE_IMPLEMENTATION_SHA_MISMATCH")

    try:
        captured = datetime.fromisoformat(
            str(payload["captured_at_utc"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise EvidenceError("WP22A_OWNER_EVIDENCE_TIMESTAMP_INVALID") from exc
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise EvidenceError("WP22A_OWNER_EVIDENCE_TIMESTAMP_NOT_UTC_AWARE")

    fingerprint = payload.get("implementation_fingerprint")
    if not isinstance(fingerprint, dict) or set(fingerprint) != set(FILES):
        raise EvidenceError("WP22A_OWNER_EVIDENCE_FINGERPRINT_FIELDS_INVALID")
    for key, path in FILES.items():
        if not path.is_file():
            raise EvidenceError(f"WP22A_IMPLEMENTATION_FILE_MISSING:{key.upper()}")
        if str(fingerprint.get(key, "")).lower() != _sha256(path):
            raise EvidenceError(
                f"WP22A_OWNER_EVIDENCE_FINGERPRINT_MISMATCH:{key.upper()}"
            )

    for key in (
        "exact_implementation_binding",
        "backend_loopback_only",
        "runner_loopback_firewall_bound",
        "tailscale_serve_private",
        "owner_identity_binding",
        "secure_server_session",
        "phone_https_reachability_confirmed",
        "logout_session_revocation_confirmed",
    ):
        _require_true(payload, key)
    for key in (
        "funnel_public_ingress",
        "public_multi_user_enabled",
        "broker_write_authority_added",
        "trading_methods",
        "real_trading_enabled",
        "raw_owner_login_collected",
        "tailscale_auth_material_collected",
        "private_url_collected",
        "broker_secret_collected",
        "private_portfolio_payload_collected",
    ):
        _require_false(payload, key)

    return {
        "schema_version": "1",
        "work_package": "WP22A",
        "evidence_class": "OWNER_PRIVATE_REMOTE_ACCEPTANCE",
        "implementation_sha": normalized_expected,
        "private_remote": {
            "backend_loopback_only": True,
            "runner_loopback_firewall_bound": True,
            "tailscale_serve_private": True,
            "funnel_public_ingress": False,
            "owner_identity_binding": True,
            "secure_server_session": True,
            "phone_https_reachability_confirmed": True,
            "logout_session_revocation_confirmed": True,
        },
        "authority": {
            "public_multi_user_enabled": False,
            "broker_write_authority_added": False,
            "trading_methods": False,
            "real_trading_enabled": False,
        },
        "privacy": {
            "raw_owner_login_collected": False,
            "tailscale_auth_material_collected": False,
            "private_url_collected": False,
            "broker_secret_collected": False,
            "private_portfolio_payload_collected": False,
        },
        "status": "PASS",
        "reason_codes": [
            "CURRENT_IMPLEMENTATION_FINGERPRINT_MATCH",
            "PRIVATE_SERVE_NO_FUNNEL_PASS",
            "RUNNER_LOOPBACK_FIREWALL_BOUND",
            "OWNER_IDENTITY_SESSION_PASS",
            "OWNER_PHONE_REHEARSAL_PASS",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate sanitized WP22A OWNER private remote evidence"
    )
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = validate(_load(args.evidence), expected_sha=args.expected_sha)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        raise SystemExit(1) from exc
