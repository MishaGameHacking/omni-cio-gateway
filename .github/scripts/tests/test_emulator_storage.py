"""Protect runner disk capacity and ownership while retaining failure evidence."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_storage import DATA_BYTES, HEADROOM_BYTES, configure_userdata, remove_disposable_avd


class EmulatorStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.attempt = self.root / "attempt-1"
        self.home = self.attempt / "avd"
        self.avd = self.home / "verification.avd"
        self.avd.mkdir(parents=True)
        self.config = self.avd / "config.ini"
        self.original = "hw.ramSize=4096\ndisk.dataPartition.size=12G\ndisk.dataPartition.size = 10G\ntag.id=ps16k\n"
        self.config.write_text(self.original, encoding="utf-8")
        self.sdk = self.root / "sdk"
        self.image = "system-images;android-35;google_apis_ps16k;x86_64"
        self.source = self.sdk.joinpath(*self.image.split(";"), "userdata.img")
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"initial")
        self.stopped = SimpleNamespace(poll=lambda: 0)

    def configure(self, free):
        with patch("emulator_storage.shutil.disk_usage", return_value=SimpleNamespace(free=free)):
            configure_userdata(self.avd, self.sdk, self.image)

    def test_replaces_duplicate_size_without_changing_ram_or_image(self):
        self.configure(DATA_BYTES + HEADROOM_BYTES)
        self.assertEqual(self.config.read_text(encoding="utf-8"),
                         f"hw.ramSize=4096\ntag.id=ps16k\ndisk.dataPartition.size={DATA_BYTES}\n")

    def test_official_initial_image_is_never_shrunk(self):
        with self.source.open("r+b") as source:
            source.truncate(DATA_BYTES + 1)
        self.configure(DATA_BYTES + HEADROOM_BYTES + 1024 * 1024)
        self.assertIn(f"disk.dataPartition.size={DATA_BYTES + 1024 * 1024}\n",
                      self.config.read_text(encoding="utf-8"))

    def test_insufficient_space_fails_before_rewriting_configuration(self):
        with self.assertRaisesRegex(RuntimeError, "Insufficient runner disk space"):
            self.configure(DATA_BYTES + HEADROOM_BYTES - 1)
        self.assertEqual(self.config.read_text(encoding="utf-8"), self.original)

    def test_cleanup_retains_report_and_other_attempt(self):
        report = self.attempt / "install-results.json"
        report.write_text("[]", encoding="utf-8")
        neighbor = self.root / "attempt-2" / "avd"
        neighbor.mkdir(parents=True)
        remove_disposable_avd(self.home, self.attempt, process=self.stopped)
        self.assertFalse(self.home.exists())
        self.assertEqual(report.read_text(encoding="utf-8"), "[]")
        self.assertTrue(neighbor.is_dir())

    def test_running_emulator_data_is_never_removed(self):
        running = SimpleNamespace(poll=lambda: None)
        with self.assertRaisesRegex(RuntimeError, "running emulator"):
            remove_disposable_avd(self.home, self.attempt, process=running)
        self.assertTrue(self.config.is_file())

    def test_other_attempt_is_never_removed(self):
        other = self.root / "other-attempt"
        with self.assertRaisesRegex(ValueError, "outside its own attempt"):
            remove_disposable_avd(self.home, other, process=self.stopped)
        self.assertTrue(self.config.is_file())


if __name__ == "__main__":
    unittest.main()
