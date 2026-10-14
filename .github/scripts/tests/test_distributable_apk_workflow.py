"""Cheap source checks for the expensive distributable-APK workflow contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "android-apk.yml"
ACTION = ROOT / ".github" / "actions" / "check-apk" / "action.yml"
REFERENCE_DIGEST = "40e1edcc31f2f2826ad7cfa6733c67bf1db0f2ab9e0c648a78045f21aa221532"


class DistributableApkWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.action = ACTION.read_text(encoding="utf-8")

    def test_workflow_builds_debug_fixture_and_preview(self):
        self.assertIn(":app:assembleDebug", self.workflow)
        self.assertIn(":app:assemblePreview", self.workflow)
        self.assertIn('RUN_PROFILE_UI_TESTS: "1"', self.workflow)

    def test_workflow_pins_the_real_installed_reference_apk(self):
        self.assertIn("Analyst-AI-0.5.1-preview-af5713e.apk", self.workflow)
        self.assertIn(REFERENCE_DIGEST, self.workflow)
        self.assertIn("core.exportVariable('PREVIOUS_APK'", self.workflow)

    def test_verification_finishes_before_artifact_retention(self):
        verification = self.workflow.index("uses: ./.github/actions/check-apk")
        retention = self.workflow.index("uses: actions/upload-artifact@")
        self.assertLess(verification, retention)

    def test_validation_source_changes_retrigger_main_apk(self):
        self.assertIn('- ".github/scripts/**"', self.workflow)
        self.assertIn('- "backend/installation_evidence.py"', self.workflow)

    def test_composite_action_is_fail_closed_and_always_tests_upgrade(self):
        self.assertIn("PREVIOUS_APK is required", self.action)
        self.assertIn("RUN_PROFILE_UI_TESTS must be 1", self.action)
        self.assertEqual(self.action.count('--previous "%PREVIOUS_APK%"'), 2)
        self.assertNotIn("if defined PREVIOUS_APK goto upgrade", self.action)


if __name__ == "__main__":
    unittest.main()
