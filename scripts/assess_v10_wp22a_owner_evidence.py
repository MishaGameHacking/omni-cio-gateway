from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_SOURCE_HASHES = {
    "configurator_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "configure_wp22a_tailscale_serve.ps1",
    "provisioner_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "provision_wp22a_private_remote_runtime.ps1",
    "launcher_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "run_wp22a_private_remote_runtime.ps1",
    "finalizer_sha256": ROOT
    / "infrastructure"
    / "windows"
    / "finalize_wp22a_private_remote_evidence.ps1",
    "remote_security_sha256": ROOT / "omni_cio" / "web" / "remote_security_v1.py",
    "execution_contract_sha256": ROOT
    / "docs"
    / "architecture"
    / "V10_WP22A_EXECUTION_CONTRACT.md",
}

_REQUIRED_TRUE = (
    "tailscale_private_serve_observed",
    "funnel_disabled_during_rehearsal",
    "backend_loopback_only",
    "private_config_acl_ok",
    "owner_identity_fingerprint_present",
    "runtime_exact_deployment",
    "runtime_non_admin",
    "runtime_task_principal_exact",
    "runtime_task_action_exact",
    "tailnet_policy_narrow_owner_only_confirmed",
    "owner_remote_https_cabinet_confirmed",
    "local_loopback_fallback_confirmed",
    "non_owner_identity_denial_deterministic",
    "serve_disabled_after_rehearsal",
    "funnel_disabled_after_rehearsal",
    "temporary_runtime_cleaned",
    "postgres_config_restored",
    "ready",
)

_REQUIRED_FALSE = (
    "runner_runtime_data_access",
    "raw_owner_identity_recorded",
    "raw_tailnet_hostname_recorded",
    "session_cookie_recorded",
    "tailscale_auth_key_recorded",
    "broker_secret_recorded",
    "private_portfolio_payload_recorded",
    "public_ingress",
    "public_multi_user_enabled",
    "broker_write_authority_added",
    "trading_methods",
    "real_trading_enabled",
)

_RUNNER_TRUE = (
    "sanitized_evidence_present",
    "runner_evidence_read_allowed",
    "private_config_present",
    "ready",
)

_RUNNER_FALSE = (
    "runner_is_administrator",
    "runner_evidence_write_allowed",
    "runner_private_config_read_allowed",
    "runner_private_config_write_allowed",
    "real_secret_values_used",
    "raw_owner_identity_recorded",
    "raw_tailnet_hostname_recorded",
    "broker_write_authority_added",
    "trading_methods",
    "real_trading_enabled",
)

_FORBIDDEN_KEYS = {
    "owner_login",
    "tailscale_user_login",
    "tailscale_auth_key",
    "auth_key",
    "cookie",
    "session_token",
    "broker_token",
    "account_id",
    "account_fingerprint",
    "portfolio_total",
    "position",
    "quantity",
    "price",
    "hostname",
    "host",
}


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_bool(value: dict[str, Any], key: str, expected: bool) -> None:
    candidate = value.get(key)
    if not isinstance(candidate, bool) or candidate is not expected:
        raise ValueError(f"{key} must be {expected}")


def _assert_no_forbidden_keys(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            if normalized in _FORBIDDEN_KEYS:
                raise ValueError(
                    f"forbidden private evidence key: {'.'.join((*path, str(key)))}"
                )
            _assert_no_forbidden_keys(child, path=(*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=(*path, str(index)))


def assess(evidence: dict[str, Any], runner: dict[str, Any], expected_sha: str) -> None:
    expected = expected_sha.strip().lower()
    if _SHA40.fullmatch(expected) is None:
        raise ValueError("expected implementation SHA must be 40 lowercase hex characters")
    if (
        evidence.get("schema_version") != "1"
        or evidence.get("work_package") != "WP22A"
    ):
        raise ValueError("unsupported WP22A OWNER evidence schema")
    if evidence.get("evidence_type") != "OWNER_PRIVATE_REMOTE_SANITIZED":
        raise ValueError("wrong OWNER evidence type")
    if str(evidence.get("implementation_sha", "")).lower() != expected:
        raise ValueError("OWNER evidence is not bound to the exact implementation SHA")
    if evidence.get("gateway_entrypoint") != "app:app":
        raise ValueError("gateway entrypoint drifted")

    generated = datetime.fromisoformat(str(evidence.get("generated_at_utc", "")))
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("OWNER evidence timestamp must be timezone-aware")
    generated = generated.astimezone(timezone.utc)
    current = datetime.now(timezone.utc)
    if generated > current + timedelta(minutes=5):
        raise ValueError("OWNER evidence timestamp is implausibly in the future")
    if current - generated > timedelta(hours=24):
        raise ValueError("OWNER evidence is stale for exact-head acceptance")

    _assert_no_forbidden_keys(evidence)
    for key in _REQUIRED_TRUE:
        _require_bool(evidence, key, True)
    for key in _REQUIRED_FALSE:
        _require_bool(evidence, key, False)

    for key, source in _SOURCE_HASHES.items():
        recorded = str(evidence.get(key, "")).lower()
        if _SHA256.fullmatch(recorded) is None:
            raise ValueError(f"invalid source hash field: {key}")
        if recorded != _sha256(source):
            raise ValueError(f"source hash mismatch: {key}")

    if (
        runner.get("schema_version") != "1"
        or runner.get("work_package") != "WP22A"
    ):
        raise ValueError("unsupported WP22A runner probe schema")
    if runner.get("evidence_type") != "RUNNER_PRIVATE_REMOTE_ISOLATION":
        raise ValueError("wrong runner evidence type")
    for key in _RUNNER_TRUE:
        _require_bool(runner, key, True)
    for key in _RUNNER_FALSE:
        _require_bool(runner, key, False)
    if runner.get("gateway_entrypoint") != "app:app":
        raise ValueError("runner probe gateway entrypoint drifted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--runner-probe", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()

    evidence = _load_object(args.evidence)
    runner = _load_object(args.runner_probe)
    assess(evidence, runner, args.expected_sha)
    print("WP22A OWNER private remote evidence: PASS")
    print(f"Implementation binding: {args.expected_sha.strip().lower()}")
    print("Runner evidence access: READ ONLY")
    print("Runner private config access: DENIED")
    print("Public ingress: OFF")
    print("Broker write / Real authority: UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
