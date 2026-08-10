from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(r"C:\ProgramData\OmniCIO\wp15\evidence\wp15-owner-live-evidence.json")
IMPLEMENTATION_FILES = (
    "omni_cio/adapters/tinvest_read_v1.py",
    "omni_cio/adapters/tinvest_market_v1.py",
    "omni_cio/adapters/tinvest_secret_v1.py",
    "scripts/rehearse_v10_wp15_owner.py",
    "infrastructure/windows/run_wp15_owner_gate.ps1",
    "docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md",
)
REQUIRED_CHECKS = (
    "owner_read_only_token",
    "expected_account_binding",
    "snapshot_complete",
    "market_read",
    "operations_read",
    "portfolio_summary_confirmed",
    "sample_position_confirmed",
    "freshness_confirmed",
    "implementation_binding",
)
PRIVATE_FLAGS = (
    "token_value_recorded",
    "full_account_id_recorded",
    "account_fingerprint_recorded",
    "portfolio_values_recorded",
    "position_values_recorded",
    "raw_broker_payload_recorded",
)


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
    if len(value) != 40:
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


def _load() -> dict[str, Any]:
    try:
        payload = json.loads(EVIDENCE.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise EvidenceValidationError("OWNER_ACTION_REQUIRED") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError("OWNER_EVIDENCE_INVALID") from exc
    if not isinstance(payload, dict):
        raise EvidenceValidationError("OWNER_EVIDENCE_INVALID")
    return payload


def _timestamp(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceValidationError("OWNER_EVIDENCE_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceValidationError("OWNER_EVIDENCE_TIMESTAMP_INVALID")
    return parsed.astimezone(timezone.utc)


def validate() -> dict[str, Any]:
    payload = _load()
    if payload.get("schema_version") != "1" or payload.get("work_package") != "WP15":
        raise EvidenceValidationError("OWNER_EVIDENCE_SCHEMA_INVALID")
    if payload.get("audit") != "owner_live_read_only":
        raise EvidenceValidationError("OWNER_EVIDENCE_AUDIT_INVALID")
    if payload.get("status") != "PASS":
        raise EvidenceValidationError("OWNER_EVIDENCE_NOT_PASS")
    if payload.get("reason") != "WP15_OWNER_LIVE_READ_ONLY_ACCEPTED":
        raise EvidenceValidationError("OWNER_EVIDENCE_REASON_INVALID")

    current_sha = _git_sha()
    if payload.get("git_sha") != current_sha:
        raise EvidenceValidationError("OWNER_EVIDENCE_GIT_SHA_MISMATCH")
    implementation = _implementation_sha256()
    if payload.get("implementation_sha256") != implementation:
        raise EvidenceValidationError("OWNER_EVIDENCE_IMPLEMENTATION_MISMATCH")

    recorded_at = _timestamp(payload.get("recorded_at"))
    now = datetime.now(timezone.utc)
    if recorded_at > now + timedelta(minutes=5):
        raise EvidenceValidationError("OWNER_EVIDENCE_FROM_FUTURE")
    if now - recorded_at > timedelta(hours=24):
        raise EvidenceValidationError("OWNER_EVIDENCE_STALE")

    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise EvidenceValidationError("OWNER_EVIDENCE_CHECKS_INVALID")
    for key in REQUIRED_CHECKS:
        if checks.get(key) is not True:
            raise EvidenceValidationError(f"OWNER_EVIDENCE_CHECK_FAILED:{key}")

    privacy = payload.get("privacy")
    if not isinstance(privacy, dict):
        raise EvidenceValidationError("OWNER_EVIDENCE_PRIVACY_INVALID")
    for key in PRIVATE_FLAGS:
        if privacy.get(key) is not False:
            raise EvidenceValidationError(f"OWNER_EVIDENCE_PRIVATE_FIELD:{key}")

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        raise EvidenceValidationError("OWNER_EVIDENCE_AUTHORITY_INVALID")
    if authority.get("broker_read") is not True:
        raise EvidenceValidationError("OWNER_EVIDENCE_READ_AUTHORITY_INVALID")
    for key in ("broker_write", "trading_methods", "real_trading_enabled"):
        if authority.get(key) is not False:
            raise EvidenceValidationError(f"OWNER_EVIDENCE_AUTHORITY_EXPANDED:{key}")

    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise EvidenceValidationError("OWNER_EVIDENCE_COUNTS_INVALID")
    for key in (
        "normalized_positions",
        "market_prices",
        "operation_pages",
        "operations",
    ):
        value = counts.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise EvidenceValidationError(f"OWNER_EVIDENCE_COUNT_INVALID:{key}")
    if counts["normalized_positions"] <= 0 or counts["market_prices"] <= 0:
        raise EvidenceValidationError("OWNER_EVIDENCE_LIVE_DATA_EMPTY")
    if counts["operation_pages"] <= 0:
        raise EvidenceValidationError("OWNER_EVIDENCE_OPERATIONS_NOT_READ")

    return {
        "schema_version": "1",
        "work_package": "WP15",
        "status": "PASS",
        "reason": "WP15_OWNER_EVIDENCE_VALID",
        "git_sha": current_sha,
        "implementation_sha256": implementation,
        "checks": {key: True for key in REQUIRED_CHECKS},
        "privacy_safe": True,
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
