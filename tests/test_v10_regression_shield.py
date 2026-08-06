from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import scripts.check_v10_regression_shield as shield


class V10RegressionShieldGuardTests(unittest.TestCase):
    def test_external_action_requires_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            failures: list[str] = []
            shield.validate_action_pins(
                path,
                "steps:\n  - uses: actions/checkout@v7\n",
                failures,
            )
            self.assertEqual(len(failures), 1)
            self.assertIn("not full-SHA pinned", failures[0])

    def test_full_sha_action_pin_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            failures: list[str] = []
            shield.validate_action_pins(
                path,
                "steps:\n  - uses: actions/checkout@"
                "df4cb1c069e1874edd31b4311f1884172cec0e10\n",
                failures,
            )
            self.assertEqual(failures, [])

    def test_python_contract_requires_test_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(shield.has_python_contract(root))
            (root / "test_contract.py").write_text("pass\n", encoding="utf-8")
            self.assertTrue(shield.has_python_contract(root))

    def test_authoritative_gate_rejects_runtime_toolchain_installers(self) -> None:
        failures: list[str] = []
        original = shield.AUTHORITATIVE_WORKFLOW
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "self-hosted-windows-smoke.yml"
                path.write_text(
                    "permissions:\n  contents: read\n"
                    "pull_request:\n"
                    "steps:\n"
                    "  - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10\n"
                    "    with:\n      persist-credentials: false\n"
                    "  - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97\n",
                    encoding="utf-8",
                )
                shield.AUTHORITATIVE_WORKFLOW = path
                shield.validate_authoritative_workflow(failures)
        finally:
            shield.AUTHORITATIVE_WORKFLOW = original
        self.assertTrue(
            any("must not install toolchains" in failure for failure in failures),
            failures,
        )

    def test_current_repository_satisfies_wp3_guard(self) -> None:
        self.assertEqual(shield.validate_repository(), [])


if __name__ == "__main__":
    unittest.main()
