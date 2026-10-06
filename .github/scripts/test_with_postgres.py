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
from tempfile import TemporaryDirectory

import psycopg

ARCHIVE_PATH = "/postgresql/postgresql-18.3-1-windows-x64-binaries.zip"
ARCHIVE_SHA256 = "4da1a93cbc69e99936616d53c34466f79e4295fc56134ce4a395e88351213d60"
MAX_ARCHIVE_BYTES = 400 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024


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
    subprocess.run([
        str(binary / "initdb.exe"), "-D", str(data), "-U", "postgres",
        "--auth=trust", "--encoding=UTF8", "--no-locale",
    ], check=True, timeout=60)
    control = [str(binary / "pg_ctl.exe"), "-D", str(data), "-w", "-t", "30"]
    try:
        subprocess.run([
            *control, "-l", str(directory / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {port}", "start",
        ], check=True, timeout=45)
        base = f"postgresql://postgres@127.0.0.1:{port}/"
        with psycopg.connect(base + "postgres", autocommit=True, connect_timeout=10) as db:
            db.execute("CREATE DATABASE omnicio_test")
        # Never consume an inherited DSN: the suite creates roles and test data.
        environment = {
            **os.environ,
            "OMNICIO_TEST_DATABASE_URL": base + "omnicio_test",
            "OMNICIO_TEST_POSTGRES_BIN": str(binary.resolve()),
        }
        print("Running full pytest suite with native PostgreSQL", flush=True)
        return subprocess.run(
            [
                sys.executable, "-m", "pytest", "-vv", "--durations=10",
                "-o", "faulthandler_timeout=60",
            ],
            cwd=Path(__file__).resolve().parents[2], env=environment,
            check=False, timeout=600,
        ).returncode
    finally:
        if (data / "postmaster.pid").exists():
            print("Stopping disposable PostgreSQL", flush=True)
            subprocess.run([*control, "-m", "fast", "stop"], check=True, timeout=45)


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("This CI entry point requires the Windows runner")
    with TemporaryDirectory(prefix="omnicio-ci-postgres-") as directory:
        path = Path(directory)
        return run_suite(install_binaries(path / "postgres"), path)


if __name__ == "__main__":
    raise SystemExit(main())
