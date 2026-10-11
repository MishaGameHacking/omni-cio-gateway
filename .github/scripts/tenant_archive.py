"""Native archive of an exhaustive RLS snapshot; no production policy/role changes."""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import secrets
import tempfile
from typing import Any
from uuid import UUID

import psycopg
import timeweb_recovery as recovery
from cryptography.fernet import Fernet
from inplace_upgrade import MAX_LOGICAL_ARCHIVE_BYTES
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio import recovery as contract

TENANT_QUAL = "(user_id = (NULLIF(current_setting('omnicio.user_id'::text, true), ''::text))::uuid)"
MAX_TENANTS = 1000


def tenant_partition(source: Any) -> tuple[list[str], dict[str, list[str]]]:
    """Prove each RLS row belongs to exactly one enumerated user."""
    if source.execute(
        "SELECT relrowsecurity FROM pg_class WHERE oid = 'public.users'::regclass",
    ).fetchone() != (False,):
        raise recovery.RecoveryBlocked("Backup requires an unfiltered users registry")
    users = [str(row[0]) for row in source.execute("SELECT id FROM users ORDER BY id").fetchall()]
    if len(users) > MAX_TENANTS or any(str(UUID(identity)) != identity for identity in users):
        raise recovery.RecoveryBlocked("Backup tenant inventory exceeds its reviewed boundary")
    scopes: dict[str, list[str]] = {}
    for name, enabled, forced, _policy, qualifier, check in contract.database_guards(source):
        if not enabled:
            continue
        if not forced or qualifier != TENANT_QUAL or check != TENANT_QUAL or name in scopes:
            raise recovery.RecoveryBlocked("Backup cannot prove an exhaustive tenant policy")
        _validate_partition_table(source, name)
        scopes[name] = users
    if not scopes:
        raise recovery.RecoveryBlocked("Expected tenant-isolated source tables")
    return users, scopes


def _validate_partition_table(source: Any, name: str) -> None:
    if re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name) is None:
        raise recovery.RecoveryBlocked("Unsupported backup table identifier")
    relation = f"public.{name}"
    if source.execute(
        """
        SELECT a.attnotnull AND EXISTS (
            SELECT 1 FROM pg_constraint c
            WHERE c.conrelid = a.attrelid AND c.contype = 'f' AND c.convalidated
              AND c.confrelid = 'public.users'::regclass AND c.conkey = ARRAY[a.attnum]
              AND c.confkey = ARRAY[(SELECT attnum FROM pg_attribute
                  WHERE attrelid = 'public.users'::regclass AND attname = 'id')]
        ) FROM pg_attribute a WHERE a.attrelid = %s::regclass AND a.attname = 'user_id'
    """,
        (relation,),
    ).fetchone() != (True,):
        raise recovery.RecoveryBlocked("Backup tenant ownership is not exhaustive")
    policy = source.execute(
        "SELECT polcmd, polpermissive, polroles FROM pg_policy WHERE polrelid = %s::regclass",
        (relation,),
    ).fetchall()
    if policy != [("*", True, [0])]:
        raise recovery.RecoveryBlocked("Backup tenant policy applies to a restricted role")


def _native(
    binary: pathlib.Path, name: str, args: list[str], dsn: str, tenant: str | None = None
) -> None:
    recovery._postgres_process(
        binary / (name + (".exe" if os.name == "nt" else "")), args, dsn, tenant=tenant
    )


def _size_guard(directory: pathlib.Path) -> None:
    if sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > 64 * 1024 * 1024:
        raise recovery.RecoveryBlocked("Recovery snapshot exceeds the reviewed size bound")


def _snapshot_archives(
    source: Any,
    dsn: str,
    binary: pathlib.Path,
    directory: pathlib.Path,
    users: list[str],
    scopes: dict[str, list[str]],
) -> dict[str, Any]:
    snapshot, observed, system_id = source.execute(
        "SELECT pg_export_snapshot(), now(), system_identifier::text FROM pg_control_system()",
    ).fetchone()
    base = ["--format=custom", "--no-password", "--no-owner", "--no-acl", "--snapshot", snapshot]
    exclusions = [f"--exclude-table-data=public.{name}" for name in scopes]
    _native(binary, "pg_dump", [*base, *exclusions, "--file", str(directory / "global.dump")], dsn)
    _size_guard(directory)
    tables = [f"--table=public.{name}" for name in scopes]
    for index, identity in enumerate(users):
        target = directory / f"tenant-{index}.dump"
        _native(
            binary,
            "pg_dump",
            [*base, "--enable-row-security", "--data-only", *tables, "--file", str(target)],
            dsn,
            identity,
        )
        _size_guard(directory)
    return {
        "source_at": observed.isoformat(),
        "source_system_id": system_id,
        "content_digest": contract.evidence_digest(contract.snapshot_fingerprints(source, scopes)),
        "schema_digest": contract.evidence_digest(contract.database_guards(source)),
    }


def _restore_parts(target: str, name: str, binary: pathlib.Path, directory: pathlib.Path) -> None:
    args = [
        "--exit-on-error",
        "--single-transaction",
        "--no-password",
        "--no-owner",
        "--no-acl",
        "--dbname",
        name,
    ]
    global_dump = str(directory / "global.dump")
    for section in ("pre-data", "data"):
        _native(binary, "pg_restore", [*args, "--section", section, global_dump], target)
    for archive in sorted(directory.glob("tenant-*.dump")):
        _native(binary, "pg_restore", [*args, str(archive)], target)
    _native(binary, "pg_restore", [*args, "--section", "post-data", global_dump], target)


def _assemble(
    isolated_dsn: str, binary: pathlib.Path, directory: pathlib.Path, evidence: dict[str, Any]
) -> bytes:
    name = "omnicio_stage_" + secrets.token_hex(12)
    with psycopg.connect(isolated_dsn, autocommit=True) as control:
        observed = control.execute(
            "SELECT system_identifier::text FROM pg_control_system()",
        ).fetchone()
        if observed is None:
            raise recovery.RecoveryBlocked("Restore cluster identity is unavailable")
        target_id = observed[0]
        if target_id == evidence["source_system_id"]:
            raise recovery.RecoveryBlocked("Restore destination is the source cluster")
        control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            target = make_conninfo(isolated_dsn, dbname=name)
            _restore_parts(target, name, binary, directory)
            with psycopg.connect(target) as restored:
                actual = contract.evidence_digest(contract.snapshot_fingerprints(restored))
                if actual != evidence["content_digest"]:
                    raise recovery.RecoveryBlocked("Assembled archive contents differ from source")
                if (
                    contract.evidence_digest(contract.database_guards(restored))
                    != evidence["schema_digest"]
                ):
                    raise recovery.RecoveryBlocked("Assembled archive policies differ from source")
            complete = directory / "complete.dump"
            _native(
                binary,
                "pg_dump",
                [
                    "--format=custom",
                    "--no-password",
                    "--no-owner",
                    "--no-acl",
                    "--file",
                    str(complete),
                ],
                target,
            )
            if not 0 < complete.stat().st_size <= MAX_LOGICAL_ARCHIVE_BYTES:
                raise recovery.RecoveryBlocked("Complete recovery archive exceeds its size bound")
            return complete.read_bytes()
        finally:
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def export_tenant_archive(
    source_dsn: str,
    isolated_dsn: str,
    binary: pathlib.Path,
    *,
    cluster_id: int,
    source_release: str,
    signing_key: str,
    archive_key: str,
) -> dict[str, Any]:
    options = conninfo_to_dict(isolated_dsn)
    if (
        options.get("host") != "127.0.0.1"
        or options.get("dbname") != "postgres"
        or "hostaddr" in options
        or "service" in options
    ):
        raise recovery.RecoveryBlocked("An isolated loopback restore destination is required")
    contract.sign_recovery_evidence({}, signing_key)
    cipher = Fernet(archive_key)
    with tempfile.TemporaryDirectory(prefix="omnicio-snapshot-") as temporary:
        directory = pathlib.Path(temporary)
        with psycopg.connect(source_dsn) as source:
            source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            source.execute("SET LOCAL statement_timeout = '120s'")
            users, scopes = tenant_partition(source)
            evidence = _snapshot_archives(source, source_dsn, binary, directory, users, scopes)
        raw = _assemble(isolated_dsn, binary, directory, evidence)
    if not raw.startswith(b"PGDMP"):
        raise recovery.RecoveryBlocked("Expected a native PostgreSQL custom archive")
    encrypted = cipher.encrypt(raw)
    recovery.restore_artifact_path().mkdir(parents=True, mode=0o700, exist_ok=False)
    archive = recovery.restore_artifact_path(recovery.ENCRYPTED_ARCHIVE_NAME)
    with archive.open("xb") as stream:
        os.chmod(archive, 0o600)
        stream.write(encrypted)
    payload = {
        "kind": "logical_export_v1",
        "source_kind": "tenant_snapshot_pg_dump",
        "cluster_id": cluster_id,
        "release_sha": source_release,
        **evidence,
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "encrypted_sha256": hashlib.sha256(encrypted).hexdigest(),
    }
    manifest = contract.sign_recovery_evidence(payload, signing_key)
    recovery._private_json("manifest.json", manifest)
    return manifest
