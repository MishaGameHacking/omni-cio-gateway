from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

import scripts.check_v10_npm_audit_policy as audit_policy
import scripts.check_v10_regression_shield as shield
import scripts.run_v10_npm_audit as npm_audit


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

    def test_self_hosted_bootstrap_requires_native_git_bash_exposure(self) -> None:
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
                "git config --local --unset-all credential.helper\n"
                'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"\n'
                'test -z "$(git config --local --get-all credential.helper || true)"\n',
                failures,
            )
            self.assertTrue(
                any(
                    "Expose installed Git Bash before repository bootstrap" in failure
                    for failure in failures
                ),
                failures,
            )
            self.assertTrue(
                any(
                    "Get-Command git.exe -ErrorAction Stop" in failure
                    for failure in failures
                ),
                failures,
            )

    def test_self_hosted_bootstrap_requires_credential_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            failures: list[str] = []
            shield.validate_self_hosted_repository_bootstrap(
                path,
                "runs-on: [self-hosted, Windows, X64, omni-cio-ci]\n"
                "Expose installed Git Bash before repository bootstrap\n"
                "Get-Command git.exe -ErrorAction Stop\n"
                "Join-Path $root 'bin'\n"
                "Join-Path $bin 'bash.exe'\n"
                "$env:GITHUB_PATH\n"
                "-Encoding utf8 -Append\n"
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
                    "Expose installed Git Bash before repository bootstrap\n"
                    "Get-Command git.exe -ErrorAction Stop\n"
                    "Join-Path $root 'bin'\n"
                    "Join-Path $bin 'bash.exe'\n"
                    "$env:GITHUB_PATH\n"
                    "-Encoding utf8 -Append\n"
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

    def test_npm_audit_classifies_observed_tls_break(self) -> None:
        stderr = (
            "npm warn audit request to https://registry.npmjs.org/-/npm/v1/security/"
            "advisories/bulk failed, reason: Client network socket disconnected before "
            "secure TLS connection was established\n"
            "npm error audit endpoint returned an error\n"
        )
        self.assertTrue(npm_audit.is_transient_registry_failure("", stderr))

    def test_npm_audit_retries_transient_then_requires_success(self) -> None:
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
        commands: list[list[str]] = []
        delays: list[float] = []

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return next(results)

        status = npm_audit.run_audit(
            npm="npm",
            attempts=3,
            backoff_seconds=2.0,
            runner=runner,
            sleeper=delays.append,
        )

        self.assertEqual(status, 0)
        self.assertEqual(len(commands), 2)
        self.assertEqual(delays, [2.0])
        self.assertEqual(commands[0], ["npm", "audit", "--audit-level=high"])

    def test_npm_audit_security_finding_is_not_retried(self) -> None:
        calls = 0

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="# npm audit report\ncritical severity vulnerability\n",
                stderr="npm error ECONNRESET after advisory response\n",
            )

        status = npm_audit.run_audit(
            npm="npm",
            attempts=3,
            runner=runner,
            sleeper=lambda _delay: self.fail("security findings must not sleep/retry"),
        )

        self.assertEqual(status, 1)
        self.assertEqual(calls, 1)

    def test_npm_audit_transient_exhaustion_stays_red(self) -> None:
        calls = 0
        delays: list[float] = []

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="",
                stderr="npm error ETIMEDOUT registry transport failed\n",
            )

        status = npm_audit.run_audit(
            npm="npm",
            attempts=3,
            backoff_seconds=1.0,
            runner=runner,
            sleeper=delays.append,
        )

        self.assertEqual(status, 1)
        self.assertEqual(calls, 3)
        self.assertEqual(delays, [1.0, 2.0])

    def test_npm_audit_policy_rejects_one_shot_workflow(self) -> None:
        failures: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            path.write_text(
                "permissions:\n  contents: read\n"
                "steps:\n"
                "  - name: Audit Web dependencies\n"
                "    run: npm audit --audit-level=high\n",
                encoding="utf-8",
            )
            audit_policy.validate_npm_audit_workflow(path, failures)
        self.assertEqual(len(failures), 2)
        self.assertTrue(any("bounded audit wrapper" in item for item in failures))
        self.assertTrue(any("one-shot npm audit" in item for item in failures))

    def test_npm_audit_policy_rejects_raw_command_variants(self) -> None:
        raw_commands = (
            "npm audit",
            "npm.cmd audit --audit-level=critical",
            'call "C:\\Program Files\\nodejs\\npm.cmd" audit --audit-level moderate',
            "npm audit --audit-level low",
        )
        for command in raw_commands:
            with self.subTest(command=command):
                self.assertTrue(audit_policy._contains_direct_one_shot_audit(command))

        wrapper_command = (
            "python ..\\..\\scripts\\run_v10_npm_audit.py --npm "
            '"C:\\Program Files\\nodejs\\npm.cmd" --audit-level high'
        )
        self.assertFalse(audit_policy._contains_direct_one_shot_audit(wrapper_command))

    def test_current_repository_satisfies_wp3_guard(self) -> None:
        self.assertEqual(shield.validate_repository(), [])
        self.assertEqual(audit_policy.validate_repository(), [])


if __name__ == "__main__":
    unittest.main()
