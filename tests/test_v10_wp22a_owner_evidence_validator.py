from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.validate_v10_wp22a_owner_evidence import EvidenceError, FILES, validate


EXPECTED_SHA = "a" * 40


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": "1",
        "work_package": "WP22A",
        "evidence_class": "OWNER_PRIVATE_REMOTE_REHEARSAL",
        "captured_at_utc": "2026-08-14T18:00:00+00:00",
        "implementation_sha": EXPECTED_SHA,
        "implementation_fingerprint": {
            key: _sha256(path) for key, path in FILES.items()
        },
        "exact_implementation_binding": True,
        "backend_loopback_only": True,
        "runner_loopback_firewall_bound": True,
        "evidence_acl_protected": True,
        "runner_evidence_read_allowed": True,
        "runner_evidence_write_allowed": False,
        "tailscale_serve_private": True,
        "funnel_public_ingress": False,
        "owner_identity_binding": True,
        "secure_server_session": True,
        "phone_https_reachability_confirmed": True,
        "logout_session_revocation_confirmed": True,
        "public_multi_user_enabled": False,
        "broker_write_authority_added": False,
        "trading_methods": False,
        "real_trading_enabled": False,
        "raw_owner_login_collected": False,
        "raw_runner_identity_collected": False,
        "raw_runner_sid_collected": False,
        "tailscale_auth_material_collected": False,
        "private_url_collected": False,
        "broker_secret_collected": False,
        "private_portfolio_payload_collected": False,
        "status": "PASS",
        "reason_code": "WP22A_OWNER_PRIVATE_REMOTE_PHONE_ACCEPTED",
    }


def test_validator_accepts_only_exact_sanitized_shape_and_current_fingerprints() -> (
    None
):
    assert "local_app_factory_sha256" in FILES
    result = validate(valid_payload(), expected_sha=EXPECTED_SHA)
    assert result["status"] == "PASS"
    assert result["implementation_sha"] == EXPECTED_SHA
    assert result["private_remote"] == {
        "backend_loopback_only": True,
        "runner_loopback_firewall_bound": True,
        "tailscale_serve_private": True,
        "funnel_public_ingress": False,
        "owner_identity_binding": True,
        "secure_server_session": True,
        "phone_https_reachability_confirmed": True,
        "logout_session_revocation_confirmed": True,
    }
    assert result["evidence_protection"] == {
        "evidence_acl_protected": True,
        "runner_evidence_read_allowed": True,
        "runner_evidence_write_allowed": False,
    }
    assert result["privacy"]["private_url_collected"] is False
    assert result["privacy"]["raw_runner_sid_collected"] is False


def test_validator_rejects_stale_implementation_sha() -> None:
    with pytest.raises(
        EvidenceError,
        match="WP22A_OWNER_EVIDENCE_IMPLEMENTATION_SHA_MISMATCH",
    ):
        validate(valid_payload(), expected_sha="b" * 40)


def test_validator_rejects_missing_runner_loopback_firewall_evidence() -> None:
    payload = valid_payload()
    payload["runner_loopback_firewall_bound"] = False
    with pytest.raises(
        EvidenceError,
        match="WP22A_OWNER_EVIDENCE_TRUE_REQUIRED:RUNNER_LOOPBACK_FIREWALL_BOUND",
    ):
        validate(payload, expected_sha=EXPECTED_SHA)


def test_validator_rejects_unprotected_or_runner_writable_owner_evidence() -> None:
    payload = valid_payload()
    payload["evidence_acl_protected"] = False
    with pytest.raises(
        EvidenceError,
        match="WP22A_OWNER_EVIDENCE_TRUE_REQUIRED:EVIDENCE_ACL_PROTECTED",
    ):
        validate(payload, expected_sha=EXPECTED_SHA)

    payload = valid_payload()
    payload["runner_evidence_write_allowed"] = True
    with pytest.raises(
        EvidenceError,
        match="WP22A_OWNER_EVIDENCE_FALSE_REQUIRED:RUNNER_EVIDENCE_WRITE_ALLOWED",
    ):
        validate(payload, expected_sha=EXPECTED_SHA)


def test_validator_rejects_any_sensitive_private_url_collection() -> None:
    payload = valid_payload()
    payload["private_url_collected"] = True
    with pytest.raises(
        EvidenceError,
        match="WP22A_OWNER_EVIDENCE_FALSE_REQUIRED:PRIVATE_URL_COLLECTED",
    ):
        validate(payload, expected_sha=EXPECTED_SHA)


def test_validator_rejects_fingerprint_drift() -> None:
    payload = valid_payload()
    fingerprint = dict(payload["implementation_fingerprint"])  # type: ignore[arg-type]
    fingerprint["external_access_sha256"] = "0" * 64
    payload["implementation_fingerprint"] = fingerprint
    with pytest.raises(
        EvidenceError,
        match="WP22A_OWNER_EVIDENCE_FINGERPRINT_MISMATCH:EXTERNAL_ACCESS_SHA256",
    ):
        validate(payload, expected_sha=EXPECTED_SHA)
