"""Runtime provenance must be bounded, read-only, and distinct from a UI pass."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_runtime import snapshot_runtime_environment
from kernel_page_size import system_image


class EmulatorRuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.sdk = Path(directory.name)

    def write_package(self, relative, contents):
        package = self.sdk / relative / "source.properties"
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text(contents, encoding="utf-8")

    def test_records_selected_installed_image_and_only_allowlisted_properties(self):
        self.write_package("emulator", "Pkg.Revision=36.4.5\n")
        self.write_package("platform-tools", "Pkg.Revision=36.0.0\n")
        image_path = Path(*system_image(37, 16384).split(";"))
        self.write_package(image_path, "Pkg.Revision=8\n")
        device = Mock(return_value=Mock(returncode=0, stdout=(
            "[ro.build.fingerprint]: [test/fingerprint]\n"
            "[dalvik.vm.usejit]: [true]\n[dalvik.vm.usejitprofiles]: []\n"
            "[unrelated.private.property]: [must-not-be-recorded]\n")))
        result = snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes=16384)
        self.assertEqual(result["sdk_packages"]["system-image"], {"revision": "8"})
        self.assertEqual(result["sdk_packages"]["emulator"], {"revision": "36.4.5"})
        self.assertEqual(result["properties"]["dalvik.vm.usejit"], "true")
        self.assertEqual(result["properties"]["dalvik.vm.usejitprofiles"], "")
        self.assertIsNone(result["properties"]["ro.build.version.sdk"])
        self.assertNotIn("unrelated.private.property", result["properties"])
        self.assertNotIn("success", result)
        device.assert_called_once_with("shell", "getprop", timeout=10)

    def test_missing_or_invalid_sdk_metadata_is_explicit(self):
        device = Mock(return_value=Mock(returncode=0, stdout=""))
        for content in ("", "Pkg.Revision=1\nPkg.Revision=2\n", "Pkg.Revision=unknown\n", "x" * 65537):
            with self.subTest(content=content[:40]):
                self.write_package("emulator", content)
                result = snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes=4096)
                self.assertEqual(result["sdk_packages"]["emulator"], {"unavailable": "ValueError"})
                self.assertEqual(result["sdk_packages"]["system-image"], {"unavailable": "FileNotFoundError"})

    def test_windows_source_properties_preserve_revision(self):
        self.write_package("emulator", "")
        (self.sdk / "emulator/source.properties").write_bytes(b"Pkg.Desc=Android Emulator\r\nPkg.Revision=36.4.5\r\n")
        device = Mock(return_value=Mock(returncode=0, stdout=""))
        result = snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes=16384)
        self.assertEqual(result["sdk_packages"]["emulator"], {"revision": "36.4.5"})

    def test_duplicate_runtime_property_does_not_report_arbitrary_value(self):
        device = Mock(return_value=Mock(returncode=0, stdout=(
            "[dalvik.vm.usejit]: [true]\n[dalvik.vm.usejit]: [false]\n")))
        result = snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes=16384)
        self.assertNotIn("properties", result)
        self.assertEqual(result["properties_unavailable"], "ValueError")

    def test_failed_read_does_not_override_existing_test_failure(self):
        device = Mock(return_value=Mock(returncode=1, stdout="permission denied"))
        self.assertEqual(snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes=16384)["properties_unavailable"], "getprop failed")
        for error in (OSError("unavailable"), RuntimeError("ADB unavailable"), subprocess.TimeoutExpired("getprop", 10)):
            with self.subTest(error=type(error).__name__):
                device.side_effect = error
                result = snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes=16384)
                self.assertIn("properties_unavailable", result)

    def test_proven_transport_loss_is_preserved_for_complete_avd_retry(self):
        error = OSError("owned emulator disappeared")
        error.emulator_transport_lost = True
        device = Mock(side_effect=error)
        with self.assertRaises(OSError) as raised:
            snapshot_runtime_environment(device, self.sdk, 37, page_size_bytes=16384)
        self.assertIs(raised.exception, error)
