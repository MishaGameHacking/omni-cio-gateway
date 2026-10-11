"""Recovery work stays on the existing Linux host; only bounded status leaves it."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
from typing import Any

import inplace_upgrade as upgrade
import psycopg
import timeweb_recovery as recovery
from cryptography.fernet import Fernet
from psycopg.conninfo import make_conninfo
from tenant_archive import export_tenant_archive

from omnicio import recovery as contract

BINARY = pathlib.Path("/usr/lib/postgresql/18/bin")
ROOT = pathlib.Path("/var/lib/omnicio-recovery")
PGDG_FINGERPRINT = "B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8"


def native(
    args: list[str], *, timeout: int = 60, user: int | None = None, group: int | None = None
) -> str:
    environment = {
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "DEBIAN_FRONTEND": "noninteractive",
        "NEEDRESTART_MODE": "l",
    }
    try:
        result = subprocess.run(
            args,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            user=user,
            group=group,
            extra_groups=[] if user is not None else None,
        )
    except (OSError, subprocess.SubprocessError):
        raise recovery.RecoveryBlocked("Recovery native command did not complete") from None
    if result.returncode:
        raise recovery.RecoveryBlocked(
            "Recovery native command failed: " + pathlib.Path(args[0]).name
        )
    return result.stdout


def atomic_file(path: pathlib.Path, data: bytes, mode: int = 0o600) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise recovery.RecoveryBlocked("Recovery destination is not an ordinary file")
    temp = path.with_name(path.name + ".recovery-new")
    with temp.open("xb") as stream:
        os.chmod(temp, mode)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def provision_postgres() -> None:
    """Signed PGDG packages; prevent package scripts creating a persistent cluster."""
    if all((BINARY / name).is_file() for name in ("pg_dump", "pg_restore", "initdb", "pg_ctl")):
        if not native([str(BINARY / "pg_dump"), "--version"]).startswith(
            "pg_dump (PostgreSQL) 18."
        ):
            raise recovery.RecoveryBlocked("PostgreSQL 18 binaries are required")
        return
    release = pathlib.Path("/etc/os-release").read_text()
    if (
        "VERSION_CODENAME=noble" not in release
        or native(["dpkg", "--print-architecture"]).strip() != "amd64"
    ):
        raise recovery.RecoveryBlocked(
            "Recovery package installation requires reviewed Ubuntu noble amd64"
        )
    native(["apt-get", "update"], timeout=180)
    native(
        [
            "apt-get",
            "install",
            "-y",
            "--no-install-recommends",
            "curl",
            "ca-certificates",
            "gnupg",
            "postgresql-common",
        ],
        timeout=180,
    )
    key = pathlib.Path("/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc")
    key.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omnicio-pgdg-") as temporary:
        downloaded = pathlib.Path(temporary) / "key.asc"
        native(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--proto",
                "=https",
                "--tlsv1.2",
                "--max-time",
                "30",
                "--output",
                str(downloaded),
                "https://www.postgresql.org/media/keys/ACCC4CF8.asc",
            ]
        )
        keys = native(["gpg", "--batch", "--show-keys", "--with-colons", str(downloaded)])
        fingerprints = [line.split(":")[9] for line in keys.splitlines() if line.startswith("fpr:")]
        if not fingerprints or fingerprints[0] != PGDG_FINGERPRINT:
            raise recovery.RecoveryBlocked("PostgreSQL repository signing key differs")
        atomic_file(key, downloaded.read_bytes(), 0o644)
    source = pathlib.Path("/etc/apt/sources.list.d/omnicio-pgdg.sources")
    atomic_file(
        source,
        (
            "Types: deb\nURIs: https://apt.postgresql.org/pub/repos/apt\nSuites: noble-pgdg\n"
            "Components: main\nArchitectures: amd64\nSigned-By: " + str(key) + "\n"
        ).encode(),
        0o644,
    )
    config = pathlib.Path("/etc/postgresql-common/createcluster.d/omnicio-recovery.conf")
    config.parent.mkdir(parents=True, exist_ok=True)
    atomic_file(config, b"create_main_cluster = false\nstart_conf = disabled\n", 0o644)
    native(["apt-get", "update"], timeout=180)
    native(
        [
            "apt-get",
            "install",
            "-y",
            "--no-install-recommends",
            "postgresql-18",
            "postgresql-client-18",
        ],
        timeout=240,
    )
    if pathlib.Path("/etc/postgresql/18/main").exists():
        raise recovery.RecoveryBlocked(
            "Unexpected persistent PostgreSQL cluster; no restore attempted"
        )


def ensure_capacity() -> None:
    memory = dict(
        line.split(":", 1) for line in pathlib.Path("/proc/meminfo").read_text().splitlines()
    )
    available = int(memory["MemAvailable"].split()[0]) * 1024
    if available < 192 * 1024 * 1024 or shutil.disk_usage(ROOT).free < 1024**3:
        raise recovery.RecoveryBlocked("Insufficient existing-host capacity for isolated recovery")


def ensure_keys() -> tuple[str, str]:
    path = pathlib.Path("/etc/omnicio/product.env")
    previous = upgrade._private_file(path, 65536)
    environment = upgrade.parse_environment(previous)
    signing = environment.get("OMNICIO_RESTORE_RECEIPT_KEY")
    archive = environment.get("OMNICIO_RESTORE_ARCHIVE_KEY")
    if bool(signing) != bool(archive):
        raise recovery.RecoveryBlocked(
            "Incomplete recovery key custody; existing keys were preserved"
        )
    if signing and archive:
        contract.sign_recovery_evidence({}, signing)
        Fernet(archive)
        return signing, archive
    if (ROOT / "database.dump.encrypted").exists() or (ROOT / "manifest.json").exists():
        raise recovery.RecoveryBlocked(
            "Existing archive has no matching keys; automatic rotation refused"
        )
    signing, archive = secrets.token_urlsafe(48), Fernet.generate_key().decode()
    updated = previous.rstrip("\n") + ("\n" if previous else "")
    updated += f"OMNICIO_RESTORE_RECEIPT_KEY={signing}\nOMNICIO_RESTORE_ARCHIVE_KEY={archive}\n"
    atomic_file(path, updated.encode())
    return signing, archive


@contextmanager
def isolated_postgres() -> Iterator[str]:
    import pwd

    account = pwd.getpwnam("postgres")
    with tempfile.TemporaryDirectory(
        prefix="omnicio-restore-", dir=recovery.RESTORE_ROOT
    ) as temporary:
        directory = pathlib.Path(temporary)
        os.chown(directory, account.pw_uid, account.pw_gid)
        password = secrets.token_urlsafe(32)
        password_file = directory / "password"
        password_file.write_text(password)
        os.chmod(password_file, 0o600)
        os.chown(password_file, account.pw_uid, account.pw_gid)
        run = partial(native, timeout=60, user=account.pw_uid, group=account.pw_gid)
        data = directory / "data"
        run(
            [
                str(BINARY / "initdb"),
                "-D",
                str(data),
                "-U",
                "postgres",
                "--auth=scram-sha-256",
                "--encoding=UTF8",
                "--no-locale",
                "--pwfile",
                str(password_file),
            ]
        )
        password_file.unlink()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        control = [str(BINARY / "pg_ctl"), "-D", str(data), "-w", "-t", "30"]
        options = (
            f"-h 127.0.0.1 -p {port} -c shared_buffers=16MB -c work_mem=1MB "
            "-c maintenance_work_mem=16MB -c max_connections=10 "
            "-c autovacuum=off -c max_parallel_workers=0 -c jit=off"
        )
        try:
            run([*control, "-l", str(directory / "postgres.log"), "-o", options, "start"])
            yield make_conninfo(
                host="127.0.0.1",
                port=port,
                dbname="postgres",
                user="postgres",
                password=password,
                connect_timeout=10,
            )
        finally:
            if (data / "postmaster.pid").exists():
                run([*control, "-m", "immediate", "stop"])


def publish_evidence(
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    signing: str,
    archive_key: str,
    expected: dict[str, Any],
    source_release: str,
) -> None:
    state_path = ROOT / "status.json"
    state = json.loads(upgrade._operational_bytes(state_path, 16384, private=False))
    if state.get("schema_version") != 1 or state.get("cluster_id") != expected["cluster_id"]:
        raise recovery.RecoveryBlocked("Recovery state belongs to another database")
    encrypted = recovery.restore_artifact_path(recovery.ENCRYPTED_ARCHIVE_NAME).read_bytes()
    raw = Fernet(archive_key).decrypt(encrypted)
    updated = dict(state, restore_verification=receipt)
    contract.require_upgrade_recovery(
        updated,
        signing,
        cluster_id=expected["cluster_id"],
        source_release=source_release,
        source_system_id=manifest["payload"]["source_system_id"],
        now=datetime.now(UTC),
        manifest=manifest,
        encrypted_archive_sha256=hashlib.sha256(encrypted).hexdigest(),
        decrypted_archive_sha256=hashlib.sha256(raw).hexdigest(),
    )
    atomic_file(ROOT / recovery.ENCRYPTED_ARCHIVE_NAME, encrypted)
    atomic_file(ROOT / "manifest.json", json.dumps(manifest).encode())
    atomic_file(state_path, json.dumps(updated).encode(), 0o644)


def recover(payload: dict[str, Any]) -> dict[str, Any]:
    if sys.platform != "linux" or os.geteuid() != 0:
        raise recovery.RecoveryBlocked("Recovery requires the existing Linux host operator")
    plan = upgrade.validate_plan(payload["plan"])
    expected = payload["database"]
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.stat().st_uid != 0:
        raise recovery.RecoveryBlocked("Existing server recovery directory is not trusted")
    with upgrade._operation_lock():
        source_query, installed = upgrade._existing_installation(plan, None, payload["release_sha"])
        dsn = upgrade._database_url(expected)
        with psycopg.connect(dsn, autocommit=True) as source:
            upgrade._verify_connected_database(source, expected)
            if source.execute(source_query).fetchone() != (True,):
                raise recovery.RecoveryBlocked("Source schema differs from reviewed installation")
        signing, archive = ensure_keys()
        ensure_capacity()
        provision_postgres()
        ensure_capacity()
        with isolated_postgres() as isolated:
            manifest = export_tenant_archive(
                dsn,
                isolated,
                BINARY,
                cluster_id=expected["cluster_id"],
                source_release=installed,
                signing_key=signing,
                archive_key=archive,
            )
            receipt = recovery.verify_logical_archive(
                isolated,
                BINARY,
                manifest,
                release_sha=installed,
                signing_key=signing,
                archive_key=archive,
            )
        # Only after successful destruction of temporary databases and cluster.
        if upgrade.CURRENT_RELEASE.resolve().name != installed:
            raise recovery.RecoveryBlocked("Installed source changed during recovery verification")
        publish_evidence(manifest, receipt, signing, archive, expected, installed)
        with psycopg.connect(dsn, autocommit=True) as source:
            upgrade._require_recovery(source, plan, expected, contract.require_upgrade_recovery)
    return {
        "status": "recovery_verified",
        "cluster_id": expected["cluster_id"],
        "source_release": installed,
        "operator_release": payload["release_sha"],
        "new_servers": 0,
        "permanent_database_clones": 0,
        "temporary_restore_removed": True,
        "source_kind": "tenant_snapshot_pg_dump",
    }
