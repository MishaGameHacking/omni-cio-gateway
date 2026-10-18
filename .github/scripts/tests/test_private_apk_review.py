"""Private APK retention must not be a deployment or bypass emulator verification."""
from pathlib import Path
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
        result = subprocess.run([node, "--test", str(test)], capture_output=True,
                                text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("# pass 8", result.stdout)

    def test_retention_follows_existing_complete_emulator_gate(self):
        source = (ROOT / ".github/workflows/android-ci.yml").read_text(encoding="utf-8")
        validation = source.index("uses: ./.github/actions/check-apk")
        retention = source.index("- name: Retain requested device-test APK as a private draft")
        self.assertLess(validation, retention)
        self.assertIn("if: success()", source[retention:])
        self.assertNotIn("continue-on-error", source[retention:])
        self.assertIn('RUN_PROFILE_UI_TESTS: "1"', source[:retention])
        self.assertIn("- name: Record synthetic UI evidence and reports\n        if: always()", source)


if __name__ == "__main__":
    unittest.main()
