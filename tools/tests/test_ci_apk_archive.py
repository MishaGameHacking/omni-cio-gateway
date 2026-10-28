"""CI archive identity and member boundary regression."""
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_apk_archive as apk_archive


class ArchiveTests(unittest.TestCase):
    def test_archive_binds_exact_head_and_rejects_extra_members_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(strict=True)
            source, target = root / "source", root / "target"
            source.mkdir()
            target.mkdir()
            for name in apk_archive.FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("synthetic-" + name).encode())
            with patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}):
                data = apk_archive.pack(source, source / "previous.apk")
                apk_archive.unpack(data, target)
                self.assertEqual((source / apk_archive.FILES[0]).read_bytes(), (target / apk_archive.FILES[0]).read_bytes())
                bad = io.BytesIO(data)
                with zipfile.ZipFile(bad, "a") as archive:
                    archive.writestr("../escape", "unexpected")
                invalid_data = bad.getvalue()
                with self.assertRaisesRegex(apk_archive.ProbeError, "members_invalid"):
                    apk_archive.unpack(invalid_data, target)
            with patch.dict(os.environ, {"GITHUB_SHA": "b" * 40}), self.assertRaisesRegex(apk_archive.ProbeError, "identity_mismatch"):
                apk_archive.unpack(data, target)
            self.assertFalse((root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
