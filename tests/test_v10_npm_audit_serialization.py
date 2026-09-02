from __future__ import annotations

from contextlib import contextmanager
import subprocess
import unittest

import scripts.run_v10_npm_audit as npm_audit


class V10NpmAuditHostSerializationTests(unittest.TestCase):
    def test_retry_sequence_holds_one_host_transport_slot(self) -> None:
        results = iter(
            (
                subprocess.CompletedProcess(
                    args=["npm"],
                    returncode=1,
                    stdout="",
                    stderr="npm error ECONNRESET registry transport failed\n",
                ),
                subprocess.CompletedProcess(
                    args=["npm"],
                    returncode=0,
                    stdout="found 0 vulnerabilities\n",
                    stderr="",
                ),
            )
        )
        locked = False
        lock_entries = 0
        delays: list[float] = []

        @contextmanager
        def host_lock():
            nonlocal locked, lock_entries
            self.assertFalse(locked)
            locked = True
            lock_entries += 1
            try:
                yield
            finally:
                locked = False

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            self.assertTrue(locked)
            return next(results)

        def sleeper(delay: float) -> None:
            self.assertTrue(locked)
            delays.append(delay)

        status = npm_audit.run_audit(
            npm="npm",
            attempts=3,
            backoff_seconds=2.0,
            runner=runner,
            sleeper=sleeper,
            lock_factory=host_lock,
        )

        self.assertEqual(status, 0)
        self.assertEqual(lock_entries, 1)
        self.assertEqual(delays, [2.0])
        self.assertFalse(locked)

    def test_default_retry_budget_reaches_fifth_attempt_under_one_slot(self) -> None:
        results = iter(
            [
                subprocess.CompletedProcess(
                    args=["npm"],
                    returncode=1,
                    stdout="",
                    stderr="npm error ECONNRESET registry transport failed\n",
                )
                for _ in range(4)
            ]
            + [
                subprocess.CompletedProcess(
                    args=["npm"],
                    returncode=0,
                    stdout="found 0 vulnerabilities\n",
                    stderr="",
                )
            ]
        )
        locked = False
        lock_entries = 0
        calls = 0
        delays: list[float] = []

        @contextmanager
        def host_lock():
            nonlocal locked, lock_entries
            self.assertFalse(locked)
            locked = True
            lock_entries += 1
            try:
                yield
            finally:
                locked = False

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            self.assertTrue(locked)
            calls += 1
            return next(results)

        def sleeper(delay: float) -> None:
            self.assertTrue(locked)
            delays.append(delay)

        status = npm_audit.run_audit(
            npm="npm",
            runner=runner,
            sleeper=sleeper,
            lock_factory=host_lock,
        )

        self.assertEqual(status, 0)
        self.assertEqual(calls, 5)
        self.assertEqual(lock_entries, 1)
        self.assertEqual(delays, [15.0, 30.0, 45.0, 60.0])
        self.assertFalse(locked)

    def test_backoff_is_capped_even_with_large_custom_base(self) -> None:
        results = iter(
            (
                subprocess.CompletedProcess(
                    args=["npm"],
                    returncode=1,
                    stdout="",
                    stderr="npm error ETIMEDOUT registry transport failed\n",
                ),
                subprocess.CompletedProcess(
                    args=["npm"],
                    returncode=1,
                    stdout="",
                    stderr="npm error ETIMEDOUT registry transport failed\n",
                ),
                subprocess.CompletedProcess(
                    args=["npm"],
                    returncode=0,
                    stdout="found 0 vulnerabilities\n",
                    stderr="",
                ),
            )
        )
        delays: list[float] = []

        @contextmanager
        def host_lock():
            yield

        status = npm_audit.run_audit(
            npm="npm",
            attempts=3,
            backoff_seconds=60.0,
            runner=lambda _command: next(results),
            sleeper=delays.append,
            lock_factory=host_lock,
        )

        self.assertEqual(status, 0)
        self.assertEqual(delays, [60.0, 60.0])

    def test_host_transport_lock_failure_stays_red_without_running_npm(self) -> None:
        @contextmanager
        def failed_lock():
            raise npm_audit.AuditTransportLockError(
                "synthetic host transport lock failure"
            )
            yield

        def forbidden_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            self.fail(f"npm must not run without the host transport lock: {command}")

        status = npm_audit.run_audit(
            npm="npm",
            runner=forbidden_runner,
            lock_factory=failed_lock,
        )

        self.assertEqual(status, 75)


if __name__ == "__main__":
    unittest.main()
