from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "verify_windows_ci_locks.py"
)
SPEC = importlib.util.spec_from_file_location("verify_windows_ci_locks", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class Runner:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.commands: list[list[str]] = []
        self.timeouts: list[float] = []

    def __call__(
        self,
        command: list[str],
        cwd: Path,
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        self.timeouts.append(timeout_seconds)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, subprocess.CompletedProcess)
        return outcome


def completed(returncode: int, stdout: str = "", stderr: str = "") -> object:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class WindowsLockVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_timeout_retries_then_verifies_both_lock_plans(self) -> None:
        runner = Runner(
            [
                subprocess.TimeoutExpired(["pip-compile"], timeout=1.0),
                completed(0),
                completed(0),
                completed(0),
                completed(0),
            ]
        )
        sleeps: list[float] = []

        status = verifier.verify_windows_ci_locks(
            root=self.root,
            attempts=3,
            backoff_seconds=2.0,
            compile_timeout_seconds=10.0,
            verify_timeout_seconds=3.0,
            runner=runner,
            sleeper=sleeps.append,
        )

        self.assertEqual(status, 0)
        self.assertEqual(sleeps, [2.0])
        compile_commands = [
            command for command in runner.commands if "piptools" in command
        ]
        verify_commands = [
            command
            for command in runner.commands
            if "scripts/windows_ci_lock.py" in command
        ]
        self.assertEqual(len(compile_commands), 3)
        self.assertEqual(len(verify_commands), 2)
        self.assertEqual(runner.timeouts.count(10.0), 3)
        self.assertEqual(runner.timeouts.count(3.0), 2)

    def test_transient_transport_failure_retries(self) -> None:
        runner = Runner(
            [
                completed(
                    1,
                    stderr=(
                        "WARNING: Retrying after connection broken by "
                        "OSError('exception: access violation writing 0x48')"
                    ),
                ),
                completed(0),
                completed(0),
                completed(0),
                completed(0),
            ]
        )
        sleeps: list[float] = []

        status = verifier.verify_windows_ci_locks(
            root=self.root,
            attempts=3,
            backoff_seconds=1.0,
            runner=runner,
            sleeper=sleeps.append,
        )

        self.assertEqual(status, 0)
        self.assertEqual(sleeps, [1.0])

    def test_transient_transport_failure_exhaustion_fails_closed(self) -> None:
        runner = Runner(
            [
                completed(1, stderr="connection broken"),
                completed(1, stderr="connection broken"),
                completed(1, stderr="connection broken"),
            ]
        )
        sleeps: list[float] = []

        status = verifier.verify_windows_ci_locks(
            root=self.root,
            attempts=3,
            backoff_seconds=1.0,
            runner=runner,
            sleeper=sleeps.append,
        )

        self.assertEqual(status, 1)
        self.assertEqual(sleeps, [1.0, 2.0])
        self.assertEqual(len(runner.commands), 3)

    def test_repeated_timeouts_fail_closed(self) -> None:
        runner = Runner(
            [
                subprocess.TimeoutExpired(["pip-compile"], timeout=1.0),
                subprocess.TimeoutExpired(["pip-compile"], timeout=1.0),
                subprocess.TimeoutExpired(["pip-compile"], timeout=1.0),
            ]
        )
        sleeps: list[float] = []

        status = verifier.verify_windows_ci_locks(
            root=self.root,
            attempts=3,
            backoff_seconds=1.0,
            runner=runner,
            sleeper=sleeps.append,
        )

        self.assertEqual(status, 75)
        self.assertEqual(sleeps, [1.0, 2.0])
        self.assertEqual(len(runner.commands), 3)

    def test_non_transient_compile_failure_is_not_retried(self) -> None:
        runner = Runner(
            [
                completed(
                    1,
                    stderr=(
                        "ERROR: Could not find a version that satisfies "
                        "requirement bad==1"
                    ),
                )
            ]
        )
        sleeps: list[float] = []

        status = verifier.verify_windows_ci_locks(
            root=self.root,
            attempts=3,
            runner=runner,
            sleeper=sleeps.append,
        )

        self.assertEqual(status, 1)
        self.assertEqual(sleeps, [])
        self.assertEqual(len(runner.commands), 1)

    def test_projection_verification_failure_is_not_retried(self) -> None:
        runner = Runner([completed(0), completed(1, stderr="projection drift")])
        sleeps: list[float] = []

        status = verifier.verify_windows_ci_locks(
            root=self.root,
            attempts=3,
            runner=runner,
            sleeper=sleeps.append,
        )

        self.assertEqual(status, 1)
        self.assertEqual(sleeps, [])
        self.assertEqual(len(runner.commands), 2)

    def test_partial_output_is_removed_before_every_compile_attempt(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            partial = root / "windows-compiled-requirements.txt"
            partial.write_text("partial", encoding="utf-8")
            observations: list[bool] = []

            def runner(
                command: list[str], cwd: Path, timeout_seconds: float
            ) -> subprocess.CompletedProcess[str]:
                del cwd, timeout_seconds
                if "piptools" in command:
                    observations.append(partial.exists())
                    raise subprocess.TimeoutExpired(command, timeout=1.0)
                raise AssertionError("verification must not run")

            status = verifier.verify_windows_ci_locks(
                root=root,
                attempts=2,
                backoff_seconds=0.0,
                runner=runner,
                sleeper=lambda _: None,
            )

        self.assertEqual(status, 75)
        self.assertEqual(observations, [False, False])

    def test_policy_rejects_unbounded_attempt_configuration(self) -> None:
        with self.assertRaises(ValueError):
            verifier.verify_windows_ci_locks(root=self.root, attempts=4)


if __name__ == "__main__":
    unittest.main()
