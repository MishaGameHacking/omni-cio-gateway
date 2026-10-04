"""Run the full suite against a disposable local database on the Windows CI host.

Never use an inherited database URL: the migration suite creates roles and data.
The pinned pgserver wheel provides binaries, not a persistent Windows service.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("This CI entry point requires the Windows runner")

    from pgserver import get_server

    root = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="omnicio-ci-postgres-") as directory:
        server = get_server(Path(directory) / "data", cleanup_mode="stop")
        try:
            with psycopg.connect(server.get_uri(), autocommit=True) as connection:
                connection.execute("CREATE DATABASE omnicio_test")
            environment = {
                **os.environ,
                "OMNICIO_TEST_DATABASE_URL": server.get_uri(database="omnicio_test"),
            }
            return subprocess.run(
                [sys.executable, "-m", "pytest"],
                cwd=root,
                env=environment,
                check=False,
                timeout=600,
            ).returncode
        finally:
            server.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
