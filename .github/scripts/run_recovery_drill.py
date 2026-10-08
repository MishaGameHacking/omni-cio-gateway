"""Manual production logical export -> isolated restore -> signed runtime receipt.

Never run from scheduled reconciliation. Source custody requires an explicit
read-only export DSN with verified TLS and private-network reachability. The
target is a newly initialized password-protected loopback PostgreSQL cluster.
No Timeweb database, storage bucket, or billable destination is created.
"""

from __future__ import annotations

import os
import pathlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

from cryptography.fernet import Fernet
from psycopg.conninfo import make_conninfo
from test_with_postgres import _wait_owned_process, available_port, install_binaries
from timeweb_auth_postgres import EphemeralSsh, TimewebClient, find_managed_server, public_ipv4
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
from verify_main_release import GitHubClient, release_context, require_checkout, wait_for_release

from omnicio.recovery import sign_recovery_evidence


def authorize() -> tuple[str, str]:
    if load_policy().mode == "single_existing_database":
        raise RecoveryBlocked("Production export is disabled by the single-database policy")
    if (os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("OMNICIO_RESTORE_DRILL_ALLOWED") != "true"):
        raise RecoveryBlocked("An explicit accepted-main restore-drill dispatch is required")
    sha, token = release_context()
    require_checkout(sha)
    wait_for_release(GitHubClient(token, deadline=time.monotonic() + 600), sha)
    return sha, token


def native(command: list[str], *, timeout: int) -> None:
    # These reviewed native programs do not inherit production DSN/crypto secrets.
    environment = {key: value for key, value in os.environ.items()
                   if key in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "LANG"}}
    try:
        # Windows PostgreSQL can inherit pg_ctl's pipe handles even with -l.
        # Popen.wait + real null handles avoids reader threads waiting forever
        # after pg_ctl exits; the shared supervisor kills only this owned tree.
        process = subprocess.Popen(
            command, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        code, stopped = _wait_owned_process(process, timeout, "Disposable PostgreSQL command")
    except (OSError, subprocess.SubprocessError):
        raise RecoveryBlocked("Disposable PostgreSQL process did not complete") from None
    if code or not stopped:
        raise RecoveryBlocked("Disposable PostgreSQL process failed")


def main() -> int:
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
    server = find_managed_server(client.get_servers(), name="omni-cio-white-site",
                                 comment="Managed by GitHub Actions: timeweb-white-site")
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
        native([str(binary / "initdb.exe"), "-D", str(data), "-U", "postgres",
                "--auth=scram-sha-256", "--encoding=UTF8", "--no-locale",
                "--pwfile", str(password_file)], timeout=60)
        password_file.unlink()
        port = available_port()
        control = [str(binary / "pg_ctl.exe"), "-D", str(data), "-w", "-t", "30"]
        try:
            native([*control, "-l", str(directory / "postgres.log"),
                    "-o", f"-h 127.0.0.1 -p {port}", "start"], timeout=45)
            target = make_conninfo(host="127.0.0.1", port=port, dbname="postgres",
                                  user="postgres", password=password, connect_timeout=10)
            manifest = export_logical_archive(
                source, binary, cluster_id=load_policy().cluster_id,
                release_sha=sha, signing_key=signing_key, archive_key=archive_key,
            )
            receipt = verify_logical_archive(
                target, binary, manifest,
                release_sha=sha, signing_key=signing_key, archive_key=archive_key,
            )
        finally:
            if (data / "postmaster.pid").exists():
                native([*control, "-m", "fast", "stop"], timeout=45)
    if receipt is None:
        raise RecoveryBlocked("No isolated restore proof was produced")
    _private_json("restore-verification.json", receipt)
    # Refuse an obsolete source checkout before touching operational runtime state.
    require_checkout(sha)
    wait_for_release(GitHubClient(token, deadline=time.monotonic() + 600), sha)
    with EphemeralSsh(client=client, server_id=managed_id, server_ip=managed_ip) as ssh:
        install_restore_receipt(ssh, receipt, sha)
    print("Logical restore proof verified and installed; "
          "physical snapshot restore remains unverified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # A driver exception can include connection details, SQL values, or row data.
        print(f"Restore drill blocked: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
