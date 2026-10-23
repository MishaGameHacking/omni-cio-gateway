"""Exercise the native Node suite and the synchronous CI entry point."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]


class SonarGateRunnerTests(unittest.TestCase):
    def test_registered_cases_and_ci_entry_point_agree(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required for the Sonar quality gate")
        native = subprocess.run(
            [node, "--test", "--test-reporter=tap", "require_clean_sonar.test.cjs"],
            cwd=SCRIPTS, capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(native.returncode, 0, native.stdout + native.stderr)
        summary = re.search(r"^# tests (\d+)$", native.stdout, re.MULTILINE)
        self.assertIsNotNone(summary, native.stdout)
        count = int(summary[1])
        self.assertGreater(count, 0)
        for field in ("fail", "cancelled", "skipped", "todo"):
            self.assertRegex(native.stdout, rf"(?m)^# {field} 0$")
        direct = subprocess.run(
            [node, "-e", "console.log(require('./require_clean_sonar.test.cjs').runTests())"],
            cwd=SCRIPTS, capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(direct.returncode, 0, direct.stdout + direct.stderr)
        self.assertEqual(direct.stdout.strip(), str(count))


if __name__ == "__main__":
    unittest.main()
