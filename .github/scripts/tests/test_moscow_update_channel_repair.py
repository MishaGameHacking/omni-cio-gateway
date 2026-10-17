from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".github/scripts/repair_moscow_update_channel.sh"
RUNNER = ROOT / ".github/scripts/run_moscow_update_channel_repair.py"
WORKFLOW = ROOT / ".github/workflows/repair-moscow-update-channel.yml"

RELEASE_COMMIT = "feb08a704e889644772c38808eebbc2d1edbb81f"
RELEASE_TAG = f"android-preview-{RELEASE_COMMIT}"
RELEASE_APK_NAME = "Analyst-AI-0.7.6-preview-feb08a7.apk"
RELEASE_APK_SHA256 = "0bb5e481f035218084b797e667c5850f9cb4b2c44ddca49a118bc61d7fe6306d"
RELEASE_REPORT_SHA256 = "994ce504596530ef5e9564edcb82d56302411c5302b3bcb29a9efe46d6a9fe7f"
CERTIFICATE_SHA256 = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"


class MoscowUpdateChannelRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        spec = spec_from_file_location("repair_launcher", RUNNER)
        if spec is None or spec.loader is None:
            raise AssertionError("repair launcher cannot be imported")
        cls.module = module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.patched = cls.module.patched_source()

    def test_exact_existing_moscow_server_is_required(self):
        for value in (
            'SERVER_ID="9334503"',
            'EXPECTED_IP="176.98.178.81"',
            'EXPECTED_HOST="176.98.178.81.sslip.io"',
            "target server is not verified as Moscow",
            "expected IP {EXPECTED_IP} is not attached",
        ):
            self.assertIn(value, self.patched)
        self.assertNotIn('request("POST", "/servers",', self.patched)
        self.assertNotIn("create_server", self.patched.lower())

    def test_only_exact_verified_076_release_can_be_published(self):
        for value in (
            'VERSION_CODE="31"',
            'VERSION_NAME="0.7.6-preview"',
            f'APK_SHA256="{RELEASE_APK_SHA256}"',
            'APK_BYTES="4167540"',
            f'CERTIFICATE_SHA256="{CERTIFICATE_SHA256}"',
            'MIN_SDK="36"',
            'PUBLISHED_AT="1792214870"',
            'report.get("device_install_test") != "passed_on_emulators_not_a_physical_phone"',
            'report.get("signature_v2") is not True',
        ):
            self.assertIn(value, self.patched)
        for stale in (
            'VERSION_CODE="23"',
            'VERSION_CODE="26"',
            'VERSION_NAME="0.6.0-preview"',
            'VERSION_NAME="0.7.1-preview"',
            'APK_SHA256="31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"',
            'APK_SHA256="343f46a392f93c5d6014f639d2e1e07ce31c7ffbf3fdd28e85cdeb8659c155a7"',
            'APK_BYTES="4100464"',
            'APK_BYTES="4151124"',
            'MIN_SDK="33"',
            'assert payload["version_code"] == 23',
            'assert payload["version_code"] == 26',
            'assert payload["minimum_version_code"] == 23',
            'assert payload["minimum_version_code"] == 26',
            'assert payload["version_name"] == "0.6.0-preview"',
            'assert payload["version_name"] == "0.7.1-preview"',
            'assert payload["apk_bytes"] == 4100464',
            'assert payload["apk_bytes"] == 4151124',
        ):
            self.assertNotIn(stale, self.patched)
        self.assertIn("Главная без панели «Живые возможности»", self.patched)
        self.assertIn("полезные данные портфеля", self.patched)

    def test_local_and_public_policy_readback_expect_the_same_076_identity(self):
        expected_twice = (
            'assert payload["version_code"] == 31',
            'assert payload["minimum_version_code"] == 31',
            'assert payload["version_name"] == "0.7.6-preview"',
            f'assert payload["apk_sha256"] == "{RELEASE_APK_SHA256}"',
            'assert payload["apk_bytes"] == 4167540',
        )
        for marker in expected_twice:
            with self.subTest(marker=marker):
                self.assertEqual(self.patched.count(marker), 2)

    def test_release_replacement_counts_fail_closed(self):
        with self.assertRaises(RuntimeError):
            self.module.replace_exact_count("marker marker", "marker", "new", 1)
        with self.assertRaises(RuntimeError):
            self.module.replace_exact_count("already new", "old", "new", 1)

    def test_workflow_pins_release_commit_assets_and_digests(self):
        for value in (
            f"RELEASE_TAG: {RELEASE_TAG}",
            f"RELEASE_APK_NAME: {RELEASE_APK_NAME}",
            f"RELEASE_APK_SHA256: {RELEASE_APK_SHA256}",
            "RELEASE_REPORT_NAME: apk-verification.json",
            f"RELEASE_REPORT_SHA256: {RELEASE_REPORT_SHA256}",
            f"release.target_commitish !== '{RELEASE_COMMIT}'",
            "Release asset checksum mismatch",
        ):
            self.assertIn(value, self.workflow)
        self.assertNotIn("android-preview-e0b82ba5", self.workflow)
        self.assertNotIn("Analyst-AI-0.7.1-preview", self.workflow)

    def test_backend_data_and_environment_are_preserved_with_rollback(self):
        self.assertIn('cp -a "$BACKEND_PATH" "$BACKUP_ROOT/backend"', self.patched)
        self.assertIn('cp -a "$ENV_FILE" "$BACKUP_ROOT/backend.env"', self.patched)
        self.assertIn("rollback()", self.patched)
        self.assertIn("systemctl restart analyst-ai-backend", self.patched)
        self.assertNotIn("/var/lib/analyst-ai/backend.db", self.patched)

    def test_canonical_update_channel_layout_and_safe_activation(self):
        for value in (
            'RELEASE_ROOT="/var/lib/analyst-ai/releases/$PACKAGE_NAME"',
            'RETAINED_MANIFEST="$RELEASE_ROOT/${RELEASE_FILENAME%.apk}.json"',
            '"$RELEASE_ROOT/current.json.next"',
            'ANDROID_RELEASE_DIR=/var/lib/analyst-ai/releases',
            'ANDROID_UPDATES_ENABLED=false',
            '/client/update-policy?package_name=$PACKAGE_NAME',
            '/client/apk/$RELEASE_FILENAME?package_name=$PACKAGE_NAME',
        ):
            self.assertIn(value, self.patched)

    def test_public_hostname_is_verified_after_restart(self):
        self.assertIn('"https://$EXPECTED_HOST/health"', self.patched)
        self.assertIn(
            '"https://$EXPECTED_HOST/client/update-policy?package_name=$PACKAGE_NAME"',
            self.patched,
        )
        self.assertIn("sha256sum -c -", self.patched)

    def test_readonly_constants_are_passed_only_to_child_processes(self):
        expected = (
            '    env SERVER_ID="$SERVER_ID" SSH_KEY_ID=',
            'env APK_PATH="$APK_UNIX" REPORT_PATH=',
            'env SSH_PUBLIC_KEY_PATH="$SSH_PUBLIC_KEY_PATH" STATE_PATH=',
            'env POLICY_PATH="$READBACK_POLICY" PACKAGE_NAME=',
        )
        for prefix in expected:
            self.assertEqual(
                sum(line.startswith(prefix) for line in self.patched.splitlines()),
                1,
            )
        self.assertIn("RELEASE_REPLACEMENTS", self.runner)
        self.assertIn("replace_exact_count", self.runner)
        self.assertIn("--check", self.runner)
        self.assertIn("READONLY_ENV_REPAIR_CHECK=passed", self.runner)

    def test_cloud_access_is_marker_gated_and_validated_first(self):
        self.assertIn("[repair-update-channel]", self.workflow)
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertIn("Validate repair workflow before cloud access", self.workflow)
        self.assertIn("run_moscow_update_channel_repair.py --check", self.workflow)
        self.assertIn(
            "py -3 .github\\scripts\\run_moscow_update_channel_repair.py",
            self.workflow,
        )
        validation = self.workflow.index("Validate repair workflow before cloud access")
        download = self.workflow.index("Download exact immutable verified release")
        repair = self.workflow.index("Repair canonical backend and update channel")
        self.assertLess(validation, download)
        self.assertLess(download, repair)


if __name__ == "__main__":
    unittest.main()

