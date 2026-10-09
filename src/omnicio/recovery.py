"""Expose bounded backup evidence without claiming that a restore was verified."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from psycopg import Connection, sql

from .freshness import FreshnessDTO, describe_freshness

INVENTORY_MAX_AGE = timedelta(hours=8)
BACKUP_MAX_AGE = timedelta(hours=24)
BACKUP_TIMEZONE = timezone(timedelta(hours=3))
RESTORE_MAX_AGE = timedelta(days=30)
RESTORE_CHECKS = frozenset({"content", "schema", "foreign_keys", "tenant_isolation"})


def sign_recovery_evidence(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Only the accepted-main operator tool holds this key; never accept browser receipts."""
    if len(key) < 32:
        raise ValueError("recovery_signing_key_required")
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(body) > 16384:
        raise ValueError("recovery_receipt_too_large")
    signature = hmac.new(key.encode(), b"omnicio-recovery-v1\x00" + body, "sha256").hexdigest()
    return {"payload": payload, "signature": signature}


def verified_recovery_evidence(envelope: object, key: str) -> dict[str, Any] | None:
    if (not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}
            or not isinstance(envelope["payload"], dict)
            or not isinstance(envelope["signature"], str)
            or re.fullmatch(r"[0-9a-f]{64}", envelope["signature"]) is None):
        return None
    try:
        expected = sign_recovery_evidence(envelope["payload"], key)["signature"]
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(expected, envelope["signature"]):
        return None
    return envelope["payload"]


def table_fingerprints(conn: Connection[Any]) -> dict[str, tuple[int, str]]:
    """Stream deterministic row hashes from a repeatable snapshot, without logging data."""
    result: dict[str, tuple[int, str]] = {}
    with conn.transaction():
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        tables = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename",
        ).fetchall()
        for (name,) in tables:
            count = 0
            digest = hashlib.sha256()
            with conn.cursor(name="omnicio_fingerprint") as rows:
                rows.execute(sql.SQL(
                    "SELECT row_to_json(t)::text FROM {} AS t ORDER BY row_to_json(t)::text",
                ).format(sql.Identifier("public", name)))
                for (row,) in rows:
                    if count:
                        digest.update(b"\n")
                    digest.update(row.encode())
                    count += 1
            result[name] = (count, digest.hexdigest())
    return result


def database_guards(conn: Connection[Any]) -> list[Any]:
    return conn.execute("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
               p.policyname, p.qual, p.with_check
        FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
        LEFT JOIN pg_policies p ON p.schemaname = n.nspname AND p.tablename = c.relname
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname, p.policyname
    """).fetchall()


def evidence_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False,
    ).encode()).hexdigest()


def _restore_verification(
    payload: dict[str, object], now: datetime, *, signing_key: str | None = None,
) -> dict[str, object]:
    proof = verified_recovery_evidence(
        payload.get("restore_verification"),
        os.environ.get("OMNICIO_RESTORE_RECEIPT_KEY", "") if signing_key is None else signing_key,
    )
    absent: dict[str, object] = {"status": "not_verified", "physical_snapshot_verified": False}
    if proof is None:
        return absent
    verified_at = _timestamp(proof.get("verified_at"))
    source_at = _timestamp(proof.get("source_at"))
    checks = proof.get("checks")
    if (proof.get("kind") != "logical_restore_v1"
            or proof.get("source_kind") != "runtime_pg_dump"
            or type(proof.get("cluster_id")) is not int
            or proof["cluster_id"] != payload.get("cluster_id")
            or verified_at is None or source_at is None or not source_at <= verified_at <= now
            or not isinstance(checks, dict) or set(checks) != RESTORE_CHECKS
            or any(value is not True for value in checks.values())
            or not isinstance(proof.get("release_sha"), str)
            or re.fullmatch(r"[0-9a-f]{40}", proof["release_sha"]) is None
            or not isinstance(proof.get("archive_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", proof["archive_sha256"]) is None
            or not isinstance(proof.get("source_system_id"), str)
            or not isinstance(proof.get("target_system_id"), str)
            or not proof["source_system_id"].isdigit() or not proof["target_system_id"].isdigit()
            or proof["source_system_id"] == proof["target_system_id"]
            or type(proof.get("duration_seconds")) not in {int, float}
            or not 0 <= proof["duration_seconds"] <= 3600):
        return absent
    return {
        "status": "verified" if now - verified_at < RESTORE_MAX_AGE else "expired",
        "method": "isolated_logical_restore", "physical_snapshot_verified": False,
        "verified_at": verified_at, "source_at": source_at,
        "release_sha": proof["release_sha"], "duration_seconds": proof["duration_seconds"],
    }


def require_upgrade_recovery(
    state: object, signing_key: str, *, cluster_id: int, source_release: str,
    source_system_id: str, now: datetime, manifest: object,
    encrypted_archive_sha256: str, decrypted_archive_sha256: str,
) -> dict[str, Any]:
    """Authenticate a fresh restore point for the observed production source.

    The accepted controller reads private files and both keys on the existing
    server. It hashes the encrypted archive and its bounded, authenticated
    PostgreSQL plaintext in memory; neither rows nor keys leave that server.
    This verifier performs no I/O and cannot create or restore a database.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("recovery_clock_unavailable")
    if (type(cluster_id) is not int or cluster_id <= 0
            or not isinstance(source_release, str)
            or re.fullmatch(r"[0-9a-f]{40}", source_release) is None
            or not isinstance(source_system_id, str)
            or re.fullmatch(r"[1-9][0-9]{0,19}", source_system_id) is None):
        raise ValueError("recovery_source_identity_invalid")
    if (not isinstance(state, dict) or type(state.get("schema_version")) is not int
            or state["schema_version"] != 1 or type(state.get("cluster_id")) is not int
            or state["cluster_id"] != cluster_id):
        raise ValueError("recovery_state_mismatch")
    proof = verified_recovery_evidence(state.get("restore_verification"), signing_key)
    required = {"kind", "source_kind", "cluster_id", "release_sha", "source_at",
                "source_system_id", "target_system_id", "archive_sha256", "verified_at",
                "duration_seconds", "checks"}
    if (proof is None or set(proof) != required
            or _restore_verification(state, now, signing_key=signing_key)["status"] != "verified"
            or re.fullmatch(r"[1-9][0-9]{0,19}", proof["target_system_id"]) is None):
        raise ValueError("recovery_proof_unverified")
    if (proof["release_sha"] != source_release
            or proof["source_system_id"] != source_system_id):
        raise ValueError("recovery_source_mismatch")
    source_at = _timestamp(proof["source_at"])
    if source_at is None or not timedelta(0) <= now - source_at <= BACKUP_MAX_AGE:
        raise ValueError("recovery_source_stale")
    _require_upgrade_archive(
        proof, manifest, signing_key, encrypted_archive_sha256=encrypted_archive_sha256,
        decrypted_archive_sha256=decrypted_archive_sha256,
    )
    return proof


def _require_upgrade_archive(
    proof: dict[str, Any], manifest: object, signing_key: str, *,
    encrypted_archive_sha256: str, decrypted_archive_sha256: str,
) -> None:
    """Bind the observed encrypted and decrypted bytes to the signed restore proof."""
    exported = verified_recovery_evidence(manifest, signing_key)
    export_fields = {"kind", "source_kind", "cluster_id", "release_sha", "source_at",
                     "source_system_id", "archive_sha256", "encrypted_sha256",
                     "content_digest", "schema_digest"}
    if (exported is None or set(exported) != export_fields
            or exported["kind"] != "logical_export_v1"
            or exported["source_kind"] != "runtime_pg_dump"
            or type(exported["cluster_id"]) is not int
            or any(exported[name] != proof[name] for name in (
                "cluster_id", "release_sha", "source_at", "source_system_id", "archive_sha256",
            ))
            or any(not isinstance(exported[name], str)
                   or re.fullmatch(r"[0-9a-f]{64}", exported[name]) is None
                   for name in ("encrypted_sha256", "content_digest", "schema_digest"))):
        raise ValueError("recovery_manifest_unverified")
    if (not isinstance(encrypted_archive_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", encrypted_archive_sha256) is None
            or not isinstance(decrypted_archive_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", decrypted_archive_sha256) is None
            or not hmac.compare_digest(exported["encrypted_sha256"], encrypted_archive_sha256)
            or not hmac.compare_digest(proof["archive_sha256"], decrypted_archive_sha256)):
        raise ValueError("recovery_archive_mismatch")


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result.astimezone(UTC) if result.tzinfo else None


def _read_evidence() -> dict[str, object]:
    """The file is produced by accepted-main infrastructure, never by HTTP input."""
    configured = os.environ.get("OMNICIO_RECOVERY_STATUS_PATH", "")
    if not configured:
        return {}
    try:
        with Path(configured).open("rb") as handle:
            raw = handle.read(8193)
        if len(raw) > 8192:
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("schema_version") == 1:
            return parsed
    except (OSError, ValueError):
        # Missing, truncated or inaccessible evidence never becomes a green badge.
        return {}
    return {}


def _weekly_evidence(payload: dict[str, object], now: datetime) -> tuple[FreshnessDTO, int | None]:
    created = _timestamp(payload.get("latest_weekly_backup_at"))
    due = _timestamp(payload.get("weekly_next_due_at"))
    copies = payload.get("weekly_available_copies")
    valid = (
        created is not None and due is not None
        and type(copies) is int and 1 <= copies <= 4
        and type(payload.get("weekly_retention_copies")) is int
        and payload["weekly_retention_copies"] == 4
    )
    max_age = timedelta(days=7)
    if valid and created is not None and due is not None:
        local = created.astimezone(BACKUP_TIMEZONE)
        monday = (local - timedelta(days=local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        valid = due == monday + timedelta(days=7)
        valid = valid and payload.get("weekly_period") == monday.date().isoformat()
        if valid:
            max_age = due - created
    freshness = describe_freshness(
        created if valid else None, max_age=max_age, coverage="complete", now=now,
    )
    return freshness, copies if type(copies) is int and freshness.status == "fresh" else None


def _status_label(
    inventory: FreshnessDTO, backup: FreshnessDTO, weekly: FreshnessDTO,
    daily: bool, copies: int | None,
) -> str:
    if inventory.status == "stale":
        return "check_stale"
    if inventory.status != "fresh":
        return "unavailable"
    if backup.status == "unavailable":
        return "missing"
    if backup.status == "stale":
        return "backup_stale"
    if not daily or copies is None or copies < 7:
        return "schedule_attention"
    if weekly.status != "fresh":
        return "weekly_attention"
    return "fresh"


def recovery_status(*, now: datetime | None = None) -> dict[str, object]:
    checked_at = now or datetime.now(UTC)
    payload = _read_evidence()

    inventory = describe_freshness(
        _timestamp(payload.get("observed_at")), max_age=INVENTORY_MAX_AGE,
        coverage="complete" if payload.get("provider_status") == "ok" else "unknown",
        now=checked_at,
    )
    backup = describe_freshness(
        _timestamp(payload.get("latest_backup_at")), max_age=BACKUP_MAX_AGE,
        coverage="complete", now=checked_at,
    )
    single_database = payload.get("policy_mode") == "single_existing_database"
    # Historical mutation receipts remain on disk; they are not a fresh managed
    # retention inventory once automatic copy creation has been disabled.
    weekly, weekly_copies = _weekly_evidence({} if single_database else payload, checked_at)
    copies = None if single_database else payload.get("retention_copies")
    if type(copies) is not int or not 1 <= copies <= 99:
        copies = None
    daily = payload.get("schedule_enabled") is True and payload.get("schedule_interval") == "day"
    restoration = _restore_verification(payload, checked_at)
    copying_disabled = (
        single_database and payload.get("copy_creation_enabled") is False
        and payload.get("schedule_enabled") is False and inventory.status == "fresh"
    )
    return {
        "status": ("copying_disabled" if copying_disabled
                   else _status_label(inventory, backup, weekly, daily, copies)),
        "copy_creation_enabled": False if copying_disabled else None,
        "checked_at": checked_at,
        "freshness": asdict(inventory),
        "backup": asdict(backup),
        "daily_schedule": daily if inventory.status == "fresh" else None,
        "retention_copies": copies if inventory.status == "fresh" else None,
        "weekly": {
            **asdict(weekly),
            "available_copies": weekly_copies if inventory.status == "fresh" else None,
            "retention_copies": (
                4 if weekly_copies is not None and inventory.status == "fresh" else None
            ),
        },
        "production_restore_verified": restoration["status"] == "verified",
        "restore": restoration,
    }
