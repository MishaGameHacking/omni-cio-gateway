"""Run migrations and a real dump/restore drill on disposable PostgreSQL 18.

Use the pinned EDB Windows binary distribution linked by postgresql.org.
It includes pg_dump, pg_restore and pgcrypto. Verify the archive before
extracting or executing anything; no persistent service is installed.
"""

from __future__ import annotations

import hashlib
import http.client
import io
import os
import shutil
import socket
import subprocess
import sys
import zipfile
from contextlib import closing
from pathlib import Path
from tempfile import mkdtemp
from typing import BinaryIO

import psycopg

ARCHIVE_PATH = "/postgresql/postgresql-18.3-1-windows-x64-binaries.zip"
ARCHIVE_SHA256 = "4da1a93cbc69e99936616d53c34466f79e4295fc56134ce4a395e88351213d60"
MAX_ARCHIVE_BYTES = 400 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 720
CLEANUP_TIMEOUT_SECONDS = 20
MAX_WORKER_LOG_BYTES = 8 * 1024 * 1024
MAX_LOG_TAIL_BYTES = 128 * 1024
WORKER_LOG = "worker.log"
POSTGRES_LOG = "postgres.log"


def install_binaries(destination: Path) -> Path:
    print("Downloading hash-pinned disposable PostgreSQL", flush=True)
    with closing(http.client.HTTPSConnection("get.enterprisedb.com", timeout=60)) as client:
        client.request("GET", ARCHIVE_PATH)
        response = client.getresponse()
        if response.status != 200:
            raise RuntimeError("PostgreSQL binary download failed")
        archive = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(archive) > MAX_ARCHIVE_BYTES or hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError("PostgreSQL binary checksum mismatch")
    print(f"Verified PostgreSQL archive: {len(archive)} bytes", flush=True)
    destination.mkdir()
    root = destination.resolve()
    expanded = 0
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for member in bundle.infolist():
            if not member.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                continue
            target = (root / member.filename.removeprefix("pgsql/")).resolve()
            expanded += member.file_size
            if not target.is_relative_to(root) or expanded > MAX_EXPANDED_BYTES:
                raise RuntimeError("Invalid PostgreSQL archive entry")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    return root / "bin"


def available_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def run_suite(binary: Path, directory: Path) -> int:
    data = directory / "data"
    port = available_port()
    # Trust applies only to this temporary loopback-only CI database.
    print("Initializing disposable loopback PostgreSQL", flush=True)
    _run_native([
        str(binary / "initdb.exe"), "-D", str(data), "-U", "postgres",
        "--auth=trust", "--encoding=UTF8", "--no-locale",
    ], timeout=60)
    control = [str(binary / "pg_ctl.exe"), "-D", str(data), "-w", "-t", "30"]
    try:
        _run_native([
            *control, "-l", str(directory / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {port}", "start",
        ], timeout=45)
        base = f"postgresql://postgres@127.0.0.1:{port}/"
        with psycopg.connect(base + "postgres", autocommit=True, connect_timeout=10) as db:
            db.execute("CREATE DATABASE omnicio_test")
            # Bound blocked SQL in this disposable database. Production and
            # the separately created backup-recovery databases are unaffected.
            db.execute("ALTER DATABASE omnicio_test SET lock_timeout = '15s'")
            db.execute("ALTER DATABASE omnicio_test SET statement_timeout = '60s'")
        # Never consume an inherited DSN: the suite creates roles and test data.
        environment = {
            **os.environ,
            "OMNICIO_TEST_DATABASE_URL": base + "omnicio_test",
            "OMNICIO_TEST_POSTGRES_BIN": str(binary.resolve()),
        }
        print("Running full pytest suite with native PostgreSQL", flush=True)
        return _run_native(
            [
                sys.executable, "-m", "pytest", "-vv", "--durations=10",
                "--junitxml=artifacts/postgres/pytest.xml",
                "-o", "faulthandler_timeout=60",
            ],
            cwd=Path(__file__).resolve().parents[2], env=environment,
            check=False, timeout=600,
        )
    finally:
        if (data / "postmaster.pid").exists():
            print("Stopping disposable PostgreSQL", flush=True)
            _run_native([*control, "-m", "fast", "stop"], timeout=45)


def _terminate_owned_tree(process: subprocess.Popen[bytes]) -> bool:
    """Terminate this still-owned process and its descendants exactly once."""
    if process.poll() is not None:
        return True
    taskkill = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "taskkill.exe"
    try:
        result = subprocess.run(
            [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
        )
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Owned process cleanup failed: {type(exc).__name__}", flush=True)
        return False
    if result.returncode != 0:
        print(f"Owned process tree cleanup returned {result.returncode}", flush=True)
        return False
    return True


def _wait_owned_process(
    process: subprocess.Popen[bytes], timeout: float, label: str,
) -> tuple[int, bool]:
    try:
        return process.wait(timeout=timeout), True
    except subprocess.TimeoutExpired:
        print(f"{label} exceeded its {timeout:g}s deadline", flush=True)
        return 124, _terminate_owned_tree(process)


def _run_native(
    command: list[str],
    *,
    timeout: float,
    check: bool = True,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    process = subprocess.Popen(command, cwd=cwd, env=env)
    code, _ = _wait_owned_process(process, timeout, Path(command[0]).name)
    if check and code != 0:
        raise subprocess.CalledProcessError(code, command)
    return code


def _log_tail(path: Path, maximum: int) -> bytes:
    if not path.is_file():
        return b"This process did not create a log.\n"
    with path.open("rb") as source:
        source.seek(0, os.SEEK_END)
        source.seek(max(0, source.tell() - maximum))
        return source.read(maximum)


def _preserve_evidence(directory: Path, destination: Path) -> None:
    for name, maximum in (
        (WORKER_LOG, MAX_WORKER_LOG_BYTES), (POSTGRES_LOG, MAX_LOG_TAIL_BYTES),
    ):
        source = directory / name
        if source.is_file() and source.stat().st_size > maximum:
            print(f"Keeping the last {maximum} bytes of {name}", flush=True)
        (destination / name).write_bytes(_log_tail(source, maximum))


def _stop_owned_postgres(directory: Path, log: BinaryIO) -> bool:
    data = directory / "data"
    if not (data / "postmaster.pid").exists():
        return True
    # A killed server can leave its PID file. pg_ctl status distinguishes this
    # from a detached live server without sending a signal to a finished PID.
    control = directory / "postgres" / "bin" / "pg_ctl.exe"
    status = subprocess.Popen(
        [str(control), "-D", str(data), "status"], stdout=log, stderr=subprocess.STDOUT,
    )
    code, stopped = _wait_owned_process(status, 10, "Owned PostgreSQL status")
    if not stopped:
        return False
    if code == 3:
        return True
    if code != 0:
        return False
    postgres = subprocess.Popen(
        [str(control), "-D", str(data), "-w", "-t", "10", "-m", "fast", "stop"],
        stdout=log, stderr=subprocess.STDOUT,
    )
    code, stopped = _wait_owned_process(postgres, 15, "Owned PostgreSQL shutdown")
    return code == 0 and stopped


def _cleanup_directory(directory: Path, output: Path) -> bool:
    """Bound cleanup too; the argument is the exact directory created by this run."""
    command = [
        sys.executable, "-c", "import shutil,sys; shutil.rmtree(sys.argv[1])", str(directory),
    ]
    try:
        with output.open("ab") as log:
            if not _stop_owned_postgres(directory, log):
                return False
            (output.parent / POSTGRES_LOG).write_bytes(
                _log_tail(directory / POSTGRES_LOG, MAX_LOG_TAIL_BYTES),
            )
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            code, stopped = _wait_owned_process(
                process, CLEANUP_TIMEOUT_SECONDS, "Temporary-directory cleanup",
            )
    except OSError as exc:
        print(f"Temporary-directory cleanup failed: {type(exc).__name__}", flush=True)
        return False
    return code == 0 and stopped and not directory.exists()


def _emit_evidence(destination: Path) -> None:
    worker = destination / WORKER_LOG
    if worker.stat().st_size > MAX_WORKER_LOG_BYTES:
        worker.write_bytes(_log_tail(worker, MAX_WORKER_LOG_BYTES))
    for name in (WORKER_LOG, POSTGRES_LOG):
        print(f"Captured {name} (last {MAX_LOG_TAIL_BYTES} bytes at most):", flush=True)
        sys.stdout.buffer.write(_log_tail(destination / name, MAX_LOG_TAIL_BYTES))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()


def _supervise_worker(destination: Path, *, timeout: float = WORKER_TIMEOUT_SECONDS) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    directory = Path(mkdtemp(prefix="omnicio-ci-postgres-"))
    code, stopped = 1, True
    print(f"Supervising disposable PostgreSQL with a {timeout:g}s overall deadline", flush=True)
    try:
        with (directory / WORKER_LOG).open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).resolve()), "--worker", str(directory)],
                stdout=log, stderr=subprocess.STDOUT,
            )
            code, stopped = _wait_owned_process(process, timeout, "PostgreSQL worker")
    except OSError as exc:
        print(f"PostgreSQL worker could not start: {type(exc).__name__}", flush=True)
    finally:
        _preserve_evidence(directory, destination)
        if stopped:
            if not _cleanup_directory(directory, destination / WORKER_LOG):
                code = 1
                print(f"Temporary-directory cleanup is incomplete: {directory}", flush=True)
        else:
            print(f"Process cleanup is incomplete; preserving owned directory: {directory}",
                  flush=True)
        _emit_evidence(destination)
    return code


def main(arguments: list[str] | None = None) -> int:
    if sys.platform != "win32":
        raise RuntimeError("This CI entry point requires the Windows runner")
    args = sys.argv[1:] if arguments is None else arguments
    if args:
        if len(args) != 2 or args[0] != "--worker":
            raise ValueError("Invalid internal worker arguments")
        path = Path(args[1])
        return run_suite(install_binaries(path / "postgres"), path)
    destination = Path(__file__).resolve().parents[2] / "artifacts" / "postgres"
    return _supervise_worker(destination)


if __name__ == "__main__":
    raise SystemExit(main())
