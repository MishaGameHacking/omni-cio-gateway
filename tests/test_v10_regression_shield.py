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

    def test_current_repository_satisfies_wp3_guard(self) -> None:
        self.assertEqual(shield.validate_repository(), [])


if __name__ == "__main__":
    unittest.main()
