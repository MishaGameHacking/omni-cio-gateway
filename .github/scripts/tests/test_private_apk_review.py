"""Private APK retention must not be a deployment or bypass emulator verification."""
from pathlib import Path
import ast
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]


class PrivateApkReviewTests(unittest.TestCase):
    def test_publisher_behavior_with_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node is needed for private-APK publisher host regressions")
        test = Path(__file__).parent / "fixtures/private_apk_review.test.cjs"
        result = subprocess.run([node, "--test", "--test-reporter=tap", str(test)], capture_output=True,
                                text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("# pass 12", result.stdout)

    def test_retention_follows_existing_complete_emulator_gate(self):
        source = (ROOT / ".github/workflows/android-ci.yml").read_text(encoding="utf-8")
        runtime = source.split("  runtime:\n", 1)[1].split("  collect:\n", 1)[0]
        publication = source.split("  publication:\n", 1)[1].split("  verify:\n", 1)[0]
        for page in (4096, 16384):
            self.assertLess(runtime.index('windows_android_ci.py" profile-' + str(page)),
                            runtime.index('windows_android_ci.py" validate'))
        self.assertLess(runtime.index('windows_android_ci.py" validate'), runtime.index('windows_android_ci.py" export'))
        self.assertIn("if: always() && steps.export.outcome == 'success'", runtime)
        self.assertIn("    needs:\n    - runtime\n    - collect\n    - cleanup\n", publication)
        for job in ("runtime", "collect", "cleanup"):
            self.assertIn("needs." + job + ".result == 'success'", publication)
        retention = publication.index("- name: Retain requested device-test APK as a private draft")
        self.assertLess(publication.index('windows_android_ci.py" inspect-retained'), retention)
        self.assertIn("if: success()", publication[retention:])
        self.assertNotIn("continue-on-error", publication[retention:])
        self.assertIn("RUN_PROFILE_UI_TESTS: '1'", runtime)
        helper = (ROOT / ".github/scripts/windows_android_ci.py").read_text(encoding="utf-8")
        module = ast.parse(helper)
        worker = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "worker")
        calls = [node for node in ast.walk(worker) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "run" and node.args and isinstance(node.args[0], ast.Constant)
                 and node.args[0].value == "distribution-validation"]
        self.assertEqual(len(calls), 1)
        self.assertIn(".github/scripts/validate_distribution.py", [node.value for node in ast.walk(calls[0])
                      if isinstance(node, ast.Constant)])


if __name__ == "__main__":
    unittest.main()
