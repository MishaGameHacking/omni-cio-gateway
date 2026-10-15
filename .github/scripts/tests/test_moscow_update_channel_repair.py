from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".github/scripts/repair_moscow_update_channel.sh"
RUNNER = ROOT / ".github/scripts/run_moscow_update_channel_repair.py"
WORKFLOW = ROOT / ".github/workflows/repair-moscow-update-channel.yml"


class MoscowUpdateChannelRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_exact_existing_moscow_server_is_required(self):
        for value in (
            'SERVER_ID="9334503"',
            'EXPECTED_IP="176.98.178.81"',
            'EXPECTED_HOST="176.98.178.81.sslip.io"',
            "target server is not verified as Moscow",
            "expected IP {EXPECTED_IP} is not attached",
        ):
            self.assertIn(value, self.script)
        self.assertNotIn('request("POST", "/servers",', self.script)
        self.assertNotIn("create_server", self.script.lower())

    def test_only_verified_immutable_release_can_be_published(self):
        for value in (
            'VERSION_CODE="23"',
            'VERSION_NAME="0.6.0-preview"',
            'APK_SHA256="31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"',
            'APK_BYTES="4100464"',
            'CERTIFICATE_SHA256="bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"',
            'report.get("device_install_test") != "passed_on_emulators_not_a_physical_phone"',
            'report.get("signature_v2") is not True',
        ):
            self.assertIn(value, self.script)
        self.assertIn("Release asset checksum mismatch", self.workflow)
        self.assertIn("release.target_commitish !==", self.workflow)

    def test_backend_data_and_environment_are_preserved_with_rollback(self):
        self.assertIn('cp -a "$BACKEND_PATH" "$BACKUP_ROOT/backend"', self.script)
        self.assertIn('cp -a "$ENV_FILE" "$BACKUP_ROOT/backend.env"', self.script)
        self.assertIn("rollback()", self.script)
        self.assertIn("systemctl restart analyst-ai-backend", self.script)
        self.assertNotIn("/var/lib/analyst-ai/backend.db", self.script)

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
            self.assertIn(value, self.script)

    def test_public_hostname_is_verified_after_restart(self):
        self.assertIn('"https://$EXPECTED_HOST/health"', self.script)
        self.assertIn(
            '"https://$EXPECTED_HOST/client/update-policy?package_name=$PACKAGE_NAME"',
            self.script,
        )
        self.assertIn("sha256sum -c -", self.script)

    def test_readonly_constants_are_passed_only_to_child_processes(self):
        spec = spec_from_file_location("repair_launcher", RUNNER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        patched = module.patched_source()
        expected = (
            '    env SERVER_ID="$SERVER_ID" SSH_KEY_ID=',
            'env APK_PATH="$APK_UNIX" REPORT_PATH=',
            'env SSH_PUBLIC_KEY_PATH="$SSH_PUBLIC_KEY_PATH" STATE_PATH=',
            'env POLICY_PATH="$READBACK_POLICY" PACKAGE_NAME=',
        )
        for prefix in expected:
            self.assertEqual(sum(line.startswith(prefix) for line in patched.splitlines()), 1)
        self.assertIn("--check", self.runner)
        self.assertIn("READONLY_ENV_REPAIR_CHECK=passed", self.runner)

    def test_cloud_access_is_marker_gated_and_validated_first(self):
        self.assertIn("[repair-update-channel]", self.workflow)
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertIn("Validate repair workflow before cloud access", self.workflow)
        self.assertIn("run_moscow_update_channel_repair.py --check", self.workflow)
        self.assertIn("py -3 .github\\scripts\\run_moscow_update_channel_repair.py", self.workflow)
        validation = self.workflow.index("Validate repair workflow before cloud access")
        download = self.workflow.index("Download exact immutable verified release")
        repair = self.workflow.index("Repair canonical backend and update channel")
        self.assertLess(validation, download)
        self.assertLess(download, repair)


if __name__ == "__main__":
    unittest.main()
