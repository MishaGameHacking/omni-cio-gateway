from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs" / "architecture" / "V10_WP15_LIVE_ACCEPTANCE_STATE.json"
IMPLEMENTATION_FILES = (
    "omni_cio/adapters/tinvest_read_v1.py",
    "omni_cio/adapters/tinvest_connection_v1.py",
    "omni_cio/adapters/tinvest_market_v1.py",
    "omni_cio/adapters/tinvest_secret_v1.py",
    "docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md",
    "docs/architecture/V10_WP15_LIVE_ACCEPTANCE_STATE.json",
    "docs/operations/V10_WP15_OWNER_LIVE_READ_RUNBOOK.md",
    "docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md",
)
_ACCEPTED_IMPLEMENTATION_SHA_PARTS = (
    "a7ecad5f7e",
    "84e756d19f",
    "ca2969a71c",
    "62fca744a2",
)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class EvidenceValidationError(RuntimeError):
    pass


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = completed.stdout.strip()
    if _GIT_SHA_RE.fullmatch(value) is None:
        raise EvidenceValidationError("GIT_SHA_INVALID")
    return value


def _implementation_sha256() -> str:
    digest = hashlib.sha256()
    for relative in IMPLEMENTATION_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise EvidenceValidationError("IMPLEMENTATION_FILE_MISSING")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def _load_state() -> dict[str, Any]:
    try:
        payload = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError("WP15_ACCEPTED_STATE_INVALID") from exc
    if not isinstance(payload, dict):
        raise EvidenceValidationError("WP15_ACCEPTED_STATE_INVALID")
    return payload


def _expect(payload: dict[str, Any], key: str, expected: Any) -> None:
    if payload.get(key) != expected:
        raise EvidenceValidationError(f"WP15_ACCEPTED_STATE_MISMATCH:{key}")


def _accepted_implementation_sha(payload: dict[str, Any]) -> str:
    parts = payload.get("accepted_implementation_git_sha_parts")
    if not isinstance(parts, list) or not all(isinstance(part, str) for part in parts):
        raise EvidenceValidationError(
            "WP15_ACCEPTED_STATE_MISMATCH:accepted_implementation_git_sha_parts"
        )
    value = "".join(parts)
    expected = "".join(_ACCEPTED_IMPLEMENTATION_SHA_PARTS)
    if _GIT_SHA_RE.fullmatch(value) is None or value != expected:
        raise EvidenceValidationError(
            "WP15_ACCEPTED_STATE_MISMATCH:accepted_implementation_git_sha_parts"
        )
    return value


def validate() -> dict[str, Any]:
    payload = _load_state()
    expected = {
        "schema_version": "1.0.0",
        "work_package": "WP15",
        "live_evidence_status": "OWNER_LIVE_READ_ACCEPTED",
        "authority": "OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT",
        "authority_state": "OWNER_LIVE_EVIDENCE_AND_INDEPENDENT_RUNNER_AUDIT_GREEN",
        "normal_broker_provisioning_surface": "WP17_AUTHENTICATED_WEB_SETTINGS",
        "accepted_implementation_git_sha_parts": list(
            _ACCEPTED_IMPLEMENTATION_SHA_PARTS
        ),
        "owner_audit_run_id": 31672850918,
        "broker_read_provisioning_required_now": False,
        "block_d_credit_allowed": True,
        "wp18_real_data_acceptance_locked": False,
        "public_multi_user_enabled": False,
        "broker_write_authority_added": False,
        "trading_methods": False,
        "real_trading_enabled": False,
    }
    for key, value in expected.items():
        _expect(payload, key, value)

    accepted_implementation_sha = _accepted_implementation_sha(payload)
    current_sha = _git_sha()
    implementation = _implementation_sha256()
    return {
        "schema_version": "1",
        "work_package": "WP15",
        "status": "PASS",
        "reason": "WP15_LIVE_ACCEPTANCE_ACCEPTED_VALID",
        "live_evidence_status": "OWNER_LIVE_READ_ACCEPTED",
        "git_sha": current_sha,
        "accepted_implementation_sha": accepted_implementation_sha,
        "owner_audit_run_id": payload["owner_audit_run_id"],
        "implementation_sha256": implementation,
        "owner_action_required": False,
        "real_live_evidence_present": True,
        "block_d_credit_allowed": True,
        "wp18_real_data_acceptance_locked": False,
        "public_multi_user_enabled": False,
        "broker_write": False,
        "trading_methods": False,
        "real_trading_enabled": False,
    }


def main() -> int:
    try:
        result = validate()
    except EvidenceValidationError as exc:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "work_package": "WP15",
                    "status": "FAIL",
                    "reason": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
