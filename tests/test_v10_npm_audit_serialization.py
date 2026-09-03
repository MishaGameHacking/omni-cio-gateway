from __future__ import annotations

from contextlib import contextmanager
import errno
import socket
import subprocess
import unittest
from unittest.mock import MagicMock

import scripts.run_v10_npm_audit as npm_audit


class V10NpmAuditHostSerializationTests(unittest.TestCase):
    def test_host_slot_port_avoids_project_preview_and_windows_dynamic_ranges(
        self,
    ) -> None:
        self.assertGreaterEqual(npm_audit._HOST_SLOT_PORT, npm_audit._HOST_SLOT_PORT_MIN)
        self.assertLessEqual(npm_audit._HOST_SLOT_PORT, npm_audit._HOST_SLOT_PORT_MAX)

    def test_host_slot_port_override_is_strictly_validated(self) -> None:
        self.assertEqual(npm_audit._resolve_host_slot_port({}), 43867)
        self.assertEqual(
            npm_audit._resolve_host_slot_port(
                {npm_audit._HOST_SLOT_PORT_ENV: " 43868 "}
            ),
            43868,
        )

        for value in ("abc", "43867.0", "-1", "31999", "49152", "１２３４５"):
            with self.subTest(value=value):
                with self.assertRaises(npm_audit.AuditTransportLockError):
                    npm_audit._resolve_host_slot_port(
                        {npm_audit._HOST_SLOT_PORT_ENV: value}
                    )

    def test_host_slot_port_override_is_propagated_before_socket_bind(self) -> None:
        slot = MagicMock(spec=socket.socket)

        with npm_audit._audit_transport_lock(
            environ={npm_audit._HOST_SLOT_PORT_ENV: "43868"},
            socket_factory=lambda: slot,
        ):
            slot.bind.assert_called_once_with((npm_audit._HOST_SLOT_ADDRESS, 43868))

        slot.close.assert_called_once_with()

    def test_host_slot_contention_accepts_only_address_in_use(self) -> None:
        self.assertTrue(
            npm_audit._is_host_slot_contention(
                OSError(errno.EADDRINUSE, "synthetic address in use")
            )
        )
        self.assertFalse(
            npm_audit._is_host_slot_contention(
                OSError(errno.EACCES, "synthetic access denied")
            )
        )
        self.assertFalse(
            npm_audit._is_host_slot_contention(
                OSError(errno.EINVAL, "synthetic invalid argument")
            )
        )

    def test_real_loopback_slot_serializes_without_filesystem_state(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((npm_audit._HOST_SLOT_ADDRESS, 0))
            port = int(probe.getsockname()[1])

        with npm_audit._audit_transport_lock(port=port):
            with self.assertRaises(npm_audit.AuditTransportLockError):
                with npm_audit._audit_transport_lock(port=port, wait_seconds=0.0):
                    self.fail("second host slot must not be acquired concurrently")

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

    def test_release_failure_preserves_prior_security_finding_status(self) -> None:
        @contextmanager
        def failed_release_lock():
            yield
            raise npm_audit.AuditTransportLockError(
                "synthetic host transport slot release failure"
            )

        result = subprocess.CompletedProcess(
            args=["npm"],
            returncode=1,
            stdout="# npm audit report\n1 high severity vulnerability\n",
            stderr="",
        )

        status = npm_audit.run_audit(
            npm="npm",
            runner=lambda _command: result,
            lock_factory=failed_release_lock,
        )

        self.assertEqual(status, 1)

    def test_release_failure_turns_clean_audit_red(self) -> None:
        @contextmanager
        def failed_release_lock():
            yield
            raise npm_audit.AuditTransportLockError(
                "synthetic host transport slot release failure"
            )

        result = subprocess.CompletedProcess(
            args=["npm"],
            returncode=0,
            stdout="found 0 vulnerabilities\n",
            stderr="",
        )

        status = npm_audit.run_audit(
            npm="npm",
            runner=lambda _command: result,
            lock_factory=failed_release_lock,
        )

        self.assertEqual(status, 75)


if __name__ == "__main__":
    unittest.main()
