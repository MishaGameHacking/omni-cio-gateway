from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from omnicio.db import UserRecord
from omnicio.main import app
from omnicio.recovery import (
    BACKUP_MAX_AGE,
    RESTORE_CHECKS,
    _restore_verification,
    recovery_status,
    require_upgrade_recovery,
    sign_recovery_evidence,
)

NOW = datetime(2026, 10, 5, 6, tzinfo=UTC)


def evidence() -> dict[str, object]:
    return {
        "schema_version": 1, "provider_status": "ok",
        "observed_at": (NOW - timedelta(minutes=1)).isoformat(),
        "latest_backup_at": (NOW - timedelta(hours=2)).isoformat(),
        "schedule_enabled": True, "schedule_interval": "day", "retention_copies": 7,
        "weekly_retention_copies": 4, "weekly_available_copies": 1,
        "latest_weekly_backup_at": (NOW - timedelta(hours=1)).isoformat(),
        "weekly_period": "2026-10-05", "weekly_next_due_at": "2026-10-12T00:00:00+03:00",
        "weekly_owned": [{"id": "private-canary"}], "weekly_create": "private-canary",
        "download_url": "private-canary", "database_password": "private-canary",
        "production_restore_verified": True,
    }


@pytest.mark.parametrize(("changes", "status"), [
    ({}, "fresh"),
    ({"provider_status": "unavailable"}, "unavailable"),
    ({"observed_at": (NOW - timedelta(hours=8)).isoformat()}, "check_stale"),
    ({"latest_backup_at": (NOW - timedelta(hours=24)).isoformat()}, "backup_stale"),
    ({"latest_backup_at": None}, "missing"),
    ({"latest_backup_at": (NOW + timedelta(seconds=1)).isoformat()}, "missing"),
    ({"observed_at": NOW.replace(tzinfo=None).isoformat()}, "unavailable"),
    ({"observed_at": (NOW + timedelta(seconds=1)).isoformat()}, "unavailable"),
    ({"schedule_enabled": False}, "schedule_attention"),
    ({"schedule_interval": "week"}, "schedule_attention"),
    ({"retention_copies": 6}, "schedule_attention"),
    ({"retention_copies": True}, "schedule_attention"),
    ({"weekly_retention_copies": 3}, "weekly_attention"),
    ({"weekly_available_copies": True}, "weekly_attention"),
    ({"weekly_available_copies": 0}, "weekly_attention"),
    ({"weekly_available_copies": 5}, "weekly_attention"),
    ({"weekly_available_copies": "1"}, "weekly_attention"),
    ({"latest_weekly_backup_at": None}, "weekly_attention"),
    ({"latest_weekly_backup_at": (NOW + timedelta(seconds=1)).isoformat()}, "weekly_attention"),
    ({"weekly_next_due_at": "2026-10-19T00:00:00+03:00"}, "weekly_attention"),
    ({"weekly_next_due_at": "2026-10-12T00:00:00"}, "weekly_attention"),
    ({"weekly_period": "2026-10-04"}, "weekly_attention"),
])
def test_recovery_badge_requires_fresh_complete_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object], status: str,
) -> None:
    path = tmp_path / "status.json"
    path.write_text(json.dumps(evidence() | changes), encoding="utf-8")
    monkeypatch.setenv("OMNICIO_RECOVERY_STATUS_PATH", str(path))
    result = recovery_status(now=NOW)
    assert result["status"] == status
    assert result["production_restore_verified"] is False
    assert "private-canary" not in str(result)
    if status in {"unavailable", "check_stale"}:
        assert result["daily_schedule"] is None
        assert result["weekly"]["available_copies"] is None


@pytest.mark.parametrize("copies", [1, 2, 4])
def test_weekly_progress_reports_only_actual_confirmed_copies(copies: int) -> None:
    with patch("omnicio.recovery._read_evidence", return_value=evidence() | {
        "weekly_available_copies": copies,
    }):
        result = recovery_status(now=NOW)
    assert result["status"] == "fresh"
    assert result["weekly"]["available_copies"] == copies
    assert result["weekly"]["retention_copies"] == 4
    assert result["weekly"]["valid_until"] == datetime(2026, 10, 11, 21, tzinfo=UTC)


def test_weekly_confirmation_expires_at_moscow_week_boundary() -> None:
    boundary = datetime(2026, 10, 11, 21, tzinfo=UTC)
    payload = evidence() | {
        "observed_at": (boundary - timedelta(minutes=1)).isoformat(),
        "latest_backup_at": (boundary - timedelta(hours=1)).isoformat(),
    }
    with patch("omnicio.recovery._read_evidence", return_value=payload):
        before = recovery_status(now=boundary - timedelta(seconds=1))
        after = recovery_status(now=boundary)
    assert before["status"] == "fresh"
    assert after["status"] == "weekly_attention"
    assert after["weekly"]["status"] == "stale"
    assert after["weekly"]["available_copies"] is None
    assert after["daily_schedule"] is True


@pytest.mark.parametrize("changes,disabled", [
    ({}, True), ({"schedule_enabled": True}, False),
    ({"copy_creation_enabled": 0}, False),
    ({"observed_at": (NOW - timedelta(hours=8)).isoformat()}, False),
    ({"provider_status": "unavailable"}, False),
])
def test_single_database_status_does_not_refresh_legacy_retention_evidence(
    changes: dict[str, object], disabled: bool,
) -> None:
    payload = evidence() | {"policy_mode": "single_existing_database",
                            "copy_creation_enabled": False, "schedule_enabled": False} | changes
    with patch("omnicio.recovery._read_evidence", return_value=payload):
        result = recovery_status(now=NOW)
    assert (result["status"] == "copying_disabled") is disabled
    assert result["copy_creation_enabled"] is (False if disabled else None)
    assert result["retention_copies"] is None
    assert result["weekly"]["available_copies"] is None
    assert result["weekly"]["retention_copies"] is None
    assert result["production_restore_verified"] is False
    assert result["backup"]["observed_at"] == NOW - timedelta(hours=2)


@pytest.mark.parametrize("body", [None, "{", "[]", '{"schema_version": 2}', " " * 8193])
def test_absent_or_malformed_evidence_never_claims_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str | None,
) -> None:
    path = tmp_path / "status.json"
    if body is not None:
        path.write_text(body, encoding="utf-8")
    monkeypatch.setenv("OMNICIO_RECOVERY_STATUS_PATH", str(path))
    assert recovery_status(now=NOW)["status"] == "unavailable"


def test_recovery_endpoint_requires_session_and_never_uses_client_path() -> None:
    user = UserRecord(UUID(int=101), 101, "active", "user")
    with patch("omnicio.main.service") as auth, patch("omnicio.main.recovery_status") as read:
        auth.return_value.refresh_session.side_effect = lambda token: user if token == "a" else None
        read.return_value = {"status": "unavailable", "production_restore_verified": False}
        client = TestClient(app, cookies={"omnicio_session": "a"})
        response = client.get("/api/system/recovery?path=/etc/omnicio/runtime.env&user_id=102")
        anonymous = TestClient(app).get("/api/system/recovery")
        read.assert_called_once_with()
    assert response.status_code == 200
    assert anonymous.status_code == 401
    assert response.headers["cache-control"] == "private, no-store"
    assert anonymous.headers["cache-control"] == "private, no-store"


def restore_proof(**changes: object) -> dict[str, object]:
    return {
        "kind": "logical_restore_v1", "source_kind": "runtime_pg_dump", "cluster_id": 4215095,
        "release_sha": "a" * 40, "archive_sha256": "b" * 64,
        "verified_at": (NOW - timedelta(minutes=1)).isoformat(),
        "source_at": (NOW - timedelta(hours=1)).isoformat(),
        "source_system_id": "70000000000000001", "target_system_id": "70000000000000002",
        "duration_seconds": 2.5,
        "checks": {"content": True, "schema": True, "foreign_keys": True, "tenant_isolation": True},
        **changes,
    }


@pytest.mark.parametrize("mode", [
    "valid", "wrong_key", "tampered", "future", "same_cluster", "failed_check", "expired",
    "wrong_source", "unicode_signature",
])
def test_restore_status_requires_authenticated_isolated_recent_proof(
    monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    key = "synthetic-signing-key-" + "x" * 32
    monkeypatch.setenv("OMNICIO_RESTORE_RECEIPT_KEY", key)
    changes: dict[str, object] = {}
    if mode == "future":
        changes["verified_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif mode == "same_cluster":
        changes["target_system_id"] = "70000000000000001"
    elif mode == "failed_check":
        changes["checks"] = {"content": True, "schema": True,
                             "foreign_keys": True, "tenant_isolation": False}
    elif mode == "expired":
        changes.update(verified_at=(NOW - timedelta(days=31)).isoformat(),
                       source_at=(NOW - timedelta(days=32)).isoformat())
    elif mode == "wrong_source":
        changes["cluster_id"] = 99999
    proof = sign_recovery_evidence(restore_proof(**changes), key)
    if mode == "wrong_key":
        monkeypatch.setenv("OMNICIO_RESTORE_RECEIPT_KEY", "different-key-" + "y" * 32)
    elif mode == "tampered":
        proof["payload"]["duration_seconds"] = 0
    elif mode == "unicode_signature":
        proof["signature"] = "я" * 64
    payload = evidence() | {"cluster_id": 4215095, "restore_verification": proof}
    with patch("omnicio.recovery._read_evidence", return_value=payload):
        result = recovery_status(now=NOW)
    assert result["production_restore_verified"] is (mode == "valid")
    assert result["restore"]["physical_snapshot_verified"] is False
    if mode == "expired":
        assert result["restore"]["status"] == "expired"
    assert "signature" not in str(result)
    assert "70000000000000001" not in str(result)


@pytest.fixture
def upgrade_recovery_inputs() -> dict[str, Any]:
    """A synthetic archive, never a production receipt or recovery point."""
    signing_key = "synthetic-signing-key-" + "x" * 32
    cipher = Fernet(Fernet.generate_key())
    encrypted = cipher.encrypt(b"PGDMPsynthetic-recovery-test")
    raw = cipher.decrypt(encrypted)
    encrypted_sha256 = hashlib.sha256(encrypted).hexdigest()
    proof = restore_proof(
        release_sha="a775679cc353eeb64fb51721fdd963eb660e5edb",
        archive_sha256=hashlib.sha256(raw).hexdigest(),
    )
    exported = {name: proof[name] for name in (
        "source_kind", "cluster_id", "release_sha", "source_at", "source_system_id",
        "archive_sha256",
    )}
    exported.update(kind="logical_export_v1", encrypted_sha256=encrypted_sha256,
                    content_digest="c" * 64, schema_digest="d" * 64)
    return {
        "state": {"schema_version": 1, "cluster_id": 4215095,
                  "restore_verification": sign_recovery_evidence(proof, signing_key)},
        "signing_key": signing_key, "cluster_id": 4215095,
        "source_release": proof["release_sha"], "source_system_id": proof["source_system_id"],
        "now": NOW, "manifest": sign_recovery_evidence(exported, signing_key),
        "encrypted_archive_sha256": encrypted_sha256,
        "decrypted_archive_sha256": proof["archive_sha256"],
    }


def test_upgrade_uses_explicit_server_key_and_both_authenticated_archive_hashes(
    upgrade_recovery_inputs: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OMNICIO_RESTORE_RECEIPT_KEY", "untrusted-ambient-key")
    values = upgrade_recovery_inputs
    assert require_upgrade_recovery(**values) == values["state"]["restore_verification"]["payload"]


@pytest.mark.parametrize("field", sorted(RESTORE_CHECKS))
@pytest.mark.parametrize("value", [False, 1, "true"])
def test_upgrade_requires_every_restore_check_to_be_exactly_true(
    upgrade_recovery_inputs: dict[str, Any], field: str, value: object,
) -> None:
    values = upgrade_recovery_inputs
    proof = values["state"]["restore_verification"]["payload"]
    proof["checks"][field] = value
    values["state"]["restore_verification"] = sign_recovery_evidence(proof, values["signing_key"])
    with pytest.raises(ValueError, match="^recovery_proof_unverified$"):
        require_upgrade_recovery(**values)


@pytest.mark.parametrize("age,allowed", [
    (BACKUP_MAX_AGE, True), (BACKUP_MAX_AGE + timedelta(microseconds=1), False),
    (timedelta(days=29), False),
])
def test_upgrade_requires_fresh_source_even_when_restore_badge_is_verified(
    upgrade_recovery_inputs: dict[str, Any], age: timedelta, allowed: bool,
) -> None:
    values = upgrade_recovery_inputs
    proof = values["state"]["restore_verification"]["payload"]
    exported = values["manifest"]["payload"]
    proof["source_at"] = exported["source_at"] = (NOW - age).isoformat()
    values["state"]["restore_verification"] = sign_recovery_evidence(proof, values["signing_key"])
    values["manifest"] = sign_recovery_evidence(exported, values["signing_key"])
    assert _restore_verification(values["state"], NOW,
                                 signing_key=values["signing_key"])["status"] == "verified"
    if allowed:
        assert require_upgrade_recovery(**values)["source_at"] == proof["source_at"]
    else:
        with pytest.raises(ValueError, match="^recovery_source_stale$"):
            require_upgrade_recovery(**values)


@pytest.mark.parametrize("field,value,reason", [
    ("release_sha", "e" * 40, "source_mismatch"),
    ("source_system_id", "70000000000000003", "source_mismatch"),
    ("cluster_id", 99999, "proof_unverified"),
    ("target_system_id", "70000000000000001", "proof_unverified"),
    ("target_system_id", "1２３", "proof_unverified"),
    ("kind", "unverified_status", "proof_unverified"),
    ("source_kind", "provider_snapshot", "proof_unverified"),
    ("verified_at", (NOW + timedelta(seconds=1)).isoformat(), "proof_unverified"),
    ("source_at", (NOW + timedelta(seconds=1)).isoformat(), "proof_unverified"),
    ("extra_field", "private-canary", "proof_unverified"),
])
def test_upgrade_binds_proof_to_observed_source_and_supported_schema(
    upgrade_recovery_inputs: dict[str, Any], field: str, value: object, reason: str,
) -> None:
    values = upgrade_recovery_inputs
    proof = values["state"]["restore_verification"]["payload"] | {field: value}
    values["state"]["restore_verification"] = sign_recovery_evidence(proof, values["signing_key"])
    with pytest.raises(ValueError, match=f"^recovery_{reason}$"):
        require_upgrade_recovery(**values)


def test_upgrade_requires_ascii_digits_in_the_observed_system_identifier(
    upgrade_recovery_inputs: dict[str, Any],
) -> None:
    values = upgrade_recovery_inputs
    values["source_system_id"] = "1２３"
    proof = values["state"]["restore_verification"]["payload"] | {"source_system_id": "1２３"}
    exported = values["manifest"]["payload"] | {"source_system_id": "1２３"}
    values["state"]["restore_verification"] = sign_recovery_evidence(proof, values["signing_key"])
    values["manifest"] = sign_recovery_evidence(exported, values["signing_key"])
    with pytest.raises(ValueError, match="^recovery_source_identity_invalid$"):
        require_upgrade_recovery(**values)


@pytest.mark.parametrize("field,value", [
    ("kind", "logical_restore_v1"), ("source_kind", "provider_snapshot"),
    ("cluster_id", 99999), ("cluster_id", "4215095"), ("release_sha", "e" * 40),
    ("source_system_id", "70000000000000003"), ("source_at", NOW.isoformat()),
    ("archive_sha256", "f" * 64), ("content_digest", "unknown"), ("schema_digest", None),
    ("extra_field", "private-canary"),
])
def test_upgrade_binds_export_manifest_to_exact_restore_proof(
    upgrade_recovery_inputs: dict[str, Any], field: str, value: object,
) -> None:
    values = upgrade_recovery_inputs
    exported = values["manifest"]["payload"] | {field: value}
    values["manifest"] = sign_recovery_evidence(exported, values["signing_key"])
    with pytest.raises(ValueError, match="^recovery_manifest_unverified$"):
        require_upgrade_recovery(**values)


@pytest.mark.parametrize("field", ["encrypted_archive_sha256", "decrypted_archive_sha256"])
@pytest.mark.parametrize("value", [None, "", "я" * 64, "f" * 64])
def test_upgrade_requires_present_intact_encrypted_and_decrypted_archive(
    upgrade_recovery_inputs: dict[str, Any], field: str, value: object,
) -> None:
    with pytest.raises(ValueError, match="^recovery_archive_mismatch$"):
        require_upgrade_recovery(**(upgrade_recovery_inputs | {field: value}))


@pytest.mark.parametrize("path,value", [
    (("state",), {"schema_version": 1, "cluster_id": 4215095,
                  "status": "verified", "production_restore_verified": True}),
    (("signing_key",), "y" * 40), (("signing_key",), ""),
    (("state", "restore_verification", "payload", "duration_seconds"), 3),
    (("manifest", "payload", "encrypted_sha256"), "f" * 64),
    (("state", "restore_verification"), {"kind": "logical_restore_v1"}),
    (("manifest",), {"kind": "logical_export_v1"}),
    (("state", "restore_verification"), None), (("manifest",), None),
    (("state", "schema_version"), 2), (("state", "schema_version"), True),
    (("state", "cluster_id"), 99999), (("now",), NOW.replace(tzinfo=None)),
])
def test_upgrade_never_accepts_unproven_recovery_claims(
    upgrade_recovery_inputs: dict[str, Any], path: tuple[str, ...], value: object,
) -> None:
    values = upgrade_recovery_inputs
    parent = values
    for name in path[:-1]:
        parent = parent[name]
    parent[path[-1]] = value
    with pytest.raises(ValueError, match="^recovery_[a-z_]+$") as caught:
        require_upgrade_recovery(**values)
    assert values["signing_key"] not in str(caught.value) or not values["signing_key"]
    assert "private-canary" not in str(caught.value)
