"Cheap source checks for the expensive distributable-APK workflow contract."
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "android-apk.yml"
ACTION = ROOT / ".github" / "actions" / "check-apk" / "action.yml"
INSTALLER = ROOT / ".github" / "scripts" / "test_apk_installation.py"
REFERENCE_DIGEST = "739fb8b16865a742118ca1930bc2488a28c3cf807a23c20628df9ebb7ca75bcb"


class DistributableApkWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.action = ACTION.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")

    def test_workflow_builds_debug_fixture_and_preview(self):
        self.assertIn(":app:assembleDebug", self.workflow)
        self.assertIn(":app:assemblePreview", self.workflow)
        self.assertIn('RUN_PROFILE_UI_TESTS: "1"', self.workflow)

    def test_workflow_pins_the_real_installed_reference_apk(self):
        self.assertIn("Analyst-AI-0.7.5-preview-bb6638f.apk", self.workflow)
        self.assertIn("android-preview-bb6638fab2188c718ccad4d8dd7b3ed76b34fdc8", self.workflow)
        self.assertIn(REFERENCE_DIGEST, self.workflow)
        self.assertIn("core.exportVariable('PREVIOUS_APK'", self.workflow)
        self.assertNotIn("Analyst-AI-0.5.1-preview", self.workflow)

    def test_verification_finishes_before_artifact_retention(self):
        verification = self.workflow.index("uses: ./.github/actions/check-apk")
        assertion = self.workflow.index("- name: Assert verified APK and evidence are present")
        retention = self.workflow.index("uses: actions/upload-artifact@")
        self.assertLess(verification, assertion)
        self.assertLess(assertion, retention)

    def test_optional_artifact_retention_cannot_hide_missing_evidence(self):
        assertion = self.workflow.index("- name: Assert verified APK and evidence are present")
        retention_start = self.workflow.index(
            "- name: Retain APK and verification evidence when storage is available"
        )
        retention_end = self.workflow.index(
            "- name: Report unavailable optional Actions retention", retention_start
        )
        assertion_block = self.workflow[assertion:retention_start]
        retention_block = self.workflow[retention_start:retention_end]
        self.assertIn('if not exist "app\\build\\outputs\\apk\\preview\\app-preview.apk" exit /b 1', assertion_block)
        self.assertIn('if not exist "app\\build\\outputs\\apk\\preview\\apk-verification.json" exit /b 1', assertion_block)
        self.assertIn("id: retain_apk", retention_block)
        self.assertIn("continue-on-error: true", retention_block)
        self.assertIn("if-no-files-found: error", retention_block)
        self.assertIn("retention-days: 1", retention_block)
        self.assertIn("if: steps.retain_apk.outcome == 'failure'", self.workflow)

    def test_release_is_explicit_and_independent_of_optional_artifact_storage(self):
        retention = self.workflow.index("uses: actions/upload-artifact@")
        publication = self.workflow.index("- name: Publish verified APK to GitHub Releases")
        self.assertLess(retention, publication)
        release_block = self.workflow[publication:]
        self.assertIn("github.ref == 'refs/heads/main'", release_block)
        self.assertIn("github.event_name == 'workflow_dispatch'", release_block)
        self.assertIn("github.event_name == 'push'", release_block)
        self.assertIn(
            "contains(github.event.head_commit.message, '[publish-apk]')",
            release_block,
        )
        self.assertIn("report.version_code <= 30", release_block)
        self.assertIn("hash !== report.sha256", release_block)

    def test_validation_source_changes_retrigger_main_apk(self):
        self.assertIn('- ".github/scripts/**"', self.workflow)
        self.assertIn('- "backend/installation_evidence.py"', self.workflow)

    def test_composite_action_is_fail_closed_and_always_tests_upgrade(self):
        self.assertIn("PREVIOUS_APK is required", self.action)
        self.assertIn("RUN_PROFILE_UI_TESTS must be 1", self.action)
        self.assertEqual(self.action.count('--previous "%PREVIOUS_APK%"'), 1)
        self.assertNotIn("if defined PREVIOUS_APK goto upgrade", self.action)

    def test_candidate_is_launched_before_and_after_clean_install(self):
        upgrade = self.installer.index('install("upgrade_to_candidate", apk, update=True)')
        upgrade_launch = self.installer.index('launch_candidate("upgrade_bootstrap_launch")')
        uninstall = self.installer.index('removed = device("uninstall", package)')
        clean = self.installer.index('install("candidate_clean_install", apk)')
        clean_launch = self.installer.index('launch_candidate("bootstrap_activity_launch")')
        self.assertLess(upgrade, upgrade_launch)
        self.assertLess(upgrade_launch, uninstall)
        self.assertLess(uninstall, clean)
        self.assertLess(clean, clean_launch)


if __name__ == "__main__":
    unittest.main()
