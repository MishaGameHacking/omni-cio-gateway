from __future__ import annotations

from collections.abc import Callable
import os
import time
from typing import Any

import psycopg


DSN_ENV = "OMNI_CIO_WP13_DSN"


def wait_for_postgres18(
    dsn: str,
    *,
    timeout_seconds: float = 45.0,
    retry_interval_seconds: float = 1.0,
    connect_timeout_seconds: int = 3,
    connect: Callable[..., Any] = psycopg.connect,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Wait until PostgreSQL accepts SQL and prove the expected major version."""
    deadline = monotonic() + timeout_seconds
    while True:
        try:
            with connect(
                dsn,
                autocommit=True,
                connect_timeout=connect_timeout_seconds,
            ) as connection:
                version_row = connection.execute("SHOW server_version_num").fetchone()
                if version_row is None:
                    raise RuntimeError("POSTGRES_VERSION_UNAVAILABLE")
                version_num = int(version_row[0])
                if version_num // 10000 != 18:
                    raise RuntimeError("POSTGRES18_REQUIRED")
                ready_row = connection.execute("SELECT 1").fetchone()
                if ready_row != (1,):
                    raise RuntimeError("POSTGRES_READINESS_QUERY_FAILED")
                return version_num
        except psycopg.OperationalError:
            if monotonic() >= deadline:
                raise RuntimeError("POSTGRES_READY_TIMEOUT") from None
            sleep(retry_interval_seconds)


def main() -> int:
    dsn = os.environ.get(DSN_ENV, "").strip()
    if not dsn:
        raise RuntimeError(f"{DSN_ENV}_REQUIRED")
    version_num = wait_for_postgres18(dsn)
    print(f"CIRCLECI_POSTGRES_VERSION_NUM={version_num}")
    print("POSTGRES18_READINESS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
