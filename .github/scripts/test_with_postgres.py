"""Run migrations against disposable Windows PostgreSQL, including pgcrypto.

The fixed Maven Central archive contains the Windows binaries repackaged by
zonkyio/embedded-postgres-binaries. Verify its SHA-256 before extracting or
executing anything. No system installation or persistent service is created.
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
import tarfile
import zipfile
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg

ARCHIVE_PATH = (
    "/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/"
    "16.15.0/embedded-postgres-binaries-windows-amd64-16.15.0.jar"
)
ARCHIVE_SHA256 = "51c7812dc1af47c9a2ccb64fe74efb88c515cff2da347ce72aab92b4cc8e1191"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024


def install_binaries(destination: Path) -> Path:
    with closing(http.client.HTTPSConnection("repo.maven.apache.org", timeout=60)) as client:
        client.request("GET", ARCHIVE_PATH)
        response = client.getresponse()
        if response.status != 200:
            raise RuntimeError("PostgreSQL binary download failed")
        archive = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(archive) > MAX_ARCHIVE_BYTES or hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError("PostgreSQL binary checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        member = bundle.getinfo("postgres-windows-x86_64.txz")
        if member.file_size > MAX_ARCHIVE_BYTES:
            raise RuntimeError("PostgreSQL inner archive is too large")
        compressed = bundle.read(member)
    destination.mkdir()
    root = destination.resolve()
    expanded = 0
    with tarfile.open(fileobj=io.BytesIO(compressed), mode="r:xz") as files:
        for member in files:
            target = (root / member.name).resolve()
            expanded += member.size
            if not target.is_relative_to(root) or expanded > MAX_EXPANDED_BYTES:
                raise RuntimeError("Invalid PostgreSQL archive entry")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                source = files.extractfile(member)
                if source is None:
                    raise RuntimeError("Missing PostgreSQL archive content")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
            else:
                raise RuntimeError("Unsupported PostgreSQL archive entry")
    return root / "bin"


def available_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def run_suite(binary: Path, directory: Path) -> int:
    data = directory / "data"
    port = available_port()
    # Trust applies only to this temporary loopback-only CI database.
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
        environment = {**os.environ, "OMNICIO_TEST_DATABASE_URL": base + "omnicio_test"}
        return subprocess.run(
            [sys.executable, "-m", "pytest"],
            cwd=Path(__file__).resolve().parents[2], env=environment,
            check=False, timeout=600,
        ).returncode
    finally:
        if (data / "postmaster.pid").exists():
            subprocess.run([*control, "-m", "fast", "stop"], check=True, timeout=45)


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("This CI entry point requires the Windows runner")
    with TemporaryDirectory(prefix="omnicio-ci-postgres-") as directory:
        path = Path(directory)
        return run_suite(install_binaries(path / "postgres"), path)


if __name__ == "__main__":
    raise SystemExit(main())
