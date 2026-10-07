from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from omnicio.db import UserRecord
from omnicio.main import app
from omnicio.recovery import recovery_status, sign_recovery_evidence

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
