"""Manual production logical export -> isolated restore -> signed runtime receipt.

Never run from scheduled reconciliation. Source custody requires an explicit
read-only export DSN with verified TLS and private-network reachability. The
target is a newly initialized password-protected loopback PostgreSQL cluster.
No Timeweb database, storage bucket, or billable destination is created.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any

from cryptography.fernet import Fernet
from host_recovery import validate_failure_report
from inplace_upgrade import load_plan
from psycopg.conninfo import make_conninfo
from test_with_postgres import _wait_owned_process, available_port, install_binaries
from timeweb_auth_postgres import (
    DesiredDatabase,
    EphemeralSsh,
    TimewebClient,
    find_managed_server,
    private_database_endpoint,
    public_ipv4,
    validate_existing_cluster,
)
from timeweb_recovery import (
    RecoveryBlocked,
    _private_json,
    export_logical_archive,
    install_restore_receipt,
    load_policy,
    restore_artifact_path,
    validate_export_source,
    verify_logical_archive,
)
from timeweb_ssh_trust import managed_server_identity, trusted_host_entry
from verify_main_release import release_context, require_checkout, wait_for_main_release

from omnicio.recovery import sign_recovery_evidence


def authorize() -> tuple[str, str]:
    if load_policy().mode == "single_existing_database":
        raise RecoveryBlocked("Production export is disabled by the single-database policy")
    if (
        os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("OMNICIO_RESTORE_DRILL_ALLOWED") != "true"
    ):
        raise RecoveryBlocked("An explicit accepted-main restore-drill dispatch is required")
    sha, token = release_context()
    require_checkout(sha)
    wait_for_main_release(sha, token, timeout=600)
    return sha, token


def native(command: list[str], *, timeout: int) -> None:
    # These reviewed native programs do not inherit production DSN/crypto secrets.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "LANG"}
    }
    try:
        # Windows PostgreSQL can inherit pg_ctl's pipe handles even with -l.
        # Popen.wait + real null handles avoids reader threads waiting forever
        # after pg_ctl exits; the shared supervisor kills only this owned tree.
        process = subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        code, stopped = _wait_owned_process(process, timeout, "Disposable PostgreSQL command")
    except (OSError, subprocess.SubprocessError):
        raise RecoveryBlocked("Disposable PostgreSQL process did not complete") from None
    if code or not stopped:
        raise RecoveryBlocked("Disposable PostgreSQL process failed")


def main() -> int:
    if sys.argv[1:] == ["--on-host"]:
        return host_main()
    if sys.argv[1:] == ["--cleanup-artifact"]:
        # Exactly this job's fixed generated directory; never caller-selected paths.
        artifact_directory = restore_artifact_path()
        if artifact_directory.is_dir():
            shutil.rmtree(artifact_directory)
        return 0
    if sys.argv[1:] or sys.platform != "win32":
        raise RecoveryBlocked("The manual restore drill requires the reviewed Windows runner")
    sha, token = authorize()
    signing_key = os.environ.get("OMNICIO_RESTORE_RECEIPT_KEY", "")
    archive_key = os.environ.get("OMNICIO_RESTORE_ARCHIVE_KEY", "")
    source = os.environ.get("OMNICIO_RESTORE_SOURCE_DSN", "")
    if not source:
        raise RecoveryBlocked("The explicit read-only production export DSN is not configured")
    sign_recovery_evidence({}, signing_key)
    Fernet(archive_key)
    client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
    validate_export_source(source, client)
    managed_id, managed_ip = managed_server_identity()
    server = find_managed_server(
        client.get_servers(),
        name="omni-cio-white-site",
        comment="Managed by GitHub Actions: timeweb-white-site",
    )
    if server.get("id") != managed_id or public_ipv4(server) != managed_ip:
        raise RecoveryBlocked("Runtime server differs from the reviewed deployment target")
    trusted_host_entry(os.environ.get("TIMEWEB_SSH_KNOWN_HOSTS", ""), managed_ip)
    if restore_artifact_path().exists():
        raise RecoveryBlocked("A previous restore artifact must be cleaned before another drill")
    receipt = None
    # Plaintext backup and restored rows never enter uploaded artifact paths.
    # The directory remains owned by this invocation and is removed before proof installation.
    with tempfile.TemporaryDirectory(prefix="omnicio-private-restore-") as temporary:
        directory = pathlib.Path(temporary)
        binary = install_binaries(directory / "postgres")
        data = directory / "data"
        password = secrets.token_urlsafe(40)
        password_file = directory / "password"
        with password_file.open("x", encoding="utf-8") as password_stream:
            os.chmod(password_file, 0o600)
            password_stream.write(password)
        native(
            [
                str(binary / "initdb.exe"),
                "-D",
                str(data),
                "-U",
                "postgres",
                "--auth=scram-sha-256",
                "--encoding=UTF8",
                "--no-locale",
                "--pwfile",
                str(password_file),
            ],
            timeout=60,
        )
        password_file.unlink()
        port = available_port()
        control = [str(binary / "pg_ctl.exe"), "-D", str(data), "-w", "-t", "30"]
        try:
            native(
                [
                    *control,
                    "-l",
                    str(directory / "postgres.log"),
                    "-o",
                    f"-h 127.0.0.1 -p {port}",
                    "start",
                ],
                timeout=45,
            )
            target = make_conninfo(
                host="127.0.0.1",
                port=port,
                dbname="postgres",
                user="postgres",
                password=password,
                connect_timeout=10,
            )
            manifest = export_logical_archive(
                source,
                binary,
                cluster_id=load_policy().cluster_id,
                release_sha=sha,
                signing_key=signing_key,
                archive_key=archive_key,
            )
            receipt = verify_logical_archive(
                target,
                binary,
                manifest,
                release_sha=sha,
                signing_key=signing_key,
                archive_key=archive_key,
            )
        finally:
            if (data / "postmaster.pid").exists():
                native([*control, "-m", "fast", "stop"], timeout=45)
    if receipt is None:
        raise RecoveryBlocked("No isolated restore proof was produced")
    _private_json("restore-verification.json", receipt)
    # Refuse an obsolete source checkout before touching operational runtime state.
    require_checkout(sha)
    wait_for_main_release(sha, token, timeout=600)
    with EphemeralSsh(client=client, server_id=managed_id, server_ip=managed_ip) as ssh:
        install_restore_receipt(ssh, receipt, sha)
    print(
        "Logical restore proof verified and installed; "
        "physical snapshot restore remains unverified."
    )
    return 0


HOST_FILES = (
    "pyproject.toml",
    ".github/scripts/inplace_upgrade.py",
    ".github/scripts/timeweb_recovery.py",
    ".github/scripts/host_recovery.py",
    ".github/scripts/tenant_archive.py",
    "src/omnicio/recovery.py",
    "src/omnicio/freshness.py",
)


def authorize_host() -> tuple[str, str]:
    root = pathlib.Path(__file__).resolve().parents[2]
    settings = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["omnicio"]["timeweb"]
    if (
        settings.get("manual_host_recovery") is not True
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("OMNICIO_RESTORE_DRILL_ALLOWED") != "true"
    ):
        raise RecoveryBlocked("Explicit accepted-main host recovery authority is required")
    sha, token = release_context()
    require_checkout(sha)
    wait_for_main_release(sha, token, timeout=600)
    return sha, token


def host_program(payload: dict[str, Any]) -> str:
    root = pathlib.Path(__file__).resolve().parents[2]
    files = {name: (root / name).read_text(encoding="utf-8") for name in HOST_FILES}
    encoded = base64.b64encode(json.dumps({"files": files, "payload": payload}).encode()).decode()
    return (
        """import base64, json, os, pathlib, shutil, signal, sys, tempfile
root = pathlib.Path('/var/lib/omnicio-recovery')
work = root / 'work'
if os.geteuid() != 0 or root.is_symlink() or not root.is_dir() or root.stat().st_uid != 0:
    raise SystemExit('Recovery host directory is not trusted')
if work.exists() or work.is_symlink():
    if work.is_symlink() or not work.is_dir() or work.stat().st_uid != 0:
        raise SystemExit('Recovery work directory is not owned')
    marker = work / '.omnicio-owned'
    if not marker.is_file() or marker.is_symlink() or marker.read_text() != 'on-host-recovery-v1':
        raise SystemExit('Unknown recovery work directory')
    shutil.rmtree(work)
work.mkdir(mode=0o711)
(work / '.omnicio-owned').write_text('on-host-recovery-v1')
os.chmod(work / '.omnicio-owned', 0o600)
def interrupted(_signal, _frame):
    raise RuntimeError('Recovery operation interrupted')
signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGHUP, interrupted)
observation = {'stage': 'bootstrap'}
try:
    bundle = json.loads(base64.b64decode('"""
        + encoded
        + """'))
    for name, content in bundle['files'].items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    (work / 'src/omnicio/__init__.py').write_text('')
    scratch = work / 'scratch'
    scratch.mkdir(mode=0o700)
    tempfile.tempdir = str(scratch)
    sys.path.insert(0, str(work / '.github/scripts'))
    sys.path.insert(0, str(work / 'src'))
    from host_recovery import recover
    print(json.dumps(recover(bundle['payload'], observation=observation)), flush=True)
except Exception as exc:
    from host_recovery import failure_report
    # Complete transport normally so the controller can read the safe failure report.
    # The controller rejects this result and fails CI; no failure becomes success.
    print(json.dumps(failure_report(observation['stage'], exc)), flush=True)
finally:
    shutil.rmtree(work)
"""
    )


def parse_host_report(raw: str, payload: dict[str, Any]) -> dict[str, Any]:
    if len(raw) > 16384:
        raise RecoveryBlocked("Host recovery report exceeded its safe bound")
    report = json.loads(raw)
    if validate_failure_report(report):
        print(json.dumps(report, sort_keys=True))
        raise RecoveryBlocked("Host recovery did not complete; see the safe stage report")
    if (
        not isinstance(report, dict)
        or set(report) != {
            "status", "cluster_id", "source_release", "operator_release", "new_servers",
            "permanent_database_clones", "temporary_restore_removed", "source_runtime_paused",
            "source_kind",
        }
        or report["status"] != "recovery_verified"
        or report["cluster_id"] != payload["database"]["cluster_id"]
        or report["source_release"] != payload["plan"]["source_release"]
        or report["operator_release"] != payload["release_sha"]
        or report["new_servers"] != 0 or report["permanent_database_clones"] != 0
        or report["temporary_restore_removed"] is not True
        or type(report["source_runtime_paused"]) is not bool
        or report["source_kind"] != "tenant_snapshot_pg_dump"
    ):
        raise RecoveryBlocked("Host recovery result was not confirmed; inspect before retrying")
    return report


def host_main() -> int:
    sha, token = authorize_host()
    client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
    managed_id, managed_ip = managed_server_identity()
    server = find_managed_server(
        client.get_servers(),
        name="omni-cio-white-site",
        comment="Managed by GitHub Actions: timeweb-white-site",
    )
    if server.get("id") != managed_id or public_ipv4(server) != managed_ip:
        raise RecoveryBlocked("Runtime server differs from the reviewed target")
    cluster_id = load_policy().cluster_id
    cluster = client.get_database_cluster(cluster_id)
    desired = DesiredDatabase(
        "omnicio-auth-postgres", "omnicio", "omnicio_app", "18", "ru-3", "msk-1"
    )
    validate_existing_cluster(cluster, desired=desired, cluster_id=cluster_id)
    endpoint = private_database_endpoint(cluster)
    if endpoint is None:
        raise RecoveryBlocked("Existing private database endpoint is unavailable")
    payload: dict[str, Any] = {
        "release_sha": sha,
        "plan": load_plan(),
        "database": {
            "cluster_id": cluster_id,
            "host": endpoint.host,
            "port": endpoint.port,
            "database": desired.instance_name,
            "user": desired.admin_login,
        },
    }
    trusted_host_entry(os.environ.get("TIMEWEB_SSH_KNOWN_HOSTS", ""), managed_ip)
    # Readiness is rechecked before sending any operator program. No data/keys are fetched.
    require_checkout(sha)
    wait_for_main_release(sha, token, timeout=600)
    command = (
        "systemd-run --quiet --wait --pipe --collect --unit=omnicio-recovery "
        "--property=RuntimeMaxSec=1200 --property=TimeoutStopSec=240 "
        "--property=KillMode=control-group --property=MemoryMax=512M "
        "/opt/omnicio/current/.venv/bin/python -"
    )
    with EphemeralSsh(client=client, server_id=managed_id, server_ip=managed_ip) as ssh:
        raw = ssh.run(command, input_text=host_program(payload), timeout=1500)
    report = parse_host_report(raw, payload)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # A driver exception can include connection details, SQL values, or row data.
        print(f"Restore drill blocked: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None

