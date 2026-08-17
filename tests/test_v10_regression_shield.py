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

    def test_self_hosted_bootstrap_rejects_codeload_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            failures: list[str] = []
            shield.validate_self_hosted_repository_bootstrap(
                path,
                "runs-on: [self-hosted, Windows, X64, omni-cio-ci]\n"
                "steps:\n"
                "  - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10\n"
                "  - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a\n",
                failures,
            )
            self.assertTrue(
                any("actions/checkout" in failure for failure in failures), failures
            )
            self.assertTrue(
                any("actions/upload-artifact" in failure for failure in failures),
                failures,
            )

    def test_self_hosted_bootstrap_requires_credential_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            failures: list[str] = []
            shield.validate_self_hosted_repository_bootstrap(
                path,
                "runs-on: [self-hosted, Windows, X64, omni-cio-ci]\n"
                "GITHUB_TOKEN: ${{ github.token }}\n"
                "find . -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +\n"
                "git init .\n"
                'git remote add origin "https://github.com/${GITHUB_REPOSITORY}.git"\n'
                "git config --local credential.helper '!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f'\n"
                "git fetch --no-tags --prune origin HEAD\n"
                "git checkout --detach $EXPECTED_HEAD\n"
                'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"\n',
                failures,
            )
            self.assertTrue(
                any("unset-all credential.helper" in failure for failure in failures),
                failures,
            )

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
                    "runs-on: [self-hosted, Windows, X64, omni-cio-ci]\n"
                    "github.event.pull_request.head.repo.full_name == github.repository\n"
                    "GITHUB_TOKEN: ${{ github.token }}\n"
                    "find . -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +\n"
                    "git init .\n"
                    'git remote add origin "https://github.com/${GITHUB_REPOSITORY}.git"\n'
                    "git config --local credential.helper '!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f'\n"
                    "git fetch --no-tags --prune origin HEAD\n"
                    "git checkout --detach $EXPECTED_HEAD\n"
                    "git config --local --unset-all credential.helper\n"
                    'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"\n'
                    'test -z "$(git config --local --get-all credential.helper || true)"\n'
                    "steps:\n"
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

    def test_soft_fail_policy_rejects_mandatory_step(self) -> None:
        failures: list[str] = []
        shield.validate_soft_fail_policy(
            shield.FULL_WORKFLOW,
            "steps:\n"
            "  - name: Run Regression Shield with coverage\n"
            "    continue-on-error: true\n"
            "    run: python -m pytest\n",
            failures,
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("may not soften mandatory authority jobs", failures[0])

    def test_soft_fail_policy_rejects_diagnostics_transport(self) -> None:
        failures: list[str] = []
        shield.validate_soft_fail_policy(
            shield.FULL_WORKFLOW,
            "steps:\n"
            "  - name: Upload test diagnostics\n"
            "    continue-on-error: true\n"
            "    uses: actions/upload-artifact@"
            "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a\n",
            failures,
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("logs/job summaries", failures[0])

    def test_current_repository_satisfies_wp3_guard(self) -> None:
        self.assertEqual(shield.validate_repository(), [])


if __name__ == "__main__":
    unittest.main()
