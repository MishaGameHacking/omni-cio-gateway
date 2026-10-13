from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

from backend.release_lock import PublicationBusy, publication_lock


class ReleaseLockTests(unittest.TestCase):
    def test_persistent_lock_path_is_reusable(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw)
            with publication_lock(path):
                self.assertTrue((path / ".publishing").is_file())
            with publication_lock(path):
                self.assertTrue((path / ".publishing").is_file())

    def test_old_sentinel_is_not_permanent_deadlock(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw)
            (path / ".publishing").write_bytes(b"")
            with publication_lock(path):
                self.assertTrue((path / ".publishing").exists())

    def test_concurrent_publishers_cannot_enter(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw)
            with publication_lock(path):
                with self.assertRaises(PublicationBusy):
                    with publication_lock(path):
                        self.fail("second publisher entered")

    def test_exception_releases_ownership(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw)
            with self.assertRaisesRegex(RuntimeError, "injected"):
                with publication_lock(path):
                    raise RuntimeError("injected")
            with publication_lock(path):
                self.assertTrue(path.exists())

    @unittest.skipIf(os.name == "nt", "Windows symlink privileges are environment-specific")
    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw)
            target = path / "unrelated"
            target.write_text("preserve", encoding="utf-8")
            (path / ".publishing").symlink_to(target)
            with self.assertRaises(PublicationBusy):
                with publication_lock(path):
                    self.fail("symlink used")
            self.assertEqual(target.read_text(encoding="utf-8"), "preserve")

    def test_process_exit_releases_ownership(self):
        code = """from pathlib import Path
import os, sys
from backend.release_lock import publication_lock
with publication_lock(Path(sys.argv[1])):
    os._exit(17)
"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(__file__).resolve().parents[2]
            result = subprocess.run([sys.executable, "-S", "-c", code, raw],
                                    cwd=root, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 17, result.stderr.decode(errors="replace"))
            with publication_lock(Path(raw)):
                self.assertTrue((Path(raw) / ".publishing").is_file())


if __name__ == "__main__":
    unittest.main()
