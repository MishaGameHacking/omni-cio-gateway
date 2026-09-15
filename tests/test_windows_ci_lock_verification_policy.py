from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_ci_security_baseline.py"
)
SPEC = importlib.util.spec_from_file_location("check_ci_security_baseline", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


class WindowsLockWorkflowPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)
        self.helper = self.root / "scripts" / "verify_windows_ci_locks.py"
        self.regression = self.root / ".github" / "workflows" / "regression-shield.yml"
        self.authoritative = (
            self.root / ".github" / "workflows" / "self-hosted-windows-smoke.yml"
        )
        self.helper.parent.mkdir(parents=True)
        self.regression.parent.mkdir(parents=True)
        self.helper.write_text("# bounded helper\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _validate(self) -> list[str]:
        failures: list[str] = []
        with (
            patch.object(baseline, "WINDOWS_LOCK_HELPER_PATH", self.helper),
            patch.object(
                baseline,
                "PROTECTED_LOCK_WORKFLOW_PATHS",
                (self.regression, self.authoritative),
            ),
        ):
            baseline.validate_bounded_windows_lock_verification(failures)
        return failures

    def test_policy_accepts_shared_bounded_helper_in_both_workflows(self) -> None:
        workflow = f"run: {baseline.BOUNDED_WINDOWS_LOCK_COMMAND}\n"
        self.regression.write_text(workflow, encoding="utf-8")
        self.authoritative.write_text(workflow, encoding="utf-8")

        self.assertEqual(self._validate(), [])

    def test_policy_rejects_raw_unbounded_pip_compile(self) -> None:
        self.regression.write_text(
            f"run: {baseline.BOUNDED_WINDOWS_LOCK_COMMAND}\n"
            f"run: {baseline.UNBOUNDED_WINDOWS_LOCK_COMMAND}\n",
            encoding="utf-8",
        )
        self.authoritative.write_text(
            f"run: {baseline.BOUNDED_WINDOWS_LOCK_COMMAND}\n",
            encoding="utf-8",
        )

        failures = self._validate()

        self.assertEqual(len(failures), 1)
        self.assertIn("raw unbounded piptools compile", failures[0])

    def test_policy_rejects_missing_bounded_helper_invocation(self) -> None:
        self.regression.write_text(
            f"run: {baseline.BOUNDED_WINDOWS_LOCK_COMMAND}\n",
            encoding="utf-8",
        )
        self.authoritative.write_text("run: python -m pytest\n", encoding="utf-8")

        failures = self._validate()

        self.assertEqual(len(failures), 1)
        self.assertIn("bounded Windows lock helper exactly once", failures[0])


if __name__ == "__main__":
    unittest.main()
