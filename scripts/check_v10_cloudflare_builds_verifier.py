from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_BUILDS_VERIFIER_CONTRACT.json"
RUNNER = ROOT / "scripts/run_v10_cloudflare_verifier.py"
EXPECTED_SHARDS = [
    "CFV-1-GOVERNANCE",
    "CFV-2-WEB-STATIC",
    "CFV-3-PYTHON-STATIC",
    "CFV-4-SECURITY-CONTRACTS",
    "CFV-5-RUNTIME-CONTRACTS",
    "CFV-6-RELEASE-PROVENANCE",
]


def _load() -> dict[str, Any]:
    try:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("CLOUDFLARE_VERIFIER_CONTRACT_UNREADABLE") from exc
    if not isinstance(value, dict):
        raise RuntimeError("CLOUDFLARE_VERIFIER_CONTRACT_INVALID")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_VERIFIER_{label}_INVALID")
    return value


def _require_bool(section: dict[str, Any], key: str, expected: bool) -> None:
    if section.get(key) is not expected:
        raise RuntimeError(f"CLOUDFLARE_VERIFIER_{key.upper()}_INVALID")


def validate() -> None:
    payload = _load()
    if payload.get("schema") != "omni-cio.v10.cloudflare-builds-verifier.v1":
        raise RuntimeError("CLOUDFLARE_VERIFIER_SCHEMA_INVALID")
    if payload.get("milestone") != "CF-A":
        raise RuntimeError("CLOUDFLARE_VERIFIER_MILESTONE_INVALID")
    if payload.get("branch") != "system/cloudflare-public-product":
        raise RuntimeError("CLOUDFLARE_VERIFIER_BRANCH_INVALID")

    authority = _object(payload.get("authority"), "AUTHORITY")
    _require_bool(authority, "provider_mutation_allowed", False)
    _require_bool(authority, "production_promotion_allowed", False)
    _require_bool(authority, "github_engineering_authority_retained", True)

    reference = _object(payload.get("workers_builds_reference"), "REFERENCE")
    expected_reference = {
        "included_build_minutes_per_month": 6000,
        "max_concurrent_builds": 6,
        "build_timeout_minutes": 20,
        "vcpu_per_build": 4,
        "memory_gib_per_build": 8,
        "disk_gib_per_build": 20,
        "automatic_paid_overage_authorized": False,
    }
    for key, expected in expected_reference.items():
        if reference.get(key) != expected:
            raise RuntimeError(f"CLOUDFLARE_VERIFIER_REFERENCE_{key.upper()}_INVALID")

    dispatch = _object(payload.get("dispatch"), "DISPATCH")
    if dispatch.get("mode") != "WORK_CONSERVING_COMPLEMENTARY_SHARDS":
        raise RuntimeError("CLOUDFLARE_VERIFIER_DISPATCH_MODE_INVALID")
    for key in (
        "fill_all_safe_slots",
        "distinct_useful_work_by_default",
        "quota_or_provider_outage_reassigns_work",
        "lenovo_catch_all_fallback_required",
        "exact_head_binding_required",
    ):
        _require_bool(dispatch, key, True)
    for key in (
        "duplicate_heavy_work_by_default",
        "missing_or_failed_shard_may_report_green",
        "cloudflare_loss_may_weaken_required_assertions",
    ):
        _require_bool(dispatch, key, False)

    shards = payload.get("shards")
    if not isinstance(shards, list):
        raise RuntimeError("CLOUDFLARE_VERIFIER_SHARDS_INVALID")
    identifiers = [item.get("id") for item in shards if isinstance(item, dict)]
    if identifiers != EXPECTED_SHARDS:
        raise RuntimeError("CLOUDFLARE_VERIFIER_SHARD_ORDER_INVALID")
    for item in shards:
        if not isinstance(item, dict):
            raise RuntimeError("CLOUDFLARE_VERIFIER_SHARD_INVALID")
        expected_command = (
            "python scripts/run_v10_cloudflare_verifier.py " + str(item.get("id"))
        )
        if item.get("command") != expected_command:
            raise RuntimeError("CLOUDFLARE_VERIFIER_SHARD_COMMAND_INVALID")
        if item.get("requires_runtime_secrets") is not False:
            raise RuntimeError("CLOUDFLARE_VERIFIER_SHARD_SECRET_SCOPE_INVALID")

    security = _object(payload.get("security"), "SECURITY")
    for key, value in security.items():
        if value is not False:
            raise RuntimeError(f"CLOUDFLARE_VERIFIER_SECURITY_{key.upper()}_INVALID")

    try:
        runner = RUNNER.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("CLOUDFLARE_VERIFIER_RUNNER_UNREADABLE") from exc
    for identifier in EXPECTED_SHARDS:
        if identifier not in runner:
            raise RuntimeError("CLOUDFLARE_VERIFIER_RUNNER_SHARD_MISSING")
    for required in (
        "WORKERS_CI_COMMIT_SHA",
        "GITHUB_SHA",
        "CLOUDFLARE_VERIFIER_SHA_MISMATCH",
        "subprocess.run",
    ):
        if required not in runner:
            raise RuntimeError("CLOUDFLARE_VERIFIER_RUNNER_GUARD_MISSING")


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare Builds verifier contract passed.")
    print("CF-A provider mutation: OFF")
    print("Portable verifier shards: 6")
    print("Automatic paid overage authority: OFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
