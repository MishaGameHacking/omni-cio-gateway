from __future__ import annotations

from pathlib import Path
import unittest

import psycopg

from scripts.wait_for_postgres18 import wait_for_postgres18


ROOT = Path(__file__).resolve().parents[1]


class _Result:
    def __init__(self, row: tuple[object, ...]) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...]:
        return self._row


class _Connection:
    def __init__(self, version_num: int = 180004) -> None:
        self.version_num = version_num

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def execute(self, statement: str) -> _Result:
        if statement == "SHOW server_version_num":
            return _Result((self.version_num,))
        if statement == "SELECT 1":
            return _Result((1,))
        raise AssertionError(f"unexpected SQL: {statement}")


class CircleCIPostgres18ReadinessTests(unittest.TestCase):
    def test_retries_operational_startup_failures_then_proves_postgres18(self) -> None:
        attempts = 0

        def connect(*args: object, **kwargs: object) -> _Connection:
            nonlocal attempts
            del args, kwargs
            attempts += 1
            if attempts < 3:
                raise psycopg.OperationalError("synthetic startup race")
            return _Connection()

        version_num = wait_for_postgres18(
            "postgresql://synthetic.invalid/ci",
            timeout_seconds=5.0,
            retry_interval_seconds=0.0,
            connect=connect,
            sleep=lambda _: None,
        )

        self.assertEqual(version_num, 180004)
        self.assertEqual(attempts, 3)

    def test_timeout_is_fail_closed_and_does_not_echo_dsn(self) -> None:
        def connect(*args: object, **kwargs: object) -> _Connection:
            del args, kwargs
            raise psycopg.OperationalError("synthetic connection failure")

        secret_dsn = "postgresql://user:do-not-print@127.0.0.1:5432/ci"
        with self.assertRaisesRegex(RuntimeError, "POSTGRES_READY_TIMEOUT") as captured:
            wait_for_postgres18(
                secret_dsn,
                timeout_seconds=0.0,
                connect=connect,
                sleep=lambda _: None,
            )
        self.assertNotIn(secret_dsn, str(captured.exception))
        self.assertNotIn("do-not-print", str(captured.exception))

    def test_wrong_postgres_major_is_not_retried(self) -> None:
        attempts = 0

        def connect(*args: object, **kwargs: object) -> _Connection:
            nonlocal attempts
            del args, kwargs
            attempts += 1
            return _Connection(version_num=170009)

        with self.assertRaisesRegex(RuntimeError, "POSTGRES18_REQUIRED"):
            wait_for_postgres18(
                "postgresql://synthetic.invalid/ci",
                connect=connect,
                sleep=lambda _: None,
            )
        self.assertEqual(attempts, 1)

    def test_circleci_wait_is_unconditional_for_all_postgres_rehearsals(self) -> None:
        config = (ROOT / ".circleci" / "config.yml").read_text(encoding="utf-8")
        job_start = config.index("  supplemental_linux_postgres18:\n")
        job_end = config.index("\nworkflows:\n", job_start)
        postgres_job = config[job_start:job_end]
        wait_name = "name: Wait for PostgreSQL 18 service readiness"
        wait_command = "python -m scripts.wait_for_postgres18"

        self.assertEqual(config.count(wait_name), 1)
        self.assertEqual(config.count(wait_command), 1)
        self.assertEqual(postgres_job.count(wait_name), 1)
        self.assertEqual(postgres_job.count(wait_command), 1)
        self.assertLess(postgres_job.index(wait_name), postgres_job.index("      - when:"))
        self.assertIn("- wp13", postgres_job)
        self.assertIn("- phase4-creator-edge", postgres_job)
        self.assertIn("- phase4-bootstrap", postgres_job)
        self.assertNotIn('python -c "import os,time,psycopg', config)


if __name__ == "__main__":
    unittest.main()
