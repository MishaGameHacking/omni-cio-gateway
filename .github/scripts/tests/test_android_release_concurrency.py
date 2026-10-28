"""Regression tests for the shared Android host and release bootstrap."""
from __future__ import annotations

import unittest
import ast
from pathlib import Path


class AndroidReleaseConcurrencyTests(unittest.TestCase):
    WRAPPER_SHA256 = "238e777fcddd7e34f9708186085def2abd6e08e658505b38718d79d74c21abd5"

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[3]
        cls.ci = (cls.root / ".github" / "workflows" / "android-ci.yml").read_text(
            encoding="utf-8"
        )
        cls.release = (
            cls.root / ".github" / "workflows" / "android-apk.yml"
        ).read_text(encoding="utf-8")
        cls.install_driver = (
            cls.root / ".github" / "scripts" / "test_apk_installation.py"
        ).read_text(encoding="utf-8")
        cls.lease = (
            cls.root / ".github" / "scripts" / "emulator_lease.py"
        ).read_text(encoding="utf-8")

    def test_unrelated_prs_and_releases_cannot_cancel_each_other(self) -> None:
        self.assertIn(
            "group: analyst-android-pr-${{ github.event.pull_request.number || github.run_id }}",
            self.ci,
        )
        self.assertIn(
            "group: analyst-android-release-${{ github.ref }}",
            self.release,
        )
        self.assertNotIn("group: analyst-android-lab", self.ci)
        self.assertNotIn("group: analyst-android-lab", self.release)
        self.assertGreaterEqual(self.ci.count("cancel-in-progress: false"), 1)
        self.assertGreaterEqual(self.release.count("cancel-in-progress: false"), 2)

    def test_active_pr_checks_finish_their_private_resource_cleanup(self) -> None:
        self.assertIn(
            "group: android-ci-${{ github.event.pull_request.number || github.run_id }}",
            self.ci,
        )
        self.assertIn(
            "cancel-in-progress: false",
            self.ci,
        )

        self.assertIn("Delete only this run private CI handoff and verify absence", self.ci)
        self.assertIn("if: always() && ((github.event_name == 'pull_request'", self.ci)
        self.assertIn("github.ref == 'refs/heads/main'", self.ci)

    def test_host_wide_os_lease_serializes_actual_emulator_access(self) -> None:
        self.assertIn("with exclusive_emulator():", self.install_driver)
        self.assertIn("tempfile.gettempdir()", self.lease)
        self.assertIn("android.lock", self.lease)
        self.assertIn("Four runners on one laptop", self.lease)

    def test_gradle_wrapper_is_verified_without_flaky_setup_action(self) -> None:
        self.assertIn("uses: ./.github/workflows/android-ci.yml", self.release)
        self.assertNotIn("gradle/actions/setup-gradle@", self.ci)
        self.assertIn('windows_android_ci.py" build\n', self.ci)
        source = (self.root / ".github/scripts/windows_android_ci.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        assignment = next(node for node in module.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "WRAPPER_SHA256" for target in node.targets))
        self.assertEqual(ast.literal_eval(assignment.value), self.WRAPPER_SHA256)
        verify = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "verify_machine")
        self.assertIn('file_identity(root / "gradle/wrapper/gradle-wrapper.jar")["sha256"] == WRAPPER_SHA256',
                      ast.get_source_segment(source, verify))
        build = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "build_worker")
        calls = [node for node in ast.walk(build) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "run" and node.args and isinstance(node.args[0], ast.Constant)
                 and node.args[0].value == "gradle-version"]
        self.assertEqual(len(calls), 1)
        self.assertIn("--version", [node.value for node in ast.walk(calls[0]) if isinstance(node, ast.Constant)])


if __name__ == "__main__":
    unittest.main()
