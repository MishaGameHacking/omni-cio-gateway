"""Regression tests for the shared physical Android lab and release bootstrap."""
from __future__ import annotations

import re
import unittest
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

    @staticmethod
    def lab_block(workflow: str) -> str:
        match = re.search(
            r"(?ms)^    concurrency:\s*\n"
            r"(?:      [^\n]+\n)*?"
            r"      group: analyst-android-lab\s*\n"
            r"(?:      [^\n]+\n)*?"
            r"      cancel-in-progress: (?P<value>true|false)\s*$",
            workflow,
        )
        if match is None:
            raise AssertionError("shared Android lab concurrency block is missing")
        return match.group("value")

    def test_pr_job_never_cancels_an_active_release(self) -> None:
        self.assertEqual(self.lab_block(self.ci), "false")
        self.assertEqual(self.lab_block(self.release), "false")

    def test_stale_heads_from_the_same_pr_are_still_cancelled(self) -> None:
        self.assertIn(
            "group: android-ci-${{ github.event.pull_request.number || github.run_id }}",
            self.ci,
        )
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            self.ci,
        )

    def test_gradle_wrapper_is_verified_without_flaky_setup_action(self) -> None:
        for workflow in (self.ci, self.release):
            self.assertNotIn("gradle/actions/setup-gradle@", workflow)
            self.assertIn("Verify pinned Gradle wrapper", workflow)
            self.assertIn(self.WRAPPER_SHA256, workflow)
            self.assertIn("call gradlew.bat --version", workflow)


if __name__ == "__main__":
    unittest.main()
