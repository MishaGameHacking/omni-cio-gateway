"""Real config-file regressions for the disposable device's Back/Home capability."""
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_storage import configure_userdata, DATA_BYTES, HEADROOM_BYTES

IMAGE = "system-images;android-37.0;google_apis_ps16k;x86_64"


class SoftwareNavigationConfigTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.avd = root / "owned.avd"
        self.avd.mkdir()
        self.sdk = root / "sdk"
        image = self.sdk.joinpath(*IMAGE.split(";"))
        image.mkdir(parents=True)
        (image / "userdata.img").write_bytes(b"official image")
        self.config = self.avd / "config.ini"
        self.original = "hw.lcd.density=160\nhw.lcd.width=720\nhw.lcd.height=1280\nhw.ramSize=4096\n"
        self.config.write_text(self.original, encoding="utf-8")
        self.space = patch("emulator_storage.shutil.disk_usage",
                           return_value=SimpleNamespace(free=DATA_BYTES + HEADROOM_BYTES))
        self.space.start()
        self.addCleanup(self.space.stop)

    def configure(self):
        configure_userdata(self.avd, self.sdk, IMAGE)
        return self.config.read_text(encoding="utf-8")

    def test_default_profile_gets_explicit_software_navigation_before_boot(self):
        result = self.configure()
        self.assertIn("hw.mainKeys=no\n", result)
        self.assertTrue(result.startswith(self.original))
        self.assertIn(f"disk.dataPartition.size={DATA_BYTES}\n", result)

    def test_hardware_keys_are_replaced_not_overlaid_with_duplicates(self):
        self.config.write_text(self.original + "hw.mainKeys=yes\n hw.mainKeys = yes\n",
                               encoding="utf-8")
        result = self.configure()
        self.assertEqual(result.count("hw.mainKeys"), 1)
        self.assertIn("hw.mainKeys=no\n", result)
        self.assertTrue(result.startswith(self.original))

    def test_configuring_twice_is_idempotent(self):
        first = self.configure()
        self.assertEqual(first, self.configure())

    def test_does_not_edit_sdk_userdata_or_another_avd(self):
        other = self.avd.parent / "other.ini"
        other.write_text("hw.mainKeys=yes\n", encoding="utf-8")
        self.configure()
        self.assertEqual(other.read_text(encoding="utf-8"), "hw.mainKeys=yes\n")
        self.assertEqual(self.sdk.joinpath(*IMAGE.split(";"), "userdata.img").read_bytes(),
                         b"official image")

    def test_insufficient_disk_does_not_partially_reconfigure(self):
        with patch("emulator_storage.shutil.disk_usage", return_value=SimpleNamespace(free=1)):
            with self.assertRaises(RuntimeError):
                configure_userdata(self.avd, self.sdk, IMAGE)
        self.assertEqual(self.config.read_text(encoding="utf-8"), self.original)

    def test_config_symlink_is_rejected_before_writing(self):
        # No platform-dependent symlink privilege is required to exercise the guard.
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(ValueError):
                configure_userdata(self.avd, self.sdk, IMAGE)
        self.assertEqual(self.config.read_text(encoding="utf-8"), self.original)


if __name__ == "__main__":
    unittest.main()
