"Cheap source checks for the expensive distributable-APK workflow contract."
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "android-apk.yml"
ACTION = ROOT / ".github" / "actions" / "check-apk" / "action.yml"
INSTALLER = ROOT / ".github" / "scripts" / "test_apk_installation.py"
REFERENCE_DIGEST = "4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6"


class DistributableApkWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caller = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github/workflows/android-ci.yml").read_text(encoding="utf-8")
        cls.action = ACTION.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.helper = (ROOT / ".github/scripts/windows_android_ci.py").read_text(encoding="utf-8")
        cls.module = ast.parse(cls.helper)

    def test_workflow_builds_debug_fixture_and_preview(self):
        build = self.workflow.split("  build:\n", 1)[1].split("  runtime:\n", 1)[0]
        self.assertIn('windows_android_ci.py" build\n', build)
        self.assertIn("RUN_PROFILE_UI_TESTS: '1'", self.workflow)
        tasks = next(node.value for node in self.module.body if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "GRADLE_TASKS" for target in node.targets))
        self.assertEqual(ast.literal_eval(tasks), (
            ":app:testDebugUnitTest", ":app:lintDebug", ":app:lintPreview", ":app:assembleDebug",
            ":app:assembleRelease", ":app:assemblePreview", ":ci-ui-driver:lintDebug", ":ci-ui-driver:assembleDebug"))
        worker = next(node for node in self.module.body if isinstance(node, ast.FunctionDef) and node.name == "build_worker")
        self.assertTrue(any(isinstance(node, ast.Starred) and isinstance(node.value, ast.Name)
                            and node.value.id == "GRADLE_TASKS" for node in ast.walk(worker)))

    def test_preflight_exports_its_attempt_only_after_verified_preparation(self):
        preflight = self.workflow[self.workflow.index("  transfer-preflight:"):
                                  self.workflow.index("  build:")]
        self.assertIn("prepared_attempt: ${{ steps.prepare.outputs.prepared_attempt }}", preflight)
        preparation = preflight[preflight.index("- name: Verify synthetic draft handoff"):
                                preflight.index("- name: Remove the temporary draft")]
        self.assertIn("id: prepare\n", preparation)
        self.assertIn(
            "await require('./.github/scripts/ci_private_transfer.cjs')"
            "({github, context, core, command:'prepare'});\n"
            "          core.setOutput('prepared_attempt', process.env.GITHUB_RUN_ATTEMPT);",
            preparation,
        )
        self.assertNotIn("continue-on-error", preparation)

    def test_runtime_prepares_only_an_evidence_attempt_not_already_verified(self):
        build = self.workflow.split("  build:\n", 1)[1].split("  runtime:\n", 1)[0]
        runtime = self.workflow.split("  runtime:\n", 1)[1].split("  collect:\n", 1)[0]
        self.assertIn("    needs:\n    - transfer-preflight\n", build)
        self.assertNotIn("command:'upload'", build)
        self.assertNotIn("command:'download'", runtime)
        self.assertIn('windows_android_ci.py" pack\n', build)
        self.assertIn("input_receipt_sha256: ${{ steps.pack_inputs.outputs.input_receipt_sha256 }}", build)
        self.assertIn("CI_INPUT_RECEIPT_SHA256: ${{ needs.build.outputs.input_receipt_sha256 }}", runtime)
        start = runtime.index("- name: Prepare the private evidence return for a later rerun attempt")
        end = runtime.index("- name: Remove this run draft immediately when rerun preparation fails")
        preparation = runtime[start:end]
        self.assertIn("id: prepare_return\n", preparation)
        self.assertIn("if: needs.transfer-preflight.outputs.prepared_attempt != format('{0}', github.run_attempt)", preparation)
        self.assertIn("ci_private_transfer.cjs')({github, context, core, command:'prepare'});", preparation)
        self.assertNotIn("continue-on-error", preparation)

    def test_failed_rerun_preparation_cleans_up_before_native_runtime(self):
        runtime = self.workflow.split("  runtime:\n", 1)[1].split("  collect:\n", 1)[0]
        cleanup = runtime.split("- name: Remove this run draft immediately when rerun preparation fails", 1)[1]
        cleanup = cleanup.split("- name: Copy verified retained inputs", 1)[0]
        self.assertIn("if: failure() && steps.prepare_return.outcome == 'failure'", cleanup)
        self.assertIn("ci_private_transfer.cjs')({github, context, core, command:'cleanup'});", cleanup)
        self.assertNotIn("continue-on-error", cleanup)
        self.assertLess(runtime.index("command:'prepare'"), runtime.index('windows_android_ci.py" runtime-prepare'))

    def test_workflow_pins_the_real_installed_reference_apk(self):
        build = self.workflow.split("  build:\n", 1)[1].split("  runtime:\n", 1)[0]
        self.assertIn("Analyst-AI-43-" + REFERENCE_DIGEST + ".apk", build)
        self.assertIn("version_code: 43", build)
        self.assertIn("bytes: 29771254", build)
        self.assertIn("core.exportVariable('PREVIOUS_APK'", build)
        self.assertIn("redirect: 'error'", build)
        self.assertIn("total > expected.bytes", build)
        self.assertIn("digest.digest('hex') !== expected.sha256", build)
        self.assertIn("Saved baseline43 read-back differs", build)
        self.assertNotIn("android-preview-0a894dd", build)
        self.assertNotIn("Analyst-AI-0.5.1-preview", build)

    def test_verification_and_private_return_finish_before_artifact_retention(self):
        runtime = self.workflow.split("  runtime:\n", 1)[1].split("  collect:\n", 1)[0]
        self.assertLess(runtime.index('windows_android_ci.py" validate'), runtime.index('windows_android_ci.py" export'))
        self.assertLess(runtime.index('windows_android_ci.py" export'), runtime.index("command:'upload'"))
        publication = self.workflow.split("  publication:\n", 1)[1].split("  verify:\n", 1)[0]
        self.assertIn("    needs:\n    - runtime\n    - collect\n    - cleanup\n", publication)
        for job in ("runtime", "collect", "cleanup"):
            self.assertIn("needs." + job + ".result == 'success'", publication)
        self.assertLess(publication.index('windows_android_ci.py" inspect-retained'),
                        publication.index("- name: Retain APK and verification evidence when storage is available"))
        worker = next(node for node in self.module.body if isinstance(node, ast.FunctionDef) and node.name == "worker")
        validation_calls = [node for node in ast.walk(worker) if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute) and node.func.attr == "run"
                            and node.args and isinstance(node.args[0], ast.Constant)
                            and node.args[0].value == "distribution-validation"]
        self.assertEqual(len(validation_calls), 1)
        self.assertIn(".github/scripts/validate_distribution.py", [node.value for node in ast.walk(validation_calls[0])
                      if isinstance(node, ast.Constant)])

    def test_optional_artifact_retention_cannot_hide_missing_evidence(self):
        publication = self.workflow.split("  publication:\n", 1)[1].split("  verify:\n", 1)[0]
        retained = publication.index('windows_android_ci.py" inspect-retained')
        start = publication.index("- name: Retain APK and verification evidence when storage is available")
        end = publication.index("- name: Report unavailable optional Actions retention")
        block = publication[start:end]
        self.assertLess(retained, start)
        self.assertIn("id: retain_apk", block)
        self.assertIn("github.ref == 'refs/heads/main'", block)
        self.assertIn("[publish-apk]", block)
        self.assertIn("continue-on-error: true", block)
        self.assertIn("if-no-files-found: error", block)
        self.assertIn("retention-days: 1", block)
        self.assertIn("${{ steps.retained.outputs.retained_root }}/app/build/outputs/apk/preview/app-preview.apk", block)
        self.assertIn("if: steps.retain_apk.outcome == 'failure'", publication)
        inspect = next(node for node in self.module.body if isinstance(node, ast.FunctionDef) and node.name == "inspect_retained")
        calls = {node.func.id for node in ast.walk(inspect) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertTrue({"require_runtime_inputs", "source_identity", "file_identity", "runtime_reference"} <= calls)
        self.assertIn('receipt.get("full_matrix_passed") is True', ast.get_source_segment(self.helper, inspect))

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

    def test_main_reuses_the_complete_laptop_runtime_private_return_and_cleanup(self):
        self.assertIn("uses: ./.github/workflows/android-ci.yml", self.caller)
        self.assertNotIn("runs-on:", self.caller)
        self.assertIn("workflow_call:", self.workflow)
        self.assertIn("TIMEWEB_CLOUD_TOKEN: ${{ secrets.TIMEWEB_CLOUD_TOKEN }}", self.caller)
        self.assertNotIn("secrets: inherit", self.caller)
        runtime = self.workflow.split("  runtime:\n", 1)[1].split("  collect:\n", 1)[0]
        self.assertIn("    - self-hosted\n    - Windows\n    - X64\n    - omni-cio-ci\n", runtime)
        self.assertNotIn("runs-on: ubuntu", runtime)
        for page in (16384, 4096):
            self.assertIn('windows_android_ci.py" profile-' + str(page) + '\n', runtime)
        self.assertNotIn("continue-on-error", runtime)
        profile = next(node for node in self.module.body if isinstance(node, ast.FunctionDef) and node.name == "profile_worker")
        runs = [node for node in ast.walk(profile) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "runpy" and node.func.attr == "run_path"]
        self.assertEqual(len(runs), 1)
        self.assertEqual({arg.arg: ast.literal_eval(arg.value) for arg in runs[0].keywords}, {"run_name": "__main__"})
        publication = self.workflow.split("  publication:\n", 1)[1].split("  verify:\n", 1)[0]
        publish = publication[publication.index("- name: Publish verified APK to GitHub Releases"):]
        self.assertLess(publish.index("require_main_release.cjs"), publish.index("createRelease"))
        self.assertNotIn("command:'cleanup'", publication)
        for required in ("needs.collect.result", "needs.cleanup.result", "needs.publication.result"):
            self.assertIn(required, self.workflow)

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
        self.assertIn('checked_installation(p.api, p.page_size_bytes, version_code=version)', validator)
        self.assertIn('for p in RUNTIME_PROFILES', validator)
        self.assertIn("version = report.get('version_code')", validator)
        self.assertIn("type(version) is int and 1 <= version <= 2_100_000_000", validator)
        self.assertIn('candidate_version_code=version_code', validator)
        self.assertIn("from_ci_reports(report['installation_tests'], report['sha256'], version_code=version)", validator)
        self.assertIn('CURRENT_UI_SUITE = "analyst-2d-live-v4"', contract)
        self.assertIn('UI_V4_MIN_VERSION_CODE = 38', contract)
        self.assertIn("verify_automation_artifacts(ui['automation_report'], archive)", validator)
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
