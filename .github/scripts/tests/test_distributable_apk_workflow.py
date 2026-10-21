"Cheap source checks for the expensive distributable-APK workflow contract."
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "android-apk.yml"
ACTION = ROOT / ".github" / "actions" / "check-apk" / "action.yml"
INSTALLER = ROOT / ".github" / "scripts" / "test_apk_installation.py"
REFERENCE_DIGEST = "3a31c602ec885a0d8cac8d76f43369cfb6ed3bdaa928f1cd7429582b0d5a40a3"


class DistributableApkWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caller = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github/workflows/android-ci.yml").read_text(encoding="utf-8")
        cls.action = ACTION.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")

    def test_workflow_builds_debug_fixture_and_preview(self):
        self.assertIn(":app:assembleDebug", self.workflow)
        self.assertIn(":app:assemblePreview", self.workflow)
        self.assertIn("RUN_PROFILE_UI_TESTS: '1'", self.workflow)

    def test_workflow_pins_the_real_installed_reference_apk(self):
        self.assertIn("Analyst-AI-0.10.0-preview-0a894dd.apk", self.workflow)
        self.assertIn("android-preview-0a894dddfa858efe6c7be60aea78935adec84c1b", self.workflow)
        self.assertIn(REFERENCE_DIGEST, self.workflow)
        self.assertIn("core.exportVariable('PREVIOUS_APK'", self.workflow)
        self.assertNotIn("Analyst-AI-0.5.1-preview", self.workflow)

    def test_verification_finishes_before_artifact_retention(self):
        verification = self.workflow.index("python3 .github/scripts/validate_distribution.py")
        assertion = self.workflow.index("- name: Assert verified APK and evidence are present")
        retention = self.workflow.index("- name: Retain APK and verification evidence when storage is available")
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
        self.assertIn("app-preview.apk", assertion_block)
        self.assertIn("apk-verification.json", assertion_block)
        self.assertIn(".is_file()", assertion_block)
        self.assertIn("raise RuntimeError", assertion_block)
        self.assertIn("id: retain_apk", retention_block)
        self.assertIn("github.ref == 'refs/heads/main'", retention_block)
        self.assertIn("[publish-apk]", retention_block)
        self.assertIn("continue-on-error: true", retention_block)
        self.assertIn("if-no-files-found: error", retention_block)
        self.assertIn("retention-days: 1", retention_block)
        self.assertIn("if: steps.retain_apk.outcome == 'failure'", self.workflow)

    def test_release_is_explicit_and_independent_of_optional_artifact_storage(self):
        retention = self.workflow.index("- name: Retain APK and verification evidence when storage is available")
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
        self.assertIn("report.version_code <= 34", release_block)
        self.assertIn("hash !== report.sha256", release_block)

    def test_validation_source_changes_retrigger_main_apk(self):
        self.assertIn('- ".github/scripts/**"', self.caller)
        self.assertIn('- "backend/installation_evidence.py"', self.caller)
        self.assertIn('- "tools/**"', self.caller)

    def test_main_reuses_the_complete_linux_runtime_and_cleanup(self):
        self.assertIn("uses: ./.github/workflows/android-ci.yml", self.caller)
        self.assertNotIn("runs-on:", self.caller)
        self.assertIn("workflow_call:", self.workflow)
        runtime = self.workflow[self.workflow.index("  runtime:"):self.workflow.index("  cleanup:")]
        self.assertIn("runs-on: ubuntu-24.04", runtime)
        self.assertIn("test_apk_installation.py", runtime)
        publication = runtime[runtime.index("- name: Publish verified APK to GitHub Releases"):]
        self.assertLess(publication.index("require_main_release.cjs"), publication.index("createRelease"))
        self.assertLess(publication.index("command:'cleanup'"), publication.index("createRelease"))
        self.assertIn("needs.cleanup.result", self.workflow)

    def test_composite_action_is_fail_closed_and_always_tests_upgrade(self):
        self.assertIn("PREVIOUS_APK is required", self.action)
        self.assertIn("RUN_PROFILE_UI_TESTS must be 1", self.action)
        self.assertEqual(self.action.count('--previous "%PREVIOUS_APK%"'), 2)
        self.assertNotIn("if defined PREVIOUS_APK goto upgrade", self.action)

    def test_both_current_os_page_size_profiles_run_full_ui(self):
        for size in (4096, 16384):
            self.assertIn(f'--api 37 --page-bytes {size}', self.action)
            self.assertIn(f'install-api37-{size}', self.action)
        contract = (ROOT / 'backend/android_runtime_contract.py').read_text(encoding='utf-8')
        self.assertIn('RuntimeProfile(37, 4096, "google_apis")', contract)
        self.assertIn('RuntimeProfile(37, 16384, "google_apis_ps16k")', contract)
        validator = (ROOT / '.github/scripts/validate_distribution.py').read_text(encoding='utf-8')
        self.assertIn('checked_installation(p.api, p.page_size_bytes)', validator)
        self.assertIn('upgrade_required=True', validator)
        self.assertIn('android_api=profile.api, page_size_bytes=profile.page_size_bytes', validator)
        self.assertIn("'profile_ui_required': True", validator)
        self.assertNotIn('if api in {35, 36}', self.installer)
        self.assertIn('device("shell", "getconf", "PAGE_SIZE")', self.installer)
        self.assertLess(self.installer.index('page_size = device'),
                        self.installer.index('install("previous_clean_install", previous)'))

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
